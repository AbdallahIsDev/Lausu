"""Guard the non-increasing comment-density ratchet.

The gate compares per-directory comment ratios against a recorded baseline
and fails only when a ratio RISES (C-COMMENT-1). Missing or malformed
baseline data fails closed so a broken floor can never become a silent pass.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_METRIC = _SCRIPTS / "comment_ratio_metrics.py"
_metric_spec = importlib.util.spec_from_file_location("comment_ratio_metrics", _METRIC)
assert _metric_spec and _metric_spec.loader
sys.modules["comment_ratio_metrics"] = importlib.util.module_from_spec(_metric_spec)
_metric_spec.loader.exec_module(sys.modules["comment_ratio_metrics"])

_SCRIPT = _SCRIPTS / "comment_ratio_ratchet_check.py"
_spec = importlib.util.spec_from_file_location("comment_ratio_ratchet_check", _SCRIPT)
assert _spec and _spec.loader
ratchet = importlib.util.module_from_spec(_spec)
sys.modules["comment_ratio_ratchet_check"] = ratchet
_spec.loader.exec_module(ratchet)


class TestCompareRatios:
    def test_equal_ratio_passes(self):
        assert ratchet.compare_ratios({"src": 10.0}, {"src": 10.0}) == []

    def test_lower_ratio_passes(self):
        assert ratchet.compare_ratios({"src": 10.0}, {"src": 8.5}) == []

    def test_higher_ratio_is_a_regression(self):
        failures = ratchet.compare_ratios({"src": 10.0}, {"src": 10.1})
        assert len(failures) == 1
        assert "REGRESSION" in failures[0]
        assert "src" in failures[0]

    def test_tiny_float_noise_is_not_a_regression(self):
        assert ratchet.compare_ratios({"src": 10.0}, {"src": 10.0 + 1e-12}) == []

    def test_missing_baseline_key_fails_closed(self):
        failures = ratchet.compare_ratios({"server": 7.0}, {"server": 7.0, "new-dir": 5.0})
        assert any("new-dir" in f and "no baseline" in f for f in failures)

    def test_missing_current_dir_fails_closed(self):
        failures = ratchet.compare_ratios({"server": 7.0, "scripts": 9.0}, {"server": 7.0})
        assert any("scripts" in f and "missing" in f for f in failures)

    def test_non_finite_current_fails_closed(self):
        failures = ratchet.compare_ratios({"src": 10.0}, {"src": math.nan})
        assert any("invalid" in f for f in failures)


class TestBaselineValidation:
    def test_accepts_valid_baseline(self):
        assert ratchet.validate_baseline({"src": 10.0}) == []

    def test_rejects_non_numeric_ratio(self):
        assert any("numeric" in f for f in ratchet.validate_baseline({"src": "10%"}))

    def test_rejects_negative_ratio(self):
        assert any("range" in f for f in ratchet.validate_baseline({"src": -1.0}))

    def test_rejects_ratio_above_100(self):
        assert any("range" in f for f in ratchet.validate_baseline({"src": 101.0}))

    def test_rejects_nan(self):
        assert any("finite" in f for f in ratchet.validate_baseline({"src": math.nan}))


class TestBaselineCoverage:
    def test_recorded_baseline_covers_every_measured_dir(self):
        assert set(ratchet.BASELINE_RATIOS) == {label for label, _pats in ratchet.TOP_DIRS}
