"""Readable output-comparison files for the translation benchmark."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

CACHE_PROMPT_EXPLANATION = (
    "cache_prompt ON lets llama-server keep the prompt prefix that never changes "
    "(the system instruction and the translation prompt shell) and skip reading it "
    "again on the next request. That usually makes repeated requests faster. It does "
    "not promise identical text: a cached prefix can take a slightly different "
    "floating-point path, so two runs of the same input can differ by a word or a "
    "space. The app ships cache_prompt OFF; this benchmark overrides only the HTTP "
    "request body to compare both settings without changing the app."
)


def make_diff(before: str, after: str, *, before_name: str, after_name: str) -> str:
    """Return a unified diff that always has a header, even for identical text."""
    lines = list(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=before_name,
            tofile=after_name,
        )
    )
    if not lines:
        return "(no differences)\n"
    return "".join(line if line.endswith("\n") else line + "\n" for line in lines)


def write_comparison(path: Path, result: dict[str, Any]) -> Path:
    """Write one plain-text file the owner can read without parsing JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = result["sample"]
    comparison = result["comparison"]
    cache = result["cache_prompt"]
    simulation = result["load_simulation"]
    chunks = result["chunk_details"]
    lines: list[str] = [
        "TRANSLATION BENCHMARK — OUTPUT COMPARISON",
        "=" * 60,
        f"generated: {result['generated_at']}",
        f"status: {result['status']}",
        f"sample: {sample['file']} ({sample['characters']} characters, "
        f"{sample['sentences']} sentences, {sample['chunks']} chunks)",
        f"source -> target: {sample['source_language']} -> {sample['target_language']}",
        f"model: {result['assets']['model']}",
        f"runtime: {result['assets']['runtime']}",
        f"translation GPU enabled: {result['assets']['gpu_enabled']}",
        "",
        "1. WHOLE TEXT vs PER-SENTENCE CHUNKS (same input)",
        "-" * 60,
        f"whole-text latency: {result['paragraph_latency_ms']['median_ms']} ms median, "
        f"{result['paragraph_latency_ms']['p90_ms']} ms p90",
        f"per-sentence latency: {result['sentence_latency_ms']['median_ms']} ms median, "
        f"{result['sentence_latency_ms']['p90_ms']} ms p90",
        f"per-chunk latency: {result['chunk_latency_ms']['median_ms']} ms median, "
        f"{result['chunk_latency_ms']['p90_ms']} ms p90",
        f"outputs identical: {comparison['identical']}",
        "",
        "[whole-text output]",
        comparison["whole_output"] or "(empty)",
        "",
        "[chunk-joined output]",
        comparison["chunk_joined_output"] or "(empty)",
        "",
        "[diff: whole-text -> chunk-joined]",
        comparison["diff"],
        "",
        "[per-sentence latency]",
    ]
    for sentence in result["sentence_details"]:
        lines.append(
            f"  sentence {sentence['index'] + 1} ({sentence['characters']} chars, {sentence['latency_ms']} ms)"
        )
    lines.append("[per-chunk outputs]")
    for chunk in chunks:
        lines.append(f"  chunk {chunk['index'] + 1} ({chunk['characters']} chars, {chunk['latency_ms']} ms)")
        lines.append(f"    source: {chunk['source']}")
        lines.append(f"    output: {chunk['output'] or '(empty)'}")
    lines.extend(
        [
            "",
            "2. cache_prompt ON vs OFF (same input, two runs each)",
            "-" * 60,
            CACHE_PROMPT_EXPLANATION,
            "",
        ]
    )
    for name in ("off", "on"):
        entry = cache[name]
        lines.append(
            f"cache_prompt={name.upper()}: runs {entry['runs_ms']} ms, two outputs identical: {entry['identical']}"
        )
        for index, output in enumerate(entry["outputs"], start=1):
            lines.append(f"  run {index}: {output or '(empty)'}")
    lines.extend(
        [
            f"ON vs OFF last output identical: {cache['on_vs_off_identical']}",
            "[diff: cache_prompt OFF -> ON]",
            cache["diff"],
            "",
            "3. ASR-LIKE LOAD SIMULATION — NOT REAL DICTATION",
            "-" * 60,
            f"load kind: {simulation['kind']} ({simulation['workers']} workers)",
            f"baseline chunk median: {simulation['baseline_median_ms']} ms",
            f"loaded chunk median: {simulation['loaded_median_ms']} ms",
            f"median slowdown: {simulation['median_slowdown']}x",
        ]
    )
    for row in simulation["per_chunk"]:
        lines.append(
            f"  chunk {row['index'] + 1}: {row['baseline_ms']} ms -> {row['loaded_ms']} ms ({row['slowdown']}x)"
        )
    lines.extend(
        [
            "",
            "4. COLD START AND MEMORY",
            "-" * 60,
            f"runtime launch to healthy: {result['cold_start']['runtime_ready_s']} s",
            f"first translated response: {result['cold_start']['first_response_ms']} ms",
            f"launch to first response: {result['cold_start']['launch_to_first_response_s']} s",
            f"peak RSS (bench process): {result['memory_mb']['bench_peak']} MB",
            f"runtime child RSS sampled: {result['memory_mb']['runtime_child']} MB (sampled, not peak)",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
