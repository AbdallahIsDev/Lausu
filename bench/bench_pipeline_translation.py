#!/usr/bin/env python
"""Measure ASR streaming windows against the local translator, bench-only.

Real assets only: the app's GGUF runner (transcribe.dll), the app's translation
service (llama-server), and a recorded 16 kHz WAV. No downloads, no product edits.

Usage:
    .venv/Scripts/python.exe bench/bench_pipeline_translation.py --self-test
    .venv/Scripts/python.exe bench/bench_pipeline_translation.py --mode b2
    .venv/Scripts/python.exe bench/bench_pipeline_translation.py --mode b3 --pacing real --durations 30
"""

from __future__ import annotations

import argparse
import base64
import json
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from pipeline_bench_common import (
    BENCH_DIR,
    DEFAULT_LIBRARY,
    DEFAULT_TRANSCRIBE_PACKAGE,
    DEFAULT_TRANSLATION_MODEL,
    DEFAULT_TRANSLATION_RUNTIME,
    DEFAULT_WAV,
    SAMPLE_RATE,
    AsrRunner,
    NativeAsrRunner,
    Sampler,
    Translator,
    join_chunk_outputs,
    load_wav_slice,
    require_existing,
    resolve_assets,
    summary,
    translate_bounded,
)
from translation_report import make_diff
from voice_typer.server.translation.chunking import _SENTENCE_SPLIT
from voice_typer.worker.streaming import SessionConfig, StreamingSession, Word, to_16k_array

GROUP_SECONDS = 8.0
CHUNK_SECONDS = 0.5
STEP_SECONDS = 5.0
SPOKEN_LANGUAGE = "en"
TARGET_LANGUAGE = "ar"


def _make_runner(args: Any, assets: dict[str, str]) -> Any:
    """App ctypes wrapper for reference, or the same DLL's Python binding with word times."""
    if args.runner == "app":
        return AsrRunner(assets["asr_model"], assets["transcribe_library"])
    return NativeAsrRunner(assets["asr_model"], assets["transcribe_library"], assets["transcribe_package"])


def _words_from_segments(result: Any, offset_seconds: float) -> list[Word]:
    """Prefer real word timestamps; fall back to real segment timings (app wrapper)."""
    words = getattr(result, "words", None)
    if words:
        return [
            Word(word.text.strip(), word.t0_ms / 1000 + offset_seconds, word.t1_ms / 1000 + offset_seconds)
            for word in words
            if word.text.strip()
        ]
    return [
        Word(segment.text.strip(), segment.start + offset_seconds, segment.end + offset_seconds)
        for segment in result.segments
        if segment.text.strip()
    ]


def _norm(text: str) -> str:
    return " ".join(text.split())


