"""OpenAI-compatible chat adapter shared by OpenRouter, Ollama and LM Studio.

One adapter, three providers (WP5: "no second client"). The caller supplies the
full chat-completions URL, headers and model id; streaming is the same code path
with ``stream: true``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Sequence
from typing import Any

from voice_typer.server.asr_errors import CloudEngineError
from voice_typer.server.model_providers._http import (
    iter_sse_json,
    open_stream,
    request_json,
)
from voice_typer.server.model_providers.contracts.llm import ChatMessage

log = logging.getLogger(__name__)


class OpenAiCompatibleChatClient:
    """Minimal OpenAI-compatible chat client (complete + stream)."""

    def __init__(
        self,
        *,
        provider_id: str,
        model_id: str,
        chat_url: str,
        headers: dict[str, str] | None = None,
        opener: Any = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.provider_id = provider_id
        self.model_id = model_id
        self.chat_url = chat_url
        self.headers = dict(headers or {})
        self._opener = opener
        self._timeout_s = timeout_s

    def _payload(self, messages: Sequence[ChatMessage], max_tokens: int, *, stream: bool) -> dict[str, Any]:
        return {
            "model": self.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "stream": stream,
        }

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int = 1024,
        timeout_s: float | None = None,
        abort_event: Any = None,
    ) -> str:
        data = request_json(
            self.chat_url,
            provider=self.provider_id,
            method="POST",
            headers=self.headers,
            body=self._payload(messages, max_tokens, stream=False),
            timeout=timeout_s or self._timeout_s,
            opener=self._opener,
        )
        try:
            return str(data["choices"][0]["message"]["content"] or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise CloudEngineError(f"{self.provider_id} returned an unexpected chat payload") from exc

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int = 1024,
        timeout_s: float | None = None,
        abort_event: Any = None,
    ) -> Iterator[str]:
        resp = open_stream(
            self.chat_url,
            provider=self.provider_id,
            headers=self.headers,
            body=self._payload(messages, max_tokens, stream=True),
            timeout=timeout_s or self._timeout_s,
            opener=self._opener,
        )
        with resp:
            for chunk in iter_sse_json(resp, provider=self.provider_id):
                if abort_event is not None and abort_event.is_set():
                    break
                try:
                    delta = chunk["choices"][0]["delta"].get("content")
                except (KeyError, IndexError, TypeError):
                    continue
                if delta:
                    yield str(delta)


class ListingChatClient(OpenAiCompatibleChatClient):
    """Chat client whose model list is fetched from ``/v1/models``."""

    def __init__(
        self,
        *,
        provider_id: str,
        model_id: str,
        base_url: str,
        headers: dict[str, str] | None = None,
        opener: Any = None,
    ) -> None:
        base = base_url.rstrip("/")
        super().__init__(
            provider_id=provider_id,
            model_id=model_id,
            chat_url=f"{base}/chat/completions",
            headers=headers,
            opener=opener,
        )
        self.models_url = f"{base}/models"

    def list_models(self, timeout_s: float = 15.0) -> list[str]:
        """Return the ids ``GET <base>/models`` reports."""
        data = request_json(
            self.models_url,
            provider=self.provider_id,
            headers=self.headers,
            timeout=timeout_s,
            opener=self._opener,
        )
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise CloudEngineError(f"{self.provider_id} returned an unexpected model list")
        return [str(row.get("id")) for row in rows if isinstance(row, dict) and row.get("id")]


def chat_payload_debug(payload: dict[str, Any]) -> str:
    """Return a key-free summary of a chat payload for logs."""
    return json.dumps({"model": payload.get("model"), "stream": payload.get("stream")})


__all__ = ["ListingChatClient", "OpenAiCompatibleChatClient"]
