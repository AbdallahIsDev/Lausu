"""Errors, tuning constants, and segment planning for the segmented downloader.

Owns ``SegmentedDownloadError``, the byte thresholds / retry budgets /
timeouts every sibling reads, the callback type aliases, and the
``SegmentRange`` planner. Moved verbatim out of
``voice_typer.server.segmented_download`` (which re-exports every name).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

#: Files at/above this size are worth segmenting (below it the extra
SEGMENT_THRESHOLD_BYTES = 200 * 1024 * 1024
#: Target bytes per segment; segment count = ceil(size / target), capped.
SEGMENT_TARGET_BYTES = 256 * 1024 * 1024
#: Upper bound on concurrent Range connections (politeness: HF's own
MAX_SEGMENTS = 6
#: Wire read size, also the pause/cancel checkpoint granularity.
READ_CHUNK_BYTES = 1024 * 1024
#: Per-request socket timeout (connect + idle read).
REQUEST_TIMEOUT_S = 30
#: Max redirect hops when resolving the download URL.
MAX_REDIRECTS = 5
#: Attempts per segment (initial + retries) before the file fails over.
SEGMENT_ATTEMPTS = 3
#: Backoff between segment attempts (429 honors Retry-After instead).
RETRY_BACKOFF_S = (1.0, 2.0, 4.0)
#: Cap for a server-provided Retry-After delay.
MAX_RETRY_AFTER_S = 60.0

GateCheck = Callable[[], None]
ProgressCb = Callable[[int, int], None]  # (bytes_done, total_size)


class SegmentedDownloadError(Exception):
    """The segmented path cannot complete this file."""


@dataclass(frozen=True)
class SegmentRange:
    """One byte range [start, end] (both inclusive), zero-based."""

    index: int
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def plan_segments(
    total_size: int,
    *,
    segment_target: int = SEGMENT_TARGET_BYTES,
    max_segments: int = MAX_SEGMENTS,
) -> list[SegmentRange]:
    """Split ``total_size`` bytes into contiguous, gapless ranges."""
    if total_size <= 0:
        raise SegmentedDownloadError(f"cannot plan segments for size {total_size}")
    uncapped = -(-total_size // segment_target)
    count = max(1, min(max_segments, uncapped))
    ranges: list[SegmentRange] = []
    start = 0
    if count < uncapped:
        # Capped (huge file): split evenly so no single tail segment
        base, extra = divmod(total_size, count)
        for i in range(count):
            length = base + (1 if i < extra else 0)
            ranges.append(SegmentRange(index=i, start=start, end=start + length - 1))
            start += length
        return ranges
    # Uncapped: full target-sized segments + remainder tail.
    for i in range(count):
        end = start + segment_target - 1 if i < count - 1 else total_size - 1
        ranges.append(SegmentRange(index=i, start=start, end=end))
        start = end + 1
    return ranges
