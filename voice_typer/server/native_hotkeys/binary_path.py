"""Native binary discovery + verification (facade).

Public API: :func:`get_native_binary_path` (locate the native key-listener
binary for the current platform) and :func:`verify_native_binary_or_skip`
(SHA-256 gate against ``binaries.json``). The filename maps live in
:mod:`.binary_names`; the verification helpers live in
:mod:`.binary_verification`. Every previously public name stays importable
from this module.
"""

from __future__ import annotations

import functools
import logging
import os
import platform  # noqa: F401  # facade re-export (tests patch binary_path.platform.machine)
import sys
from pathlib import Path

from voice_typer.server.native_hotkeys.binary_names import (  # noqa: F401  # facade re-export
    _ARCH_SUFFIX_TO_LEGACY,
    _BINARY_NAMES,
    _LEGACY_BINARY_NAMES,
    _LEGACY_TO_ARCH_SUFFIX,
    _MANIFEST_PATH,
    _ArchAwareBinaryNameMap,
    _candidate_binary_names,
    _normalize_machine,
)
from voice_typer.server.native_hotkeys.binary_verification import (  # noqa: F401  # facade re-export
    _VERIFIED_CACHE,
    _VERIFIED_CACHE_LOCK,
    _env_specified_paths,
    _equivalent_manifest_names,
    _is_trusted_path_override,
    _path_matches_env_override,
    _verified_cache_key,
    clear_verified_cache,
    get_expected_sha256,
    load_binary_manifest,
    verify_native_binary,
)

log = logging.getLogger("voice_typer.server.native_hotkeys.binary_path")

@functools.lru_cache(maxsize=1)
def get_native_binary_path() -> Path | None:
    """Find the native key-listener binary for the current platform+arch.

     (CACHED): the result is memoised with
    :func:`functools.lru_cache(maxsize=1)` so the 6-step lookup chain
    (env var → dev mode → PyInstaller onedir → ``_MEIPASS``) runs at
    most ONCE per process. Pre-fix, the function was called up to
    three times at startup (once per backend factory probe, see
    :func:`voice_typer.server.native_hotkeys.factory.create_native_backend`
    and
    :func:`voice_typer.server.native_hotkeys.factory.is_native_backend_available`,
    plus once from :class:`SubprocessHotkeyBackend.__init__` in
    ``base.py``), each call performing up to 6 ``Path.is_file()`` /
    ``os.stat`` probes: i.e. ~18 stats at boot for a result that
    cannot change within a single process.

    The function is PURE with respect to a single process: the
    platform (``sys.platform``), the architecture
    (``platform.machine()``), the candidate binary names
    (:data:`_BINARY_NAMES` / :data:`_LEGACY_BINARY_NAMES`), and the
    filesystem layout are all fixed for the lifetime of the process.
    The only inputs that COULD change are the
    ``VOICE_TYPER_NATIVE_BINARY`` / ``VOICE_TYPER_NATIVE_DIR`` env
    vars, but those are set by the Tauri host (or the user's shell)
    BEFORE the sidecar starts and do not change afterwards. Tests
    that need to simulate different env / platform / filesystem state
    MUST call :meth:`get_native_binary_path.cache_clear` (or use the
    ``clear_binary_path_cache`` autouse fixture in ``tests/conftest.py``)
    between scenarios: see ``tests/test_binary_path_caching.py`` for
    the pinning tests.

    Search order:
    1. ``VOICE_TYPER_NATIVE_BINARY`` env var (explicit override, single binary)
    2. ``VOICE_TYPER_NATIVE_DIR`` env var (ADR-0020 §7. Tauri resource dir containing all native binaries)
    3. ``voice_typer/server/native/<binary-name>`` (dev mode, source tree)
    4. ``voice_typer/server/native/<binary-name>.exe`` (Windows dev mode)
    5. Next to the Python executable (PyInstaller onedir mode)
    6. Inside ``_MEIPASS`` (PyInstaller onefile mode)

    At each step (2–6) the arch-suffixed name () is tried first;
    if no file is found, the legacy non-arch-suffixed name is tried as
    a fallback ( transition: see :data:`_LEGACY_BINARY_NAMES`).

    Returns ``None`` if no binary is found.

    on Windows, the binary name is arch-suffixed
    (``windows-key-listener-x86_64.exe`` or
    ``windows-key-listener-aarch64.exe``), resolved via
    :func:`_candidate_binary_names` for the current
    ``platform.machine()``. The legacy non-suffixed
    ``windows-key-listener.exe`` name (still emitted by
    ``scripts/build/compile_native.ps1``) is tried as a fallback
    at each lookup step.

    callers SHOULD follow this with a call to
    :func:`verify_native_binary_or_skip` to verify the SHA-256 of the
    returned path against the manifest (``binaries.json``).
    """
    binary_names = _candidate_binary_names()
    if not binary_names:
        return None

    # 1. Explicit override (single binary path), name-agnostic.
    env_path = os.environ.get("VOICE_TYPER_NATIVE_BINARY")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p
    env_dir = os.environ.get("VOICE_TYPER_NATIVE_DIR")
    if env_dir:
        for binary_name in binary_names:
            candidate = Path(env_dir) / binary_name
            if candidate.is_file():
                return candidate

    # 3/4. Dev mode, alongside this package's source tree.  Use
    module_dir = Path(__file__).resolve().parent.parent / "native"
    for binary_name in binary_names:
        candidates = [
            module_dir / binary_name,
            # Some platforms may have a .exe suffix even in dev (cross-compile)
            module_dir / f"{binary_name}.exe",
        ]
        for c in candidates:
            if c.is_file():
                return c

    # 5. PyInstaller onedir: binary sits next to python executable.
    exe_dir = Path(sys.executable).resolve().parent
    for binary_name in binary_names:
        onedir_candidate = exe_dir / binary_name
        if onedir_candidate.is_file():
            return onedir_candidate

    # 6. PyInstaller onefile: binary extracted to _MEIPASS.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        for binary_name in binary_names:
            meipass_candidate = Path(meipass) / "voice_typer" / "server" / "native" / binary_name
            if meipass_candidate.is_file():
                return meipass_candidate

    return None


def verify_native_binary_or_skip(path: Path) -> bool:
    #  + : trusted-path override now requires BOTH:
    if _is_trusted_path_override() and _path_matches_env_override(path):
        # elevated from DEBUG to WARNING so the bypass is
        log.warning(
            "[NATIVE-BINARY] Skipping checksum for %s, trusted-path "
            "override active (VOICE_TYPER_NATIVE_TRUST=1 + path matches "
            "env-specified location).",
            path,
        )
        return True
    cache_key = _verified_cache_key(path)
    if cache_key is not None:
        with _VERIFIED_CACHE_LOCK:
            if _VERIFIED_CACHE.get(cache_key) is True:
                return True
    expected = get_expected_sha256(path.name)
    if expected is None:
        # FAIL CLOSED. Previously this branch silently trusted
        log.error(
            "[NATIVE-BINARY] FAIL CLOSED for %s, no usable manifest entry "
            "(manifest missing, entry missing, or sha256 empty). "
            "Refusing to use this binary; falling back to legacy backend. "
            "Run scripts/build/update_native_manifests.py to populate the manifest.",
            path.name,
        )
        return False
    verified = verify_native_binary(path, expected)
    if verified and cache_key is not None:
        # Only cache when the file was stable across the hash: re-stat
        fresh_key = _verified_cache_key(path)
        if fresh_key is not None and fresh_key == cache_key:
            with _VERIFIED_CACHE_LOCK:
                _VERIFIED_CACHE[cache_key] = True
    return verified
