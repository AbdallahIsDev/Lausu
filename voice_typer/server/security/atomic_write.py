"""Secure atomic file writes: unique tmp file + fsync + atomic replace.

Extracted verbatim from :mod:`voice_typer.server.security.file_io`
(callers import these names from that facade). The order of operations
inside ``_secure_atomic_write`` is load-bearing: write + flush
(+fsync), atomic ``os.replace`` (Windows retry loop), ``chmod`` to
0o600, then the parent-directory fsync. ``_chmod_owner_only`` is
resolved through the facade at call time (tests monkeypatch it there).
"""

import contextlib
import logging
import os
import tempfile
import time
from pathlib import Path

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.platform_utils import is_windows

log = logging.getLogger("voice_typer.server.config")

_facade = lazy_module("voice_typer.server.security.file_io")


def _windows_fsync_directory(path: str) -> None:
    """fsync a directory on Windows via ``CreateFileW`` +
    ``FlushFileBuffers`` with ``FILE_FLAG_BACKUP_SEMANTICS``.

    This is the standard Windows durability recipe (used by SQLite,
    PostgreSQL, etc.). Without it, ``os.replace``'s directory-entry
    update sits in the NTFS log buffer for seconds and may not survive
    power loss, the file DATA is durable (fsynced earlier) but the
    rename itself is not.

    Best-effort: any failure (ctypes missing, CreateFileW fails,
    FlushFileBuffers fails) is logged at DEBUG and swallowed so the
    caller's write still succeeds, the pre-fix behavior (rename not
    durable across power loss) is the fallback.

    Only invoked on Windows (guarded by ``is_windows()`` at the call
    site). The ``ctypes.windll`` attribute does not exist on POSIX, so
    this function MUST NOT be called from a non-Windows host (the
    call-site guard handles that).
    """
    try:
        import ctypes
        from ctypes import wintypes

        # kernel32 is always available on Windows.
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        # Constants (avoid relying on pywin32 / Windows SDK headers):
        GENERIC_WRITE = 0x40000000  # noqa: N806
        FILE_SHARE_READ = 0x00000001  # noqa: N806
        FILE_SHARE_WRITE = 0x00000002  # noqa: N806
        OPEN_EXISTING = 3  # noqa: N806
        FILE_FLAG_BACKUP_SEMANTICS = 0x02000000  # noqa: N806
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value  # noqa: N806

        # CreateFileW signature:
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        handle = kernel32.CreateFileW(
            path,
            GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle == INVALID_HANDLE_VALUE or handle is None:
            raise ctypes.WinError()  # type: ignore[attr-defined]
        try:
            # FlushFileBuffers signature: BOOL FlushFileBuffers(HANDLE hFile)
            kernel32.FlushFileBuffers.restype = wintypes.BOOL
            kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
            if not kernel32.FlushFileBuffers(handle):
                raise ctypes.WinError()  # type: ignore[attr-defined]
        finally:
            # CloseHandle signature: BOOL CloseHandle(HANDLE hObject)
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            if not kernel32.CloseHandle(handle):
                log.debug(
                    "[CONFIG] CloseHandle failed for directory %s (best-effort)",
                    path,
                )
    except OSError as e:
        log.debug(
            "[CONFIG] Windows directory-fsync of %s failed (best-effort): %s",
            path,
            e,
        )
    except Exception as e:  # noqa: BLE001, best-effort; never raise
        log.debug(
            "[CONFIG] Windows directory-fsync of %s failed (best-effort, non-OSError): %s",
            path,
            e,
        )

def _secure_atomic_write(
    path: os.PathLike,
    content: str,
    *,
    durability: bool = True,
) -> None:
    """Write content to ``path`` atomically and securely.

        The temp filename is generated via
        ``tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".",
        suffix=".tmp")`` instead of the previous fixed name
        (``path.with_suffix(path.suffix + ".tmp")``).  The fixed name
        caused concurrent callers to collide on ``O_EXCL`` (EEXIST); the
        second caller's broad ``except`` then ``unlink()``-ed the FIRST
        caller's already-written temp file (silent data loss).

        The Windows branch now uses the mkstemp-provided fd
        (which has O_EXCL semantics on Windows too) wrapped with
        ``os.fdopen`` instead of plain ``open()``.

        On POSIX, after ``os.replace`` the parent directory is
        fsynced so the rename is durable across power loss.  Best-effort.

    ``durability`` controls whether the two ``fsync`` calls
        (file data + parent directory) run.  The default ``True``
        preserves the existing POSIX-durability behavior used by
        ``Config.save()`` and ``credential_store._write_plaintext_fallback``
       , both of which persist security-critical data (API keys, user
        settings) where the fsync cost is justified.  Pass
        ``durability=False`` for non-critical writes (cache files,
        telemetry dumps, PID files, onboarding sentinels) where the
        atomicity guarantee still matters but a power-loss window of a
        few seconds is acceptable.  Trade-off: skipping fsync can lose
        the most-recent write on power loss (the os.replace rename may
        not be durable on disk), but saves ~2ms per write on SSDs and
        ~10-50ms on spinning rust, significant for high-frequency
        non-critical writes.

    the inner ``with os.fdopen(fd, ...)`` was previously
        wrapped in a try/except that called ``os.close(fd)`` on any
        exception.  But the with-block's ``__exit__`` ALREADY closes
        the fd, so the except's ``os.close(fd)`` was a DOUBLE-CLOSE.
        On a quiet fd-table this only emits EBADF (suppressed by
        ``contextlib.suppress(OSError)``); but under concurrent load
        the closed fd number can be REUSED by another thread's
        ``os.open``/``socket``/etc., and the second ``os.close(fd)``
        would close that unrelated fd, silent corruption of an
        unrelated resource.  The fix uses an ``owned_fd`` sentinel
        (set to ``-1`` immediately after ``os.fdopen`` succeeds) so the
        except path only closes the fd if ``os.fdopen`` itself failed
        (i.e. the fd is still owned by this function, not by ``f``).
    """
    from pathlib import Path

    target = Path(path)
    parent = target.parent
    tmp_path = None
    # ``owned_fd`` tracks ownership of the raw fd.  ``-1`` is the
    owned_fd = -1
    try:
        # use a UNIQUE tmp name per call.  mkstemp returns
        fd, tmp_name = tempfile.mkstemp(
            dir=str(parent),
            prefix=target.name + ".",
            suffix=".tmp",
        )
        owned_fd = fd
        tmp_path = Path(tmp_name)

        # manual try/finally (not a with-block) so we can flip
        f = os.fdopen(fd, "wb")
        owned_fd = -1  # fd is now owned by f; sentinel prevents double-close
        try:
            if isinstance(content, str):
                f.write(content.encode("utf-8"))
            else:
                f.write(content)
            f.flush()
            # skip fsync of the file data when durability=False.
            if durability:
                os.fsync(f.fileno())
        finally:
            f.close()

        # os.replace is atomic and does NOT follow symlinks on the target.
        if is_windows():
            _last_replace_exc: OSError | None = None
            for _attempt in range(_OS_REPLACE_MAX_ATTEMPTS):
                try:
                    os.replace(str(tmp_path), str(target))
                    break
                except PermissionError as exc:
                    _last_replace_exc = exc
                    time.sleep(_OS_REPLACE_RETRY_DELAY_S)
            else:
                if _last_replace_exc is not None:
                    raise _last_replace_exc
        else:
            os.replace(str(tmp_path), str(target))

        # explicit chmod to 0o600 (POSIX, best-effort) —
        _facade._chmod_owner_only(target)

        # fsync the parent directory so the rename is durable.
        if durability:
            if not is_windows():
                try:
                    dir_fd = os.open(str(parent), os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        with contextlib.suppress(OSError):
                            os.close(dir_fd)
                except OSError as e:
                    log.debug(
                        "[CONFIG] fsync of parent directory %s failed (best-effort): %s",
                        parent,
                        e,
                    )
            else:
                _windows_fsync_directory(str(parent))
    except Exception:
        if owned_fd != -1:
            with contextlib.suppress(OSError):
                os.close(owned_fd)
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise

# Windows-only: os.replace onto a destination that another thread/process
_OS_REPLACE_MAX_ATTEMPTS = 20
_OS_REPLACE_RETRY_DELAY_S = 0.1


def _chmod_owner_only(path: Path) -> None:
    """Best-effort chmod ``path`` to 0o600 on POSIX.

    Mirrors ``config.py:1172-1174``.  POSIX-only (Windows ignores POSIX
    permission bits and uses ACLs instead).  Errors are logged at debug
    level so the caller's write still succeeds on a read-only
    filesystem.
    """
    if is_windows():
        return
    try:
        os.chmod(path, 0o600)
    except OSError as e:
        log.debug(
            "[CONFIG] Failed to chmod %s to 0o600 (best-effort): %s",
            path,
            e,
        )
