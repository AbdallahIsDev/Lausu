"""In-memory sample reassembly + frame helpers for the worker WS server.

Split out of ``voice_typer.worker._ws_server`` (one concern per file).
The facade keeps the module names and every monkeypatch seam; this
module owns the moved bodies only (ADR-0025 C3). Pure reassembly: no IO,
no inference, no logging.
"""

from __future__ import annotations

# ─── In-memory sample reassembly (ADR-0025 C3) ──────────────────────────

# Bound the per-request reassembly state: 64 chunks × ~720 KiB raw keeps
# one request under ~46 MiB before inference (a 30 s window needs ~3).
_SAMPLES_MAX_CHUNKS = 64
# Base64 of one chunk must itself respect the frame cap (ADR-0020 §10).
_SAMPLES_MAX_PAYLOAD_B64 = 1_400_000
_SAMPLES_MIN_RATE = 1000
_SAMPLES_MAX_RATE = 192000


def _valid_request_id(value: object) -> int | None:
    """Numeric request id, or ``None`` (E8; JSON true/false never pass)."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


class _SamplesBuffer:
    """Accumulates one ``transcribe_samples`` request's base64 chunks.

    Pure reassembly (no IO, no inference): ``add_chunk`` validates and
    stores, ``audio_bytes`` returns the concatenated raw float32 PCM once
    every declared chunk has arrived, regardless of arrival order.
    """

    def __init__(self, total: int, sample_rate: int, language: object) -> None:
        self.total = total
        self.sample_rate = sample_rate
        self.language = str(language) if language is not None else None
        self._chunks: dict[int, bytes] = {}

    def add_chunk(self, index: int, payload_b64: str) -> str | None:
        """Store one chunk; return an error string, or ``None`` on success."""
        if not isinstance(index, int) or isinstance(index, bool):
            return "chunk index must be an integer"
        if not 0 <= index < self.total:
            return f"chunk index {index} out of range for total={self.total}"
        if index in self._chunks:
            return f"duplicate chunk index {index}"
        if not isinstance(payload_b64, str) or len(payload_b64) > _SAMPLES_MAX_PAYLOAD_B64:
            return "chunk payload too large"
        try:
            import base64

            raw = base64.b64decode(payload_b64, validate=True)
        except Exception:
            return "chunk payload is not valid base64"
        self._chunks[index] = raw
        return None

    def is_complete(self) -> bool:
        """True once every declared chunk has arrived (any order)."""
        return len(self._chunks) == self.total

    def audio_bytes(self) -> bytes:
        """Concatenated raw float32 PCM in index order (call when complete)."""
        return b"".join(self._chunks[i] for i in range(self.total))


def _valid_samples_header(data: dict) -> tuple[int, int, int, object, str | None]:
    """Validate a ``transcribe_samples`` chunk header.

    Returns ``(total, index, sample_rate, language, error)``; ``error``
    is ``None`` when the header is usable.
    """
    total = data.get("total")
    index = data.get("index")
    sample_rate = data.get("sample_rate")
    if isinstance(total, bool) or not isinstance(total, int) or not 1 <= total <= _SAMPLES_MAX_CHUNKS:
        return (0, 0, 0, None, f"total must be an integer in 1..{_SAMPLES_MAX_CHUNKS}")
    if isinstance(index, bool) or not isinstance(index, int):
        return (0, 0, 0, None, "index must be an integer")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int):
        return (0, 0, 0, None, "sample_rate must be an integer")
    if not _SAMPLES_MIN_RATE <= sample_rate <= _SAMPLES_MAX_RATE:
        return (0, 0, 0, None, f"sample_rate {sample_rate} out of range")
    return (total, index, sample_rate, data.get("language"), None)


def _word_to_dict(word: object) -> dict:
    """Serialize a window word (local Word or engine-shaped mapping/object)."""
    if isinstance(word, dict):
        return {
            "word": word.get("word"),
            "start_seconds": word.get("start_seconds"),
            "end_seconds": word.get("end_seconds"),
        }
    return {
        "word": getattr(word, "word", None),
        "start_seconds": getattr(word, "start_seconds", None),
        "end_seconds": getattr(word, "end_seconds", None),
    }
