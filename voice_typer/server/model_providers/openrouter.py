"""OpenRouter: one key, a catalogue classified into the three domains.

Classification reads the catalogue's own modality metadata, never the model
name (WP3): a model that accepts audio and returns text is an ASR model, a
model that returns audio is a TTS model, text-in/text-out is an LLM.
"""

from __future__ import annotations

import base64
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from voice_typer.server.asr_errors import CloudEngineError
from voice_typer.server.model_providers._http import bearer, request_json
from voice_typer.server.model_providers.catalogue import get_catalogue_cache
from voice_typer.server.model_providers.contracts.llm import ChatMessage
from voice_typer.server.model_providers.contracts.tts import TtsAudio, TtsRequest
from voice_typer.server.model_providers.descriptor import Domain, ModelDescriptor
from voice_typer.server.model_providers.errors import ProviderCapabilityError, ProviderRuntimeError
from voice_typer.server.model_providers.openai_compat import OpenAiCompatibleChatClient

log = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_PROVIDER_ID = "openrouter"

#: Declared OpenRouter TTS voices (OpenRouter serves the OpenAI voice set).
_OPENROUTER_VOICES: tuple[str, ...] = ("alloy", "echo", "fable", "onyx", "nova", "shimmer")


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_architecture(architecture: dict[str, Any] | None) -> frozenset[Domain]:
    """Classify one catalogue entry from its modalities (not its name)."""
    if not isinstance(architecture, dict):
        return frozenset()
    inputs = {str(m).lower() for m in (architecture.get("input_modalities") or [])}
    outputs = {str(m).lower() for m in (architecture.get("output_modalities") or [])}
    if not inputs or not outputs:
        modality = str(architecture.get("modality") or "")
        if "->" in modality:
            left, right = modality.split("->", 1)
            inputs = {part.strip().lower() for part in left.split("+") if part.strip()}
            outputs = {part.strip().lower() for part in right.split("+") if part.strip()}
    domains: set[Domain] = set()
    if "audio" in outputs:
        domains.add(Domain.TTS)
    if "audio" in inputs and "text" in outputs:
        domains.add(Domain.ASR)
    if "text" in inputs and "text" in outputs:
        domains.add(Domain.LLM)
    return frozenset(domains)


def _audio_input(architecture: dict[str, Any]) -> bool:
    """True when the catalogue says this model accepts audio."""
    inputs = {str(m).lower() for m in (architecture.get("input_modalities") or [])}
    if inputs:
        return "audio" in inputs
    modality = str(architecture.get("modality") or "")
    if "->" in modality:
        left = modality.split("->", 1)[0]
        return "audio" in {part.strip().lower() for part in left.split("+") if part.strip()}
    return False


def classify_pricing(pricing: dict[str, Any] | None) -> tuple[float | None, float | None, bool]:
    """Return ``(prompt_price, completion_price, free)``."""
    if not isinstance(pricing, dict):
        return None, None, False
    prompt = _to_float(pricing.get("prompt"))
    completion = _to_float(pricing.get("completion"))
    free = prompt == 0.0 and completion == 0.0
    return prompt, completion, free


def parse_models(payload: Any) -> list[ModelDescriptor]:
    """Turn ``GET /api/v1/models`` into descriptors."""
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise CloudEngineError("openrouter returned an unexpected catalogue payload")
    models: list[ModelDescriptor] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        raw_architecture = row.get("architecture")
        architecture: dict[str, Any] = raw_architecture if isinstance(raw_architecture, dict) else {}
        domains = classify_architecture(architecture)
        if not domains:
            continue
        prompt, completion, free = classify_pricing(row.get("pricing"))
        context = row.get("context_length")
        metadata: dict[str, Any] = {}
        note = "Free" if free else None
        if _audio_input(architecture):
            # Measured 2026-11-01: OpenRouter has no /audio/transcriptions route;
            # audio-in models are multimodal CHAT models, never dedicated ASR.
            note = "chat model with audio input (not a dedicated ASR endpoint)"
            metadata = {"audio_mode": "chat"}
        models.append(
            ModelDescriptor(
                id=str(row["id"]),
                label=str(row.get("name") or row["id"]),
                domains=domains,
                context_length=int(context) if isinstance(context, (int, float)) else None,
                prompt_price=prompt,
                completion_price=completion,
                free=free,
                note=note,
                metadata=metadata,
            )
        )
    return models


