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
import re
import sys
import threading
from pathlib import Path
from types import ModuleType
from typing import Any

from voice_typer.server.local_asr_readiness import (
    ENV_TRANSCRIBE_LIBRARY,
    LIBRARY_BASENAME,
)
from voice_typer.server.worker_backed_asr import _TRANSCRIBE_TIMEOUT_SECONDS as DEFAULT_TIMEOUT_S
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


class _LoadParams(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint64),
        ("backend", ctypes.c_int),
        ("device", ctypes.c_void_p),
        ("no_mmap", ctypes.c_bool),
    ]


class _RunParams(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint64),
        ("task", ctypes.c_int),
        ("timestamps", ctypes.c_int),
        ("pnc", ctypes.c_int),
        ("itn", ctypes.c_int),
        ("diarize", ctypes.c_int),
        ("language", ctypes.c_char_p),
        ("target_language", ctypes.c_char_p),
        ("keep_special_tags", ctypes.c_bool),
        ("family", ctypes.c_void_p),
        ("spec_k_drafts", ctypes.c_int32),
        ("vocabulary", ctypes.POINTER(ctypes.c_char_p)),
        ("n_vocabulary", ctypes.c_int32),
        ("prompt", ctypes.c_char_p),
        ("prefix", ctypes.c_char_p),
    ]


_ABI_SEGMENT = 6
_ABI_RUN_PARAMS = 2
_ABI_MODEL_LOAD_PARAMS = 0
_MAX_LEAKED_SESSIONS = 2
_ABORT_CB = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p)
_BACKEND_REQUEST = {"auto": 0, "cpu": 1, "metal": 2, "vulkan": 3, "cpu_accel": 4, "cuda": 5, "rocm": 6}
_INITIALISED: set[str] = set()
_LEAKED_SESSIONS: list[ctypes.c_void_p] = []


def library_dir(
    *,
    module_globals: dict[str, object] | None = None,
    sys_module: ModuleType | None = None,
) -> Path | None:
    """Return the shipped DLL directory; never use PATH inside a frozen build.

    Delegates to the sidecar-safe shared resolver so the worker loader and the
    pre-mic readiness probe cannot disagree about the runtime location.
    """
    from voice_typer.server.local_asr_readiness import resolve_native_runtime_dir

    return resolve_native_runtime_dir(module_globals=module_globals, sys_module=sys_module)


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
    lib.transcribe_init_backends.argtypes = [ctypes.c_char_p]
    lib.transcribe_init_backends.restype = ctypes.c_int
    lib.transcribe_model_load_params_init.argtypes = [ctypes.POINTER(_LoadParams)]
    lib.transcribe_model_load_params_init.restype = None
    lib.transcribe_run_params_init.argtypes = [ctypes.POINTER(_RunParams)]
    lib.transcribe_run_params_init.restype = None
    lib.transcribe_abi_struct_size.argtypes = [ctypes.c_int]
    lib.transcribe_abi_struct_size.restype = ctypes.c_size_t


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
        try:
            lib = ctypes.CDLL(str(path))
        except OSError:
            log.exception("[GGUF] native library load failed")
            raise RunnerError("The installed speech runtime could not be loaded.") from None
        _bind(lib)
        for which, local in (
            (_ABI_MODEL_LOAD_PARAMS, _LoadParams),
            (_ABI_RUN_PARAMS, _RunParams),
            (_ABI_SEGMENT, _Segment),
        ):
            expected = int(lib.transcribe_abi_struct_size(which))
            if expected == 0 or expected != ctypes.sizeof(local):
                log.error(
                    "[GGUF] ABI size mismatch: struct=%d native=%d local=%d",
                    which,
                    expected,
                    ctypes.sizeof(local),
                )
                raise RunnerError("The installed speech runtime has an incompatible API.")
        directory_key = str(directory.resolve())
        if directory_key not in _INITIALISED:
            status = lib.transcribe_init_backends(str(directory).encode("utf-8"))
            if status != OK:
                log.error("[GGUF] backend init failed: status=%d", status)
                raise RunnerError("The speech runtime backends could not be loaded.")
            _INITIALISED.add(directory_key)
        return lib, directory

    def transcribe(
        self,
        audio: Any,
        *,
        language: str | None = None,
        backend: str | None = None,
        abort_event: threading.Event | None = None,
    ) -> RunnerResult:
        if len(_LEAKED_SESSIONS) >= _MAX_LEAKED_SESSIONS:
            raise RunnerError("The speech worker is unhealthy and must be restarted.")
        if language and not re.fullmatch(r"[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})*", language):
            raise RunnerError("The selected language is not supported.")
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

            load_params: _LoadParams | None = None
            if backend and backend in _BACKEND_REQUEST:
                load_params = _LoadParams()
                lib.transcribe_model_load_params_init(ctypes.byref(load_params))
                load_params.backend = _BACKEND_REQUEST[backend]
            params_arg = ctypes.byref(load_params) if load_params is not None else None
            status = lib.transcribe_open(self.model_path.encode("utf-8"), params_arg, None, ctypes.byref(session))
            if status != OK or not session.value:
                message = lib.transcribe_status_string(status)
                log.error("[GGUF] model load failed: status=%d %s", status, message)
                raise RunnerError("The speech model could not be loaded.")

            leaked = False
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
                run_params = _RunParams()
                lib.transcribe_run_params_init(ctypes.byref(run_params))
                language_bytes = (language or "").encode("utf-8") or None
                run_params.language = language_bytes
                box: list[int | BaseException] = []

                def _run() -> None:
                    try:
                        params = ctypes.byref(run_params)
                        box.append(lib.transcribe_run(session, buf, len(pcm), params))
                    except BaseException as exc:  # native-layer failure must not hang
                        box.append(exc)

                thread = threading.Thread(target=_run, name="gguf-run", daemon=True)
                thread.start()
                thread.join(self._timeout)
                if thread.is_alive():
                    abort.set()
                    thread.join(5.0)
                    if thread.is_alive():
                        # The native call still owns this session. Freeing it
                        # now is a use-after-free; keep it alive until process
                        # exit and never swap its callback.
                        leaked = True
                        _LEAKED_SESSIONS.append(session)
                        log.error("[GGUF] native run still active after abort grace; session retained")
                        raise RunnerError("Speech recognition took too long and was stopped.")
                    raise RunnerError("Speech recognition took too long and was stopped.")
                if not box:
                    raise RunnerError("Speech recognition stopped unexpectedly.")
                outcome = box[0]
                if isinstance(outcome, BaseException):
                    log.error("[GGUF] native run raised: %r", outcome)
                    raise RunnerError("Speech recognition stopped unexpectedly.") from outcome
                status = int(outcome)
                partial = status in (ERR_OUTPUT_TRUNCATED, ERR_OUTPUT_REPETITION)
                if partial:
                    log.warning("[GGUF] partial decode: status=%d", status)
                elif status != OK:
                    message = lib.transcribe_status_string(status)
                    log.error("[GGUF] decode failed: status=%d %s", status, message)
                    if status == ERR_ABORTED or abort.is_set():
                        raise RunnerError("Transcription was stopped.")
                    if language:
                        log.error("[GGUF] decode failed for language=%s", language)
                        raise RunnerError("Speech recognition could not read the audio with that language.")
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
                    partial=partial,
                )
            finally:
                if not leaked:
                    try:
                        lib.transcribe_set_abort_callback(session, None, None)
                    except Exception:
                        log.debug("[GGUF] clearing abort callback failed", exc_info=True)
                    lib.transcribe_session_free(session)
