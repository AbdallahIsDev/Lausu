"""Ollama: local runtime first, hosted cloud mode under the same provider row.

Local mode probes ``/api/tags`` and lists only what is actually pulled; it needs
no key and works offline. Cloud mode talks to a hosted endpoint with a key and
reuses the OpenAI-compatible adapter.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from typing import Any

from voice_typer.server.asr_errors import CloudEngineError
from voice_typer.server.model_providers._http import request_json
from voice_typer.server.model_providers.contracts.llm import ChatMessage
from voice_typer.server.model_providers.descriptor import Domain, ModelDescriptor
from voice_typer.server.model_providers.openai_compat import OpenAiCompatibleChatClient

log = logging.getLogger(__name__)

OLLAMA_PROVIDER_ID = "ollama"
OLLAMA_LOCAL_BASE = "http://localhost:11434"
OLLAMA_CLOUD_BASE = "https://ollama.com/v1"


def list_local_models(
    base_url: str = OLLAMA_LOCAL_BASE,
    *,
    opener: Any = None,
    timeout_s: float = 5.0,
) -> list[ModelDescriptor]:
    """Return only the models actually pulled into the local Ollama runtime."""
    payload = request_json(
        f"{base_url.rstrip('/')}/api/tags",
        provider=OLLAMA_PROVIDER_ID,
        timeout=timeout_s,
        opener=opener,
    )
    rows = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise CloudEngineError("ollama returned an unexpected model list")
    out: list[ModelDescriptor] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("name"):
            continue
        out.append(
            ModelDescriptor(
                id=str(row["name"]),
                label=str(row.get("name")),
                domains=frozenset({Domain.LLM}),
                note=str(row.get("details", {}).get("parameter_size") or "") or None,
            )
        )
    return out


class OllamaChatClient:
    """Ollama ``/api/chat`` client (local mode; no OpenAI compatibility layer)."""

    provider_id = OLLAMA_PROVIDER_ID

    def __init__(self, model_id: str, base_url: str = OLLAMA_LOCAL_BASE, *, opener: Any = None) -> None:
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self._opener = opener

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int = 1024,
        timeout_s: float | None = None,
        abort_event: Any = None,
    ) -> str:
        payload = {
            "model": self.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        data = request_json(
            f"{self.base_url}/api/chat",
            provider=OLLAMA_PROVIDER_ID,
            method="POST",
            body=payload,
            timeout=timeout_s or 120.0,
            opener=self._opener,
        )
        try:
            return str(data["message"]["content"] or "")
        except (KeyError, TypeError) as exc:
            raise CloudEngineError("ollama returned an unexpected chat payload") from exc

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int = 1024,
        timeout_s: float | None = None,
        abort_event: Any = None,
    ) -> Iterator[str]:
        yield self.complete(messages, max_tokens=max_tokens, timeout_s=timeout_s, abort_event=abort_event)


class OllamaCloudClient(OpenAiCompatibleChatClient):
    """Hosted Ollama endpoint through the shared OpenAI-compatible adapter."""

    def __init__(self, model_id: str, api_key: str, base_url: str = OLLAMA_CLOUD_BASE, *, opener: Any = None) -> None:
        super().__init__(
            provider_id=OLLAMA_PROVIDER_ID,
            model_id=model_id,
            chat_url=f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            opener=opener,
        )


def list_cloud_models(api_key: str, *, base_url: str = OLLAMA_CLOUD_BASE, opener: Any = None) -> list[str]:
    """Return hosted model ids (``GET <base>/models``)."""
    data = request_json(
        f"{base_url.rstrip('/')}/models",
        provider=OLLAMA_PROVIDER_ID,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=20.0,
        opener=opener,
    )
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise CloudEngineError("ollama cloud returned an unexpected model list")
    return [str(row["id"]) for row in rows if isinstance(row, dict) and row.get("id")]


__all__ = [
    "OLLAMA_CLOUD_BASE",
    "OLLAMA_LOCAL_BASE",
    "OLLAMA_PROVIDER_ID",
    "OllamaChatClient",
    "OllamaCloudClient",
    "list_cloud_models",
    "list_local_models",
]
