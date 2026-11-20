#!/usr/bin/env python3
"""Non-increasing comment-density ratchet over the top-level code dirs.

Reuses ``scripts/comment_ratio_metrics.py`` as the single source of truth for
what counts as a comment and for each directory's ratio (C-COMMENT-1). The
baseline is a module constant so the gate needs no extra data file;
``--print-baseline`` prints a fresh dict to paste in after a real improvement.

Exit codes: 0 the gate holds, 1 a ratio rose, 2 baseline/input error.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Mapping

from comment_ratio_metrics import ROOT, TOP_DIRS, measure_tree

# Measured on win32 via `python scripts/comment_ratio_metrics.py --json`.
# The orchestrator records the same numbers in worklog.md; keep this in sync
# when a deliberate, reviewed improvement lowers a ratio.
BASELINE_RATIOS: dict[str, float] = {
    ".github/workflows": 17.526555,
    "scripts": 9.336333,
    "src-tauri/src": 24.001549,
    "tests": 3.829451,
    "voice_typer/client/src": 17.003734,
    "voice_typer/server": 7.084802,
}

# Absorb the 6-decimal baseline precision without admitting a real rise.
_EPSILON = 1e-5


def current_ratios() -> dict[str, float]:
    """Return ``ratio_of_total`` (%) for every directory in TOP_DIRS."""
    return {label: measure_tree(ROOT / label, pats)["ratio_of_total"] for label, pats in TOP_DIRS}


def _is_ratio(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= 100
    )


def validate_baseline(baseline: Mapping[str, object]) -> list[str]:
    """Return one message per malformed ratio; empty means usable."""
    errors: list[str] = []
    for label, value in sorted(baseline.items()):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{label}: baseline ratio must be numeric, got {value!r}")
        elif not math.isfinite(value):
            errors.append(f"{label}: baseline ratio must be finite, got {value!r}")
        elif not 0 <= value <= 100:
            errors.append(f"{label}: baseline ratio out of range 0-100, got {value!r}")
    return errors


def compare_ratios(baseline: Mapping[str, float], current: Mapping[str, float]) -> list[str]:
    """Return one message per regression or uncomparable directory."""
    failures: list[str] = []
    for label in sorted(set(baseline) | set(current)):
        if label not in baseline:
            failures.append(f"{label}: no baseline recorded, refusing to pass an untracked dir")
            continue
        if label not in current:
            failures.append(f"{label}: missing from current measurement")
            continue
        now = current[label]
        if not _is_ratio(now):
            failures.append(f"{label}: invalid current ratio {now!r}")
            continue
        base = baseline[label]
        if now > base + _EPSILON:
            failures.append(f"{label}: REGRESSION baseline {base:.2f}% -> current {now:.2f}%")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Non-increasing comment-density ratchet (C-COMMENT-1).")
    parser.add_argument(
        "--print-baseline",
        action="store_true",
        help="Print current ratios as a BASELINE_RATIOS dict to paste in after an improvement.",
    )
    args = parser.parse_args(argv)

    current = current_ratios()
    if args.print_baseline:
        print("BASELINE_RATIOS: dict[str, float] = {")
        for label in sorted(current):
            print(f'    "{label}": {current[label]:.6f},')
        print("}")
        return 0

    errors = validate_baseline(BASELINE_RATIOS)
    if errors:
        print("COMMENT RATIO RATCHET: ERROR (baseline unusable)", file=sys.stderr)
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        return 2

    failures = compare_ratios(BASELINE_RATIOS, current)
    print(f"{'directory':<28} {'baseline':>10} {'current':>10}  status")
    for label in sorted(set(BASELINE_RATIOS) | set(current)):
        base = BASELINE_RATIOS.get(label)
        now = current.get(label)
        status = "REGRESSION" if any(f.startswith(f"{label}:") for f in failures) else "ok"
        print(f"{label:<28} {base if base is not None else float('nan'):>10.2f} "
              f"{now if now is not None else float('nan'):>10.2f}  {status}")

    if failures:
        print("COMMENT RATIO RATCHET: FAILED", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        print("Shorten new comments or move essays to docs/code-notes/ (C-COMMENT-6).", file=sys.stderr)
        print("Never remove SEC-/RACE-/PERF-, C-* or workflow tags (C-COMMENT-7).", file=sys.stderr)
        return 1

    print("COMMENT RATIO RATCHET: ok (no directory got denser).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
