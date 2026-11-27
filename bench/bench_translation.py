#!/usr/bin/env python
"""Opt-in benchmark for the LOCAL ADR-0030 text translator.

NO DOWNLOADS. This script refuses to run unless an already-installed GGUF and
an already-installed llama-server are on disk. Paths come from the same
resolvers the app uses. Production ``TranslationService`` makes every request;
only the POST body's ``cache_prompt`` flag is rewritten for the A/B comparison.

Measures: cold start to first response, whole-text and per-sentence latency,
tokens/s, peak RSS, cache_prompt ON/OFF speed and output stability, and an
ASR-like CPU/GPU load simulation (explicitly NOT a dictation).

Usage:
    .venv/Scripts/python.exe bench/bench_translation.py --iterations 10 --json
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent
SAMPLES_DIR = BENCH_DIR / "translation_samples"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BENCH_DIR))

from translation_load import make_load  # noqa: E402
from translation_report import CACHE_PROMPT_EXPLANATION, make_diff, write_comparison  # noqa: E402

_bench_common = importlib.import_module("bench_transcription")  # noqa: E402
_peak_rss_mb = _bench_common._peak_rss_mb
_try_psutil = _bench_common._try_psutil

from voice_typer.server.translation import (  # noqa: E402
    paths as translation_paths,
    service as translation_service,
)
from voice_typer.server.translation.catalogue import resolve_spec  # noqa: E402
from voice_typer.server.translation.chunking import _SENTENCE_SPLIT, bounded_chunks  # noqa: E402


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


def _response_content(payload: dict[str, Any]) -> str:
    try:
        value = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""
    return value.strip() if isinstance(value, str) else ""


def _urlopen_factory(cache_prompt: bool | None, records: list[dict[str, Any]]) -> Any:
    """Wrap loopback POSTs; leave health-check GETs untouched."""
    original = translation_service.urlopen

    def _wrapped(request: Any, timeout: float) -> Any:
        body = bytes(getattr(request, "data", None) or b"")
        if not body:
            return original(request, timeout=timeout)
        payload = json.loads(body.decode("utf-8"))
        if cache_prompt is not None:
            payload["cache_prompt"] = cache_prompt
            request = translation_service.Request(
                request.full_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        with original(request, timeout=timeout) as response:
            raw = response.read()
        decoded = json.loads(raw.decode("utf-8"))
        records.append(
            {
                "cache_prompt": payload.get("cache_prompt"),
                "content": _response_content(decoded),
                "usage": decoded.get("usage") or {},
                "timings": decoded.get("timings") or {},
            }
        )
        return _ReplayResponse(raw)

    return _wrapped


def _config(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        translation_enabled=True,
        translation_model="index-translate-2b-q4-k-m",
        translation_model_path=args.model_path or "",
        translation_runtime_path=args.runtime_path or "",
        translation_gpu_enabled=not args.cpu,
        translation_glossary="",
        language=args.source_language,
    )


def _check_assets(config: SimpleNamespace) -> dict[str, str]:
    """Resolve through app code; never fetch a missing asset."""
    spec = resolve_spec(str(config.translation_model))
    for field, label in (("translation_model_path", "GGUF"), ("translation_runtime_path", "llama-server")):
        explicit = str(getattr(config, field, "") or "")
        if explicit and not Path(explicit).expanduser().exists():
            raise SystemExit(f"Explicit {label} path does not exist: {explicit}. This bench never downloads.")

    model = translation_paths.resolve_model_path(spec, config)
    runtime = translation_paths.resolve_runtime_path(config)
    if model is None or runtime is None:
        missing = []
        if model is None:
            missing.append(
                f"GGUF {spec.filename} ({spec.size_gb} GB) from {spec.repo_id}. "
                "In the app open Models -> Text translation and consent to the model download."
            )
        if runtime is None:
            missing.append(
                f"{translation_paths.RUNTIME_BASENAME} bundled by the installer into "
                "<config directory>/translation (reinstall or repair the app to restore it)."
            )
        command = ".venv/Scripts/python.exe bench/bench_translation.py --iterations 10 --json"
        raise SystemExit(
            "Missing translation assets; nothing was downloaded.\n"
            + "\n".join(f"  - {item}" for item in missing)
            + f"\nSet {translation_paths.MODEL_ENV} and {translation_paths.RUNTIME_ENV} to files already on disk.\n"
            + f"Re-run: {command}"
        )
    return {
        "model": str(model),
        "runtime": str(runtime),
        "model_id": spec.id,
        "model_size_bytes": str(spec.size_bytes),
    }


def _load_text(args: argparse.Namespace) -> tuple[str, str]:
    if args.text:
        return args.text.strip(), "<inline>"
    raw = Path(args.text_file).expanduser() if args.text_file else SAMPLES_DIR / "ar_long.txt"
    if not raw.is_file():
        raise SystemExit(f"Sample text file not found: {raw}. Use --list-samples to see bundled samples.")
    return raw.read_text(encoding="utf-8").strip(), str(raw)


def _token_counts(record: dict[str, Any]) -> tuple[int, float | None]:
    usage = record["usage"]
    timings = record["timings"]
    count = int(usage.get("completion_tokens") or timings.get("predicted_n") or 0)
    predicted_ms = timings.get("predicted_ms")
    if isinstance(predicted_ms, bool) or not isinstance(predicted_ms, (int, float)):
        return count, None
    return count, float(predicted_ms)


def _token_stats(records: list[dict[str, Any]]) -> dict[str, float | None]:
    total = 0
    decode_tokens = 0
    decode_ms = 0.0
    for record in records:
        count, predicted_ms = _token_counts(record)
        total += count
        if predicted_ms is not None:
            decode_tokens += count
            decode_ms += predicted_ms
    return {"tokens": total, "decode_tokens": decode_tokens, "decode_ms": round(decode_ms, 3)}


def _summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"median_ms": 0.0, "p90_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0}
    ordered = sorted(values)
    return {
        "median_ms": round(statistics.median(values), 3),
        "p90_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))], 3),
        "min_ms": round(ordered[0], 3),
        "max_ms": round(ordered[-1], 3),
    }


def _child_rss_mb(proc: Any) -> int | None:
    if proc is None:
        return None
    try:
        children = [child for child in proc.children(recursive=True) if "llama" in child.name().lower()]
        if children:
            return max(int(child.memory_info().rss / (1024 * 1024)) for child in children)
    except Exception:
        return None
    return None


def _timed_translate(service: Any, text: str, target: str) -> tuple[str, float]:
    started = time.perf_counter()
    output = service.translate(text, target)
    return output, round((time.perf_counter() - started) * 1000, 3)


def join_chunk_outputs(chunks: list[str], outputs: list[str]) -> str:
    """Join translated chunks with the exact whitespace the source had between them.

    ``bounded_chunks`` preserves every source character, so the separator lives at
    the tail of the preceding chunk and the head of the following one. The model
    strips its responses, so re-inserting that separator is the only way to keep
    a space (or to avoid inventing one for scripts that do not use spaces).
    """
    if len(chunks) != len(outputs):
        raise ValueError("chunk and output counts differ")
    if not outputs:
        return ""
    parts = [outputs[0].strip()]
    for index, output in enumerate(outputs[1:], start=1):
        tail = re.search(r"\s*$", chunks[index - 1]).group(0)
        head = re.search(r"^\s*", chunks[index]).group(0)
        parts.append(tail + head)
        parts.append(output.strip())
    return "".join(parts)


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = _config(args)
    assets = _check_assets(config)
    text, sample_file = _load_text(args)
    chunks = bounded_chunks(text, args.max_chars)
    sentences = [part for part in _SENTENCE_SPLIT.split(text) if part.strip()]
    if not chunks or not sentences:
        raise SystemExit("Sample text has no sentences to benchmark.")

    records: list[dict[str, Any]] = []
    proc = _try_psutil()
    original_urlopen = translation_service.urlopen
    translation_service.urlopen = _urlopen_factory(None, records)
    translation_service.shutdown()
    load = None
    try:
        memory_before = _peak_rss_mb(proc)
        launch_started = time.perf_counter()
        service = translation_service.get_service(config)
        service.ensure_runtime()
        runtime_ready_s = round(time.perf_counter() - launch_started, 3)
        memory_after_load = _peak_rss_mb(proc)
        child_after_load = _child_rss_mb(proc)

        cold_output, first_response_ms = _timed_translate(service, text, args.target_language)
        launch_to_first_response_s = round(time.perf_counter() - launch_started, 3)
        for _ in range(args.warmup):
            service.translate(text, args.target_language)

        record_start = len(records)
        paragraph: list[float] = []
        whole_outputs: list[str] = []
        for _ in range(args.iterations):
            output, elapsed = _timed_translate(service, text, args.target_language)
            paragraph.append(elapsed)
            whole_outputs.append(output)
        paragraph_records = records[record_start:]

        chunk_details: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks):
            output, elapsed = _timed_translate(service, chunk, args.target_language)
            chunk_details.append(
                {
                    "index": index,
                    "characters": len(chunk),
                    "latency_ms": elapsed,
                    "source": chunk,
                    "output": output,
                }
            )

        sentence_details: list[dict[str, Any]] = []
        for index, sentence in enumerate(sentences):
            output, elapsed = _timed_translate(service, sentence, args.target_language)
            sentence_details.append(
                {
                    "index": index,
                    "characters": len(sentence),
                    "latency_ms": elapsed,
                    "source": sentence,
                    "output": output,
                }
            )

        batch_started = time.perf_counter()
        service.translate_batch(chunks, args.target_language)
        batch_ms = round((time.perf_counter() - batch_started) * 1000, 3)

        cache_results: dict[str, Any] = {}
        for flag, name in ((False, "off"), (True, "on")):
            translation_service.urlopen = _urlopen_factory(flag, records)
            outputs: list[str] = []
            timings: list[float] = []
            for _ in range(2):
                output, elapsed = _timed_translate(service, text, args.target_language)
                outputs.append(output)
                timings.append(elapsed)
            cache_results[name] = {
                "runs_ms": timings,
                "outputs": outputs,
                "identical": outputs[0] == outputs[1],
            }
        translation_service.urlopen = _urlopen_factory(None, records)
        cache_results["on_vs_off_identical"] = cache_results["on"]["outputs"][-1] == cache_results["off"]["outputs"][-1]
        cache_results["diff"] = make_diff(
            cache_results["off"]["outputs"][-1],
            cache_results["on"]["outputs"][-1],
            before_name="cache_prompt OFF",
            after_name="cache_prompt ON",
        )

        load = make_load(args.load_kind, args.load_workers)
        simulation: dict[str, Any] = {
            "label": "SIMULATION — ASR-like background load, not a real dictation",
            "kind": args.load_kind,
            "workers": args.load_workers if args.load_kind == "cpu" else 1,
            "per_chunk": [],
        }
        if load is not None:
            load.start()
        try:
            for detail in chunk_details:
                output, elapsed = _timed_translate(service, detail["source"], args.target_language)
                baseline = detail["latency_ms"]
                simulation["per_chunk"].append(
                    {
                        "index": detail["index"],
                        "baseline_ms": baseline,
                        "loaded_ms": elapsed,
                        "slowdown": round(elapsed / baseline, 2) if baseline else None,
                        "output": output,
                    }
                )
        finally:
            if load is not None:
                load.stop()

        memory_after = _peak_rss_mb(proc)
        child_after = _child_rss_mb(proc)
    finally:
        if load is not None:
            load.stop()
        translation_service.urlopen = original_urlopen
        translation_service.shutdown()

    if not paragraph_records:
        raise SystemExit("No model request was made. Use a different source/target language.")

    token_stats = _token_stats(paragraph_records)
    wall_seconds = sum(paragraph) / 1000
    decode_ms = token_stats["decode_ms"] or 0.0
    whole_output = whole_outputs[-1]
    joined_chunks = join_chunk_outputs(chunks, [detail["output"] for detail in chunk_details])
    legacy_join = "".join(detail["output"] for detail in chunk_details)
    chunk_ms = [detail["latency_ms"] for detail in chunk_details]
    sentence_ms = [detail["latency_ms"] for detail in sentence_details]
    ratios = [row["slowdown"] for row in simulation["per_chunk"] if row["slowdown"] is not None]
    simulation["baseline_median_ms"] = _summary(chunk_ms)["median_ms"]
    simulation["loaded_median_ms"] = _summary([row["loaded_ms"] for row in simulation["per_chunk"]])["median_ms"]
    simulation["median_slowdown"] = round(statistics.median(ratios), 2) if ratios else None

    result: dict[str, Any] = {
        "status": "MEASURED" if paragraph_records else "UNVERIFIED",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "assets": {**assets, "gpu_enabled": not args.cpu},
        "sample": {
            "file": sample_file,
            "source_language": args.source_language,
            "target_language": args.target_language,
            "characters": len(text),
            "chunks": len(chunks),
            "sentences": len(sentences),
            "chunk_characters": [len(chunk) for chunk in chunks],
        },
        "cold_start": {
            "runtime_ready_s": runtime_ready_s,
            "first_response_ms": first_response_ms,
            "launch_to_first_response_s": launch_to_first_response_s,
            "note": "stream=False in production; time is to the first complete response, not first token",
        },
        "paragraph_latency_ms": _summary(paragraph),
        "sentence_latency_ms": _summary(sentence_ms),
        "sentence_details": sentence_details,
        "chunk_latency_ms": _summary(chunk_ms),
        "chunk_details": chunk_details,
        "batch_total_ms": batch_ms,
        "tokens_per_second": {
            "wall": round(token_stats["tokens"] / wall_seconds, 2) if wall_seconds else None,
            "decode": round(token_stats["decode_tokens"] * 1000 / decode_ms, 2) if decode_ms else None,
            "counts": token_stats,
        },
        "memory_mb": {
            "before": memory_before,
            "after_load": memory_after_load,
            "after_runs": memory_after,
            "bench_peak": _peak_rss_mb(proc),
            "runtime_child": {"after_load": child_after_load, "after_runs": child_after},
            "note": "bench numbers are peak RSS on Windows; runtime child numbers are sampled RSS",
        },
        "comparison": {
            "join_rule": "exact source whitespace between chunks; no invented space",
            "whole_output": whole_output,
            "chunk_joined_output": joined_chunks,
            "identical": whole_output == joined_chunks,
            "diff": make_diff(
                whole_output,
                joined_chunks,
                before_name="whole text",
                after_name="chunk joined (whitespace preserved)",
            ),
            "legacy_join_output": legacy_join,
            "legacy_join_label": "LEGACY (dropped inter-chunk whitespace — kept only as evidence)",
            "legacy_join_identical": whole_output == legacy_join,
        },
        "cache_prompt": {
            "explanation": CACHE_PROMPT_EXPLANATION,
            "production_value": False,
            **cache_results,
        },
        "load_simulation": simulation,
        "cold_first_output": cold_output,
    }
    output_dir = Path(args.output_dir).expanduser()
    result["comparison"]["diff_file"] = str(write_comparison(output_dir / "translation-compare.txt", result))
    result_path = output_dir / "translation-results.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["results_file"] = str(result_path)
    return result


def _print_human(result: dict[str, Any]) -> None:
    print(f"status: {result['status']}")
    print(
        f"cold: ready {result['cold_start']['runtime_ready_s']}s, first response "
        f"{result['cold_start']['first_response_ms']}ms, launch-to-response "
        f"{result['cold_start']['launch_to_first_response_s']}s"
    )
    print(f"whole text: {result['paragraph_latency_ms']}")
    print(f"per sentence: {result['sentence_latency_ms']}")
    print(f"per chunk: {result['chunk_latency_ms']}")
    print(f"tokens/s: wall={result['tokens_per_second']['wall']}, decode={result['tokens_per_second']['decode']}")
    print(f"memory MB: {result['memory_mb']}")
    print(f"whole vs chunks identical: {result['comparison']['identical']}")
    print(f"diff file: {result['comparison']['diff_file']}")
    print(f"cache_prompt OFF repeat identical: {result['cache_prompt']['off']['identical']}")
    print(f"cache_prompt ON repeat identical: {result['cache_prompt']['on']['identical']}")
    print(f"cache_prompt ON vs OFF identical: {result['cache_prompt']['on_vs_off_identical']}")
    print(CACHE_PROMPT_EXPLANATION)
    print(result["load_simulation"]["label"])
    print(f"load median slowdown: {result['load_simulation']['median_slowdown']}x")
    print(f"results file: {result['results_file']}")


def _self_test() -> int:
    from translation_load import CpuLoad

    sample = "The cache stores the prompt. A repeated request reuses it. The answer can vary."
    if "".join(bounded_chunks(sample, 32)) != sample:
        raise AssertionError("bounded_chunks changed the source text")
    spaced = ["first sentence. ", "second sentence."]
    if join_chunk_outputs(spaced, ["A", "B"]) != "A B":
        raise AssertionError("source whitespace between chunks was lost")
    unspaced = ["句一。", "句二。"]
    if join_chunk_outputs(unspaced, ["甲", "乙"]) != "甲乙":
        raise AssertionError("a space was invented for a no-space script")
    diff = make_diff("one\ntwo\n", "one\nthree\n", before_name="a", after_name="b")
    if "--- a" not in diff or "+++ b" not in diff:
        raise AssertionError("unified diff header missing")
    loader = CpuLoad(workers=1)
    loader.start()
    time.sleep(0.05)
    loader.stop()
    if loader.iterations < 1:
        raise AssertionError("CPU load worker did not run")
    fake = SimpleNamespace(translation_model="index-translate-2b-q4-k-m")
    fake.translation_model_path = "C:/definitely-missing-translation-model.gguf"
    fake.translation_runtime_path = ""
    try:
        _check_assets(fake)
    except SystemExit as exc:
        if "never downloads" not in str(exc):
            raise AssertionError("missing-asset message did not say 'never downloads'") from exc
    else:
        raise AssertionError("missing asset was accepted")
    print("self-test: OK (no model, no network)")
    return 0


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
    parser.add_argument("--output-dir", default=str(BENCH_DIR / "results"), help="where comparison files are written")
    parser.add_argument("--load-kind", choices=("cpu", "gpu", "none"), default="cpu")
    parser.add_argument("--load-workers", type=int, default=2)
    parser.add_argument("--check", action="store_true", help="resolve assets and exit without starting a model")
    parser.add_argument("--self-test", action="store_true", help="fake/no-model harness check")
    parser.add_argument("--list-samples", action="store_true", help="list bundled sample texts and exit")
    args = parser.parse_args(argv)
    if args.iterations < 1 or args.warmup < 0 or args.max_chars < 1 or args.load_workers < 1:
        parser.error("iterations/max-chars/load-workers must be positive and warmup non-negative")
    if args.text and args.text_file:
        parser.error("use either --text or --text-file")
    return args


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    args = parse_args(argv)
    if args.list_samples:
        for path in sorted(SAMPLES_DIR.glob("*.txt")):
            print(path)
        return 0
    if args.self_test:
        return _self_test()
    if args.check:
        print(json.dumps(_check_assets(_config(args)), indent=2))
        return 0
    result = run(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
