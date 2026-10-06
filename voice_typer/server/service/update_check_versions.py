"""Dotted pack-version parsing and comparison.

Extracted from ``update_check.py``.
"""

from __future__ import annotations


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a dotted version string into a tuple of ints."""
    if not v:
        return (0,)
    # Strip a leading ``v`` (GitHub release tags commonly use ``v1.2.3``).
    s = v.strip().lstrip("vV")
    # Drop any ``-suffix`` (pre-release / build metadata).
    if "-" in s:
        s = s.split("-", 1)[0]
    parts: list[int] = []
    for segment in s.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            # Non-numeric segment (e.g. ``"1.2.x"``), treat as 0.
            parts.append(0)
    return tuple(parts) if parts else (0,)


def is_newer_version(remote: str, local: str) -> bool:
    """Return True if *remote* is strictly newer than *local*.

    Equal versions return False (no update needed). Shorter tuples pad
    with zeros: ``1.2`` == ``1.2.0``. Non-numeric segments are treated
    as 0 (defensive, a malformed version should NOT trigger a
    spurious update).

    Examples:
        >>> is_newer_version("1.2.3", "1.2.2")
        True
        >>> is_newer_version("1.2.3", "1.2.3")
        False
        >>> is_newer_version("v2.0.0", "1.9.9")
        True
        >>> is_newer_version("1.2", "1.2.0")
        False
    """
    r = _parse_version(remote)
    l_ = _parse_version(local)
    # Pad to equal length so ``(1, 2)`` compares equal to ``(1, 2, 0)``.
    n = max(len(r), len(l_))
    r_padded = r + (0,) * (n - len(r))
    l_padded = l_ + (0,) * (n - len(l_))
    return r_padded > l_padded