def _feed_session(
    session: StreamingSession,
    audio: Any,
    asr: AsrRunner,
    backend: str,
    *,
    pacing: str,
    on_window: Any = None,
) -> dict[str, Any]:
    """Feed real audio in 0.5 s pieces and decode each planned window."""
    decode_ms: list[float] = []
    window_seconds: list[float] = []
    missed_deadlines = 0
    pacing_overruns = 0
    windows: list[dict[str, Any]] = []
    total = len(audio)
    started = time.perf_counter()
    index = 0
    for start_sample in range(0, total, int(CHUNK_SECONDS * SAMPLE_RATE)):
        chunk = audio[start_sample : start_sample + int(CHUNK_SECONDS * SAMPLE_RATE)]
        session.append_chunk(index, base64.b64encode(chunk.tobytes()).decode("ascii"))
        index += 1
        if pacing == "real":
            due = started + (start_sample + len(chunk)) / SAMPLE_RATE
            delay = due - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                pacing_overruns += 1
        while True:
            planned = session.due_window()
            if planned is None:
                break
            start_seconds, end_seconds, _horizon = planned
            raw = session.window_bytes(start_seconds, end_seconds)
            slice_audio = to_16k_array(raw, SAMPLE_RATE)
            decode_started = time.perf_counter()
            committed_before = session.assembler.committed_text
            result = asr.transcribe(slice_audio, backend, language=SPOKEN_LANGUAGE)
            elapsed_ms = round((time.perf_counter() - decode_started) * 1000, 3)
            words = _words_from_segments(result, start_seconds)
            new_text, _new_words = session.commit_window(words, end_seconds)
            duration = round(end_seconds - start_seconds, 3)
            decode_ms.append(elapsed_ms)
            window_seconds.append(duration)
            if elapsed_ms > STEP_SECONDS * 1000:
                missed_deadlines += 1
            row = {
                "start_seconds": round(start_seconds, 3),
                "end_seconds": round(end_seconds, 3),
                "window_seconds": duration,
                "decode_ms": elapsed_ms,
                "realtime_factor": round(duration * 1000 / elapsed_ms, 2) if elapsed_ms else None,
                "new_committed_text": new_text,
                "segments": len(result.segments),
                "status": getattr(result, "status", 0),
            }
            windows.append(row)
            if on_window is not None:
                on_window(row, new_text, session.assembler.committed_text, committed_before)
    return {
        "windows": windows,
        "window_decode_ms": summary(decode_ms),
        "window_seconds": summary(window_seconds),
        "missed_realtime_deadlines": missed_deadlines,
        "pacing_overruns": pacing_overruns,
        "feed_wall_seconds": round(time.perf_counter() - started, 3),
        "chunks_fed": index,
    }


def _finalize_session(session: StreamingSession, asr: AsrRunner, backend: str) -> tuple[str, dict[str, Any]]:
    """Run the production finalize plan (batch or tail) and return final text."""
    kind, offset_seconds, raw = session.finalize_plan()
    started = time.perf_counter()
    result = asr.transcribe(to_16k_array(raw, SAMPLE_RATE), backend, language=SPOKEN_LANGUAGE)
    final = session.commit_tail(_words_from_segments(result, offset_seconds))
    return final, {
        "kind": kind,
        "offset_seconds": round(offset_seconds, 3),
        "decode_ms": round((time.perf_counter() - started) * 1000, 3),
        "audio_seconds": round(len(raw) / (SAMPLE_RATE * 4), 3),
    }


def run_b2(args: Any, assets: dict[str, str]) -> dict[str, Any]:
    """ASR alone: real windows, real decode times, CPU vs Vulkan."""
    asr = _make_runner(args, assets)
    results: dict[str, Any] = {}
    audio_cache: dict[int, Any] = {}
    for duration in args.durations:
        if duration not in audio_cache:
            audio_cache[duration] = load_wav_slice(Path(assets["wav"]), duration)
        audio, actual = audio_cache[duration]
        for backend in args.backends:
            session = StreamingSession(0, SessionConfig())
            with Sampler() as sampler:
                stats = _feed_session(session, audio, asr, backend, pacing=args.pacing)
                final, finalize = _finalize_session(session, asr, backend)
                memory = sampler.report()
            decode = stats["window_decode_ms"]["median"] or 0.0
            results[f"{duration}s_{backend}"] = {
                "audio_seconds": round(actual, 3),
                "backend": backend,
                "runner": args.runner,
                "model_load_s": asr.load_seconds.get(backend),
                "pacing": args.pacing,
                "streaming_config": {
                    "chunk_seconds": 12.0,
                    "step_seconds": 5.0,
                    "left_overlap_seconds": 3.0,
                    "right_guard_seconds": 1.5,
                    "source": "voice_typer/worker/streaming.py:71-79 (SessionConfig defaults)",
                },
                "finalize": finalize,
                "final_text_chars": len(final),
                "final_text": final,
                "decode_ms": stats["window_decode_ms"],
                "window_decode_ms": stats["window_decode_ms"],
                "window_seconds": stats["window_seconds"],
                "median_decode_ms": decode,
                "median_window_seconds": stats["window_seconds"]["median"],
                "deadline_seconds": STEP_SECONDS,
                "missed_realtime_deadlines": stats["missed_realtime_deadlines"],
                "pacing_overruns": stats["pacing_overruns"],
                "feed_wall_seconds": stats["feed_wall_seconds"],
                "windows": stats["windows"],
                "memory": memory,
                "status": "MEASURED",
            }
    return results


