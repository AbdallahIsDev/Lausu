"""Chunker + chunked polish: bounded, sentence-aligned, contiguous output."""

from __future__ import annotations

import logging

from voice_typer.server.model_providers.local_onnx.chunked import polish_chunked
from voice_typer.server.model_providers.local_onnx.chunker import chunk_sentences


def _sentences(count: int) -> str:
    return " ".join(f"Sentence {index} says " + "filler " * 12 + "done." for index in range(count))


def test_chunks_are_bounded_and_never_cut_a_sentence() -> None:
    text = _sentences(30)

    chunks = chunk_sentences(text, min_words=60, max_words=90)

    assert len(chunks) >= 2
    assert all(len(chunk.split()) <= 90 for chunk in chunks)
    assert "".join("".join(chunks).split()) == "".join(text.split())
    for chunk in chunks[:-1]:
        assert chunk.endswith((".", "!", "?", "…"))


def test_a_single_overlong_sentence_may_split_but_never_exceeds_max() -> None:
    text = " ".join(["word"] * 50) + "."

    chunks = chunk_sentences(text, min_words=10, max_words=20)

    assert chunks
    assert all(len(chunk.split()) <= 20 for chunk in chunks)


class _StubClient:
    provider_id = "stub"
    model_id = "stub"

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self.calls: list[str] = []

    def complete(self, messages, *, max_tokens: int = 1024, timeout_s=None, abort_event=None) -> str:
        self.calls.append(messages[-1].content)
        return self._outputs.pop(0)

    def stream(self, messages, **kwargs):
        yield ""


def test_chunked_polish_joins_with_one_space_and_reuses_an_empty_chunk(caplog) -> None:
    text = _sentences(4)
    chunks = chunk_sentences(text, min_words=10, max_words=50)
    assert len(chunks) >= 2
    client = _StubClient([""] + ["OK"] * (len(chunks) - 1))

    with caplog.at_level(logging.WARNING):
        out = polish_chunked(client, text, "system", min_words=10, max_words=50)

    assert "\n\n" not in out
    assert out.startswith(chunks[0])
    assert "returned empty text" in caplog.text
    assert f"chunk 1/{len(chunks)}" in caplog.text


def test_chunked_polish_honours_abort_between_chunks() -> None:
    class _Abort:
        def __init__(self) -> None:
            self.calls = 0

        def is_set(self) -> bool:
            self.calls += 1
            return self.calls > 1

    text = _sentences(6)
    chunks = chunk_sentences(text, min_words=10, max_words=40)
    client = _StubClient(["OK"] * len(chunks))

    out = polish_chunked(client, text, "system", min_words=10, max_words=40, abort_event=_Abort())

    assert len(client.calls) < len(chunks)
    assert out == "OK"
