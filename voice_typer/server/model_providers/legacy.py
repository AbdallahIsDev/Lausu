"""Adapters: the pre-existing single-provider paths behind the domain contracts.

These are the WP1 "first entries": the cloud engine and the LLM polisher keep
their exact behaviour and error mapping, only their surface becomes a contract.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from typing import Any

from voice_typer.server.model_providers.contracts.llm import ChatMessage
from voice_typer.server.model_providers.errors import ProviderRuntimeError
from voice_typer.server.model_providers.routing import provider_key

log = logging.getLogger(__name__)


class CloudAsrAdapter:
    """``CloudEngine`` behind the ASR contract."""

    provider_id = "cloud_direct"

    def __init__(self, engine: Any) -> None:
        self._engine = engine
        self.model_id = str(getattr(engine, "model_name", "") or "")

    def transcribe(self, audio: Any, *, abort_event: Any = None) -> str:
        return str(self._engine.transcribe(audio, abort_event=abort_event))


class LegacyLlmAdapter:
    """``LLMPolisher`` behind the LLM contract."""

    provider_id = "cloud_direct"

    def __init__(self, polisher: Any) -> None:
        self._polisher = polisher
        self.model_id = str(getattr(polisher, "model", "") or "")

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int = 1024,
        timeout_s: float | None = None,
        abort_event: Any = None,
    ) -> str:
        system = "\n".join(m.content for m in messages if m.role == "system")
        user = "\n".join(m.content for m in messages if m.role == "user")
        preset = getattr(self._polisher, "preset", "professional")
        return str(
            self._polisher._call_api(user, system, timeout_s=timeout_s)
            if system
            else self._polisher.polish(user, preset=preset, timeout_s=timeout_s)
        )

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int = 1024,
        timeout_s: float | None = None,
        abort_event: Any = None,
    ) -> Iterator[str]:
        yield self.complete(
            messages,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            abort_event=abort_event,
        )


def cloud_asr_client(config: Any, model_id: str = "") -> CloudAsrAdapter:
    """Build the configured cloud ASR engine for the ASR contract."""
    from voice_typer.server.cloud._engine import CloudEngine

    provider = str(getattr(config, "cloud_provider", "") or "")
    if not provider:
        raise ProviderRuntimeError(
            "no cloud provider selected",
            provider="cloud_direct",
            domain="asr",
        )
    consent_field = f"cloud_{provider}_consent"
    engine = CloudEngine(
        provider=provider,
        api_key=provider_key(config, provider),
        api_url=str(getattr(config, "cloud_api_url", "") or "") or None,
        model=model_id or str(getattr(config, "cloud_model", "") or "") or None,
        language=str(getattr(config, "language", "en") or "en"),
        consent_given=bool(getattr(config, consent_field, False)),
    )
    return CloudAsrAdapter(engine)


def legacy_llm_client(config: Any, model_id: str = "") -> LegacyLlmAdapter:
    """Build the configured OpenAI-compatible LLM polisher for the LLM contract."""
    from voice_typer.server.llm_polish import LLMPolisher

    key = str(getattr(config, "llm_api_key", "") or "") or provider_key(config, "openai")
    polisher = LLMPolisher(
        api_key=key,
        api_url=str(getattr(config, "llm_api_url", "") or "") or None,
        model=model_id or str(getattr(config, "llm_model", "") or "") or None,
        preset=str(getattr(config, "llm_preset", "professional") or "professional"),
        enabled=True,
    )
    return LegacyLlmAdapter(polisher)


__all__ = [
    "CloudAsrAdapter",
    "LegacyLlmAdapter",
    "cloud_asr_client",
    "legacy_llm_client",
]
