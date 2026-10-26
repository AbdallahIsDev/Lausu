"""Invariant: a test's subprocess budget stays under its pytest-timeout budget.

Overrunning the latter makes pytest-timeout (``--timeout-method=thread``) kill
the whole xdist worker, which strands the run at ~99% instead of failing it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixtures.subprocess_budget import (
    DEFAULT_MARGIN_SEC,
    effective_item_timeout,
    subprocess_budget,
)


class _Options:
    def __init__(self, timeout: object) -> None:
        self.timeout = timeout


class _Config:
    def __init__(self, timeout: object) -> None:
        self.option = _Options(timeout)


class _Mark:
    def __init__(self, *args: object) -> None:
        self.args = args


class _Item:
    """Minimal stand-in for a pytest item (``config`` + marker lookup)."""

    def __init__(self, timeout: object = None, mark: _Mark | None = None) -> None:
        self.config = _Config(timeout)
        self._mark = mark

    def get_closest_marker(self, name: str) -> _Mark | None:
        assert name == "timeout"
        return self._mark


class TestClamp:
    def test_ci_timeout_shortens_a_long_subprocess_budget(self) -> None:
        assert subprocess_budget(_Item(timeout=120.0), 600) == 120.0 - DEFAULT_MARGIN_SEC

    def test_mark_override_raises_the_ceiling(self) -> None:
        item = _Item(timeout=120.0, mark=_Mark(600))
        assert effective_item_timeout(item) == 600.0
        assert subprocess_budget(item, 540) == 540.0

    def test_requested_budget_below_the_ceiling_is_untouched(self) -> None:
        assert subprocess_budget(_Item(timeout=120.0), 5) == 5.0

    def test_disabled_timeout_keeps_the_requested_budget(self) -> None:
        item = _Item()
        assert effective_item_timeout(item) is None
        assert subprocess_budget(item, 600) == 600.0

    def test_ceiling_never_drops_to_zero(self) -> None:
        assert subprocess_budget(_Item(timeout=10.0), 600) == 1.0

    def test_string_option_values_are_honoured(self) -> None:
        assert effective_item_timeout(_Item(timeout="120")) == 120.0

    @pytest.mark.parametrize("raw", ["", "abc", 0, -1, None, True, object()])
    def test_garbage_or_absent_values_mean_no_ceiling(self, raw: object) -> None:
        assert effective_item_timeout(_Item(timeout=raw)) is None
        assert subprocess_budget(_Item(timeout=raw), 600) == 600.0


class TestCallSites:
    """The sites whose literal budget used to exceed the suite timeout."""

    def test_rust_runtime_perms_test_clamps_its_cargo_budget(self) -> None:
        src = (Path(__file__).resolve().parent / "tauri" / "test_rust_log_file_perms.py").read_text(
            encoding="utf-8"
        )
        assert "timeout=600" not in src, "the cargo runtime test must clamp its budget"
        assert "subprocess_budget(request.node" in src

    def test_slim_import_probe_clamps_its_subprocess_budget(self) -> None:
        src = (Path(__file__).resolve().parent / "test_slim_no_asr_imports.py").read_text(encoding="utf-8")
        assert "timeout=300" not in src
        assert "subprocess_budget(request.node" in src

    def test_slow_manual_wrapper_raises_its_item_timeout_above_its_budget(self) -> None:
        src = (Path(__file__).resolve().parent / "test_manual_slow.py").read_text(encoding="utf-8")
        assert "timeout=180," in src
        assert "@pytest.mark.timeout(240)" in src
