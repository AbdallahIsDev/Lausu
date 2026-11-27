#!/usr/bin/env python
"""Print a compact markdown table from the real bench result files.

Read-only: never starts a model and never writes result files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RESULTS = Path(__file__).resolve().parent / "results"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def translator_table() -> None:
    print("## Translator alone (same samples, real llama-server)")
    print(
        "| sample | lang->target | gpu | cold s | whole ms | chunk ms | sentence ms "
        "| tok/s decode | child RSS MB | join fixed | legacy |"
    )
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---|---|")
    for path in sorted(RESULTS.glob("b1-*/translation-results.json")):
        data = _load(path)
        name = path.parent.name.removeprefix("b1-")
        parts = name.rsplit("_", 1)
        cold = data["cold_start"]["runtime_ready_s"]
        whole = data["paragraph_latency_ms"]["median_ms"]
        chunk = data["chunk_latency_ms"]["median_ms"]
        sentence = data["sentence_latency_ms"]["median_ms"]
        tokens = data["tokens_per_second"]["decode"]
        rss = (data["memory_mb"]["runtime_child"] or {}).get("after_runs")
        comparison = data["comparison"]
        print(
            f"| {parts[0]} | {data['sample']['source_language']}->{data['sample']['target_language']} "
            f"| {'on' if data['assets']['gpu_enabled'] else 'off'} | {cold} | {whole} | {chunk} | "
            f"{sentence} | {tokens} | {rss} | {comparison['identical']} "
            f"| {comparison.get('legacy_join_identical', 'n/a')} |"
        )


def asr_table() -> None:
    path = RESULTS / "pipeline-translation-results.json"
    if not path.is_file():
        return
    data = _load(path)
    b2 = data.get("b2", {})
    if b2:
        print()
        print("## ASR alone (real 12 s windows, 5 s step, 3 s overlap)")
        print(
            "| duration | backend | median decode ms | median window s "
            "| missed deadlines | pacing overruns | RTF median |"
        )
        print("|---|---|---:|---:|---:|---:|---:|")
        for _key, row in b2.items():
            decode = row["window_decode_ms"]["median"] or 0
            window = row["window_seconds"]["median"] or 0
            rtf = round(window * 1000 / decode, 2) if decode else None
            print(
                f"| {row['audio_seconds']:.0f}s | {row['backend']} | {decode} | {window} "
                f"| {row['missed_realtime_deadlines']} | {row['pacing_overruns']} | {rtf} |"
            )
    b3 = data.get("b3", {}).get("runs", {})
    if b3:
        print()
        print("## Pipeline (ASR × translator × design)")
        print(
            "| case | wait after stop s | window decode ms | vs baseline | group latency ms "
            "| translator slowdown | revised groups | VRAM sampled MB |"
        )
        print("|---|---:|---:|---:|---:|---:|---:|---:|")
        for key, row in b3.items():
            vram = row["memory"].get("vram_mb_sampled", {}).get("median")
            print(
                f"| {key} | {row['wait_after_stop_s']} | {row['window_decode_ms']['median']} "
                f"| {row['window_slowdown_vs_baseline']} | {row['group_latency_ms']['median']} "
                f"| {row['translator_slowdown']} | {row['revised_groups_after_translation']} | {vram} |"
            )


if __name__ == "__main__":
    translator_table()
    asr_table()
