"""TEMPORARY reference: the pre-ffmpeg PyAV decoder, kept ONLY for parity tests.

This is not production code. It is the exact algorithm that decoder.py used
before the subprocess-ffmpeg change; parity tests compare its chunk output to
the new decoder's byte-for-byte (or within a documented epsilon). Delete this
file together with the parity tests once the decoder is retired.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

TARGET_SAMPLE_RATE = 16_000
CHUNK_SAMPLES = TARGET_SAMPLE_RATE * 5


def _concat(parts: list):
    import numpy as np

    if len(parts) == 1:
        return parts[0].astype(np.float32, copy=False)
    return np.concatenate(parts).astype(np.float32, copy=False)


def decode_chunks(source: str, *, remote: bool = False, start_seconds: float = 0.0) -> Iterator[Any]:
    """Yield mono float32 16 kHz chunks from a local file or remote URL (old path)."""
    from pathlib import Path

    from voice_typer.server.media_ingest.errors import DECODE_FAILED, MediaIngestError

    try:
        import av
    except ImportError as exc:
        raise MediaIngestError(DECODE_FAILED, "audio decoder unavailable") from exc

    if not remote and not Path(source).is_file():
        raise MediaIngestError(DECODE_FAILED, f"media file not found: {source}")

    options = {"open_timeout": "15000000", "read_timeout": "30000000"} if remote else None
    container = av.open(source, options=options) if options else av.open(source)
    with container:
        if start_seconds > 0:
            container.seek(int(start_seconds * 1_000_000))
        streams = [s for s in container.streams if s.type == "audio"]
        if not streams:
            from voice_typer.server.media_ingest.errors import NO_AUDIO

            raise MediaIngestError(NO_AUDIO, "no audio track found in media")
        resampler = av.AudioResampler(format="flt", layout="mono", rate=TARGET_SAMPLE_RATE)
        buffer: list = []
        buffered = 0
        try:
            for frame in container.decode(streams[0]):
                if type(frame) is not av.AudioFrame:
                    continue
                for out in resampler.resample(frame):
                    samples = out.to_ndarray()[0]
                    buffer.append(samples)
                    buffered += samples.shape[0]
                    while buffered >= CHUNK_SAMPLES:
                        merged = _concat(buffer)
                        yield merged[:CHUNK_SAMPLES]
                        rest = merged[CHUNK_SAMPLES:]
                        buffer = [rest] if rest.shape[0] else []
                        buffered = rest.shape[0]
        finally:
            for out in resampler.resample(None):
                samples = out.to_ndarray()[0]
                buffer.append(samples)
        if buffer:
            import numpy as np

            merged = _concat(buffer)
            if merged.shape[0]:
                yield merged.astype(np.float32, copy=False)
