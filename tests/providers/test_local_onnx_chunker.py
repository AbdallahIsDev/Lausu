"""Sentence-packed chunking: boundaries respected, size bounded, no mid-sentence cuts."""

from __future__ import annotations

from voice_typer.server.model_providers.local_onnx.chunker import MAX_CHUNK_WORDS, MIN_CHUNK_WORDS, chunk_sentences


def test_empty_input_yields_no_chunks() -> None:
    assert chunk_sentences("") == []
    assert chunk_sentences("   ") == []


def test_chunks_never_exceed_the_word_bound() -> None:
    text = " ".join(f"This is sentence number {i}, and it keeps going for a while." for i in range(40))
    for chunk in chunk_sentences(text):
        assert len(chunk.split()) <= MAX_CHUNK_WORDS


def test_chunks_prefer_the_minimum_size() -> None:
    text = " ".join(f"Sentence {i} has a handful of words in it." for i in range(60))
    chunks = chunk_sentences(text)
    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        assert len(chunk.split()) >= MIN_CHUNK_WORDS // 2


def test_sentences_are_never_cut_mid_sentence() -> None:
    sentence = "The quick brown fox jumps over the lazy dog."
    text = " ".join([sentence] * 30)
    for chunk in chunk_sentences(text):
        assert chunk.endswith(".")
        assert not chunk.startswith(" ")


def test_a_single_long_sentence_is_split_on_clause_boundaries() -> None:
    long_sentence = ", ".join(f"clause {i} with several words" for i in range(80)) + "."
    chunks = chunk_sentences(long_sentence, min_words=20, max_words=40)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.split()) <= 40


def test_output_preserves_every_word() -> None:
    text = "First sentence here. Second sentence follows! Third one ends the paragraph?"
    joined = " ".join(chunk_sentences(text))
    assert joined.split() == text.split()
