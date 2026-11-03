"""OpenAI-compatible speech client for the local TTS runtimes.

This module exists so the app calls both engines through the API shape they
already publish (``POST /v1/audio/speech``) instead of tailoring a subprocess
call per engine, and so the call reuses the project's non-redirecting,
loopback-permitting opener rather than a fresh HTTP client.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

from voice_typer.server._http_safety import build_secure_opener
from voice_typer.server.tts.types import TtsError, TtsRequest, TtsResult
from voice_typer.server.tts.wav import probe_wav

log = logging.getLogger(__name__)

#: A full paragraph on CPU Vulkan can take a while; the runtime itself buffers
#: the complete utterance before replying (documented: no streaming on this
#: compatibility subset), so the ceiling covers synthesis, not transfer.
DEFAULT_TIMEOUT_S = 300.0
_ERROR_BODY_CHARS = 600


class LocalSpeechClient:
    """Client bound to one runtime's base URL."""

    def __init__(self, base_url: str, engine: str, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self._base_url = base_url.rstrip("/")
        self._engine = engine
        self._timeout_s = timeout_s
        self._opener = build_secure_opener()

    def speech(
        self,
        request: TtsRequest,
        output_wav: Path,
        *,
        model: str,
        voice: str | None = None,
        language: str | None = None,
    ) -> TtsResult:
        """Render ``request`` and write the returned WAV to ``output_wav``."""
        payload: dict[str, object] = {
            "model": model,
            "input": request.text,
            "response_format": "wav",
        }
        chosen_voice = voice or request.voice
        if chosen_voice:
            payload["voice"] = chosen_voice
        chosen_language = language or request.language
        if chosen_language:
            payload["language"] = chosen_language

        body = json.dumps(payload).encode("utf-8")
        http_request = Request(
            f"{self._base_url}/v1/audio/speech",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with self._opener.open(http_request, timeout=self._timeout_s) as response:
                audio = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace").strip()
            # Developer detail stays in the log; the renderer only ever sees a
            # mapped, plain-language message.
            log.warning(
                "[TTS] %s HTTP %d voice=%s language=%s body=%s",
                self._engine,
                exc.code,
                chosen_voice or "-",
                chosen_language or "-",
                detail[:_ERROR_BODY_CHARS],
            )
            raise TtsError(
                f"{self._engine}: HTTP {exc.code} from /v1/audio/speech\n{detail[:_ERROR_BODY_CHARS]}"
            ) from exc
        except URLError as exc:
            log.warning(
                "[TTS] %s unreachable voice=%s language=%s reason=%s",
                self._engine,
                chosen_voice or "-",
                chosen_language or "-",
                exc.reason,
            )
            raise TtsError(f"{self._engine}: cannot reach {self._base_url}: {exc.reason}") from exc
        wall = time.perf_counter() - started

        # The audio.cpp docs call this out explicitly: a failed request can save
        # an error body instead of a WAV, so a 200 with JSON must not be played.
        stripped = audio.lstrip()
        if not audio or stripped[:1] in (b"{", b"[", b"<"):
            raise TtsError(f"{self._engine}: response is not audio: {audio[:200]!r}")

        output_wav.parent.mkdir(parents=True, exist_ok=True)
        output_wav.write_bytes(audio)
        duration, sample_rate = probe_wav(output_wav)
        log.debug(
            "[TTS] %s rendered %.2fs audio in %.2fs (RTF %.2f) voice=%s language=%s -> %s",
            self._engine,
            duration,
            wall,
            duration / wall if wall else 0.0,
            chosen_voice or "-",
            chosen_language or "-",
            output_wav,
        )
        return TtsResult(
            engine=self._engine,
            wav_path=output_wav,
            duration_s=duration,
            wall_s=wall,
            sample_rate=sample_rate,
        )
