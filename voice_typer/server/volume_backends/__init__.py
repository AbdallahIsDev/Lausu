"""Concrete volume backends for Windows, macOS, and Linux.

Two families live here: the render-endpoint ``*VolumeBackend`` classes
(ducking) and the capture-endpoint ``*MicVolumeBackend`` classes (the
100% mic guard). They share the platform files because they share the
same underlying APIs (pycaw, pactl/wpctl, CoreAudio).
"""

from __future__ import annotations

from pathlib import Path  # re-exported for test monkeypatch compatibility

from .linux import LinuxMicVolumeBackend, LinuxVolumeBackend
from .macos import MacMicVolumeBackend, MacVolumeBackend
from .windows import WinMicVolumeBackend, WinVolumeBackend

__all__ = [
    "WinVolumeBackend",
    "MacVolumeBackend",
    "LinuxVolumeBackend",
    "WinMicVolumeBackend",
    "MacMicVolumeBackend",
    "LinuxMicVolumeBackend",
    "Path",
]
