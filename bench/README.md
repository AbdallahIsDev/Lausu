# Lausu: Benchmarks

**Status: Benchmark harness available, run on your hardware (cold import is tens of milliseconds and depends on hardware/OS, ≈ 84 ms observed on Windows; the CI-tracked worker-startup metric runs ≈ 0.9 s first-run / ≈ 0.3 s median on CI runners, target ≤ 600 ms first-run (cold); model sizes verified: tiny.en 74 MB, small.en 463 MB, parakeet 2393 MB).**

The benchmark harness (`bench_transcription.py`) is ready for use. Run it
to generate measurements for your hardware configuration. The startup
claims in the README are now backed by `bench/bench_startup.py` output
(cold-import latency and on-disk model sizes).

## Running the benchmark

```bash
# Transcription latency (default: small.en on CPU, 5 iterations)
python bench/bench_transcription.py --model small.en --device cpu

# Model load time only
python bench/bench_transcription.py --model tiny.en --device cpu --load-only

# GPU transcription
python bench/bench_transcription.py --model small.en --device cuda --iterations 10
```

## Media concurrency stress test

`media_concurrency_stress.py` exercises the ADR-0023 multi-job manager against
the REAL job manager, the REAL `engine_loop` (ASR lane + abort guard), the REAL
PyAV decoder and a REAL faster-whisper model. Six scenarios: serial-vs-
concurrent throughput, the concurrency cap, per-job cancel isolation, decode
parity (mp3 vs mp4, and the same clip decoded concurrently), and the log
contract.

```bash
# Default: the ~/Downloads mp3+mp4 pair, 6 jobs x 240 s, cap 4.
.venv/Scripts/python.exe bench/media_concurrency_stress.py

# Any equivalent pair (the same recording in two containers):
.venv/Scripts/python.exe bench/media_concurrency_stress.py \
    --audio ~/Downloads/talk.mp3 --video ~/Downloads/talk.mp4 \
    --device cuda --compute float16
```

It prints `RESULT: PASS` only when every scenario holds. Reference numbers are
recorded in the ADR-0023 addendum (2026-10-27): 1.37x on tiny/int8 CPU, 1.70x
on large-v3-turbo/float16 CUDA, transcripts byte-identical to the serial
baseline.

**Why this file is not named `bench_*.py`:** the CI glob runs every
`bench/bench_*.py` as a smoke benchmark on a machine with no model weights and
no sample media. This script needs both (it loads a real checkpoint and decodes
a real 240 s clip), so it is deliberately outside that glob and runs on demand.

## Metrics measured

1. **Full transcription latency**: time from audio input to complete text
2. **Model load time**: cold-start time for each model size

## Planned metrics

3. **First-token latency**: time from hotkey release to first character
   appearing in the target window.
4. **Streaming partial latency**: time from audio chunk to partial
   transcription appearing (if streaming is enabled).
5. **Memory usage**: peak RSS during transcription.

## Methodology

- Run on a dedicated machine (no other CPU-intensive apps).
- Use a fixed 10-second audio sample at 16 kHz mono.
- Repeat 10 times, report median + p90.
- Measure on both CPU and GPU (if available).
- Report Python version, OS, and hardware specs.

## pytest-benchmark integration

To add automated regression benchmarks:

```bash
pip install pytest-benchmark
```

Then create `tests/bench/` with fixtures that use the `benchmark` fixture
to track performance across commits.
