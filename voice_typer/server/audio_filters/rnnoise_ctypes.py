"""Minimal ctypes binding to the native RNNoise C API, without pyrnnoise's Python package."""

from __future__ import annotations

import contextlib
import ctypes
import importlib.util
import os
import platform
import sys
import threading
from typing import Any

import numpy as np

SAMPLE_RATE = 48000
FRAME_SIZE = 480

_LIB_FILENAMES: dict[str, str] = {
    "Windows": "rnnoise.dll",
    "Darwin": "librnnoise.dylib",
    "Linux": "librnnoise.so",
}

_lib: Any | None = None
_lib_lock = threading.Lock()


class LibraryLoadError(RuntimeError):
    """The native RNNoise library is absent or cannot be loaded."""


def _candidate_dirs() -> list[str]:
    dirs: list[str] = []
    # Nuitka onefile unpacks data next to the main module, not next to the exe.
    containing_dir = getattr(sys.modules.get("__compiled__"), "containing_dir", None)
    if containing_dir:
        dirs.append(containing_dir)
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if main_file:
        dirs.append(os.path.dirname(os.path.abspath(main_file)))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(meipass)
    dirs.append(os.path.dirname(os.path.abspath(__file__)))
    dirs.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for exe in (sys.executable, sys.argv[0] if sys.argv else None):
        if exe:
            with contextlib.suppress(OSError, RuntimeError):
                dirs.append(os.path.dirname(os.path.abspath(exe)))
    # find_spec does not execute pyrnnoise/__init__.py (which pulls audiolab/av).
    try:
        spec = importlib.util.find_spec("pyrnnoise")
    except (ImportError, ValueError, AttributeError):
        spec = None
    if spec is not None and spec.submodule_search_locations:
        dirs.extend(spec.submodule_search_locations)
    return dirs


def find_library_path() -> str | None:
    """Return the native library path, or None when it is not installed."""
    override = os.environ.get("VOICE_TYPER_RNNOISE_LIB")
    if override:
        return override if os.path.isfile(override) else None
    filename = _LIB_FILENAMES.get(platform.system())
    if filename is None:
        return None
    for directory in _candidate_dirs():
        for relative in (filename, os.path.join("pyrnnoise", filename), os.path.join("lib", filename)):
            path = os.path.join(directory, relative)
            if os.path.isfile(path):
                return path
    return None


def _get_lib() -> Any:
    global _lib
    if _lib is not None:
        return _lib
    with _lib_lock:
        if _lib is not None:
            return _lib
        path = find_library_path()
        if path is None:
            lib_name = _LIB_FILENAMES.get(platform.system(), "library")
            raise LibraryLoadError(f"native RNNoise library ({lib_name}) not found")
        try:
            lib = ctypes.CDLL(path)
            lib.rnnoise_create.argtypes = [ctypes.c_void_p]
            lib.rnnoise_create.restype = ctypes.c_void_p
            lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
            lib.rnnoise_destroy.restype = None
            lib.rnnoise_process_frame.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
            ]
            lib.rnnoise_process_frame.restype = ctypes.c_float
            lib.rnnoise_get_frame_size.argtypes = []
            lib.rnnoise_get_frame_size.restype = ctypes.c_int
        except (OSError, AttributeError) as exc:
            raise LibraryLoadError(f"cannot load native RNNoise library at {path}: {exc}") from exc
        _lib = lib
        return lib


class RNNoise:
    """Per-instance RNNoise denoiser over the public C API."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = int(sample_rate)
        self.channels = 1
        self._lib = _get_lib()
        self._states: list[Any] = []

    def reset(self) -> None:
        for state in self._states:
            self._lib.rnnoise_destroy(state)
        self._states = []

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self.reset()

    def denoise_frame(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Denoise [channels, samples] int16 frames; return (speech_prob, cleaned_int16)."""
        frame = np.asarray(frame)
        if frame.ndim == 1:
            frame = frame[np.newaxis, :]
        channels = int(frame.shape[0])
        if not self._states:
            self._states = [self._lib.rnnoise_create(None) for _ in range(channels)]
        frames: list[np.ndarray] = []
        probs: list[float] = []
        ptr_type = ctypes.POINTER(ctypes.c_float)
        for channel in range(channels):
            # RNNoise expects int16 magnitudes as float32, in place.
            floats = frame[channel].astype(np.float32)
            count = len(floats)
            if count < FRAME_SIZE:
                floats = np.pad(floats, (0, FRAME_SIZE - count))
            ptr = floats.ctypes.data_as(ptr_type)
            probs.append(float(self._lib.rnnoise_process_frame(self._states[channel], ptr, ptr)))
            frames.append(floats.astype(np.int16)[:count])
        return (
            np.asarray(probs, dtype=np.float32).reshape(channels, 1),
            np.vstack(frames),
        )
