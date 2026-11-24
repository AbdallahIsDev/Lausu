#!/usr/bin/env python
"""Opt-in benchmark for the LOCAL ADR-0030 text translator.

NO DOWNLOADS. This script refuses to run unless an already-installed GGUF and
an already-installed llama-server are on disk. It uses the real
``TranslationService`` against loopback, so the measured path is production's.

Measures: cold runtime start, paragraph latency, per-chunk/sentence latency,
tokens/s from the response's own counters, and process memory. All numbers are
UNVERIFIED until a local agent runs this on the owner's machine.

Usage:
    .venv/Scripts/python.exe bench/bench_translation.py \
        --model-path "<HF cache>/Index-Translate-2B.Q4_K_M.gguf" \
        --runtime-path "<install dir>/llama-server.exe" --iterations 10 --json
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Bench dir is on sys.path above; importlib keeps this resolvable at runtime
# without adding a package marker to a directory owned by other benchmarks.
_bench_common = importlib.import_module("bench_transcription")  # noqa: E402
_peak_rss_mb = _bench_common._peak_rss_mb
_try_psutil = _bench_common._try_psutil

from voice_typer.server.translation import service as translation_service  # noqa: E402
from voice_typer.server.translation.chunking import bounded_chunks  # noqa: E402

DEFAULT_TEXT = (
    "الملف اللي بعتهولي امبارح مش بيفتح. "
    "جربت أفتحه من تاني على الكمبيوتر التاني وبرضه ظهرت رسالة خطأ. "
    "المهم ان المرسلة وصلت تماما، بس محتاج حد يراجع الرابط ويقولي اعمل ايه بعد كده."
)


class _ReplayResponse:
    """Replay a captured loopback body to the production urlopen caller."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _ReplayResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _recording_urlopen(original: Any, records: list[dict[str, Any]]) -> Any:
    def _wrapped(request: Any, timeout: float) -> _ReplayResponse:
        with original(request, timeout=timeout) as response:
            body = response.read()
        records.append(json.loads(body.decode("utf-8")))
        return _ReplayResponse(body)

    return _wrapped


def _config(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        translation_enabled=True,
        translation_model="index-translate-2b-q4-k-m",
        translation_model_path=args.model_path or os.environ.get("LAUSU_TRANSLATION_MODEL", ""),
        translation_runtime_path=args.runtime_path or os.environ.get("LAUSU_TRANSLATION_RUNTIME", ""),
        translation_gpu_enabled=not args.cpu,
        translation_glossary="",
        language=args.source_language,
    )


def _check_assets(config: SimpleNamespace) -> None:
    """Fail before any subprocess spawn; never try to fetch a missing asset."""
    from voice_typer.server.translation import paths as tp
    from voice_typer.server.translation.catalogue import resolve_spec

    for field, label in (("translation_model_path", "GGUF"), ("translation_runtime_path", "llama-server")):
        explicit = str(getattr(config, field, "") or "")
        if explicit and not Path(explicit).expanduser().exists():
            raise SystemExit(f"Explicit {label} path does not exist: {explicit}. This bench never downloads.")

    spec = resolve_spec(str(config.translation_model))
    if tp.resolve_model_path(spec, config) is None:
        raise SystemExit(
            "Translation GGUF not found. Download it yourself with the consented app flow, "
            f"then pass --model-path or set {tp.MODEL_ENV}. This bench never downloads."
        )
    if tp.resolve_runtime_path(config) is None:
        raise SystemExit(
            "llama-server not found. Install the bundled runtime, then pass --runtime-path "
            f"or set {tp.RUNTIME_ENV}. This bench never downloads."
        )


