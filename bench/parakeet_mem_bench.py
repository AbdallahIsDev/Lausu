#!/usr/bin/env python
"""Measure Parakeet ORT CPU-arena retention (one arm per process).

The engine disables ORT's CPU memory arena so each decode's scratch is
freed instead of held at the high-water mark for the process lifetime.
This bench proves the difference on real weights: it loads the cached
Parakeet model, decodes the same clip twice, and reports RSS/private
bytes after load and after each decode.

Run each arm in its OWN process (fresh allocator state)::

    python bench/parakeet_mem_bench.py --arm arena-off
    python bench/parakeet_mem_bench.py --arm arena-on

Deliberately NOT named ``bench_*.py``: CI runs every ``bench/bench_*.py``
as a smoke benchmark on a host with no model weights.

``arena-on`` restores ORT's default arena for the comparison; the app
itself never runs that way.  ``--json <path>`` also writes the report.
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import sys
import time
import wave
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_CLIP = PROJECT_ROOT / "bench-out" / "speech.wav"
SAMPLE_RATE = 16000
DEFAULT_SECONDS = 45.0


def _memory_snapshot() -> dict[str, int | None]:
    """Current RSS / private bytes / peak working set, in MB."""
    try:
        import psutil
    except ImportError:
        return {"rss_mb": None, "private_mb": None, "peak_wset_mb": None}
    mi = psutil.Process().memory_info()
    mb = 1024 * 1024

    def _mb(value: Any) -> int | None:
        return int(value / mb) if value is not None else None

    return {
        "rss_mb": _mb(getattr(mi, "rss", None)),
        "private_mb": _mb(getattr(mi, "private", None)),
        "peak_wset_mb": _mb(getattr(mi, "peak_wset", None)),
    }


def _load_clip(path: Path, seconds: float) -> tuple[Any, float]:
    """Read a mono 16 kHz WAV and tile/crop it to ``seconds``."""
    import numpy as np

    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getframerate() != SAMPLE_RATE:
            raise SystemExit(
                f"expected mono {SAMPLE_RATE} Hz, got {handle.getnchannels()}ch @ {handle.getframerate()} Hz"
            )
        raw = handle.readframes(handle.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    target = int(seconds * SAMPLE_RATE)
    if samples.size == 0:
        raise SystemExit("clip is empty")
    reps = (target + samples.size - 1) // samples.size
    return np.tile(samples, reps)[:target], target / SAMPLE_RATE


def _set_arena(arena_on: bool) -> None:
    """Force the CPU arena on (baseline) for this process only."""
    if not arena_on:
        return
    from voice_typer.server.parakeet_engine import ParakeetEngine

    original = ParakeetEngine._make_sess_options

    def _arena_on(self: Any) -> Any:
        options = original(self)
        if options is not None:
            options.enable_cpu_mem_arena = True
        return options

    ParakeetEngine._make_sess_options = _arena_on  # type: ignore[method-assign]


def main() -> int:
    parser = argparse.ArgumentParser(description="Parakeet ORT arena retention bench")
    parser.add_argument("--arm", choices=("arena-off", "arena-on"), required=True)
    parser.add_argument("--clip", type=Path, default=DEFAULT_CLIP)
    parser.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    if not args.clip.is_file():
        raise SystemExit(f"clip not found: {args.clip}")

    _set_arena(args.arm == "arena-on")
    audio, audio_seconds = _load_clip(args.clip, args.seconds)

    from voice_typer.server.parakeet_engine import ParakeetEngine

    engine = ParakeetEngine(device="cpu", language="en")
    t0 = time.perf_counter()
    if not engine.load():
        raise SystemExit("model load failed")
    load_seconds = time.perf_counter() - t0
    gc.collect()
    after_load = _memory_snapshot()

    decodes: list[dict[str, Any]] = []
    texts: list[str] = []
    for index in range(2):
        started = time.perf_counter()
        text = engine.transcribe(audio)
        elapsed = time.perf_counter() - started
        texts.append(text)
        gc.collect()
        decodes.append(
            {
                "index": index + 1,
                "seconds": round(elapsed, 2),
                "text_chars": len(text),
                **_memory_snapshot(),
            }
        )

    report = {
        "arm": args.arm,
        "clip": str(args.clip),
        "audio_seconds": round(audio_seconds, 2),
        "model_load_seconds": round(load_seconds, 2),
        "after_load": after_load,
        "decodes": decodes,
        "retained_after_two_decodes_mb": (
            decodes[-1]["rss_mb"] - after_load["rss_mb"]
            if decodes[-1]["rss_mb"] is not None and after_load["rss_mb"] is not None
            else None
        ),
        "sample_text": texts[0][:120],
    }
    print(json.dumps(report, indent=2))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
