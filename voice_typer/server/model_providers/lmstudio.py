"""LM Studio: local OpenAI-compatible server, no key, same adapter as Ollama."""

from __future__ import annotations

import logging
from typing import Any

from voice_typer.server.model_providers.descriptor import Domain, ModelDescriptor
from voice_typer.server.model_providers.openai_compat import ListingChatClient

log = logging.getLogger(__name__)

LMSTUDIO_PROVIDER_ID = "lmstudio"
LMSTUDIO_DEFAULT_BASE = "http://localhost:1234/v1"


def list_models(base_url: str = LMSTUDIO_DEFAULT_BASE, *, opener: Any = None) -> list[ModelDescriptor]:
    """Return the models LM Studio currently serves."""
    client = ListingChatClient(
        provider_id=LMSTUDIO_PROVIDER_ID,
        model_id="",
        base_url=base_url,
        opener=opener,
    )
    out: list[ModelDescriptor] = []
    for model_id in client.list_models():
        out.append(
            ModelDescriptor(
                id=model_id,
                label=model_id,
                domains=frozenset({Domain.LLM}),
            )
        )
    return out


def chat_client(model_id: str, base_url: str = LMSTUDIO_DEFAULT_BASE, *, opener: Any = None) -> ListingChatClient:
    """Build a chat client against the local LM Studio server."""
    return ListingChatClient(
        provider_id=LMSTUDIO_PROVIDER_ID,
        model_id=model_id,
        base_url=base_url,
        opener=opener,
    )


__all__ = [
    "LMSTUDIO_DEFAULT_BASE",
    "LMSTUDIO_PROVIDER_ID",
    "chat_client",
    "list_models",
]