def _token_counts(payload: dict[str, Any]) -> tuple[int, float | None]:
    usage = payload.get("usage") or {}
    timings = payload.get("timings") or {}
    count = int(usage.get("completion_tokens") or timings.get("predicted_n") or 0)
    predicted_ms = timings.get("predicted_ms")
    return count, float(predicted_ms) if isinstance(predicted_ms, (int, float)) else None


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * fraction))
    return round(ordered[index], 3)


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "median_ms": round(statistics.median(values), 3),
        "p90_ms": _percentile(values, 0.9),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = _config(args)
    _check_assets(config)
    text = args.text or (Path(args.text_file).read_text(encoding="utf-8") if args.text_file else DEFAULT_TEXT)
    chunks = bounded_chunks(text, max_chars=args.max_chars)

    proc = _try_psutil()
    records: list[dict[str, Any]] = []
    original_urlopen = translation_service.urlopen
    translation_service.urlopen = _recording_urlopen(original_urlopen, records)
    translation_service.shutdown()
    try:
        memory_before = _peak_rss_mb(proc)
        started = time.perf_counter()
        service = translation_service.get_service(config)
        service.ensure_runtime()
        cold_start_s = time.perf_counter() - started
        memory_after_load = _peak_rss_mb(proc)

        for _ in range(args.warmup):
            service.translate(text, args.target_language)

        paragraph: list[float] = []
        wall_tokens = 0
        decode_tokens = 0
        decode_ms = 0.0
        for _ in range(args.iterations):
            before = time.perf_counter()
            service.translate(text, args.target_language)
            paragraph.append((time.perf_counter() - before) * 1000)
            payload = records[-1]
            count, predicted_ms = _token_counts(payload)
            wall_tokens += count
            if predicted_ms is not None:
                decode_tokens += count
                decode_ms += predicted_ms

        if len(records) < args.warmup + args.iterations:
            raise SystemExit("No model request was made. Use different source/target languages.")

        sentence: list[float] = []
        for chunk in chunks:
            before = time.perf_counter()
            service.translate(chunk, args.target_language)
            sentence.append((time.perf_counter() - before) * 1000)

        batch_before = time.perf_counter()
        service.translate_batch(chunks, args.target_language)
        batch_ms = (time.perf_counter() - batch_before) * 1000
        memory_after = _peak_rss_mb(proc)
    finally:
        translation_service.urlopen = original_urlopen
        translation_service.shutdown()

    wall_seconds = sum(paragraph) / 1000 if paragraph else 0.0
    return {
        "cold_start_s": round(cold_start_s, 3),
        "paragraph_latency_ms": _summary(paragraph),
        "sentence_latency_ms": _summary(sentence),
        "batch_total_ms": round(batch_ms, 3),
        "tokens_per_second_wall": round(wall_tokens / wall_seconds, 2) if wall_seconds else None,
        "tokens_per_second_decode": round(decode_tokens * 1000 / decode_ms, 2) if decode_ms else None,
        "memory_mb": {
            "before": memory_before,
            "after_load": memory_after_load,
            "after_runs": memory_after,
        },
        "sample": {
            "source_language": args.source_language,
            "target_language": args.target_language,
            "characters": len(text),
            "chunks": len(chunks),
        },
        "status": "LOCAL-RUN-REQUIRED",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", default="", help="already-downloaded GGUF path (no downloads)")
    parser.add_argument("--runtime-path", default="", help="already-installed llama-server path")
    parser.add_argument("--source-language", default="ar")
    parser.add_argument("--target-language", default="en")
    parser.add_argument("--text", default="", help="inline source text")
    parser.add_argument("--text-file", default="", help="UTF-8 file with source text")
    parser.add_argument("--max-chars", type=int, default=240, help="bounded sentence chunk size")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--cpu", action="store_true", help="force -ngl 0 instead of Vulkan")
    parser.add_argument("--json", action="store_true", help="emit only machine-readable JSON")
    args = parser.parse_args(argv)
    if args.iterations < 1 or args.warmup < 0 or args.max_chars < 1:
        parser.error("iterations/max-chars must be positive and warmup non-negative")
    if args.text and args.text_file:
        parser.error("use either --text or --text-file")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run(args)
    print(json.dumps(result, indent=2))
    if not args.json:
        print("\nAll figures are LOCAL-RUN-REQUIRED until measured on the owner's machine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
