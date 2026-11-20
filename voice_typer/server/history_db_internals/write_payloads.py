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
        "kind",
        "source_type",
        "source_title",
        "source_url",
        "file_name",
        "thumbnail_url",
        "media_duration_seconds",
        "processing_seconds",
        "download_seconds",
        "method",
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
        kind: str = "dictation",
        source_type: str | None = None,
        source_title: str | None = None,
        source_url: str | None = None,
        file_name: str | None = None,
        thumbnail_url: str | None = None,
        media_duration_seconds: float | None = None,
        processing_seconds: float | None = None,
        download_seconds: float | None = None,
        method: str | None = None,
        future: concurrent.futures.Future | None = None,
    ) -> None:
        self.text = text
        self.duration = duration
        self.model = model
        self.device = device
        self.word_count = word_count
        self.char_count = char_count
        self.language = language
        self.kind = kind
        self.source_type = source_type
        self.source_title = source_title
        self.source_url = source_url
        self.file_name = file_name
        self.thumbnail_url = thumbnail_url
        self.media_duration_seconds = media_duration_seconds
        self.processing_seconds = processing_seconds
        self.download_seconds = download_seconds
        self.method = method
        self.future = future
