"""Direct pins for the ingest validation thresholds (ADR-0023 §2).

The module was only exercised through the job bodies, so a threshold drift
(the floor, the unknown-expected path, the truncation slack) would only show
up as an end-to-end copy change.
"""

from __future__ import annotations

import pytest
from voice_typer.server.media_ingest import validation as v
from voice_typer.server.media_ingest.errors import MEDIA_TOO_SHORT, MEDIA_TRUNCATED


class TestDurationFloor:
    def test_sub_second_decode_is_too_short(self):
        verdict = v.validate_decoded(decoded_seconds=0.4, expected_seconds=None)
        assert verdict.ok is False
        assert verdict.code == MEDIA_TOO_SHORT

    def test_floor_is_inclusive(self):
        assert v.validate_decoded(decoded_seconds=v.MIN_MEDIA_SECONDS, expected_seconds=None).ok is True

    def test_negative_decode_is_floored_to_zero(self):
        verdict = v.validate_decoded(decoded_seconds=-3.0, expected_seconds=10.0)
        assert verdict.code == MEDIA_TOO_SHORT


class TestUnknownAndZeroExpected:
    @pytest.mark.parametrize("expected", [None, 0.0, -5.0])
    def test_no_total_means_no_truncation_claim(self, expected):
        """``None``/``<= 0`` cannot prove truncation, so only the floor applies."""
        assert v.validate_decoded(decoded_seconds=3.0, expected_seconds=expected).ok is True


class TestTruncationSlack:
    def test_absolute_slack_starts_at_two_seconds(self):
        """expected 10s -> slack max(2.0, 1.0) = 2.0, boundary inclusive."""
        assert v.validate_decoded(decoded_seconds=8.0, expected_seconds=10.0).ok is True
        assert v.validate_decoded(decoded_seconds=7.9, expected_seconds=10.0).code == MEDIA_TRUNCATED

    def test_relative_slack_takes_over_for_long_media(self):
        """expected 42s -> slack max(2.0, 4.2) = 4.2."""
        assert v.validate_decoded(decoded_seconds=37.8, expected_seconds=42.0).ok is True
        assert v.validate_decoded(decoded_seconds=37.7, expected_seconds=42.0).code == MEDIA_TRUNCATED

    def test_verdict_carries_a_readable_message(self):
        verdict = v.validate_decoded(decoded_seconds=3.0, expected_seconds=42.0)
        assert "3.0s of 42.0s" in verdict.message
        assert verdict.is_truncated is True
        assert verdict.is_too_short is False


class TestTotalSilence:
    @pytest.mark.parametrize(
        ("rms", "silence_pct", "expected"),
        [
            (0.0, 100.0, True),
            (0.009, 95.0, True),
            (0.01, 95.0, False),
            (0.0, 94.9, False),
            (None, 100.0, False),
            (0.0, None, False),
        ],
    )
    def test_both_readings_are_required(self, rms, silence_pct, expected):
        assert v.is_total_silence(rms, silence_pct) is expected
