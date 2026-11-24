"""ctypes wrapper for the sibling ``transcribe.dll`` shared library.

The pinned Windows release is DLLs only (no CLI). The library is loaded from
the shipped directory using the ffmpeg/Nuitka frozen-path authority
(``bundled_bin_dir()`` / ``is_frozen_build()``); there is no PATH fallback in a
frozen build and ``sys.executable`` is never used as a sibling base. This runs
inside the separate worker process, so a native crash cannot take down the UI.
"""

from __future__ import annotations

import array
import ctypes
import logging
import os
import sys
import threading
from pathlib import Path
from types import ModuleType
from typing import Any

from voice_typer.server.media_ingest.ffmpeg_binaries import (
    _shipped_dirs,
    bundled_bin_dir,
    is_frozen_build,
)
from voice_typer.worker.asr_runner.contract import (
    ERR_ABORTED,
    ERR_OUTPUT_REPETITION,
    ERR_OUTPUT_TRUNCATED,
    OK,
    RunnerResult,
    RunnerSegment,
    check_contract,
)

log = logging.getLogger("voice_typer.worker.asr_runner")

ENV_TRANSCRIBE_LIBRARY = "TRANSCRIBE_LIBRARY"
LIBRARY_BASENAME = "transcribe.dll" if os.name == "nt" else "libtranscribe.so"
DEFAULT_TIMEOUT_S = 300.0
MAX_SAMPLES = 16_000 * 60 * 30  # 30 minutes of 16 kHz mono; bounds native allocations


class RunnerError(RuntimeError):
    """Runner invocation failed. Detail stays in the log, not in UI copy."""


class _Segment(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint64),
        ("t0_ms", ctypes.c_int64),
        ("t1_ms", ctypes.c_int64),
        ("first_word", ctypes.c_int),
        ("n_words", ctypes.c_int),
        ("first_token", ctypes.c_int),
        ("n_tokens", ctypes.c_int),
        ("text", ctypes.c_char_p),
        ("speaker_id", ctypes.c_int32),
    ]


_ABORT_CB = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p)


def library_dir(
    *,
    module_globals: dict[str, object] | None = None,
    sys_module: ModuleType | None = None,
) -> Path | None:
    """Return the shipped DLL directory; never use PATH inside a frozen build."""
    override = os.environ.get(ENV_TRANSCRIBE_LIBRARY)
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_file():
            return candidate.parent
        return None
    for directory in _shipped_dirs():
        for candidate in (directory, directory / "transcribe-cpp"):
            if (candidate / LIBRARY_BASENAME).is_file():
                return candidate
    if not is_frozen_build(module_globals=module_globals, sys_module=sys_module):
        return bundled_bin_dir() if (bundled_bin_dir() / LIBRARY_BASENAME).is_file() else None
    return None


def _bind(lib: ctypes.CDLL) -> None:
    lib.transcribe_open.argtypes = [
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    lib.transcribe_open.restype = ctypes.c_int
    lib.transcribe_session_free.argtypes = [ctypes.c_void_p]
    lib.transcribe_run.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.c_void_p]
    lib.transcribe_run.restype = ctypes.c_int
    lib.transcribe_full_text.argtypes = [ctypes.c_void_p]
    lib.transcribe_full_text.restype = ctypes.c_char_p
    lib.transcribe_n_segments.argtypes = [ctypes.c_void_p]
    lib.transcribe_n_segments.restype = ctypes.c_int
    lib.transcribe_get_segment.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(_Segment)]
    lib.transcribe_get_segment.restype = ctypes.c_int
    lib.transcribe_segment_init.argtypes = [ctypes.POINTER(_Segment)]
    lib.transcribe_detected_language.argtypes = [ctypes.c_void_p]
    lib.transcribe_detected_language.restype = ctypes.c_char_p
    lib.transcribe_status_string.argtypes = [ctypes.c_int]
    lib.transcribe_status_string.restype = ctypes.c_char_p
    lib.transcribe_set_abort_callback.argtypes = [ctypes.c_void_p, _ABORT_CB, ctypes.c_void_p]
    lib.transcribe_set_abort_callback.restype = None


