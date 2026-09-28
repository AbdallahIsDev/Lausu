#!/usr/bin/env python3
"""ML-import ratchet for the slim-core build (ADR-0024 Step 7, plan §11.2).

Counts the ASR/ML runtime imports that the SLIM-CORE sidecar must
eventually stop pulling in, and refuses to let that count grow. This is
the reversible measurement layer that lands BEFORE any Nuitka exclusion:
it makes the current gap visible and blocks regressions while the
dictation-engine cutover proceeds.

Scope (the two libraries the worker owns exclusively, plan §4.1 "Box B"):

* ``faster_whisper`` — Whisper ASR weights/runtime
* ``ctranslate2``  — the decoder backend behind ``faster_whisper``

Deliberately NOT counted (ADR-0024 Step-7 ownership decision,
2026-09-26): ``onnxruntime``. VAD (``vad.py``) and the GTCRN noise
filter (``audio_filters/gtcrn_backend.py``) run on the real-time audio
processing path in the slim core, so ``onnxruntime`` stays a declared
slim-core dependency (plan §5.3). Excluding it would break speech
detection, not slim the build. Counting it here would produce a gate
that can never go green and would push someone to "fix" it by breaking
VAD.

CI policy
---------
* ``total_count`` MUST NOT grow.
* Per-library counts in ``by_library`` MUST NOT grow.
* Counts MAY shrink — that is the whole point of the ratchet. When one
  shrinks, regenerate the baseline so the new lower number is the floor.

Usage
-----
Run from the project root::

    python scripts/slim_core_ml_ratchet_check.py            # CI mode
    python scripts/slim_core_ml_ratchet_check.py --regenerate

Exit code 0 if every count is at or below its baseline, 1 if any grew,
2 on a usage/baseline error.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tokenize
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO_ROOT / "slim-core-ml-baseline.json"

# The slim-core source closure. The worker package is EXCLUDED on
# purpose: it is Box B and is *supposed* to import all of this.
SLIM_CORE_ROOTS = ("voice_typer/server",)

#: Libraries owned exclusively by the runtime pack (worker).
COUNTED_LIBRARIES = ("faster_whisper", "ctranslate2")

#: Matches ``import faster_whisper`` / ``from faster_whisper import X``.
#: The optional leading BOM keeps Windows-written files (PowerShell
#: ``Set-Content -Encoding UTF8``) from hiding a real import.
_IMPORT_RE = re.compile(
    r"^[^\S\n]*\ufeff?[ \t]*(?:import|from)[ \t]+(" + "|".join(re.escape(lib) for lib in COUNTED_LIBRARIES) + r")\b",
    re.MULTILINE,
)


def _comment_spans(source: str) -> list[tuple[int, int]]:
    """Return ``(line_index, col)`` for every comment token, 0-based.

    Uses the stdlib tokenizer so a ``#`` inside a string literal is not
    mistaken for a comment, and so indented ``#``s are found. Falls back
    to a conservative line heuristic when the file does not tokenize
    (e.g. a syntax error under construction), where only lines whose
    first non-space character is ``#`` are treated as comments.
    """
    try:
        spans: list[tuple[int, int]] = []
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                spans.append((token.start[0] - 1, token.start[1]))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return [
            (idx, len(line) - len(line.lstrip()))
            for idx, line in enumerate(source.splitlines())
            if line.lstrip().startswith("#")
        ]
    return spans


def _strip_noise(source: str) -> str:
    """Blank out comment TEXT (not whole lines) so imports stay visible.

    Only the comment characters are replaced with spaces, so a real import
    on a line that also carries a trailing comment still counts, and the
    line count is preserved exactly. That line-count preservation is what
    lets a match offset in the stripped text map to the import's true
    line in the original file.
    """
    lines = source.splitlines()
    for line_idx, col in _comment_spans(source):
        if 0 <= line_idx < len(lines):
            line = lines[line_idx]
            lines[line_idx] = line[:col] + " " * (len(line) - col)
    return "\n".join(lines)


def scan(roots: tuple[str, ...] = SLIM_CORE_ROOTS) -> list[dict[str, Any]]:
    """Return one record per counted import site under ``roots``."""
    hits: list[dict[str, Any]] = []
    for root in roots:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Line numbers MUST be counted against the SAME text the regex
            # matched. Blanking (not deleting) comment lines keeps the two
            # line-for-line aligned, so the stripped offset yields the
            # import's true line in the original file.
            stripped = _strip_noise(source)
            for match in _IMPORT_RE.finditer(stripped):
                lineno = stripped[: match.start()].count("\n") + 1
                hits.append(
                    {
                        "library": match.group(1),
                        "file": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                        "line": lineno,
                    }
                )
    return hits


def summarize(hits: list[dict[str, Any]]) -> dict[str, Any]:
    by_library = Counter(h["library"] for h in hits)
    return {
        "total_count": len(hits),
        "by_library": {lib: by_library.get(lib, 0) for lib in COUNTED_LIBRARIES},
        "sites": [f"{h['file']}:{h['line']}" for h in hits],
    }


def _load_baseline() -> dict[str, Any]:
    if not BASELINE_PATH.is_file():
        print(f"ERROR: baseline missing: {BASELINE_PATH}", file=sys.stderr)
        print("Bootstrap it with --regenerate once the cutover plan is agreed.", file=sys.stderr)
        raise SystemExit(2)
    try:
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: baseline unreadable: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    if not isinstance(data.get("by_library"), dict) or not isinstance(data.get("total_count"), int):
        print("ERROR: baseline is malformed (needs total_count + by_library).", file=sys.stderr)
        raise SystemExit(2)
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Slim-core ML-import ratchet (ADR-0024 Step 7).")
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="rewrite the baseline to the current counts (refuses to grow without --force)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow --regenerate to raise the floor (deliberate scope change only)",
    )
    args = parser.parse_args(argv)

    current = summarize(scan())

    if args.regenerate:
        baseline = _load_baseline() if BASELINE_PATH.is_file() else None
        if baseline is not None and not args.force:
            grew = current["total_count"] > baseline["total_count"]
            for lib in COUNTED_LIBRARIES:
                grew = grew or current["by_library"][lib] > baseline["by_library"].get(lib, 0)
            if grew:
                print("REFUSING to regenerate: the new total is HIGHER than the baseline.", file=sys.stderr)
                print(f"  baseline total={baseline['total_count']} current total={current['total_count']}")
                print("That is a regression, not a ratchet. Revert the new imports.", file=sys.stderr)
                return 1
        BASELINE_PATH.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        print(f"Baseline regenerated: total={current['total_count']} {current['by_library']}")
        return 0

    baseline = _load_baseline()
    failures: list[str] = []
    if current["total_count"] > baseline["total_count"]:
        failures.append(f"total {current['total_count']} > baseline {baseline['total_count']}")
    for lib in COUNTED_LIBRARIES:
        now = current["by_library"][lib]
        was = baseline["by_library"].get(lib, 0)
        if now > was:
            failures.append(f"{lib} {now} > baseline {was}")

    if failures:
        print("SLIM-CORE ML RATCHET: FAILED", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        print("New ASR-library imports must not be added to the slim core.", file=sys.stderr)
        print("  (onnxruntime is intentionally NOT counted: VAD/gtcrn stay in slim core.)", file=sys.stderr)
        return 1

    print(
        f"SLIM-CORE ML RATCHET: ok "
        f"(total={current['total_count']} <= {baseline['total_count']}, {current['by_library']})"
    )
    if current["total_count"] < baseline["total_count"]:
        print("  count shrank — consider regenerating the baseline to lock in the win")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
