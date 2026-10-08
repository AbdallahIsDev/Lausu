"""``PersistedJSON``: atomic write + single-slot ``.bak`` + quarantine.

Extracted verbatim from :mod:`voice_typer.server.security.file_io`
(callers import these names from that facade). Resolves its patch seams
through the ``voice_typer.server.secure_file_io`` shim
(``_secure_read_text`` / ``time`` / ``_QUARANTINE_SUFFIX_SEQ``) and the
``voice_typer.server.config`` re-export (``_secure_atomic_write``) at
call time, so every existing monkeypatch site keeps working.
"""

import itertools
import json
import logging
import os
from pathlib import Path
from typing import Any, Generic, TypeVar

log = logging.getLogger("voice_typer.server.config")


def _sfio_shim():
    """Return the ``voice_typer.server.secure_file_io`` back-compat shim.

    ``PersistedJSON`` resolves ``_secure_read_text`` / ``time`` /
    ``_QUARANTINE_SUFFIX_SEQ`` through the SHIM at call time so existing
    tests that monkeypatch ``voice_typer.server.secure_file_io.<name>``
    keep working (the shim re-exports the canonical symbols; the
    re-export is what the tests patch, same pattern as the lazy
    ``voice_typer.server.config._secure_atomic_write`` lookup below).
    """
    from voice_typer.server import secure_file_io as _shim

    return _shim

# Monotonic counter mixed into the ``.corrupt-<ts>-<pid>-<ns>`` quarantine
_QUARANTINE_SUFFIX_SEQ: "itertools.count" = itertools.count()

# Generic type parameter for :class:`PersistedJSON`.
T = TypeVar("T")

