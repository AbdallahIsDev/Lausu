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
ffmpeg decoder and a REAL GGUF model. Six scenarios: serial-vs-
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

It prints `RESULT: PASS` only when every scenario holds. Reference numbers and
the exact per-row flags live in the ADR-0023 stress tables
(`docs/adr/0023-media-ingest-transcription.md`, addendum 2026-10-27 plus its
2026-10-28 re-measurement) — those tables are the single canonical record; do
not duplicate the numbers here. Transcripts must stay byte-identical to the
serial baseline.

The serial-vs-concurrent speedup is printed as `[INFO]` and is NOT a gate: run
it on an idle machine, the ratio is not a gate (the same flags measured 1.34x
and 0.76x on a busy box while every correctness check passed).

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

## Translation benchmark (opt-in, LOCAL agent only)

`bench_translation.py` measures the ADR-0030 text translator using the REAL
`TranslationService` and a REAL, already-installed `llama-server`. It never
downloads a model or a binary: it exits immediately when the GGUF or runtime is
missing, so `make bench` records a skip marker on model-less CI machines.
**Every figure it produces is UNVERIFIED until the local run happens.**

Exact command (run from the repo root, substitute the two absolute paths of
assets already on the owner's machine):

```bash
.venv/Scripts/python.exe bench/bench_translation.py \
  --model-path "<absolute path to Index-Translate-2B.Q4_K_M.gguf>" \
  --runtime-path "<absolute path to llama-server.exe>" \
  --source-language ar --target-language en \
  --iterations 10 --warmup 2 --json
```

Equivalent without flags, for a local agent that has set the app's own escape
hatches once:

```bash
set LAUSU_TRANSLATION_MODEL=<absolute path to Index-Translate-2B.Q4_K_M.gguf>
set LAUSU_TRANSLATION_RUNTIME=<absolute path to llama-server.exe>
.venv/Scripts/python.exe bench/bench_translation.py --iterations 10 --warmup 2 --json
```

Add `--cpu` to force `-ngl 0`; omit it for the app's default Vulkan path.
`--text` / `--text-file` replace the built-in Arabic paragraph; `--max-chars`
controls the bounded sentence chunks (default 240). Chunking here is opt-in
benchmark tooling only — the dictation path still sends the whole Stage A text
in one call (ADR-0021 §5.2).

Record in `worklog.md`, with hardware/OS/Python version:

1. `cold_start_s` — first runtime start to healthy `/health`.
2. `paragraph_latency_ms` (median + p90) — one whole-paragraph request.
3. `sentence_latency_ms` (median + p90) — per bounded sentence chunk.
4. `batch_total_ms` — same chunks through one loaded runtime.
5. `tokens_per_second_wall` and `tokens_per_second_decode` — from the runtime's
   own token counters.
6. `memory_mb` before start, after load, after runs (peak RSS where available).
7. Any failure/timeout text from `lausu.log` and `<config>/translation/llama-server.log`.

Do not turn these numbers into product claims, change the model, or flip
`cache_prompt` without a separate owner decision and an A/B quality check.
