"""SHA-256 manifest verification for native key-listener binaries.

Owns the per-process verification cache, ``binaries.json`` manifest loading,
expected-digest lookup, the digest comparison, and the trusted-path override.

Extracted from ``binary_path.py``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from pathlib import Path

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.native_hotkeys.binary_names import (
    _ARCH_SUFFIX_TO_LEGACY,
    _LEGACY_TO_ARCH_SUFFIX,
)

log = logging.getLogger("voice_typer.server.native_hotkeys.binary_path")

# ``_MANIFEST_PATH`` is patched on the facade (``binary_path._MANIFEST_PATH``)
# by tests, so it MUST be resolved through the facade at call time.
_facade = lazy_module("voice_typer.server.native_hotkeys.binary_path")

# Per-process verification cache: maps ``(resolved path, size, mtime_ns)``
_VERIFIED_CACHE: dict[tuple[str, int, int], bool] = {}
_VERIFIED_CACHE_LOCK = threading.Lock()


def _verified_cache_key(path: Path) -> tuple[str, int, int] | None:
    """Return the cache key for ``path`` or None if it cannot be stated."""
    try:
        stat_result = path.stat()
    except OSError:
        return None
    try:
        resolved = str(path.resolve())
    except OSError:
        resolved = str(path)
    return (resolved, stat_result.st_size, stat_result.st_mtime_ns)


def clear_verified_cache() -> None:
    """Clear the per-process verification cache (tests only)."""
    with _VERIFIED_CACHE_LOCK:
        _VERIFIED_CACHE.clear()


def load_binary_manifest() -> dict | None:
    manifest_path = _facade._MANIFEST_PATH
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        log.debug("[NATIVE-BINARY] No manifest at %s", manifest_path)
        return None
    except OSError as exc:
        log.warning("[NATIVE-BINARY] Failed to read manifest %s: %s", manifest_path, exc)
        return None
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("[NATIVE-BINARY] Malformed manifest %s: %s", manifest_path, exc)
        return None
    if not isinstance(manifest, dict):
        log.warning("[NATIVE-BINARY] Manifest %s is not a JSON object", manifest_path)
        return None
    return manifest


def _equivalent_manifest_names(binary_name: str) -> list[str]:
    """Return the ordered list of manifest keys to try for ``binary_name``.

    the manifest may be keyed by either the arch-suffixed name
    (``linux-key-listener-x86_64``) or the legacy non-suffixed name
    (``linux-key-listener``), depending on which form
    ``scripts/build/compile_native.sh`` emitted and which form
    ``scripts/build/update_native_manifests.py`` recorded. The shipped
    manifest (``binaries.json``) now carries BOTH forms as aliases (with
    the same sha256 where the binary exists), so the direct lookup
    usually succeeds. This helper returns the direct name first, then
    any equivalents (legacy <-> arch-suffixed x86_64 ONLY, aarch64 has
    no legacy equivalent because aarch64 builds are new in ), so
    :func:`get_expected_sha256` can still find the right entry if a
    future manifest drops one form.

    The returned list is de-duplicated while preserving order (the
    direct name is always first). macOS uses the same universal name
    for both forms (``macos-key-listener``), so it returns a
    single-element list.
    """
    candidates: list[str] = [binary_name]
    arch_equivalent = _LEGACY_TO_ARCH_SUFFIX.get(binary_name)
    if arch_equivalent:
        candidates.append(arch_equivalent)
    legacy_equivalent = _ARCH_SUFFIX_TO_LEGACY.get(binary_name)
    if legacy_equivalent:
        candidates.append(legacy_equivalent)
    # De-dup while preserving order.
    seen: set[str] = set()
    result: list[str] = []
    for name in candidates:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def get_expected_sha256(binary_name: str) -> str | None:
    """Look up the expected SHA-256 for a binary by its filename.

    ``binary_name`` MUST be the arch-suffixed name actually
    produced by ``scripts/build/compile_native.sh`` and discovered by
    :func:`get_native_binary_path` (e.g. ``linux-key-listener-x86_64``,
    ``windows-key-listener-aarch64.exe``, ``macos-key-listener``).
    Pre- the manifest was keyed by the legacy non-suffixed names
    (``linux-key-listener``, ``windows-key-listener.exe``), so every
    call with an arch-suffixed name returned ``None`` and
    :func:`verify_native_binary_or_skip` silently trusted the binary.
    The manifest is now keyed by the arch-suffixed names; this function
    is a plain dict lookup, so callers MUST pass the same name
    :func:`get_native_binary_path` returned (``path.name``).

    the build script (``compile_native.sh``) still emits the
    legacy non-suffixed names on Linux/Windows
    (``linux-key-listener``, ``windows-key-listener.exe``), so
    ``path.name`` may be EITHER form. The manifest now carries BOTH
    forms as aliases (with the same sha256), so the direct lookup
    succeeds either way. As a defensive fallback, if the direct lookup
    misses (or hits an empty sha256 entry), this function also tries
    the equivalent name (legacy <-> arch-suffixed x86_64) via
    :func:`_equivalent_manifest_names`. This keeps verification working
    even if a future manifest drops one form. aarch64 arch-suffixed
    names have NO legacy equivalent (aarch64 builds are new in ),
    so they only match their own manifest entry.
    """
    manifest = load_binary_manifest()
    if manifest is None:
        return None
    binaries = manifest.get("binaries", {})
    if not isinstance(binaries, dict):
        return None
    # try the direct name first, then equivalent names (legacy
    for candidate_name in _equivalent_manifest_names(binary_name):
        entry = binaries.get(candidate_name)
        if not isinstance(entry, dict):
            continue
        sha = entry.get("sha256", "")
        if isinstance(sha, str) and sha:
            return sha.strip().lower()
    return None


def verify_native_binary(path: Path, expected_sha256: str) -> bool:
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        log.warning("[NATIVE-BINARY] Failed to read %s: %s", path, exc)
        return False
    expected = expected_sha256.strip().lower()
    if actual != expected:
        log.error(
            "[NATIVE-BINARY] CHECKSUM MISMATCH for %s, expected %s, got %s. "
            "Refusing to use this binary; falling back to legacy backend.",
            path,
            expected,
            actual,
        )
        return False
    log.debug("[NATIVE-BINARY] Checksum OK for binary=%s (sha256=%s)", path.name, actual)
    return True


def _is_trusted_path_override() -> bool:
    """+ : Return True only when BOTH conditions hold:

      1. The user has explicitly set the trusted-path confirmation env
         var ``VOICE_TYPER_NATIVE_TRUST=1``. This is a paired
         confirmation required in addition to the binary/dir env vars
         so that an attacker with env-var write access cannot silently
         disable the checksum gate by merely setting
         ``VOICE_TYPER_NATIVE_BINARY``.
      2. The user has set ``VOICE_TYPER_NATIVE_BINARY`` OR
         ``VOICE_TYPER_NATIVE_DIR`` (the actual override path/dir).

    The bypass is logged at WARNING (, previously DEBUG which
    was invisible at default log levels, making the silent checksum
    bypass unauditable in production).
    """
    has_trust_flag = os.environ.get("VOICE_TYPER_NATIVE_TRUST") == "1"
    has_path_override = bool(os.environ.get("VOICE_TYPER_NATIVE_BINARY")) or bool(
        os.environ.get("VOICE_TYPER_NATIVE_DIR")
    )
    return has_trust_flag and has_path_override


def _env_specified_paths() -> list[Path]:
    """Return the list of paths the user explicitly trust-listed
    via ``VOICE_TYPER_NATIVE_BINARY`` / ``VOICE_TYPER_NATIVE_DIR``.

    Used by :func:`verify_native_binary_or_skip` to confirm that the
    discovered binary actually lives under an env-specified location
    (rather than being discovered via fallback search after the env
    override was set). This closes the  hole where setting
    ``VOICE_TYPER_NATIVE_BINARY=/nonexistent`` disabled verification
    for ANY binary found via fallback search.

    Returns an empty list if neither env var is set.
    """
    paths: list[Path] = []
    binary_env = os.environ.get("VOICE_TYPER_NATIVE_BINARY")
    if binary_env:
        paths.append(Path(binary_env))
    dir_env = os.environ.get("VOICE_TYPER_NATIVE_DIR")
    if dir_env:
        paths.append(Path(dir_env))
    return paths


def _path_matches_env_override(path: Path) -> bool:
    """Return True if ``path`` equals or lives under one of the
    env-specified paths from :func:`_env_specified_paths`.

    The check is path-prefix-based: a discovered path
    ``/opt/vt/native/linux-key-listener-x86_64`` matches an env override
    ``VOICE_TYPER_NATIVE_DIR=/opt/vt/native`` (the binary lives under
    the env dir). A discovered path
    ``/opt/vt/native/linux-key-listener-x86_64`` also matches an env
    override ``VOICE_TYPER_NATIVE_BINARY=/opt/vt/native/linux-key-listener-x86_64``
    (the binary equals the env path).
    """
    env_paths = _env_specified_paths()
    if not env_paths:
        return False
    resolved = path.resolve()
    for env_path in env_paths:
        env_resolved = env_path.resolve()
        # Exact match (VOICE_TYPER_NATIVE_BINARY case).
        if resolved == env_resolved:
            return True
        # Parent-dir match (VOICE_TYPER_NATIVE_DIR case): the discovered
        try:
            if resolved.is_relative_to(env_resolved):
                return True
        except AttributeError:
            # Python <3.9 fallback, not expected on 3.12, but defensive.
            try:
                resolved.relative_to(env_resolved)
                return True
            except ValueError:
                pass
    return False
