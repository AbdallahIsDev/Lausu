"""Sequential, sentence-packed polish through a local text client.

Chunks are independent calls, run in order, concatenated in order. Abort is the
pipeline's scoped event, so a cancelled dictation stops at the current chunk and
keeps the partial result instead of losing it.
"""

from __future__ import annotations

import logging

from voice_typer.server.model_providers.contracts.llm import ChatMessage, LlmClient
from voice_typer.server.model_providers.local_onnx.chunker import MAX_CHUNK_WORDS, MIN_CHUNK_WORDS, chunk_sentences

log = logging.getLogger(__name__)


def polish_chunked(
    client: LlmClient,
    text: str,
    system_prompt: str,
    *,
    min_words: int = MIN_CHUNK_WORDS,
    max_words: int = MAX_CHUNK_WORDS,
    max_tokens: int = 768,
    abort_event: object | None = None,
) -> str:
    """Polish ``text`` chunk by chunk and return the joined result."""
    chunks = chunk_sentences(text, min_words=min_words, max_words=max_words)
    if not chunks:
        return text
    results: list[str] = []
    for index, chunk in enumerate(chunks):
        if abort_event is not None and getattr(abort_event, "is_set", lambda: False)():
            log.info("[LOCAL_ONNX] polish aborted after %d/%d chunks", index, len(chunks))
            break
        messages = [ChatMessage(role="system", content=system_prompt), ChatMessage(role="user", content=chunk)]
        try:
            out = client.complete(messages, max_tokens=max_tokens, abort_event=abort_event)
        except Exception as exc:
            log.warning("[LOCAL_ONNX] chunk %d/%d failed: %s", index + 1, len(chunks), exc)
            raise
        cleaned = out.strip()
        if not cleaned:
            log.warning(
                "[LOCAL_ONNX] chunk %d/%d returned empty text, reusing the input",
                index + 1,
                len(chunks),
            )
            cleaned = chunk
        results.append(cleaned)
    # A dictation is one continuous text: never inject paragraph breaks.
    return " ".join(results)


__all__ = ["polish_chunked"]
