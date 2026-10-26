"""Keep a test's subprocess timeout below the pytest-timeout budget that governs it.

pytest-timeout runs here with ``--timeout-method=thread``, which kills the whole
xdist worker process when an item overruns. A subprocess timeout longer than
that budget therefore never gets to raise its own ``TimeoutExpired`` handling:
the worker dies first, xdist drops the dead worker's queued tests, and the run
idles at ~99% until the job-level cap cancels it.
"""

from __future__ import annotations

from typing import Any, Protocol

# Seconds reserved for the calling test after its subprocess returns (fixture
# setup, assertions, cleanup) so the skip/fail path can still run.
DEFAULT_MARGIN_SEC = 30.0


class _ItemLike(Protocol):
    """The slice of a pytest item this module needs."""

    config: Any

    def get_closest_marker(self, name: str) -> Any: ...


def effective_item_timeout(item: _ItemLike) -> float | None:
    """Seconds pytest-timeout allows this item, or ``None`` when it is disabled.

    A ``@pytest.mark.timeout(...)`` override wins over the ``--timeout`` CLI
    option, mirroring pytest-timeout's own precedence.
    """
    marker = item.get_closest_marker("timeout")
    if marker is not None and marker.args:
        marked = _as_positive_seconds(marker.args[0])
        if marked is not None:
            return marked
    return _as_positive_seconds(getattr(item.config.option, "timeout", None))


def subprocess_budget(
    item: _ItemLike,
    requested: float,
    *,
    margin: float = DEFAULT_MARGIN_SEC,
) -> float:
    """Cap ``requested`` so its timeout fires before pytest-timeout kills the worker."""
    suite_timeout = effective_item_timeout(item)
    if suite_timeout is None:
        return requested
    return min(requested, max(1.0, suite_timeout - margin))


def _as_positive_seconds(raw: object) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None
