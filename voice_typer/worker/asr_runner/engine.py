"""Engine adapter that keeps the existing decode/gate pipeline unchanged.

``transcription_result.transcribe_unlocked`` and ``transcribe_words_unlocked``
consume duck-typed segment/info objects and collect ``avg_logprob`` /
``no_speech_prob`` with ``getattr(..., None)``. The runner supplies no such
confidence fields, so the existing fail-open branch is preserved verbatim;
this module deliberately does not substitute a proxy value.
"""

from __future__ import annotations

import logging
import threading
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from voice_typer.server.hallucination import REJECTION_REASON_HALLUCINATION
from voice_typer.server.transcription_result import (
    reject_low_audio_hallucination,
    transcribe_unlocked as _transcribe_unlocked_impl,
    transcribe_words_unlocked as _transcribe_words_unlocked_impl,
)
from voice_typer.worker.asr_runner.families import gguf_model_path_for
from voice_typer.worker.asr_runner.runner import GgufRunner, RunnerError

if TYPE_CHECKING:
    import numpy as np

log = logging.getLogger("voice_typer.worker.asr_runner")


class _DecodedSegment:
    """Duck-type of the faster-whisper Segment fields the pipeline reads."""

    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text
        self.avg_logprob: float | None = None
        self.no_speech_prob: float | None = None
        self.words: list[Any] = []


class _DecodedInfo:
    def __init__(self, language: str) -> None:
        self.language = language
        self.language_probability: float | None = None


class _GgufModelAdapter:
    """Presents the runner as the ``model.transcribe(...)`` object in use."""

    def __init__(self, engine: GgufTranscriptionEngine, runner: GgufRunner) -> None:
        self._engine = engine
        self._runner = runner

    def transcribe(self, audio: np.ndarray, **kwargs: Any) -> tuple[list[_DecodedSegment], _DecodedInfo]:
        language = kwargs.get("language")
        if language in ("", "auto"):
            language = None
        result = self._runner.transcribe(audio, language=language, abort_event=self._engine._abort_event)
        segments = [_DecodedSegment(seg.start, seg.end, seg.text) for seg in result.segments]
        if not segments and result.text:
            segments = [_DecodedSegment(0.0, len(audio) / 16000.0, result.text)]
        language_used = language or ""
        if language_used:
            log.info("[GGUF] language=%s (configured; not detected)", language_used)
        return segments, _DecodedInfo(language_used)


class GgufTranscriptionEngine:
    """Drop-in engine for the worker's ASR registry slot."""

    worker_backed = True

    def __init__(
        self,
        model_size: str = "",
        *,
        model_path: str | None = None,
        config: Any = None,
        device: str = "cpu",
        language: str | None = None,
        **_: Any,
    ) -> None:
        self.model_size = model_size
        if config is None:
            config = SimpleNamespace(
                asr_backend="whisper",
                model_size=model_size,
                language=language,
                hallucination_filter_mode="balanced",
            )
        self.config = config
        if model_path is None:
            model_path = gguf_model_path_for(config)
        self.model_path = model_path
        self.language: str | None = None
        self.beam_size = 1
        self.condition_on_previous_text = False
        self._device = device
        self._compute_type = "gguf"
        self._model: _GgufModelAdapter | None = None
        self._lock = threading.RLock()
        self._abort_event = threading.Event()
        self.last_quality_summary: dict[str, float] | None = None
        self.last_rejection_reason: str | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def device_info(self) -> str:
        return f"{self._device} (transcribe.cpp)"

    @property
    def loaded_via(self) -> str:
        return f"gguf/transcribe-cpp/{self.model_size}"

    def request_abort(self) -> None:
        self._abort_event.set()

    def clear_abort(self) -> None:
        self._abort_event.clear()

    def load(self, progress_callback: Any = None) -> None:
        with self._lock:
            if self._model is not None:
                return
            runner = GgufRunner(self.model_path)
            runner.executable  # resolve early; fail before a record starts
            self._model = _GgufModelAdapter(self, runner)

    def unload(self) -> None:
        with self._lock:
            self._model = None

    def transcribe(self, audio: np.ndarray, audio_stats: tuple[float, float, float] | None = None) -> str:
        with self._lock:
            return _transcribe_unlocked_impl(self, audio, audio_stats)

    def transcribe_with_fallback(self, audio: np.ndarray, *args: Any, **kwargs: Any) -> str:
        return self.transcribe(audio)

    def transcribe_words(self, audio: np.ndarray, offset_seconds: float = 0.0) -> list[Any]:
        with self._lock:
            return _transcribe_words_unlocked_impl(self, audio, offset_seconds)

    def reject_low_audio_hallucination(self, **kwargs: Any) -> bool:
        rejected = reject_low_audio_hallucination(self, **kwargs)
        if rejected:
            log.info("[GGUF] low-audio hallucination rejected")
        return rejected

    @property
    def rejection_reason(self) -> str | None:
        return self.last_rejection_reason


__all__ = ["GgufTranscriptionEngine", "RunnerError", "REJECTION_REASON_HALLUCINATION"]
