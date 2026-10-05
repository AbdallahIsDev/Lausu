"""Structured payloads enqueued on the history writer queue."""

from __future__ import annotations

import concurrent.futures


class _BatchableInsert:
    """Structured payload for a batchable transcription INSERT.

    ``add_transcription`` enqueues this instead of a closure so the writer
    thread can drain several pending rows into ONE multi-row transaction.
    ``future`` is ``None`` for the fire-and-forget dictation path and set
    only by a caller that wants the row_id back.

    ``__slots__`` keeps per-row memory small: the queue can hold thousands
    of these under bursty dictation.
    """

    __slots__ = (
        "text",
        "duration",
        "model",
        "device",
        "word_count",
        "char_count",
        "language",
        "future",
    )

    def __init__(
        self,
        *,
        text: str,
        duration: float,
        model: str,
        device: str,
        word_count: int,
        char_count: int,
        language: str,
        future: concurrent.futures.Future | None = None,
    ) -> None:
        self.text = text
        self.duration = duration
        self.model = model
        self.device = device
        self.word_count = word_count
        self.char_count = char_count
        self.language = language
        self.future = future
