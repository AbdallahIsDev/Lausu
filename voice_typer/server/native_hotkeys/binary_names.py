"""Native key-listener binary filename resolution (per platform + arch).

Per-arch naming convention:
- Linux:   ``linux-key-listener-x86_64`` / ``linux-key-listener-aarch64``
- Windows: ``windows-key-listener-x86_64.exe`` / ``windows-key-listener-aarch64.exe``
- macOS:   ``macos-key-listener`` (single universal binary, no arch suffix).

:data:`_BINARY_NAMES` is an :class:`_ArchAwareBinaryNameMap` keyed by
``(platform, machine)`` with a legacy string-key shim so callers that index by
a bare platform string keep working. :func:`_normalize_machine` folds
``platform.machine()`` aliases into a canonical arch token.

Extracted from ``binary_path.py``.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

# Legacy (non-arch-suffixed) names, kept as a backward-compat fallback
_LEGACY_BINARY_NAMES: dict[str, str] = {
    "darwin": "macos-key-listener",
    "win32": "windows-key-listener.exe",
    "linux": "linux-key-listener",
}

# without needing this fallback. The fallback exists as a defensive
_LEGACY_TO_ARCH_SUFFIX: dict[str, str] = {
    "linux-key-listener": "linux-key-listener-x86_64",
    "windows-key-listener.exe": "windows-key-listener-x86_64.exe",
}
_ARCH_SUFFIX_TO_LEGACY: dict[str, str] = {
    "linux-key-listener-x86_64": "linux-key-listener",
    "windows-key-listener-x86_64.exe": "windows-key-listener.exe",
}

# path to the SHA-256 manifest emitted by the build script
_MANIFEST_PATH = Path(__file__).resolve().parent.parent / "native" / "binaries.json"


class _ArchAwareBinaryNameMap(dict):
    """Dict keyed by ``(platform, machine)`` with a legacy string-key shim.

     mandates that ``_BINARY_NAMES`` be a ``dict[tuple[str, str],
    str]`` keyed by ``(platform, machine)``. This subclass satisfies
    that contract while *also* keeping the pre- string-key
    interface alive for backward compatibility:

    - ``_BINARY_NAMES[("linux", "x86_64")]`` → ``"linux-key-listener-x86_64"``
      (new arch-aware lookup, ).
    - ``_BINARY_NAMES.get("linux")`` → ``"linux-key-listener"``
      (legacy string-key lookup, delegates to
      :data:`_LEGACY_BINARY_NAMES`).

    The string-key shim is implemented only on ``__getitem__``,
    ``get``, and ``__contains__``; iteration and other dict operations
    only see the tuple keys (so ``len(_BINARY_NAMES)`` returns the
    arch-aware entry count, not the legacy count).
    """

    def __getitem__(self, key):
        if isinstance(key, tuple):
            return super().__getitem__(key)
        if isinstance(key, str):
            return _LEGACY_BINARY_NAMES[key]
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        if isinstance(key, tuple):
            return super().__contains__(key)
        if isinstance(key, str):
            return key in _LEGACY_BINARY_NAMES
        return False


# Per-(platform, machine) binary filename map ().
_BINARY_NAMES: dict[tuple[str, str], str] = _ArchAwareBinaryNameMap(
    {
        # macOS: universal binary covers both arm64 + x86_64.
        ("darwin", "x86_64"): "macos-key-listener",
        ("darwin", "arm64"): "macos-key-listener",
        ("darwin", "aarch64"): "macos-key-listener",
        # Windows: per-arch variants.
        ("win32", "x86_64"): "windows-key-listener-x86_64.exe",
        ("win32", "amd64"): "windows-key-listener-x86_64.exe",
        ("win32", "aarch64"): "windows-key-listener-aarch64.exe",
        ("win32", "arm64"): "windows-key-listener-aarch64.exe",
        # Linux: per-arch variants.
        ("linux", "x86_64"): "linux-key-listener-x86_64",
        ("linux", "amd64"): "linux-key-listener-x86_64",
        ("linux", "aarch64"): "linux-key-listener-aarch64",
        ("linux", "arm64"): "linux-key-listener-aarch64",
    }
)


def _normalize_machine(machine: str | None) -> str:
    """Normalize :func:`platform.machine` output to a canonical arch token.

    ``platform.machine()`` returns:

    - ``"x86_64"`` on Linux x86_64 and macOS Intel
    - ``"amd64"`` on Windows x86_64
    - ``"aarch64"`` on Linux ARM64
    - ``"arm64"`` on macOS Apple Silicon and Windows 11 ARM
    - ``"ARM64"`` (uppercase) on some Windows 11 ARM builds
    - ``"i386"`` / ``"i686"`` / ``"x86"`` on 32-bit hosts

    The normalization lowercases the input and folds aliases together
    so the ``_BINARY_NAMES`` lookup table only needs one entry per
    architecture family.
    """
    m = (machine or "").lower()
    if m in ("x86_64", "amd64"):
        return "x86_64"
    if m in ("aarch64", "arm64"):
        return "aarch64"
    if m in ("i386", "i686", "x86"):
        return "i686"
    return m  # unknown, caller will see no _BINARY_NAMES entry


def _candidate_binary_names() -> list[str]:
    """Return the candidate binary names for the current platform+arch.

    The arch-suffixed name () is preferred; the legacy
    non-arch-suffixed name is appended as a fallback so existing
    bundles keep working during the ``tauri.conf.json`` transition.
    The returned list is de-duplicated (macOS universal binary uses
    the same name for both arch and legacy, so it appears once).

    Returns an empty list if the platform is unknown.
    """
    machine = _normalize_machine(platform.machine())
    names: list[str] = []
    primary = _BINARY_NAMES.get((sys.platform, machine))
    if primary:
        names.append(primary)
    legacy = _LEGACY_BINARY_NAMES.get(sys.platform)
    if legacy and legacy not in names:
        names.append(legacy)
    return names
