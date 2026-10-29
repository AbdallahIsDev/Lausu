"""Ingest validation: prove the decoded audio is the media the user asked for.

A media job must never persist text (or report success) from an ingest that
produced nothing, produced only a fraction of the requested media, or
produced only silence. These thresholds live in one place because three
callers need them: the guarded stream-fallback probe, the post-decode gate
for every job (local and URL), and the outcome log.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_typer.server.media_ingest.errors import MEDIA_TOO_SHORT, MEDIA_TRUNCATED

#: Anything shorter than this is not media we can transcribe; a URL stream
#: that cannot prove at least this much audio is refused outright.
MIN_MEDIA_SECONDS: float = 1.0

#: Truncation tolerance: max(absolute, fraction of expected). Containers and
#: VAD-trimmed windows legitimately land a little short of the header
#: duration, so a strict equality would fail healthy jobs.
TRUNCATION_ABS_SLACK_SECONDS: float = 2.0
TRUNCATION_REL_SLACK: float = 0.10

#: "Total silence" uses the engine's own near-silence shape (RMS floor and
#: silence percentage), so a silent ingest gets the same "no speech" outcome
#: a silent dictation would.
SILENCE_RMS_THRESHOLD: float = 0.01
SILENCE_PERCENT_THRESHOLD: float = 95.0


@dataclass(frozen=True)
class IngestVerdict:
    """Result of validating one job's decoded audio."""

    ok: bool
    code: str | None = None
    message: str = ""

    def summary(self, decoded: float, expected: float | None) -> str:
        """One-line description for the outcome log."""
        total = f"{expected:.1f}s" if expected is not None else "n/a"
        return f"decoded={decoded:.1f}s expected={total}"

    @property
    def is_too_short(self) -> bool:
        return self.code == MEDIA_TOO_SHORT

    @property
    def is_truncated(self) -> bool:
        return self.code == MEDIA_TRUNCATED


def validate_decoded(*, decoded_seconds: float, expected_seconds: float | None) -> IngestVerdict:
    """Reject an ingest that decoded (almost) nothing or a truncated tail.

    ``expected_seconds`` is the duration the resolver reported, or a probe of
    the file that was actually ingested. ``None`` means "unknown" — the
    duration floor still applies, but no truncation claim can be made.
    """
    decoded = max(0.0, float(decoded_seconds or 0.0))
    if decoded < MIN_MEDIA_SECONDS:
        return IngestVerdict(
            ok=False,
            code=MEDIA_TOO_SHORT,
            message="the media was too short to transcribe",
        )
    if expected_seconds is None:
        return IngestVerdict(ok=True)
    expected = float(expected_seconds)
    if expected <= 0:
        return IngestVerdict(ok=True)
    slack = max(TRUNCATION_ABS_SLACK_SECONDS, expected * TRUNCATION_REL_SLACK)
    if decoded < expected - slack:
        return IngestVerdict(
            ok=False,
            code=MEDIA_TRUNCATED,
            message=f"only {decoded:.1f}s of {expected:.1f}s of audio could be read",
        )
    return IngestVerdict(ok=True)


def is_total_silence(rms: float | None, silence_pct: float | None) -> bool:
    """True when the decoded audio carries no usable speech energy.

    Both readings are required: an unknown statistic is not evidence of
    silence, and treating it as such would drop real transcripts.
    """
    if rms is None or silence_pct is None:
        return False
    return float(rms) < SILENCE_RMS_THRESHOLD and float(silence_pct) >= SILENCE_PERCENT_THRESHOLD
