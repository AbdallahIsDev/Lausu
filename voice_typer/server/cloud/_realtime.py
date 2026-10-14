"""Realtime capability flag plus pure realtime message/framing helpers."""

from __future__ import annotations

import base64
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

import numpy as np

from voice_typer.server.asr_errors import CloudConfigError, CloudEngineError

REALTIME_MODELS = frozenset(
    {
        ("openai", "gpt-live-transcribe"),
        ("openai", "gpt-realtime-whisper"),
        ("gemini", "gemini-3.5-transcribe-live"),
    }
)

# OpenAI realtime WS models: the subset of REALTIME_MODELS served by the
# wss transcription session below (gemini-live uses the Live API instead).
WS_REALTIME_MODELS = frozenset(
    {
        ("openai", "gpt-live-transcribe"),
        ("openai", "gpt-realtime-whisper"),
    }
)

OFFICIAL_REALTIME_HOST = "api.openai.com"
WS_REALTIME_URL = f"wss://{OFFICIAL_REALTIME_HOST}/v1/realtime?intent=transcription"
WS_OVERALL_TIMEOUT_S = 120.0
WS_MAX_MESSAGE_BYTES = 2**20
# Client-side input guard (~9 min at 24 kHz mono): a longer burst is
# outside the live-turn use case and the server would reject it after a
# pathological upload, so refuse up front and let local fallback serve it.
_REALTIME_MAX_PCM_BYTES = 15 * 1024 * 1024


def is_realtime_model(provider: str | None, model: str | None) -> bool:
    if not isinstance(provider, str) or not isinstance(model, str):
        return False
    return (provider.strip(), model.strip()) in REALTIME_MODELS


def is_ws_realtime_model(provider: str | None, model: str | None) -> bool:
    if not isinstance(provider, str) or not isinstance(model, str):
        return False
    return (provider.strip(), model.strip()) in WS_REALTIME_MODELS


def assert_official_realtime_host(api_url: str | None) -> None:
    # Custom hosts stay on batch: the WS session below only trusts the
    # official endpoint, so a swapped URL must fail loudly, never redirect.
    host = (urlparse(api_url or "").hostname or "").lower()
    if host != OFFICIAL_REALTIME_HOST:
        raise CloudConfigError(
            f"Realtime transcription requires the official host "
            f"({OFFICIAL_REALTIME_HOST}), got {host!r}"
        )


def build_session_update(model_id: str) -> dict[str, Any]:
    return {
        "type": "session.update",
        "session": {
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": 24000},
                    "transcription": {"model": model_id},
                    "turn_detection": None,
                }
            },
        },
    }


def build_append_envelope(pcm16_bytes: bytes) -> dict[str, str]:
    return {
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(pcm16_bytes).decode("ascii"),
    }


def build_commit_envelope() -> dict[str, str]:
    return {"type": "input_audio_buffer.commit"}


def float32_to_pcm16(audio: np.ndarray) -> bytes:
    flat = np.asarray(audio, dtype=np.float32).ravel()
    if flat.size == 0:
        return b""
    clipped = np.clip(flat, -1.0, 1.0)
    # "<i2" pins the little-endian wire format on every platform.
    return (clipped * 32767).astype("<i2").tobytes()


def resample_16k_to_24k(pcm16: bytes) -> bytes:
    if len(pcm16) == 0:
        return b""
    samples = np.frombuffer(pcm16[: len(pcm16) // 2 * 2], dtype="<i2").astype(np.float64)
    n = samples.shape[0]
    if n == 0:
        return b""
    out_len = (n * 3 + 1) // 2
    positions = np.linspace(0.0, float(n - 1), num=out_len)
    resampled = np.interp(positions, np.arange(n, dtype=np.float64), samples)
    return np.clip(np.rint(resampled), -32768, 32767).astype("<i2").tobytes()


def frame_200ms(pcm24k: bytes, frame_samples: int = 4800) -> Iterator[bytes]:
    if len(pcm24k) == 0:
        return
    stride = frame_samples * 2
    for offset in range(0, len(pcm24k), stride):
        yield pcm24k[offset : offset + stride]


class DeltaAssembler:
    """Buffer streaming transcription deltas until the completed event."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._final: str | None = None

    def feed(self, event: dict[str, Any]) -> None:
        event_type = event.get("type", "") if isinstance(event, dict) else ""
        if not isinstance(event_type, str):
            return
        if event_type.endswith("transcription.failed"):
            raise CloudEngineError("realtime transcription failed")
        if event_type.endswith("transcription.delta"):
            delta = event.get("delta", "")
            if isinstance(delta, str) and delta:
                self._parts.append(delta)
        elif event_type.endswith("transcription.completed"):
            transcript = event.get("transcript")
            if transcript is None:
                transcript = event.get("text", "")
            if isinstance(transcript, str) and transcript:
                self._final = transcript
            else:
                self._final = "".join(self._parts)

    def result(self) -> str:
        if self._final is not None:
            return self._final
        return "".join(self._parts)

    def reset(self) -> None:
        self._parts = []
        self._final = None


def ensure_not_realtime(provider: str | None, model_name: str | None) -> None:
    if is_realtime_model(provider, model_name):
        model = model_name.strip() if isinstance(model_name, str) else model_name
        raise CloudConfigError(
            f"Model '{model}' requires a live-streaming session"
            " and cannot be used with batch transcription"
        )
