"""Stress-test CLI for the local TTS engines.

This module exists so the two runtimes can be exercised and compared from a
terminal without the desktop UI: it renders the same text N times per engine
and reports wall time, audio duration, and real-time factor per engine.
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import tempfile
import time
from pathlib import Path

from voice_typer.server.tts.engines import Audio8Engine, MagpieEngine
from voice_typer.server.tts.service import TtsService
from voice_typer.server.tts.types import TtsError, TtsRequest, TtsResult

log = logging.getLogger("tts.cli")

DEFAULT_TEXT = "Welcome to Audio Eight. This sentence is rendered locally, with no Python runtime in the loop."


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voice-typer-tts", description=__doc__)
    parser.add_argument("--text", default=None, help="text to synthesize")
    parser.add_argument("--text-file", type=Path, default=None, help="file with one utterance per line")
    parser.add_argument("--runs", type=int, default=3, help="timed runs per engine (default 3)")
    parser.add_argument("--warmup", type=int, default=1, help="untimed runs per engine (default 1)")
    parser.add_argument("--engines", default="audio8,magpie", help="comma-separated engines to run")
    parser.add_argument("--workdir", type=Path, default=None, help="runtime config/log directory")
    parser.add_argument("--out", type=Path, default=None, help="WAV output directory")
    parser.add_argument("--json-out", type=Path, default=None, help="write the summary as JSON here")
    parser.add_argument("--audio8-bin", type=Path, default=None)
    parser.add_argument("--audio8-model", type=Path, default=None)
    parser.add_argument("--audio8-backend", default="vulkan")
    parser.add_argument("--magpie-bin", type=Path, default=None)
    parser.add_argument("--magpie-model", type=Path, default=None)
    parser.add_argument("--magpie-codec", type=Path, default=None)
    parser.add_argument("--magpie-tokenizer", type=Path, default=None)
    return parser


def _service_from_args(args: argparse.Namespace, workdir: Path) -> TtsService:
    audio8 = None
    if args.audio8_bin and args.audio8_model:
        audio8 = Audio8Engine(binary=args.audio8_bin, model=args.audio8_model, backend=args.audio8_backend)
    magpie = None
    if args.magpie_bin and args.magpie_model and args.magpie_codec and args.magpie_tokenizer:
        magpie = MagpieEngine(
            binary=args.magpie_bin,
            magpie_model=args.magpie_model,
            codec_model=args.magpie_codec,
            tokenizer_dir=args.magpie_tokenizer,
        )
    if audio8 is None and magpie is None:
        raise TtsError("no engine configured: pass --audio8-* and/or --magpie-* paths")
    return TtsService(workdir=workdir, audio8=audio8, magpie=magpie)


def _summarize(engine: str, results: list[TtsResult]) -> dict[str, object]:
    walls = [r.wall_s for r in results]
    audio = [r.duration_s for r in results]
    return {
        "engine": engine,
        "runs": len(results),
        "mean_wall_s": round(statistics.fmean(walls), 3),
        "p95_wall_s": round(sorted(walls)[max(0, int(len(walls) * 0.95) - 1)], 3),
        "min_wall_s": round(min(walls), 3),
        "max_wall_s": round(max(walls), 3),
        "audio_s": round(statistics.fmean(audio), 3),
        "realtime_factor": round(statistics.fmean(audio) / statistics.fmean(walls), 2),
        "sample_rate": results[0].sample_rate,
    }


def _run_engine(service: TtsService, engine: str, request: TtsRequest, out_dir: Path, args: argparse.Namespace):
    results: list[TtsResult] = []
    for index in range(args.warmup + args.runs):
        target = out_dir / f"{engine}-{index}.wav"
        result = service.synthesize(request, engine, target)
        if index >= args.warmup:
            results.append(result)
        print(f"  {engine} run {index + 1}: {result.wall_s:.2f}s wall, {result.duration_s:.2f}s audio")
    return _summarize(engine, results) if results else None


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    text = args.text or (args.text_file.read_text(encoding="utf-8").splitlines()[0] if args.text_file else DEFAULT_TEXT)
    request = TtsRequest(text=text)

    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="vt-tts-"))
    out_dir = args.out or workdir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    engines = [name.strip() for name in args.engines.split(",") if name.strip()]

    summaries: list[dict[str, object]] = []
    failures: list[tuple[str, str]] = []
    started = time.perf_counter()
    service = _service_from_args(args, workdir)
    try:
        for engine in engines:
            if engine not in service.configured_engines():
                print(f"{engine}: not configured, skipping")
                continue
            try:
                summary = _run_engine(service, engine, request, out_dir, args)
            except Exception as exc:
                log.exception("[TTS] %s failed", engine)
                failures.append((engine, str(exc)))
                continue
            if summary is not None:
                summaries.append(summary)
    finally:
        service.stop()

    print("\n=== summary ===")
    for summary in summaries:
        print(
            f"{summary['engine']:>8}: {summary['runs']} runs, mean {summary['mean_wall_s']}s "
            f"(p95 {summary['p95_wall_s']}s), {summary['audio_s']}s audio, "
            f"{summary['realtime_factor']}x realtime, {summary['sample_rate']} Hz"
        )
    for name, error in failures:
        print(f"{name:>8}: FAILED - {error}")

    payload = {
        "text": text,
        "engines": summaries,
        "failures": [{"engine": name, "error": error} for name, error in failures],
        "total_s": round(time.perf_counter() - started, 2),
    }
    if args.json_out:
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\njson -> {args.json_out}")
    return 0 if summaries and not failures else 1


if __name__ == "__main__":
    sys.exit(main())