def fetch_catalogue(
    api_key: str,
    *,
    base_url: str = OPENROUTER_BASE_URL,
    opener: Any = None,
    timeout_s: float = 20.0,
) -> list[ModelDescriptor]:
    """Fetch and cache the live OpenRouter catalogue."""
    payload = request_json(
        f"{base_url.rstrip('/')}/models",
        provider=OPENROUTER_PROVIDER_ID,
        headers=bearer(api_key),
        timeout=timeout_s,
        opener=opener,
    )
    models = parse_models(payload)
    get_catalogue_cache().write(
        OPENROUTER_PROVIDER_ID,
        [
            {
                "id": m.id,
                "label": m.label,
                "domains": sorted(d.value for d in m.domains),
                "context_length": m.context_length,
                "prompt_price": m.prompt_price,
                "completion_price": m.completion_price,
                "free": m.free,
                "note": m.note,
                "metadata": m.metadata,
            }
            for m in models
        ],
    )
    return models


def probe_key(
    api_key: str,
    *,
    base_url: str = OPENROUTER_BASE_URL,
    opener: Any = None,
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    """Prove the stored key works (``GET /api/v1/key``).

    ``/models`` is public, so a catalogue read cannot tell a good key from a
    revoked one; this endpoint answers with the key's own budget and rejects an
    invalid key with 401, which is mapped onto the typed auth error.
    """
    from voice_typer.server.asr_errors import CloudAuthError
    from voice_typer.server.model_providers.errors import ProviderAuthRequiredError

    try:
        payload = request_json(
            f"{base_url.rstrip('/')}/key",
            provider=OPENROUTER_PROVIDER_ID,
            headers=bearer(api_key),
            timeout=timeout_s,
            opener=opener,
        )
    except CloudAuthError as exc:
        raise ProviderAuthRequiredError(
            f"OpenRouter rejected the API key ({exc})",
            provider=OPENROUTER_PROVIDER_ID,
        ) from exc
    data = payload.get("data") if isinstance(payload, dict) else None
    out: dict[str, Any] = {"authenticated": True}
    if isinstance(data, dict):
        for key in ("label", "limit", "limit_remaining", "usage", "is_free_tier"):
            if data.get(key) is not None:
                out[key] = data[key]
    return out


def cached_models() -> list[ModelDescriptor]:
    """Return the cached catalogue as descriptors (may be stale)."""
    snap = get_catalogue_cache().read(OPENROUTER_PROVIDER_ID)
    if snap is None:
        return []
    out: list[ModelDescriptor] = []
    for row in snap.models:
        domains = frozenset(Domain(d) for d in row.get("domains") or [] if d in Domain._value2member_map_)
        if not domains:
            continue
        metadata = row.get("metadata")
        out.append(
            ModelDescriptor(
                id=str(row.get("id", "")),
                label=str(row.get("label") or row.get("id") or ""),
                domains=domains,
                context_length=row.get("context_length"),
                prompt_price=row.get("prompt_price"),
                completion_price=row.get("completion_price"),
                free=bool(row.get("free")),
                note=row.get("note"),
                metadata=dict(metadata) if isinstance(metadata, dict) else {},
            )
        )
    return out


@dataclass
class _OpenRouterAuth:
    api_key: str
    base_url: str = OPENROUTER_BASE_URL


def _chat_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


class OpenRouterLlmClient(OpenAiCompatibleChatClient):
    """LLM client with SSE streaming for long dictations."""

    def __init__(self, auth: _OpenRouterAuth, model_id: str, opener: Any = None) -> None:
        super().__init__(
            provider_id=OPENROUTER_PROVIDER_ID,
            model_id=model_id,
            chat_url=_chat_url(auth.base_url),
            headers=bearer(auth.api_key),
            opener=opener,
        )


class OpenRouterAsrClient:
    """ASR through an audio-input chat model."""

    provider_id = OPENROUTER_PROVIDER_ID

    def __init__(
        self,
        auth: _OpenRouterAuth,
        model_id: str,
        opener: Any = None,
        *,
        language: str | None = None,
        sample_rate: int = 16000,
    ) -> None:
        self._auth = auth
        self.model_id = model_id
        self._opener = opener
        self._language = (language or "").strip()
        self._sample_rate = sample_rate

    def _hint_prompt(self, audio: np.ndarray) -> str:
        base = "Transcribe this audio verbatim. Output only the transcript."
        hints: list[str] = []
        if self._language:
            hints.append(f"Language: {self._language}.")
        samples = int(getattr(audio, "size", 0) or 0)
        if samples and self._sample_rate > 0:
            hints.append(f"Audio duration: {samples / self._sample_rate:.1f} seconds.")
        return f"{base} {' '.join(hints)}" if hints else base

    def transcribe(self, audio: np.ndarray, *, abort_event: Any = None) -> str:
        if abort_event is not None and abort_event.is_set():
            return ""
        from voice_typer.server.cloud._transport import _audio_to_wav_bytes

        wav = _audio_to_wav_bytes(audio)
        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._hint_prompt(audio)},
                        {
                            "type": "input_audio",
                            "input_audio": {"data": base64.b64encode(wav).decode("ascii"), "format": "wav"},
                        },
                    ],
                }
            ],
        }
        data = request_json(
            _chat_url(self._auth.base_url),
            provider=OPENROUTER_PROVIDER_ID,
            method="POST",
            headers=bearer(self._auth.api_key),
            body=payload,
            timeout=120.0,
            opener=self._opener,
        )
        if abort_event is not None and abort_event.is_set():
            # The request is synchronous; cancel cleanly before parsing/reporting.
            return ""
        try:
            return str(data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise CloudEngineError("openrouter returned an unexpected transcription payload") from exc


class OpenRouterTtsClient:
    """TTS through a chat model that returns audio in ``message.audio``."""

    provider_id = OPENROUTER_PROVIDER_ID

    def __init__(
        self,
        auth: _OpenRouterAuth,
        model_id: str,
        opener: Any = None,
        *,
        language: str | None = None,
    ) -> None:
        self._auth = auth
        self.model_id = model_id
        self._opener = opener
        self._language = (language or "").strip()

    def voices(self) -> tuple[str, ...]:
        return _OPENROUTER_VOICES

    def languages(self) -> tuple[str, ...]:
        """Provider-declared: the configured language, else the OpenAI set.

        OpenRouter exposes no per-model language list, so claiming a single
        hard-coded tag was a lie; the configured language is the only fact.
        """
        if self._language:
            return (self._language,)
        from voice_typer.server.model_providers.hosted_tts import OPENAI_TTS_LANGUAGES

        return tuple(OPENAI_TTS_LANGUAGES)

    def synthesize(self, request: TtsRequest, *, abort_event: Any = None) -> TtsAudio:
        voice = request.voice or "alloy"
        if voice not in self.voices():
            raise ProviderCapabilityError(
                f"openrouter does not advertise voice {voice!r}",
                provider=OPENROUTER_PROVIDER_ID,
                domain="tts",
            )
        payload = {
            "model": self.model_id,
            "modalities": ["text", "audio"],
            "audio": {"voice": voice, "format": "wav"},
            "messages": [{"role": "user", "content": request.text}],
        }
        data = request_json(
            _chat_url(self._auth.base_url),
            provider=OPENROUTER_PROVIDER_ID,
            method="POST",
            headers=bearer(self._auth.api_key),
            body=payload,
            timeout=120.0,
            opener=self._opener,
        )
        try:
            encoded = data["choices"][0]["message"]["audio"]["data"]
            return TtsAudio(data=base64.b64decode(encoded), content_type="audio/wav")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderRuntimeError("openrouter returned no audio for the request") from exc

    def stream(self, messages: Sequence[ChatMessage], **_: Any) -> Iterator[str]:
        raise ProviderRuntimeError("openrouter TTS client is not a text client")


__all__ = [
    "OPENROUTER_BASE_URL",
    "OPENROUTER_PROVIDER_ID",
    "OpenRouterAsrClient",
    "OpenRouterLlmClient",
    "OpenRouterTtsClient",
    "cached_models",
    "classify_architecture",
    "classify_pricing",
    "fetch_catalogue",
    "parse_models",
]
