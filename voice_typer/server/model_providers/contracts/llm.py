"""LLM domain contract: chat messages in, polished text out.

``stream`` is part of the contract even when a provider cannot stream: the
default implementation yields the whole completion once, so callers can always
iterate and never branch on provider identity.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ChatMessage:
    """One chat turn (``system`` / ``user`` / ``assistant``)."""

    role: str
    content: str


@runtime_checkable
class LlmClient(Protocol):
    """A text-generation client for exactly one provider + model."""

    provider_id: str
    model_id: str

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int = 1024,
        timeout_s: float | None = None,
        abort_event: Any = None,
    ) -> str:
        """Return the assistant text for ``messages``."""
        ...

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int = 1024,
        timeout_s: float | None = None,
        abort_event: Any = None,
    ) -> Iterator[str]:
        """Yield text deltas in order (a single chunk when not streamable)."""
        ...


__all__ = ["ChatMessage", "LlmClient"]