class GgufRunner:
    """Drive ``transcribe.dll`` for one in-memory 16 kHz mono float32 clip."""

    def __init__(self, model_path: str, *, loader: Any = None, timeout: float = DEFAULT_TIMEOUT_S):
        self.model_path = model_path
        self._loader = loader or self._load_library
        self._timeout = timeout
        self._lock = threading.Lock()

    @staticmethod
    def _load_library() -> tuple[ctypes.CDLL, Path | None]:
        directory = library_dir()
        if directory is None:
            raise RunnerError("The speech runtime is not installed. Reinstall the app or contact support.")
        path = Path(os.environ.get(ENV_TRANSCRIBE_LIBRARY) or (directory / LIBRARY_BASENAME))
        check_contract(directory if directory.is_dir() else path.parent)
        if os.name == "nt" and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(directory))
        lib = ctypes.CDLL(str(path))
        _bind(lib)
        return lib, directory

    def transcribe(
        self,
        audio: Any,
        *,
        language: str | None = None,
        backend: str | None = None,
        abort_event: threading.Event | None = None,
    ) -> RunnerResult:
        sample_count = len(audio) if hasattr(audio, "__len__") else 0
        if sample_count <= 0 or sample_count > MAX_SAMPLES:
            raise RunnerError("The audio is empty or too long to transcribe.")
        with self._lock:
            lib, _ = self._loader()
            session = ctypes.c_void_p()
            abort = abort_event or threading.Event()
            callback_holder: list[Any] = []

            def _abort(_user_data: Any) -> bool:
                return abort.is_set()

            status = lib.transcribe_open(self.model_path.encode("utf-8"), None, None, ctypes.byref(session))
            if status != OK or not session.value:
                message = lib.transcribe_status_string(status)
                log.error("[GGUF] model load failed: status=%d %s", status, message)
                raise RunnerError("The speech model could not be loaded.")

            try:
                if abort.is_set():
                    raise RunnerError("Transcription was stopped.")
                callback = _ABORT_CB(_abort)
                callback_holder.append(callback)
                lib.transcribe_set_abort_callback(session, callback, None)
                pcm = array.array("f", audio.tolist() if hasattr(audio, "tolist") else audio)
                if sys.byteorder == "big":
                    pcm.byteswap()
                buf = (ctypes.c_float * len(pcm)).from_buffer(pcm)
                box: list[object] = []

                def _run() -> None:
                    try:
                        box.append(lib.transcribe_run(session, buf, len(pcm), None))
                    except BaseException as exc:  # native-layer failure must not hang
                        box.append(exc)

                thread = threading.Thread(target=_run, name="gguf-run", daemon=True)
                thread.start()
                thread.join(self._timeout)
                if thread.is_alive():
                    abort.set()
                    thread.join(5.0)
                    raise RunnerError("Speech recognition took too long and was stopped.")
                if not box:
                    raise RunnerError("Speech recognition stopped unexpectedly.")
                if isinstance(box[0], BaseException):
                    log.error("[GGUF] native run raised: %r", box[0])
                    raise RunnerError("Speech recognition stopped unexpectedly.") from box[0]
                status = box[0]
                if status in (ERR_OUTPUT_TRUNCATED, ERR_OUTPUT_REPETITION):
                    log.warning("[GGUF] partial decode: status=%d", status)
                elif status != OK:
                    message = lib.transcribe_status_string(status)
                    log.error("[GGUF] decode failed: status=%d %s", status, message)
                    if status == ERR_ABORTED or abort.is_set():
                        raise RunnerError("Transcription was stopped.")
                    raise RunnerError("Speech recognition could not read the audio.")

                text_ptr = lib.transcribe_full_text(session)
                text = text_ptr.decode("utf-8", "replace") if text_ptr else ""
                segments: list[RunnerSegment] = []
                for i in range(max(0, lib.transcribe_n_segments(session))):
                    seg = _Segment()
                    lib.transcribe_segment_init(ctypes.byref(seg))
                    if lib.transcribe_get_segment(session, i, ctypes.byref(seg)) == OK:
                        segments.append(
                            RunnerSegment(
                                t0_ms=int(seg.t0_ms),
                                t1_ms=int(seg.t1_ms),
                                text=seg.text.decode("utf-8", "replace") if seg.text else "",
                                speaker_id=int(seg.speaker_id) or None,
                            )
                        )
                lang_ptr = lib.transcribe_detected_language(session)
                language_out = lang_ptr.decode("utf-8", "replace") if lang_ptr else (language or "")
                log.info("[GGUF] run complete: status=%d segments=%d", status, len(segments))
                return RunnerResult(
                    text=text,
                    segments=tuple(segments),
                    language=language_out or None,
                    status=status,
                )
            finally:
                try:
                    lib.transcribe_set_abort_callback(session, None, None)
                except Exception:
                    log.debug("[GGUF] clearing abort callback failed", exc_info=True)
                lib.transcribe_session_free(session)
