#!/usr/bin/env python
"""Stress the dictation microphone filter chain on REAL speech.

``bench/bench_audio_filter_chain.py`` measures the chain on synthetic tones
with a fixed chunk size and exits. That cannot answer the questions the
microphone fixes actually raised (docs/microphone-filter-failures.md):

* does 2 s of dictation cost 2 s of CPU, or 10 s?
* does a long take drift (length, latency, guard state) as it runs?
* does the divergence guard stay quiet on honest presets and only trip on a
  chain that really eats speech?
* does the delivered take still transcribe (live model, not a mock)?

Audio is REAL speech (Windows SAPI TTS by default, or any 16 kHz mono WAV via
``--speech``). Synthetic tones are useless here: dPDFNet is a deep filter, it
legitimately strips a pure sine 60-90 dB and reports nothing wrong.

Usage (from the repo root, venv active):

    python bench/stress_mic_filters.py
    python bench/stress_mic_filters.py --presets auto,busy_auto --snr-db 0
    python bench/stress_mic_filters.py --speech C:\\tmp\\take.wav --no-asr
    python bench/stress_mic_filters.py --long-seconds 600 --json out.json

Exit code is 1 when a gate fails, so CI/scripts can gate on it.
"""

from __future__ import annotations

import argparse
import json
import math
import string
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SR = 16000
SHORT_TAKE_SECONDS = 2.0
HONESTY_SECONDS = 20.0
DEFAULT_CHUNK_MS = (10, 20, 32, 64, 128)
# A 2 s take must not cost more than this fraction of its duration: the
# failure this replaces was ~5x realtime (2 s of speech -> ~10 s of work).
MAX_SHORT_TAKE_RTF = 0.5
# Allowed bucket-to-bucket spread of the long-run RTF (drift detector).
MAX_LONG_RUN_DRIFT = 1.5

SPEECH_TEXT = (
    "The microphone filter should never remove the speaker's own voice. "
    "Short dictations must stay fast, and long dictations must not drift. "
    "When the chain does eat the speech, the guard swaps the whole take to "
    "the raw recording and keeps the words the user actually said. "
    "This paragraph exists to give the recogniser real sentences with "
    "plosives, sibilance, pauses, and normal English prosody. "
    "Numbers, dates, and names follow: twenty twenty six, the third of March, "
    "seventeen point five decibels, and the name Alexandria."
)


# --------------------------------------------------------------------------
# audio
# --------------------------------------------------------------------------
def generate_speech_wav(path: Path) -> None:
    """Render ``SPEECH_TEXT`` to a 16 kHz mono WAV with the OS TTS voice."""
    if sys.platform != "win32":
        raise SystemExit(
            "No --speech WAV given and automatic speech generation is Windows-only. "
            "Pass --speech <16 kHz mono WAV> on this platform."
        )
    raw = path.with_suffix(".sapi.wav")
    path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate = 0; "
        f"$s.SetOutputToWaveFile('{raw}'); "
        f"$s.Speak({json.dumps(SPEECH_TEXT)}); "
        "$s.Dispose();"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not raw.is_file():
        raise SystemExit(f"speech generation failed: {proc.stderr.strip() or proc.returncode}")
    audio, rate = read_wav(raw)
    write_wav(path, resample(audio, rate, SR), SR)
    raw.unlink(missing_ok=True)


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read a PCM/float WAV as float32 mono samples plus its rate."""
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if width == 2:
        data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 4:
        data = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    elif width == 1:
        data = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise SystemExit(f"unsupported WAV sample width: {width} bytes")
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, rate


def write_wav(path: Path, audio: np.ndarray, rate: int = SR) -> None:
    """Write float32 mono samples as 16-bit PCM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes((pcm * 32767.0).astype("<i2").tobytes())