class _GroupTranslator:
    """Translate completed stable groups on a second thread, in order."""

    def __init__(self, translator: Translator) -> None:
        self.translator = translator
        self.jobs: queue.Queue[tuple[int, str] | None] = queue.Queue()
        self.done: list[dict[str, Any]] = []
        self._thread = threading.Thread(target=self._loop, name="bench-translate-groups", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while True:
            job = self.jobs.get()
            if job is None:
                self.jobs.task_done()
                return
            index, text = job
            started = time.perf_counter()
            output = self.translator.translate(text)
            self.done.append(
                {
                    "index": index,
                    "source": text,
                    "output": output,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    "finished_at": time.perf_counter(),
                }
            )
            self.jobs.task_done()

    def submit(self, index: int, text: str) -> None:
        self.jobs.put((index, text))

    def finish(self) -> list[dict[str, Any]]:
        self.jobs.join()
        self.jobs.put(None)
        self._thread.join(timeout=5)
        return sorted(self.done, key=lambda row: row["index"])


def _grouper() -> tuple[Any, Any]:
    """Return (offer, flush) for punctuation- or duration-bounded sentence groups."""
    state: dict[str, Any] = {"texts": [], "seconds": 0.0, "index": 0}

    def offer(text: str, duration_seconds: float) -> list[tuple[int, str]]:
        cleaned = _norm(text)
        if not cleaned:
            return []
        state["texts"].append(cleaned)
        state["seconds"] += duration_seconds
        ready = cleaned.endswith((".", "!", "?", "。", "！", "？")) or state["seconds"] >= GROUP_SECONDS
        if not ready:
            return []
        group = " ".join(state["texts"])
        job = (state["index"], group)
        state["index"] += 1
        state["texts"] = []
        state["seconds"] = 0.0
        return [job]

    def flush() -> list[tuple[int, str]]:
        if not state["texts"]:
            return []
        group = " ".join(state["texts"])
        job = (state["index"], group)
        state["index"] += 1
        state["texts"] = []
        state["seconds"] = 0.0
        return [job]

    return offer, flush


def run_b3(args: Any, assets: dict[str, str], baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    """Four combinations, two designs, three durations, translated groups."""
    translator = Translator(args, TARGET_LANGUAGE)
    cold_starts: dict[str, float] = {}
    for mode, gpu in (("gpu", True), ("cpu", False)):
        cold_starts[mode] = translator.start(gpu=gpu)
    translator.stop()

    asr = _make_runner(args, assets)
    audio_cache: dict[int, Any] = {}
    results: dict[str, Any] = {}
    for duration in args.durations:
        if duration not in audio_cache:
            audio_cache[duration] = load_wav_slice(Path(assets["wav"]), duration)
        audio, actual = audio_cache[duration]
        for backend in args.backends:
            for mode in args.translation_modes:
                for design in args.designs:
                    key = f"{duration}s_{backend}_translator-{mode}_{design}"
                    session = StreamingSession(0, SessionConfig())
                    offer, flush_groups = _grouper()
                    submitted: list[tuple[int, str]] = []
                    anchors: dict[int, str] = {}
                    revisions: list[dict[str, Any]] = []
                    worker: _GroupTranslator | None = None
                    selected = (
                        duration == args.durations[0]
                        and backend == args.backends[0]
                        and mode == args.translation_modes[0]
                        and design == "stream"
                    )
                    sentence_translations: list[dict[str, Any]] = []
                    translator.start(gpu=(mode == "gpu"))
                    if design == "stream":
                        worker = _GroupTranslator(translator)

                    def on_window(
                        row: dict[str, Any],
                        new_text: str,
                        committed: str,
                        previous_committed: str,
                        *,
                        worker: _GroupTranslator | None = worker,
                        offer: Any = offer,
                        submitted: list[tuple[int, str]] = submitted,
                        anchors: dict[int, str] = anchors,
                        revisions: list[dict[str, Any]] = revisions,
                    ) -> None:
                        if worker is None:
                            return
                        for job in offer(new_text, row["window_seconds"]):
                            submitted.append(job)
                            anchors[job[0]] = _norm(previous_committed)
                            worker.submit(*job)
                        current = _norm(committed)
                        for index, source in submitted:
                            if index not in anchors:
                                continue
                            anchor = anchors[index]
                            unchanged = current.startswith(anchor) and _norm(source) in current[len(anchor) :]
                            if not unchanged and not any(entry["group"] == index for entry in revisions):
                                revisions.append(
                                    {
                                        "group": index,
                                        "source": source,
                                        "committed_after": committed[-240:],
                                    }
                                )

                    with Sampler() as sampler:
                        stats = _feed_session(session, audio, asr, backend, pacing=args.pacing, on_window=on_window)
                        committed_before_finalize = session.assembler.committed_text
                        stop_marked = time.perf_counter()
                        final_asr, finalize = _finalize_session(session, asr, backend)
                        if design == "stream":
                            assert worker is not None
                            for job in flush_groups():
                                submitted.append(job)
                                worker.submit(*job)
                            if committed_before_finalize and final_asr.startswith(committed_before_finalize):
                                tail_text = final_asr[len(committed_before_finalize) :]
                            else:
                                tail_text = final_asr
                            for job in list(offer(tail_text, 0.0)) + list(flush_groups()):
                                submitted.append(job)
                                worker.submit(*job)
                            translated_groups = worker.finish()
                            delivered_at = time.perf_counter()
                            final_text = " ".join(row["output"] for row in translated_groups)
                            translation_seconds = round(delivered_at - stop_marked, 3)
                            group_latencies = [row["latency_ms"] for row in translated_groups]
                            control_latencies: list[float] = []
                            for _index, source in submitted:
                                started = time.perf_counter()
                                translator.translate(source)
                                control_latencies.append(round((time.perf_counter() - started) * 1000, 3))
                            if selected:
                                for sentence in (part.strip() for part in _SENTENCE_SPLIT.split(final_asr)):
                                    if not sentence:
                                        continue
                                    started = time.perf_counter()
                                    output = translator.translate(sentence)
                                    sentence_translations.append(
                                        {
                                            "source": sentence,
                                            "output": output,
                                            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                                        }
                                    )
                        else:
                            final_text, translation_seconds, bounded_count = translate_bounded(translator, final_asr)
                            delivered_at = time.perf_counter()
                            translated_groups = []
                            group_latencies = []
                            control_latencies = []
                        memory = sampler.report()
                    wait_after_stop = round(delivered_at - stop_marked, 3)
                    baseline_row = (baseline or {}).get(f"{duration}s_{backend}", {})
                    baseline_ms = baseline_row.get("median_decode_ms")
                    results[key] = {
                        "status": "MEASURED",
                        "audio_seconds": round(actual, 3),
                        "asr_backend": backend,
                        "asr_runner": args.runner,
                        "asr_model_load_s": asr.load_seconds.get(backend),
                        "translator_mode": mode,
                        "design": design,
                        "pacing": args.pacing,
                        "translator_cold_start_s": cold_starts[mode],
                        "wait_after_stop_s": wait_after_stop,
                        "translation_and_finalize_s": translation_seconds,
                        "finalize": finalize,
                        "asr_final_text": final_asr,
                        "final_translated_text": final_text,
                        "groups_submitted": len(submitted),
                        "group_sources": [source for _index, source in submitted],
                        "group_translations": translated_groups,
                        "group_latency_ms": summary(group_latencies),
                        "control_group_latency_ms": summary(control_latencies),
                        "translator_slowdown": (
                            round(summary(group_latencies)["median"] / summary(control_latencies)["median"], 2)
                            if group_latencies and control_latencies and summary(control_latencies)["median"]
                            else None
                        ),
                        "window_decode_ms": stats["window_decode_ms"],
                        "window_count": len(stats["windows"]),
                        "missed_realtime_deadlines": stats["missed_realtime_deadlines"],
                        "pacing_overruns": stats["pacing_overruns"],
                        "baseline_window_decode_ms": baseline_ms,
                        "window_slowdown_vs_baseline": (
                            round(stats["window_decode_ms"]["median"] / baseline_ms, 2)
                            if baseline_ms and stats["window_decode_ms"]["median"]
                            else None
                        ),
                        "revised_groups_after_translation": len(revisions),
                        "revision_examples": revisions[:3],
                        "sentence_translations": sentence_translations,
                        "memory": memory,
                    }
                    if design == "current":
                        results[key]["bounded_chunks"] = bounded_count
    translator.stop()
    return {"runs": results, "cold_starts": cold_starts}


def _write_quality(path: Path, b3: dict[str, Any]) -> None:
    """Write a human-readable quality comparison from real translations."""
    runs = b3.get("runs", {})
    stream_run = next((row for key, row in runs.items() if key.endswith("_stream")), None)
    current_run = next((row for key, row in runs.items() if key.endswith("_current")), None)
    lines = ["PIPELINE TRANSLATION — REAL OUTPUT COMPARISON", "=" * 60]
    if stream_run is None or current_run is None:
        lines.append("No paired stream/current runs were measured.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    asr_text = current_run["asr_final_text"]
    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(asr_text) if part.strip()]
    lines.extend(
        [
            "ASR final text (current design run):",
            asr_text,
            "",
            "Current design — one bounded translation after stop:",
            current_run["final_translated_text"] or "(empty)",
            "",
            "Streaming design — translated stable groups during recording:",
            stream_run["final_translated_text"] or "(empty)",
            "",
            "Group sources (stable text actually translated):",
        ]
    )
    for index, source in enumerate(current_run.get("group_sources", []), start=1):
        lines.append(f"  {index}. {source}")
    for key, row in runs.items():
        if key.endswith("_stream"):
            lines.extend(
                [
                    "",
                    f"Revision count [{key}]: {row['revised_groups_after_translation']} "
                    "translated groups changed afterwards",
                ]
            )
            for example in row["revision_examples"]:
                lines.append(f"  group {example['group']}: {example['source'][:120]}")
    lines.extend(
        [
            "",
            "[diff: current -> streaming output]",
            make_diff(
                current_run["final_translated_text"],
                stream_run["final_translated_text"],
                before_name="current (translate once at stop)",
                after_name="streaming (translate stable groups)",
            ),
            f"sentence count in ASR final text: {len(sentences)}",
            "",
            "Per-sentence translations from the streaming run's ASR final text (real extra pass):",
        ]
    )
    for row in stream_run.get("sentence_translations", []):
        lines.append(f"  source: {row['source']}")
        lines.append(f"  output: {row['output']} ({row['latency_ms']} ms)")
    path.write_text("\n".join(lines), encoding="utf-8")


def _self_test() -> int:
    join_a = join_chunk_outputs(["alpha ", "beta"], ["X", "Y"])
    join_b = join_chunk_outputs(["甲。", "乙。"], ["甲", "乙"])
    if join_a != "X Y" or join_b != "甲乙":
        raise AssertionError("chunk join invariant broken")
    session = StreamingSession(0, SessionConfig())
    if (
        session.config.chunk_seconds != 12.0
        or session.config.step_seconds != 5.0
        or session.config.left_overlap_seconds != 3.0
    ):
        raise AssertionError("streaming window config differs from production defaults")
    fake = type("Args", (), {})()
    fake.library = "C:/definitely-missing-transcribe.dll"
    fake.audio = "C:/definitely-missing.wav"
    fake.translation_model = "C:/definitely-missing.gguf"
    fake.translation_runtime = "C:/definitely-missing-runtime.exe"
    fake.spoken_language = SPOKEN_LANGUAGE
    try:
        require_existing(Path(fake.library), "transcribe.dll")
    except SystemExit as exc:
        if "never downloads" not in str(exc):
            raise AssertionError("missing-asset error did not refuse downloads") from exc
    else:
        raise AssertionError("missing asset was accepted")
    print("self-test: OK (no model loaded, no network)")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="fake/no-model preflight")
    parser.add_argument("--check", action="store_true", help="resolve local assets and exit")
    parser.add_argument("--mode", choices=("b2", "b3", "all"), default="all")
    parser.add_argument("--runner", choices=("app", "native"), default="native")
    parser.add_argument("--package", default=str(DEFAULT_TRANSCRIBE_PACKAGE))
    parser.add_argument("--pacing", choices=("real", "virtual"), default="virtual")
    parser.add_argument("--durations", default="30,120,480", help="comma-separated seconds of the recorded WAV")
    parser.add_argument("--backends", default="cpu,vulkan", help="ASR backends")
    parser.add_argument("--translation-modes", default="gpu,cpu")
    parser.add_argument("--designs", default="current,stream")
    parser.add_argument("--audio", default=str(DEFAULT_WAV))
    parser.add_argument("--library", default=str(DEFAULT_LIBRARY))
    parser.add_argument("--translation-model", default=str(DEFAULT_TRANSLATION_MODEL))
    parser.add_argument("--translation-runtime", default=str(DEFAULT_TRANSLATION_RUNTIME))
    parser.add_argument("--output-dir", default=str(BENCH_DIR / "results"))
    args = parser.parse_args(argv)
    args.durations = [int(value) for value in args.durations.split(",") if value.strip()]
    args.backends = [value for value in args.backends.split(",") if value.strip()]
    args.translation_modes = [value for value in args.translation_modes.split(",") if value.strip()]
    args.designs = [value for value in args.designs.split(",") if value.strip()]
    if not args.durations or not args.backends or not args.translation_modes or not args.designs:
        parser.error("durations, backends, translation-modes and designs must not be empty")
    if any(value <= 0 for value in args.durations):
        parser.error("durations must be positive seconds")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        return _self_test()
    assets = resolve_assets(args)
    if args.check:
        print(json.dumps(assets, indent=2))
        return 0
    from pipeline_bench_common import translation_config

    b2_result: dict[str, Any] = {}
    b3_result: dict[str, Any] = {}
    if args.mode in ("b2", "all"):
        b2_result = run_b2(args, assets)
    if args.mode in ("b3", "all"):
        b3_result = run_b3(args, assets, b2_result)
    result = {
        "status": "MEASURED",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": " ".join(sys.argv),
        "assets": assets,
        "note": (
            "The WAV is the earlier round's recorded test16k.wav sliced to the requested durations. "
            "The native runner is the same transcribe.dll through its already-installed Python binding "
            "with real word timestamps; the app ctypes wrapper exposes only segments "
            "(voice_typer/worker/asr_runner/engine.py:40) and is kept as a reference runner. "
            "Stable text uses the production 1.5 s right guard. Virtual pacing feeds audio without "
            "sleeping; decode and translation are real."
        ),
        "translation_config": {
            "model": "index-translate-2b-q4-k-m",
            "gpu_values": [mode == "gpu" for mode in args.translation_modes],
            "target": TARGET_LANGUAGE,
        },
        "source_config": str(translation_config(args, gpu=True)),
        "b2": b2_result,
        "b3": b3_result,
    }
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "pipeline-translation-results.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    compare_path = out_dir / "pipeline-translation-compare.txt"
    _write_quality(compare_path, b3_result)
    print(f"results: {result_path}")
    print(f"comparison: {compare_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