class PersistedJSON(Generic[T]):
    """Atomic-write + single-slot ``.bak`` + corrupt-quarantine + 0o600 perms.

    A higher-level helper that bundles the three-pronged safe-persistence
    pattern that was previously copy-pasted (with drift) across
    ``config.py``, ``crash_recovery.py``, ``duck_crash_recovery.py``,
    ``vocabulary.py``, and ``templates.py``.

    Behaviour summary:

    * :meth:`load` reads the JSON file via :func:`_secure_read_text`
      (POSIX ``O_NOFOLLOW`` + inode re-verification).  On parse failure
      (``json.JSONDecodeError`` / ``OSError`` / ``ValueError``), the
      corrupt file is *quarantined* by atomically renaming it to
      ``<path>.corrupt-<timestamp>`` (best-effort) and the configured
      ``default`` is returned.  This preserves the corrupt file for
      forensic recovery AND prevents the next :meth:`save` from
      overwriting it.

    * :meth:`save` writes the JSON content via
      :func:`_secure_atomic_write` (POSIX ``O_NOFOLLOW`` on the tmp
      file, ``fsync`` of data + parent dir, atomic ``os.replace``).
      Before the overwrite, if the existing file's bytes differ from
      the new content, a single-slot ``<path>.bak`` is written
      byte-for-byte (so a re-save of identical content does not
      churn the backup).  The ``.bak`` and the final file are
      chmod'd to 0o600 on POSIX by :func:`_secure_atomic_write`
      itself (it chmods its target on every success branch —
      ``save`` adds no second permission layer; mirrors
      ``config.py:1172-1174``).

    The helper is intentionally minimal, it does NOT know about
    schema validation, defaults-merging, or in-memory cacheing.  Those
    concerns remain in the caller (``VocabularyManager``,
    ``TemplateManager``, etc.).  The caller is responsible for calling
    :meth:`load` and :meth:`save` at the right points and for
    interpreting the returned default.

    Generic type parameter ``T``:
        The class is parameterised by ``T`` so callers can opt into
        static type-checking on the JSON round-trip. The default value
        is intentionally typed as ``Any`` so legacy callers that pass
        ``default=None`` and later ``.save(some_dict)`` keep
        type-checking clean (they get the pre-generic ``Any`` behaviour
       , ``T`` is left unconstrained and resolves to ``Unknown``).
        Callers that want type safety parameterise explicitly:

        >>> from voice_typer.server.secure_file_io import PersistedJSON
        >>> store: PersistedJSON[dict[str, object]] = PersistedJSON(
        ...     path, default={},
        ... )
        >>> data: dict[str, object] = store.load()
        >>> store.save({"key": "value"})

        Without parameterisation, ``load()`` returns ``T = Unknown``
        (effectively ``Any``) and ``save(data)`` accepts anything —
        identical to the pre-generic behaviour. The two existing call
        sites (``VocabularyManager``, ``TemplateManager``) do not
        parameterise yet; parameterising them is a mechanical
        follow-up out of scope for this change.
    """

    def __init__(self, path: Path, *, default: Any = None) -> None:
        self._path = Path(path)
        self._default = default
        self._bak_path = self._path.with_name(self._path.name + ".bak")
        # (High): _last_written_bytes cache for  diff optimization.
        self._last_written_bytes: bytes | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def default(self) -> Any:
        return self._default

    def load(self) -> T:
        """Load JSON.  On parse failure, quarantine the corrupt file and
                return the configured default.

                If the file does not exist, returns the default without logging
                (the typical first-launch case).

                If the file exists but cannot be read (``OSError``) or parsed
                (``json.JSONDecodeError`` / ``ValueError``), the corrupt file is
                renamed to ``<path>.corrupt-<timestamp>`` (best-effort; if the
                rename fails the corrupt file is left in place) and the default
                is returned.  This mirrors the pattern in
                ``config.py:1744-1763`` and ``crash_recovery.py:186-219``.

        (Medium): if the main file is corrupt/missing, attempt
                to load from the ``.bak`` before returning the default. The
                ``.bak`` is a single-slot snapshot written on every save (when
                content differs). If the ``.bak`` loads successfully, log a
                warning and return the recovered data.

                Returns ``T`` so callers that parameterise the class get a
                statically-typed value back; unparameterised callers get
                ``T = Unknown`` (effectively ``Any``: preserves the
                pre-generic behaviour).
        """
        if not self._path.exists():
            # main file missing, try .bak before returning default.
            recovered = self._try_load_bak()
            if recovered is not None:
                return recovered  # type: ignore[return-value, no-any-return]
            return self._default  # type: ignore[return-value, no-any-return]
        try:
            raw = _sfio_shim()._secure_read_text(self._path, encoding="utf-8")
            result = json.loads(raw)
            # populate the diff cache so the next save() can skip
            self._last_written_bytes = raw.encode("utf-8")
            return result  # type: ignore[return-value, no-any-return]
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            log.warning(
                "[PERSISTED_JSON] Failed to load %s: %s, quarantining corrupt file and returning default",
                self._path,
                exc,
            )
            self._quarantine_corrupt()
            # try .bak recovery after quarantining the corrupt main.
            recovered = self._try_load_bak()
            if recovered is not None:
                return recovered  # type: ignore[return-value, no-any-return]
            return self._default  # type: ignore[return-value]

    def _try_load_bak(self) -> Any | None:
        """attempt to load from the .bak file. Returns None if .bak
        is missing or also corrupt (caller falls back to default)."""
        try:
            if not self._bak_path.exists() or self._bak_path.is_symlink():
                return None
            raw = _sfio_shim()._secure_read_text(self._bak_path, encoding="utf-8")
            result = json.loads(raw)
            log.warning(
                "[PERSISTED_JSON] Main file corrupt/missing, restored from .bak: %s",
                self._bak_path.name,
            )
            # cache the recovered .bak bytes so the next save()
            self._last_written_bytes = raw.encode("utf-8")
            return result
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            log.debug(
                "[PERSISTED_JSON] .bak recovery failed for %s: %s",
                self._bak_path,
                exc,
            )
            return None

    def _quarantine_corrupt(self) -> None:
        """Best-effort rename the corrupt file to ``<path>.corrupt-<ts>-<pid>-<ns>``.

                Mirrors ``crash_recovery.py:_quarantine_corrupt``: the corrupt
                file is renamed aside for forensic recovery.  Best-effort —
                never raises.  If the file disappeared between the
                ``exists()`` check and now, or the rename fails (cross-device,
                permissions), the failure is logged at debug level and
                swallowed so the caller's load still returns the default
                cleanly.

        the filename embeds epoch seconds + PID + sub-second
                nanoseconds (``time.time_ns() % 1_000_000``) so two
                concurrent corruptions, even within the same second from
                DIFFERENT processes, or back-to-back from the same process
               , produce distinct filenames without needing an
                ``exists()`` probe loop.  This mirrors the
                migration-backup path in ``config.py:1900-1903`` and the
                corrupt-config rename in ``config.py:1779-1782``.  The
                previous implementation used ``int(time.time())`` + a
                counter loop with an ``exists()`` TOCTOU window: two
                processes corrupting their files in the same second both
                picked ``ts`` + ``counter=0`` and one overwrote the
                other's quarantine via the subsequent ``os.replace`` —
                losing forensic history.

        uses :func:`os.replace` instead of :meth:`Path.rename`.
                ``os.rename`` is atomic on POSIX but FAILS on Windows if the
                destination already exists (``OSError`` winerror 183).  The
                PID + nanosecond suffix makes a destination collision
                essentially impossible, but ``os.replace`` is retained as
                the safety net: it is atomic AND overwrites an existing
                destination on BOTH POSIX and Windows, so even if a future
                change weakens the suffix uniqueness, the worst case is the
                previous-behavior overwrite (no corruption, just lost
                forensics, strictly better than raising).
        """
        try:
            if not self._path.exists():
                return
            # Embed epoch seconds + PID + sub-second nanoseconds so two
            _sfio = _sfio_shim()
            ts = int(_sfio.time.time())
            pid = os.getpid()
            ts_ns = (_sfio.time.time_ns() % 1_000_000 + next(_sfio._QUARANTINE_SUFFIX_SEQ)) % 1_000_000
            corrupt_path = self._path.with_name(f"{self._path.name}.corrupt-{ts}-{pid}-{ts_ns}")
            # os.replace is atomic AND overwrites the destination
            os.replace(str(self._path), str(corrupt_path))
            log.warning(
                "[PERSISTED_JSON] Quarantined corrupt file: %s -> %s",
                self._path.name,
                corrupt_path.name,
            )
        except OSError as move_exc:
            log.debug(
                "[PERSISTED_JSON] Could not move corrupt file %s aside: %s",
                self._path,
                move_exc,
            )

    def save(self, data: T, *, durability: bool = True) -> None:
        """Atomic save.  Creates ``.bak`` before overwrite.  Sets 0o600 perms.

                Parameters
                ----------
                data : T
                    JSON-serialisable payload.  ``json.dumps(data, indent=2,
                    ensure_ascii=False)`` is used so non-ASCII characters
                    survive the round-trip (mirrors ``vocabulary.py`` and
                    ``templates.py`` which both pass ``ensure_ascii=False``).
                    Typed as ``T`` so callers that parameterise the class get
                    static type-checking on the saved shape; unparameterised
                    callers pass ``T = Unknown`` (accepts anything —
                    pre-generic behaviour).
                durability : bool
        (High): when ``True`` (default), the write
                    uses the full ``_secure_atomic_write`` path with ``fsync``
                    of both file data and parent directory. When ``False``, the
                    fsync calls are skipped, suitable for non-critical cache
                    files where the OS page cache is sufficient and the
                    fsync overhead (2 syscalls per save) is undesirable.

                Notes
                -----
                * The ``.bak`` is single-slot: each save overwrites the previous
                  ``.bak`` (so re-running saves does not accumulate backup
                  files).  Only files whose bytes DIFFER from the new content
                  are backed up (a re-save of identical content is a no-op for
                  the backup slot).
                * On POSIX the ``.bak`` and the final file are chmod'd to 0o600
                  by :func:`_secure_atomic_write` itself, once per write, on
                  every success branch (mirrors ``config.py:1172-1174``).
                  On Windows this is a no-op (POSIX permission bits are
                  ignored; ACLs apply). ``save`` deliberately does NOT
                  re-chmod either path, the write helper already did.
                * The parent directory is created (``parents=True,
                  exist_ok=True``) so the caller doesn't have to.
                * ``_secure_atomic_write`` is imported LAZILY from
                  :mod:`voice_typer.server.config` (not from this module) so
                  existing test patches on
                  ``voice_typer.server.config._secure_atomic_write`` keep
                  working, the symbol is defined here but re-exported from
                  ``config``; the re-export is what existing tests monkeypatch
        (e.g. ``test_vocabulary_history_db_fixes.py``'s  retry
                  tests).  Lazy import avoids the circular import that a
                  module-level ``from voice_typer.server.config import ...``
                  would create (``config`` itself imports from
                  ``secure_file_io``).

        the previous implementation used ``Path.read_bytes()``
                and ``Path.write_bytes()`` for the ``.bak`` comparison + write.
                Both follow symlinks, so an attacker who planted symlinks at
                BOTH ``self._path`` and ``self._bak_path`` got a
                read-from-arbitrary-file + write-to-arbitrary-file primitive
                (the previous config: which contains API keys for
                ``credential_store``: was read through the ``self._path``
                symlink and written through the ``self._bak_path`` symlink).
                The fix refuses to follow symlinks on EITHER path: if either
                is a symlink, the backup is skipped (the main save still
                proceeds because ``_secure_atomic_write`` already handles
                symlinks safely via ``os.replace``).  The existing-file read
                is routed through :func:`_secure_read_text` (POSIX
                ``O_NOFOLLOW`` + inode re-verification); the ``.bak`` write
                is routed through :func:`_secure_atomic_write` (atomic
                ``os.replace`` does not follow the destination symlink).
        """
        # Lazy import so monkeypatches on
        from voice_typer.server.config import _secure_atomic_write

        self._path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(data, indent=2, ensure_ascii=False)
        content_bytes = content.encode("utf-8")

        # (High): diff-cache optimization. The cache
        if self._last_written_bytes is not None and content_bytes == self._last_written_bytes:
            return

        # Best-effort single-slot .bak before overwrite.
        if self._path.exists() and not self._path.is_symlink() and not self._bak_path.is_symlink():
            try:
                # Read via _secure_read_text (O_NOFOLLOW on POSIX,
                existing_text = _sfio_shim()._secure_read_text(self._path, encoding="utf-8")
                existing_bytes = existing_text.encode("utf-8")
                if existing_bytes != content_bytes:
                    # The 0o600 perms on the ``.bak`` are set inside
                    _secure_atomic_write(self._bak_path, existing_text)
            except OSError as e:
                log.debug(
                    "[PERSISTED_JSON] Failed to back up %s to %s: %s",
                    self._path,
                    self._bak_path,
                    e,
                )
        elif self._path.is_symlink() or self._bak_path.is_symlink():
            # explicit log so a symlink-planting attack is
            log.warning(
                "[PERSISTED_JSON] Refusing to back up %s to %s, one of "
                "the paths is a symlink (symlink-following defense). "
                "The main save will still proceed (os.replace replaces "
                "the symlink with a fresh regular file).",
                self._path,
                self._bak_path,
            )

        _secure_atomic_write(self._path, content, durability=durability)
        # update the diff cache so the next save() can skip if
        self._last_written_bytes = content_bytes
