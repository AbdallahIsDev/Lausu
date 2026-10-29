"""PyAV decode to 16 kHz mono float32 chunks (ADR-0023 tiers 0/1/4)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

log = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16_000
CHUNK_SAMPLES = TARGET_SAMPLE_RATE * 5
OPEN_TIMEOUT_US = 15_000_000
READ_TIMEOUT_US = 30_000_000


def decode_chunks(source: str, *, remote: bool = False, start_seconds: float = 0.0) -> Iterator[Any]:
    """Yield mono float32 16 kHz chunks from a local file or remote URL.

    ``start_seconds`` seeks past already-transcribed audio so a stalled or
    expired stream can resume without duplicating text (E9/E10). Seek
    failure raises STREAM_STALLED so the caller can fall back to a full
    temp download instead of emitting a duplicated transcript.
    """
    from voice_typer.server.media_ingest.errors import DECODE_FAILED, MediaIngestError

    try:
        import av
    except ImportError as exc:
        raise MediaIngestError(DECODE_FAILED, "audio decoder unavailable") from exc

    if not remote and not Path(source).is_file():
        raise MediaIngestError(DECODE_FAILED, f"media file not found: {source}")

    options = {"open_timeout": str(OPEN_TIMEOUT_US), "read_timeout": str(READ_TIMEOUT_US)} if remote else None
    try:
        container = av.open(source, options=options) if options else av.open(source)
    except Exception as exc:
        raise _classify_stream_error(exc, context="open") from exc

    with container:
        if start_seconds > 0:
            try:
                container.seek(int(start_seconds * 1_000_000))
            except Exception as exc:
                from voice_typer.server.media_ingest.errors import STREAM_STALLED

                raise MediaIngestError(STREAM_STALLED, "could not resume media stream") from exc
        streams = [s for s in container.streams if s.type == "audio"]
        if not streams:
            from voice_typer.server.media_ingest.errors import NO_AUDIO

            raise MediaIngestError(NO_AUDIO, "no audio track found in media")
        stream = streams[0]
        try:
            resampler = av.AudioResampler(format="flt", layout="mono", rate=TARGET_SAMPLE_RATE)
        except Exception as exc:
            raise MediaIngestError(DECODE_FAILED, f"resampler unavailable: {exc}") from exc
        buffer: list = []
        buffered = 0
        try:
            for frame in container.decode(stream):
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
        except MediaIngestError:
            raise
        except Exception as exc:
            raise _classify_stream_error(exc, context="decode") from exc
        finally:
            try:
                for out in resampler.resample(None):
                    samples = out.to_ndarray()[0]
                    buffer.append(samples)
            except Exception:  # noqa: BLE001, best-effort flush
                log.debug("[MEDIA] resampler flush failed", exc_info=True)
        if buffer:
            import numpy as np

            merged = _concat(buffer)
            if merged.shape[0]:
                yield merged.astype(np.float32, copy=False)


@dataclass(frozen=True)
class RemoteProbe:
    """What a remote URL proved about itself before we streamed it.

    ``audio_streams`` is the count PyAV found (a web page served as HTML has
    none) and ``duration_seconds`` is the container-header duration, which
    is what a stream tier needs for percent/ETA and for the truncation gate.
    """

    audio_streams: int
    duration_seconds: float | None


def probe_remote(url: str) -> RemoteProbe | None:
    """Probe a resolved URL without decoding it; ``None`` when unusable.

    Streaming is the FALLBACK tier, and a signed CDN link that expired, a
    web page, or a non-HTTP scheme must never reach it: the failure would
    be a silent zero-chunk "success". Cheap enough to run once per job —
    one container open, no decode pass.
    """
    scheme = urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        return None
    try:
        import av
    except ImportError:
        return None
    try:
        container = av.open(url, options={"open_timeout": str(OPEN_TIMEOUT_US)})
    except Exception as exc:  # noqa: BLE001, a probe failure IS the signal
        log.debug("[MEDIA] remote probe failed to open (%s)", type(exc).__name__)
        return None
    with container:
        audio_streams = sum(1 for s in container.streams if s.type == "audio")
        duration = _container_duration(container)
    return RemoteProbe(audio_streams=audio_streams, duration_seconds=duration)


def _container_duration(container: Any) -> float | None:
    if container.duration:
        return float(container.duration) / 1_000_000.0
    stream = next((s for s in container.streams if s.type == "audio"), None)
    if stream is not None and stream.duration and stream.time_base:
        return float(stream.duration * stream.time_base)
    return None


def probe_duration_seconds(source: str, *, remote: bool = False) -> float | None:
    """Container duration in seconds, or ``None`` when unknown.

    Local jobs need a total to report a fraction/ETA (URL jobs get it from
    the resolver). The container header already carries it, so this costs
    one open, no decode pass; best-effort by design.
    """
    try:
        import av
    except ImportError:
        return None
    options = {"open_timeout": str(OPEN_TIMEOUT_US)} if remote else None
    try:
        container = av.open(source, options=options) if options else av.open(source)
        with container:
            return _container_duration(container)
    except Exception:  # noqa: BLE001, a probe never blocks the job
        log.debug("[MEDIA] duration probe failed", exc_info=True)
    return None


def _concat(parts: list):
    import numpy as np

    if len(parts) == 1:
        return parts[0].astype(np.float32, copy=False)
    return np.concatenate(parts).astype(np.float32, copy=False)


def _classify_stream_error(exc: Exception, *, context: str) -> Any:
    """Map PyAV/FFmpeg failures to the ADR-0023 stall/expiry taxonomy.

    PyAV's own TimeoutError extends the builtin, so the builtin catch
    covers both. HTTP 403 on a CDN URL means the signed link expired;
    5xx/429 are transient stalls.
    """
    from voice_typer.server.media_ingest.errors import (
        DECODE_FAILED,
        STREAM_STALLED,
        URL_EXPIRED,
        MediaIngestError,
    )

    if isinstance(exc, TimeoutError):
        return MediaIngestError(STREAM_STALLED, "media stream timed out")
    try:
        import av

        forbidden = getattr(av.error, "HTTPForbiddenError", None)
        if forbidden is not None and isinstance(exc, forbidden):
            return MediaIngestError(URL_EXPIRED, "media link expired")
        transient = tuple(
            cls
            for cls in (getattr(av.error, n, None) for n in ("HTTPTooManyRequestsError", "HTTPServerError"))
            if isinstance(cls, type)
        )
        if transient and isinstance(exc, transient):
            return MediaIngestError(STREAM_STALLED, "media server error")
    except ImportError:  # av was importable above; defensive only
        pass
    verb = "could not open media" if context == "open" else "decode failed"
    return MediaIngestError(DECODE_FAILED, f"{verb}: {exc}")