def resample(audio: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Resample with the same polyphase primitive the pipeline uses."""
    if src == dst:
        return np.asarray(audio, dtype=np.float32)
    from scipy.signal import resample_poly

    gcd = math.gcd(src, dst)
    return np.asarray(resample_poly(audio, dst // gcd, src // gcd), dtype=np.float32)


def pink_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    """Speech-shaped-ish background: white noise tilted to pink."""
    white = rng.standard_normal(n).astype(np.float32)
    spectrum = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, d=1.0 / SR)
    spectrum[1:] /= np.sqrt(np.maximum(freqs[1:], 1.0))
    spectrum[0] = 0.0
    shaped = np.fft.irfft(spectrum, n=n).astype(np.float32)
    return shaped / max(float(np.sqrt(np.mean(shaped**2))), 1e-12)


def rms(audio: np.ndarray) -> float:
    """Linear RMS of a signal."""
    flat = np.asarray(audio, dtype=np.float32).reshape(-1)
    if flat.size == 0:
        return 0.0
    return float(np.sqrt(np.dot(flat, flat) / flat.size))


def dbfs(value: float) -> float:
    """dBFS for a linear RMS value."""
    return 20.0 * math.log10(value) if value > 0.0 else -200.0


def mix_at_snr(speech: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """Scale ``noise`` so it sits ``snr_db`` below ``speech``."""
    speech_rms = rms(speech)
    noise_rms = max(rms(noise), 1e-12)
    target = speech_rms / (10.0 ** (snr_db / 20.0))
    return (noise * (target / noise_rms)).astype(np.float32)


# --------------------------------------------------------------------------
# pipeline
# --------------------------------------------------------------------------
def build_config(preset: str) -> Any:
    """Config for a scenario name (see SCENARIOS)."""
    from voice_typer.server.config import Config

    cfg = Config()
    cfg.sample_rate = SR
    if preset == "auto":
        cfg.audio_preset = "auto"
        cfg.noise_filter_highpass = True
        cfg.noise_filter_gate = False
        cfg.noise_filter_eq = False
        cfg.noise_filter_compressor = False
        cfg.noise_filter_limiter = True
        cfg.noise_filter_notch = False
        cfg.noise_suppression_method = "dpdfnet"
    elif preset == "noisy_room":
        cfg.audio_preset = "noisy_room"
        cfg.noise_filter_highpass = True
        cfg.noise_filter_gate = False
        cfg.noise_filter_eq = False
        cfg.noise_filter_compressor = False
        cfg.noise_filter_limiter = True
        cfg.noise_filter_notch = True
        cfg.noise_suppression_method = "dpdfnet"
    elif preset == "off":
        cfg.audio_preset = "off"
        cfg.noise_filter_highpass = False
        cfg.noise_filter_gate = False
        cfg.noise_filter_eq = False
        cfg.noise_filter_compressor = False
        cfg.noise_filter_limiter = False
        cfg.noise_filter_notch = False
        cfg.noise_suppression_method = "none"
    elif preset == "broken_gate":
        # Deliberately lying chain: a gate that only opens above -10 dBFS
        # mutes ordinary speech (-20 dBFS) and must trip the guard.
        cfg.audio_preset = "custom"
        cfg.noise_filter_highpass = False
        cfg.noise_filter_gate = True
        cfg.noise_filter_gate_open_threshold_db = -10.0
        cfg.noise_filter_gate_close_threshold_db = -14.0
        cfg.noise_filter_eq = False
        cfg.noise_filter_compressor = False
        cfg.noise_filter_limiter = False
        cfg.noise_filter_notch = False
        cfg.noise_suppression_method = "none"
    else:
        raise SystemExit(f"unknown preset scenario: {preset}")
    return cfg


def make_pipeline(config: Any) -> Any:
    """Real ``AudioProcessor`` + ``AudioPipeline`` on a recorder stand-in."""
    from unittest.mock import MagicMock

    from voice_typer.server.audio_processor import AudioProcessor
    from voice_typer.server.recording.audio_pipeline import AudioPipeline

    recorder = MagicMock(name="StressRecorder")
    recorder.config = config
    recorder._effective_sr = SR
    recorder._audio_processor = AudioProcessor(config, sample_rate=SR, quiet=True)
    pipeline = AudioPipeline(recorder)
    recorder._audio_pipeline = pipeline
    return recorder, pipeline


def run_take(
    recorder: Any,
    pipeline: Any,
    audio: np.ndarray,
    chunk_ms: int,
) -> dict[str, Any]:
    """Push ``audio`` through the pipeline in ``chunk_ms`` pieces."""
    chunk = max(1, int(SR * chunk_ms / 1000))
    per_chunk: list[float] = []
    delivered = 0
    fallback = pipeline._filter_fallback
    for start in range(0, len(audio), chunk):
        piece = audio[start : start + chunk]
        t0 = time.perf_counter()
        filtered = pipeline.apply_filter_chain(piece)
        pipeline.append_to_buffer_locked(filtered)
        elapsed = time.perf_counter() - t0
        per_chunk.append(elapsed)
        delivered += 0 if filtered is None else len(filtered)
    total = sum(per_chunk)
    fallback.finalize(recorder)
    return {
        "audio_seconds": round(len(audio) / SR, 3),
        "chunk_ms": chunk_ms,
        "wall_seconds": round(total, 4),
        "rtf": round(total / max(len(audio) / SR, 1e-9), 4),
        "p99_chunk_ms": round(float(np.percentile(per_chunk, 99)) * 1000, 3),
        "delivered_samples": delivered,
        "length_exact": delivered == len(audio),
        "tripped": fallback.tripped,
        "swapped": fallback.swapped,
        "delivered": pipeline._buffer.export_copy(),
        "guard": fallback.summary_fields(),
        "filter_names": list(getattr(recorder._audio_processor, "filter_names", [])),
        "degraded": bool(getattr(recorder._audio_processor, "is_degraded", False)),
    }


# --------------------------------------------------------------------------
# scenarios
# --------------------------------------------------------------------------
def scenario_short_takes(speech: np.ndarray, presets: list[str], chunks: list[int]) -> list[dict[str, Any]]:
    """A 2 s dictation must cost a fraction of 2 s, at every chunk size."""
    take = speech[: int(SHORT_TAKE_SECONDS * SR)]
    rows: list[dict[str, Any]] = []
    for preset in presets:
        for chunk_ms in chunks:
            recorder, pipeline = make_pipeline(build_config(preset))
            row = run_take(recorder, pipeline, take, chunk_ms)
            row["scenario"] = "short_take"
            row["preset"] = preset
            rows.append(row)
    return rows


def scenario_long_take(
    speech: np.ndarray,
    preset: str,
    chunk_ms: int,
    seconds: float,
    noise: np.ndarray,
) -> dict[str, Any]:
    """One long dictation: length conservation, per-minute RTF, guard state."""
    repeats = int(math.ceil(seconds * SR / len(speech)))
    take = np.tile(speech, repeats)[: int(seconds * SR)]
    take = np.asarray(take + noise[: len(take)], dtype=np.float32)
    recorder, pipeline = make_pipeline(build_config(preset))
    chunk = max(1, int(SR * chunk_ms / 1000))
    per_chunk: list[float] = []
    delivered = 0
    minute_rtf: list[float] = []
    window_start = 0.0
    window_cost = 0.0
    for start in range(0, len(take), chunk):
        piece = take[start : start + chunk]
        t0 = time.perf_counter()
        filtered = pipeline.apply_filter_chain(piece)
        pipeline.append_to_buffer_locked(filtered)
        cost = time.perf_counter() - t0
        per_chunk.append(cost)
        window_cost += cost
        delivered += len(filtered)
        window_start += len(piece) / SR
        if window_start >= 60.0:
            minute_rtf.append(round(window_cost / window_start, 4))
            window_start = 0.0
            window_cost = 0.0
    fallback = pipeline._filter_fallback
    fallback.finalize(recorder)
    if window_start > 0.0:
        minute_rtf.append(round(window_cost / window_start, 4))
    return {
        "scenario": "long_take",
        "preset": preset,
        "chunk_ms": chunk_ms,
        "audio_seconds": round(len(take) / SR, 2),
        "wall_seconds": round(sum(per_chunk), 3),
        "rtf": round(sum(per_chunk) / (len(take) / SR), 4),
        "minute_rtf": minute_rtf,
        "drift_ratio": round(max(minute_rtf) / max(min(minute_rtf), 1e-9), 3),
        "p99_chunk_ms": round(float(np.percentile(per_chunk, 99)) * 1000, 3),
        "delivered_samples": delivered,
        "length_exact": delivered == len(take),
        "tripped": fallback.tripped,
        "swapped": fallback.swapped,
        "guard": fallback.summary_fields(),
        "delivered": pipeline._buffer.export_copy(),
    }


def scenario_chain_gain(
    speech: np.ndarray,
    noise: np.ndarray,
    preset: str,
    snr_db: float,
) -> dict[str, Any]:
    """Speech vs noise gain on the same chain (honest presets must keep speech)."""
    noise_at_snr = mix_at_snr(speech, noise[: len(speech)], snr_db)
    speech_mix = np.asarray(speech + noise_at_snr, dtype=np.float32)

    recorder, pipeline = make_pipeline(build_config(preset))
    row = run_take(recorder, pipeline, speech_mix, 32)
    filtered = row.pop("delivered")

    recorder_s, pipeline_s = make_pipeline(build_config(preset))
    speech_only = run_take(recorder_s, pipeline_s, speech, 32)
    speech_out = speech_only.pop("delivered")

    recorder_n, pipeline_n = make_pipeline(build_config(preset))
    noise_only = run_take(recorder_n, pipeline_n, noise_at_snr, 32)
    noise_out = noise_only.pop("delivered")

    speech_gain = dbfs(rms(speech_out)) - dbfs(rms(speech))
    noise_gain = dbfs(rms(noise_out)) - dbfs(rms(noise_at_snr))
    return {
        "scenario": "chain_gain",
        "preset": preset,
        "snr_in_db": snr_db,
        "speech_gain_db": round(speech_gain, 2),
        "noise_gain_db": round(noise_gain, 2),
        "snr_gain_db": round(speech_gain - noise_gain, 2),
        "speech_rms_out": round(rms(speech_out), 6),
        "tripped": row["tripped"],
        "guard": row["guard"],
        "rtf": row["rtf"],
        "delivered_mix": filtered,
        "filter_names": row["filter_names"],
        "degraded": row["degraded"],
    }


# --------------------------------------------------------------------------
# live model
# --------------------------------------------------------------------------
def _word_errors(reference: str, hypothesis: str) -> tuple[int, int]:
    """Word-level Levenshtein distance and reference length."""
    ref = reference.split()
    hyp = hypothesis.split()
    prev = list(range(len(hyp) + 1))
    for i, ref_word in enumerate(ref, start=1):
        cur = [i]
        for j, hyp_word in enumerate(hyp, start=1):
            cur.append(
                min(
                    prev[j] + 1,
                    cur[j - 1] + 1,
                    prev[j - 1] + (0 if ref_word == hyp_word else 1),
                )
            )
        prev = cur
    return prev[-1], len(ref)


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    cleaned = text.lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(cleaned.split())


class Transcriber:
    """faster-whisper wrapper for the delivered-take comparison."""

    def __init__(self, model: str) -> None:
        from faster_whisper import WhisperModel

        self._model = WhisperModel(model, device="cpu", compute_type="int8")

    def text(self, audio: np.ndarray) -> str:
        """Transcribe 16 kHz mono float32 audio."""
        segments, _info = self._model.transcribe(
            np.asarray(audio, dtype=np.float32),
            language="en",
            beam_size=1,
            vad_filter=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def compare(self, reference: str, audio: np.ndarray) -> dict[str, Any]:
        """Word error rate of ``audio`` against ``reference``."""
        hypothesis = self.text(audio)
        errors, total = _word_errors(_normalise(reference), _normalise(hypothesis))
        return {
            "wer": round(errors / max(total, 1), 3),
            "words": len(_normalise(hypothesis).split()),
            "text": hypothesis,
        }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def _gate(results: list[dict[str, Any]], failures: list[str]) -> None:
    """Apply the pass/fail gates to the collected rows."""
    for row in results:
        where = f"{row['scenario']}/{row.get('preset', '-')}/chunk={row.get('chunk_ms', '-')}ms"
        if row["scenario"] == "short_take" and row["rtf"] > MAX_SHORT_TAKE_RTF:
            failures.append(f"{where}: 2 s take RTF {row['rtf']} > {MAX_SHORT_TAKE_RTF}")
        if row["scenario"] == "long_take":
            if not row["length_exact"]:
                failures.append(f"{where}: delivered {row['delivered_samples']} != {row['audio_seconds']}s of samples")
            if row["drift_ratio"] > MAX_LONG_RUN_DRIFT:
                failures.append(f"{where}: RTF drift {row['drift_ratio']}x across minutes")
        if (
            row["scenario"] in {"short_take", "long_take", "chain_gain"}
            and row.get("preset") in {"auto", "noisy_room"}
            and row.get("tripped")
        ):
            failures.append(f"{where}: guard tripped on an honest preset")
        if row["scenario"] == "chain_gain" and row.get("preset") == "broken_gate":
            continue
        if row["scenario"] == "chain_gain" and row.get("speech_gain_db", 0.0) < -12.0:
            failures.append(f"{where}: honest preset dropped speech by {row['speech_gain_db']} dB")
    broken = [row for row in results if row.get("preset") == "broken_gate" and row["scenario"] == "chain_gain"]
    for row in broken:
        if not row["tripped"]:
            failures.append("broken_gate: the divergence guard did NOT trip on a chain that mutes speech")


def _print_table(results: list[dict[str, Any]]) -> None:
    """Human-readable report (no delivered audio blobs)."""
    print("=" * 78)
    print("Lausu: microphone filter stress (real speech)")
    print("=" * 78)
    for row in results:
        head = f"  [{row['scenario']}] preset={row.get('preset')}"
        if row.get("chunk_ms"):
            head += f" chunk={row['chunk_ms']}ms"
        print()
        print(head)
        for key, value in row.items():
            if key in {"scenario", "preset", "delivered", "delivered_mix", "text", "guard"}:
                continue
            if key == "minute_rtf":
                print(f"    minute_rtf      : {value}")
                continue
            print(f"    {key:<15} : {value}")
        if row.get("guard"):
            print(f"    guard           : {row['guard']}")
        if row.get("text"):
            print(f"    text            : {row['text'][:110]}...")


def main() -> int:
    parser = argparse.ArgumentParser(description="Microphone filter stress on real speech")
    parser.add_argument("--speech", type=Path, default=None, help="16 kHz mono WAV with real speech")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("bench-out"),
        help="Directory for the generated speech + delivered takes (default: bench-out)",
    )
    parser.add_argument("--presets", default="auto,noisy_room", help="honest presets to measure")
    parser.add_argument("--chunks", default=",".join(str(c) for c in DEFAULT_CHUNK_MS), help="chunk sizes in ms")
    parser.add_argument("--long-seconds", type=float, default=180.0, help="long-take duration")
    parser.add_argument("--snr-db", type=float, default=5.0, help="noise level relative to speech")
    parser.add_argument("--asr-model", default="tiny", help="faster-whisper model for the live check")
    parser.add_argument("--no-asr", action="store_true", help="skip the live-model section")
    parser.add_argument("--json", type=Path, default=None, help="write the raw results as JSON")
    args = parser.parse_args()

    presets = [item.strip() for item in args.presets.split(",") if item.strip()]
    chunks = [int(item) for item in args.chunks.split(",") if item.strip()]
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    speech_path = args.speech
    if speech_path is None:
        speech_path = out_dir / "speech.wav"
        if not speech_path.is_file():
            print(f"generating real speech -> {speech_path}")
            generate_speech_wav(speech_path)
    audio, rate = read_wav(speech_path)
    if rate != SR:
        audio = resample(audio, rate, SR)
    if len(audio) < SR:
        raise SystemExit(f"{speech_path} holds {len(audio) / SR:.2f}s of audio, need at least 1s")
    speech = np.asarray(audio, dtype=np.float32)
    speech = (speech / max(float(np.abs(speech).max()), 1e-9) * 0.25).astype(np.float32)
    print(f"speech: {speech_path} ({len(speech) / SR:.2f}s, peak {np.abs(speech).max():.2f})")

    from voice_typer.server.audio_filters import dpdfnet_backend

    print(f"dpdfnet runtime: available={dpdfnet_backend.has_runtime()} last_error={dpdfnet_backend.last_error()!r}")
    if not dpdfnet_backend.has_runtime():
        print("warming DPDFNet runtime (one-time session build)…")
        dpdfnet_backend.preload()
        deadline = time.perf_counter() + 120.0
        while time.perf_counter() < deadline and not dpdfnet_backend.has_runtime():
            time.sleep(0.05)
    print(
        f"dpdfnet ready={dpdfnet_backend.has_runtime()} "
        f"last_error={dpdfnet_backend.last_error()!r}"
    )
    runtime = getattr(dpdfnet_backend, "_runtime", None)
    print(f"dpdfnet realtime factor: {getattr(runtime, 'realtime_factor', None)}")

    rng = np.random.default_rng(20261102)
    noise = pink_noise(int((args.long_seconds + len(speech) / SR + 5.0) * SR), rng) * 0.01

    results: list[dict[str, Any]] = []
    results.extend(_strip(scenario_short_takes(speech, presets, chunks)))
    results.append(_strip(scenario_long_take(speech, presets[0], 32, args.long_seconds, noise)))
    for preset in presets:
        results.append(_strip(scenario_chain_gain(speech, noise, preset, args.snr_db)))
    results.append(_strip(scenario_chain_gain(speech, noise, "broken_gate", args.snr_db)))

    failures: list[str] = []
    _gate(results, failures)

    if not args.no_asr:
        transcriber = Transcriber(args.asr_model)
        short = speech[: int(SHORT_TAKE_SECONDS * SR)]
        baseline_text = transcriber.text(short)
        baseline_words = len(_normalise(baseline_text).split())
        print(f"\nlive model ({args.asr_model}) raw 2 s baseline: words={baseline_words} {baseline_text!r}")
        for preset in presets:
            recorder, pipeline = make_pipeline(build_config(preset))
            row = run_take(recorder, pipeline, short, 32)
            take = row.pop("delivered")
            write_wav(out_dir / f"take_{preset}.wav", take)
            scored = transcriber.compare(baseline_text, take)
            scored.update({"scenario": "live_model", "preset": preset, "chunk_ms": 32, "tripped": row["tripped"]})
            results.append(scored)
            if baseline_words and scored["words"] == 0:
                failures.append(f"live_model/{preset}: the filtered take transcribed to nothing")

        recorder, pipeline = make_pipeline(build_config("broken_gate"))
        row = run_take(recorder, pipeline, short, 32)
        recovered = row.pop("delivered")
        write_wav(out_dir / "take_broken_gate_recovered.wav", recovered)
        scored = transcriber.compare(baseline_text, recovered)
        scored.update({"scenario": "live_model", "preset": "broken_gate", "chunk_ms": 32, "tripped": row["tripped"]})
        results.append(scored)
        if not row["tripped"]:
            failures.append("live_model/broken_gate: no guard trip")
        if scored["words"] == 0:
            failures.append("live_model/broken_gate: the recovered take transcribed to nothing")

    _print_table(results)
    if args.json is not None:
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\njson -> {args.json}")

    print()
    if failures:
        print("FAILURES")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(f"ALL GATES PASSED ({len(results)} rows)")
    return 0


def _strip(row: Any) -> Any:
    """Drop the delivered audio before reporting (kept by callers that need it)."""
    if isinstance(row, list):
        return [_strip(item) for item in row]
    row.pop("delivered", None)
    row.pop("delivered_mix", None)
    return row


if __name__ == "__main__":
    raise SystemExit(main())
