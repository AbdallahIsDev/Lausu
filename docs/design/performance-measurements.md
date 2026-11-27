# Real performance measurements on Windows (verification of the cloud audit)

Measured 2026-11-27 by Worker S1 Part A on this machine. The cloud audit in
`docs/design/rust-migration-audit.md` was written in a sandbox with no Windows,
no numpy/scipy and no running app. This document replaces its guesses with
measurements from the real process paths where possible. `MEASURED` means the
numbers came from the code on this machine; `UNVERIFIED` means the asset or
entry point was not available and no number is claimed.

## Plain English

The audit's big picture survives, but two of its numbers were wrong by a lot on
this machine:

- The Python text path is tiny. Config load is ~1 ms, a feature-flag read is
  ~21 ns, one bubble publish is ~3-4 microseconds. Rewriting those in Rust
  cannot buy anything a user can feel.
- Startup import is **200 ms**, not 96-115 ms. About half of that is CPython's
  own standard library. The rest is mostly one-time config/security setup.
  This is real but still small next to native startup, which the logs put at
  1.6 s warm / 3.0 s spaced-out (up to 8 s) before the Python app even says
  hello.
- The whole-buffer copy the audit called the one real defect was real in the
  baseline, but this Windows machine copies 30 MB in **1.9 s of CPU over an
  8-minute take**, not 5.7 s, and stalls other threads up to **38 ms**, not
  25 ms. Also important: the path is **dormant in this profile** — the offline
  pack is missing and a browser plugin owns dictation, so no worker-backed
  local engine is active. Round 6 fixed it anyway (unseen-tail copy); the
  measurement above is the before picture.
- The resampler was the one place where the cloud estimate was too _low_. With
  real numpy/scipy the 16 kHz → 48 kHz → 16 kHz pair burned **~8.6% of one core**
  while a suppressor runs, not 0.8%. At 44.1 kHz the audit's exact shape costs
  ~22 ms CPU per audio-second, about 2.7x its proxy. Round 6 vectorized it down
  to 0.37% of one core; the figures above are the before picture.
- The 5 ms / 300 ms teardown poll is correctly described in the source, but on
  a real audio device it added **0 ms** in normal stops. It adds the full 300 ms
  only when a callback flag never clears. A real 1-second take stopped in
  **17 ms** median. Round 6 left it alone: zero normal-path gain, nonzero risk.
- The overlay bubble's Python half is microseconds. The missing end-to-end
  "hotkey → bubble visible" measurement is what would justify a renderer
  change; there is no measured Python bottleneck to remove there.

## Round 6 fixes and verdicts (2026-11-27)

Plain English: two fixes shipped, two were deliberately declined, and no Rust
rewrite is supported by the numbers. The worker now copies only the audio it
has not sent yet (480 s take: ~1.9 s of conversion CPU down to ~2 ms), and the
resampler now does one vectorized reduction per chunk instead of a per-sample
loop (16→48→16 pair: 2.84 → 0.12 ms per chunk, 8.9% → 0.37% of one core). The
teardown poll costs nothing in a normal stop, so changing it was not worth the
risk; lazy imports save only tens of milliseconds of a multi-second start and
were not done because of frozen-build risk. Every number below comes from the
Round 6 worker reports, using the same harnesses as the measurements above.
Where a path could not be driven in this profile, it is marked UNVERIFIED.

### B1 — SHIPPED: unseen-tail copy instead of whole-buffer copy

`worker_streaming.py` now converts only `snapshot[from_samples:]` before
`tobytes()` on each push and at `finalize()`. Wire bytes, frame indices,
chunking, thread name, log lines, public API and failure behavior are unchanged.

| Take | Before: whole-copy CPU median / p95 | After: real push-path CPU median / p95 | After: wall median (before) |
| --- | --- | --- | --- |
| 30 s | 7.877 / 7.920 ms | **0.135 / 0.155 ms** | 7.365 ms (15.834) |
| 120 s | 96.538 / 96.592 ms | **0.526 / 0.548 ms** | 28.547 ms (129.201) |
| 480 s | **1856.642 / 2035.309 ms** | **2.043 / 2.051 ms** | 113.873 ms (2034.968) |

- 480 s: conversion ~1857 → ~2.0 ms (~910x); bytes copied 14,077 → 29.3 MiB
  (~480x); wall ~2035 → ~114 ms (~18x). Per-call conversion is ~2 µs
  (2.043 ms over 960 polls).
- GIL probe: the old path gave p95 17.17 ms / max 21.18 ms lateness (baseline
  p95 0.59 ms). A tight loop of 32 KB delta copies still shows median 14.6 ms
  lateness because it saturates a core; that is not a per-call stall. Real-app
  GIL effect: **UNVERIFIED**.
- Remaining 480 s cost is push encode (base64/JSON frame building), median
  **111.3 ms**, untouched by this change and out of scope.
- Correctness: byte-identical oracle tests (growth, no-change, shrink/resync,
  non-contiguous view, delta larger than `_PUSH_RAW_BYTES`; finalize with
  unseen-all / partial / all-seen / over-large cursor), exact 4x and 16x
  linearity and one copy per sample through the real `_drive_pushes`; unusable
  input stays non-fatal. Scoped run: **139 passed, 0 failed**; ruff check and
  format clean. The four required files (`test_worker_streaming.py`,
  `test_worker_streaming_session.py`, `test_worker_samples_atomic_send.py`,
  `test_recorder_snapshot_view.py`) were not modified and pass unchanged.
- The path is dormant in this profile (offline pack missing, browser plugin
  owns dictation), but the fix is justified by the measured copy/GIL cost when
  the path is active. No real local-engine take was driven here: **UNVERIFIED**.

### B2 — NOT SHIPPED: 5 ms / 300 ms teardown poll left alone

- Real `Recorder.start()` → 1 s capture → `stop()`: stop median **17.3 ms**
  (p95 17.5, max 46.9).
- Isolated teardown: no callback in flight **55.97 ms**; callback clears after
  10 ms **56.02 ms** (poll hidden inside stop/close, **+0.05 ms**); callback
  never clears **356.95 ms** (the poll adds the full 300 ms).
- The poll is a confirmed worst-case bound, **0 ms in normal stops**. Changing
  it adds risk for zero measured normal gain. If a never-clearing callback is
  ever seen in a real log, fix the callback release, not the poll.

### B3 — SHIPPED: vectorized streaming resampler

The per-output `for j in range(count)` + `np.dot` loop is replaced by one gather
plus row-wise `np.einsum("ij,ij->i", ..., optimize=False)`; public interface,
output count, history/phase/counter updates, `reset()` and zero-length behavior
are unchanged.

| Pair | Before median | After median | Speedup | Before p99 | After p99 | CPU per audio-second |
| --- | --- | --- | --- | --- | --- | --- |
| 16→48→16 | 2.8373 ms | 0.1194 ms | 23.8x | 3.6498 ms | 0.1932 ms | 88.666 → 3.731 ms (8.9% → 0.37% of one core) |
| 44.1 kHz | 1.4828 ms | 0.0713 ms | 20.8x | 2.3595 ms | 0.1081 ms | 46.336 → 2.23 ms |

All single stages got faster (median / p99, ms):

| Shape | Before | After | Speedup | Before p99 | After p99 |
| --- | --- | --- | --- | --- | --- |
| 16→48 (3/1), 512→1536 | 2.0953 | 0.0718 | 29.2x | 3.3701 | 0.1511 |
| 48→16 (1/3), 1536→512 | 0.7033 | 0.0487 | 14.4x | 0.8742 | 0.1056 |
| 16→44.1 (160/147), 512→557 | 0.7564 | 0.0378 | 20.0x | 1.0228 | 0.0682 |
| 44.1→16 (147/160), 1411→1296 | 1.7792 | 0.0630 | 28.2x | 2.6358 | 0.1174 |
| 44.1→16 narrow (160/441), 512→185 | 0.2595 | 0.0275 | 9.4x | 0.5527 | 0.0592 |

- Correctness: **6,661** golden float32 values compared; 3,726 bit-identical
  (56%); worst absolute difference **7.45e-9** on 0.05-scale inputs, worst
  difference relative to a chunk's output peak 1.8e-7. That is float32
  reduction-order noise between BLAS `sdot` and einsum's row reduction; a
  phase/history error would shift whole samples (~1e-2). Tolerance 2e-8
  absolute, rtol=0, still 50x below the existing 1e-6 chunking tolerance.
- State (`phase`, `in_total`, `out_total`, `hist` bytes) byte-identical in every
  golden chunk. 10,000-chunk runs at 13/1, 1/3 and 160/147: worst divergence
  7.45e-09 / 1.12e-08 / 1.16e-10, no drift, final state byte-identical to the
  scalar reference. Zero-length input still returns empty float32 and leaves
  state untouched.
- Scoped run: **250 passed in 5.40 s** (18 new, 232 existing tests unchanged);
  ruff check and format clean. Existing suppressor/noise-gate tests unchanged.
  Construction cost 0.119 → 0.120 ms (16 kHz) and 0.477 → 0.544 ms (44.1 kHz,
  noise); noise-gate scalar-fallback counters unchanged (0/160 both scenarios).

### B4 — NOT DONE per instruction: no lazy import of ssl / security.http_safety

15-30 ms of a multi-second start does not justify the Nuitka frozen-import risk.
Left as an idea, not a change; nothing was lazy-imported for this item.

### B5 — startup ideas, ranked; none implemented

| # | Measured cost | Idea | Risk / reason not done |
| --- | --- | --- | --- |
| 1 | Browser-plugin activation: 3.1 s median, 10.3 s at last boot | Prepare/overlap it with host boot | The plugin must be ready before the first hotkey; recovery stays bounded |
| 2 | Speech-synthesis prewarm: 3.2 s median, 1.6 s at last boot | Defer to first use | Moves the wait into the first synthesis request |
| 3 | Worker process spawn: 0.6 s median (0.4 s last boot; p95 22.8 s under load) | Overlap with startup | Worker liveness/parent-watch contract must stay intact |
| 4 | scipy file warm: 0.5 s median (1.5 s at last boot) | Warm on a background thread after the handshake | First decode could pay it instead |
| 5 | Worker warm-import pass: 0.2-2.3 s (1.7 s at last boot) | Same background overlap | Same first-use latency risk |
| 6 | Config import graph: 78 ms cumulative | Lazy imports | Frozen-build import failures (see B4) |
| 7 | Security / TLS import graph: 60.7 ms cumulative (`security.http_safety` 34.4) | Lazy imports | Same Nuitka frozen-import risk (B4) |

The owner's "enabled-feature checks" suspicion is **refuted**: 21.5 ns per flag
read, ~0.37 µs for all 17 flags. The cost is importing the modules those flags
gate (~130 ms cumulative of the 200 ms import), not reading the flags.

### Rust verdict after Round 6

No broad Rust rewrite is supported. After B3 the resampler's 16→48→16 p99 is
0.1932 ms against a 32 ms chunk budget and 0.37% of one core: a PyO3 extension
would add a Nuitka build artifact, integrity-manifest entry and installer work
for a sub-0.5% core cost, so it is **not worth it now**. Revisit only if the
suppressor path shows a different bottleneck after this change. The GPUI bubble
remains orthogonal to Python performance; the missing measurement is WebView /
host paint latency on Windows. No Rust or PyO3 build was attempted in Round 6.

## Audit claim → measured on Windows → verdict

| Audit claim | Measured on Windows | Verdict |
| --- | --- | --- |
| Whole Python text path <1 ms | `clean_transcribed_text` 0.0525 ms for a 93-char sentence (p95 0.061), 0.372 ms at 631 chars (p95 0.607); `Config.load()` 1.03 ms; 17 flags at 21.5 ns each; one bubble publish 3.4 µs | Confirmed |
| Startup import ~96-115 ms, ~47% stdlib | `-X importtime` total **200.38 ms** median (9 runs, 199.55-225.64); owner split ~119 ms our code / ~98 ms stdlib (duplicate module names make the split approximate) | **Corrected**: same shape, ~2x larger on Windows |
| Whole-buffer copy 5.7 s CPU per 480 s take, GIL stalls to 25 ms | 480 s: **1909.7 ms** median whole copy (max 2592), 166 ms push encode, delta-only 19 ms; 1 ms timer max lateness **37.7 ms** (baseline 0.93) | **Corrected** magnitude; defect and GIL effect confirmed; path dormant in this profile |
| Stream teardown poll 5 ms / 300 ms budget | Constants confirmed at `recording/stream_lifecycle.py:601,615` and `_audio_constants.py:77-78`; real stop+close 56 ms, callback clearing after 10 ms adds 0 ms, never-clearing adds 300 ms (357 ms total); real 1 s take stop 17 ms | Confirmed as worst-case bound, not normal cost |
| Resampler ~8 ms CPU per audio-second (proxy) | 16→48 upsampler 2.044 ms per 32 ms chunk = 63.9 ms/s; 48→16 downsampler 21.7 ms/s; pair **85.6 ms/s (8.6% core)**; audit's 44.1 kHz shape 0.254 ms/chunk = 21.9 ms/s | **Corrected upward**, ~3-10x; still not felt latency, but a real CPU-safety cost |
| Bubble publish ~8.6 µs | Single real publish + real IPC send: 3.4 µs (p95 3.8); loopback round trip 4.4 µs | Confirmed order of magnitude; not a bottleneck |
| Idle thread count/RAM unknown | Sidecar 49 threads / 31.7 MiB RSS / 0.6% CPU; host 22 threads / 29.5 MiB / ~0% | Corrected with real values; Python-level thread names still UNVERIFIED |
| "Check whether user enabled X" is a startup cost | 1.03 ms for the whole config load; 21.5 ns per flag read; module imports, not flag reads, dominate | Refuted as stated; the cost is importing gated modules |

## Machine, load, method

- Windows 11 build 10.0.26200; AMD Ryzen 5 7600, 6 cores / 12 threads, 16 GB RAM; CPython 3.13.7 from `C:\Users\11\voice-typer\.venv` with numpy 2.5.2, scipy 1.18.0, psutil 7.2.2, sounddevice 0.5.6 and onnxruntime 1.29.0.
- 406 processes at session start; Chrome, the running app, and other agents were active. Machine CPU during the 5-minute idle sample ranged 3.9-34.3% (median 11.05%). No processes were killed and no heavy work was started during timing runs. Every timing ran serially, 5+ repetitions unless noted; median, p95 and max are reported. A p95/max spike is machine noise, not a second result.
- Live profile at measurement time: `active_plugin=anthropic_stt`, `waveform_bubble=false`, `audio_preset=off`, `noise_suppression_method=none`, `noise_filter_enabled=false`, `model_size=parakeet`, `asr_backend=parakeet`. The local model is not loaded at startup and the app log says a plugin serves dictation. The in-repo native runtime bundle is a placeholder; the DLL exists only outside the app bundle. Frozen-build startup is therefore UNVERIFIED.

Text path, measured on this machine with 7 runs of 200 calls each:
`clean_transcribed_text` (real function, auto-punctuation on) is 0.0051 ms at 11
characters, **0.0525 ms** at ~93 characters (p95 0.061, max 0.107), and 0.372
ms at 631 characters (p95 0.607, max 0.698). The whole measured Python text
work per dictation stays under 1 ms.

## A1 — startup timeline

Real log evidence (`lausu.log`, 73 launches on 2026-11-27):

| Window | host boot → backend first log | backend spawn → first log | spawn → `Startup complete` |
| --- | --- | --- | --- |
| all 73 (median / p95 / max) | 1.6 / 3.9 / 8.0 s | 1.2 / 3.0 / 7.4 s | 2.1 / 7.0 / 9.9 s |
| 61 warm boots (<120 s apart) | 1.6 / 1.9 / 4.7 s | 1.2 / 1.4 / 3.3 s | 2.1 / 2.3 / 7.9 s |
| 12 spaced/cold boots (≥2 min gap) | 3.0 / 6.3 / 8.0 s | 2.15 / 4.1 / 7.4 s | 3.35 / 7.2 / 9.9 s |

The coldest case was a 12-hour gap: host boot 8.0 s, backend init 7.4 s, complete 9.9 s. The warmest burst ran every ~12 s: host boot 1.4-1.7 s, complete 2.0-2.1 s. Log resolution is 0.1 s; the durations come from the app's own `format_duration()` lines.

`python -X importtime -c "import voice_typer.server.app"`, 9 fresh serial processes: total median **200.38 ms** (199.55-225.64), 344 modules, wall including interpreter launch 257 ms; bare interpreter 46 ms. Self-time owner split (median per module): `voice_typer` **118.85 ms**, standard library **97.6 ms** (small overlap from repeated module names). Top self-time sites: `config._schema` 8.56 ms, `config` 8.28, `_ssl` 4.30, `translation.prompt` 2.49, `site` 2.26, `typing` 2.24, `gguf_model_registry` 2.08, `security.secret_patterns` 1.76. Top cumulative sites: `app` 200, `app_construction` 98.8, `config` 78.0, `config._lifecycle` 66.2, `_security_attributes` 60.7, `security.http_safety` 34.4, `win32_dacl` 31.0.

15 heaviest startup steps and their class:

| Phase | Windows measurement | Class |
| --- | --- | --- |
| Browser-plugin activation | 3.1 s median, 10.3 s at last boot (prepare 4.3 s) | wait / child process |
| Speech-synthesis server prewarm | 3.2 s median, 1.6 s at last boot | native launch / wait |
| Host boot → backend first log | 1.6 s warm, 3.0-8.0 s spaced | native + disk |
| Backend init → first log | 1.2 s warm, 2.15-7.4 s spaced | Python import + disk |
| Worker process spawn | 0.6 s median (0.4 s last boot; p95 22.8 s under load) | native process wait |
| Worker warm-import pass | 0.2-2.3 s (1.7 s at last boot) | disk read |
| scipy file warm | 0.5 s median (1.5 s at last boot) | disk |
| Config import graph | 78 ms cumulative | Python CPU |
| Security / TLS import graph | 60.7 ms cumulative | Python CPU + stdlib |
| Native denoiser preload | 0.4 s median | ONNX native load |
| VAD preload | 0.1 s median | ONNX native load |
| second denoiser preload | ≤0.1 s | ONNX native load |
| Worker socket connect | ≤0.1 s at last boot | wait |
| History database init | <0.1 s | SQLite C |
| `Config.load()` / flag reads | 1.03 ms / 21.5 ns per read | disk+JSON / Python CPU |

The owner's "check whether the user enabled X" suspicion does not hold: 17 flags × 200k iterations of real `getattr` cost 21.5 ns per read, ~0.37 µs for the whole set. The expensive part is importing the modules those flags gate (~130 ms cumulative of the 200 ms import).

Frozen-build startup: UNVERIFIED. No built executable exists in the release install paths; `AppData\Local\lausu\onefile-tmp` contains only unpacked runtime files, not a frozen app.

## A2 — hotkey → bubble visible, stop → text pasted

UNVERIFIED end-to-end. The live profile routes dictation to a browser plugin, has the overlay bubble disabled, and has no local engine loaded; driving the real Caps Lock hotkey and paste path would disturb other sessions here. The native runtime DLL sits outside the app bundle, so a real local-engine take cannot be driven through the shipped entry point in this checkout.

Measured pieces (real components): real `event_bus.publish` → real IPC `_send` into a StringIO sink: `bubble_show` 3.4 µs median (p95 3.8, max 49.1), `bubble_set_state` 3.6 µs, `bubble_level` 3.5 µs; loopback socket round trip 4.4 µs. Real `WaveformBubble.apply_visibility("recording")` → two publishes → two IPC sends: **7.9 µs** median (p95 8.9, max 87.8) — the cloud's 8.6 µs is confirmed on this machine.

To reproduce the missing number: run `npm run tauri:dev` with a scratch profile that sets `waveform_bubble=true` and a local engine, press Caps Lock, and timestamp `[HOTKEY] dictation`, the bubble publish, host WS frame arrival, renderer first paint, `[RECORDING] Audio stopped`, and paste dispatch.

Verdict: no evidence supports a Rust rewrite for this step. GPUI would replace the renderer half, but the Python half is microseconds and the WebView/host paint cost has not been measured on Windows; the GPUI decision needs that measurement, not a rewrite.

## A3 — whole-buffer copy

The worker streaming session starts only when the active transcriber reports `worker_backed=True` **and** the offline pack is present. Real gate result on this machine: `worker_path_for_backend(...) == (False, "offline_pack_missing")`. The code path is dormant in this profile but real for worker-backed local engines.

`_to_f32_bytes()` and `_push_bytes()` from `worker_streaming.py` were run with the real numpy code and a fake transport (only the outbound socket boundary is faked), 16 kHz float32, 0.5 s polls, 5 serial runs:

| Take | Whole-buffer copy | Delta-only copy | Push encode | Wall | Bytes copied |
| --- | --- | --- | --- | --- | --- |
| 30 s | 10.08 ms (p95 10.70 / max 11.18) | 0.152 ms | 7.34 ms | 17.7 ms | 55.8 MiB |
| 120 s | 148.08 ms (150.78 / 154.27) | 0.761 ms | 29.68 ms | 178.7 ms | 882.6 MiB |
| 480 s | **1909.7 ms** (1918 / 2592) | 19.18 ms | 166.5 ms | 2096.9 ms | 14,077 MiB |

GIL probe: a thread copying 30 MB in a loop while a 1 ms timer thread measured lateness, 2 s, repeated: median lateness 15.56 ms, p95 30.05 ms, max **37.72 ms**, 112/112 samples over 5 ms. Idle baseline: median 0.52 ms, max 0.93 ms, 0/1317 samples over 5 ms.

Other whole-buffer / quadratic patterns found:

| Location | What it does | Hot? |
| --- | --- | --- |
| `recording/recording_buffer.py:400` (`view()`) | `np.concatenate` of the whole take once the ring wraps | Per snapshot only after wrap; otherwise a view |
| `recording/recording_buffer.py:218`, `:361` | wrap-span and relocation copies | Bounded / one-off |
| `recording/recording_buffer.py:416` (`export_copy()`) | one owning copy at stop | Once |
| `recording/filter_divergence.py:255` | bounded pitch-buffer concatenate | Per chunk, bounded |
| `recording/session_state.py:304`, `recording/buffer.py:68` | `list(buffer)` | Legacy fallbacks only |
| `worker_streaming.py:43` | whole take to bytes at finalize | Once |
| `streaming.py:226` | recorder snapshot per window | Zero-copy view; bounded window |

## A4 — teardown wait

Real `Recorder.start()` → 1 s capture → `stop()` with a real audio device (the WASAPI candidate failed with `-9999` in this process, the MME device worked), 5 serial runs: stop wall median **17.3 ms** (p95 17.5, max 46.9). The app's own stop line reports stream 16 ms (max 46), concat 0 ms, resample 0-1 ms, total 17 ms. Start itself was 51.9 ms median (max 78.3).

Isolated real `StreamLifecycle.teardown_stream_body()` with a real `sd.InputStream` and a forced in-flight callback flag, 5 runs each: no callback in flight **55.97 ms** (real stop+close), callback clears after 10 ms **56.02 ms** (poll hidden inside stop+close), callback never clears **356.95 ms** (the 300 ms budget is added). Constants confirmed at `recording/stream_lifecycle.py:601,615` and `_audio_constants.py:77-78`.

The audit's "0.3 s + up to 2 s drain" is a worst-case bound. Normal Windows stops here pay no poll wait; the cost is PortAudio `stop()`/`close()`.

## A5 — resampler and noise gate

Real numpy/scipy, 5 runs × 62 chunks per shape, per-chunk wall (single-threaded; `thread_time` has 0 resolution on Windows, so wall is the CPU proxy):

| Shape | Per chunk | p99 | CPU per audio-second |
| --- | --- | --- | --- |
| 16→48 kHz upsampler (3/1), 512→1536 | 2.044 ms | 2.67 ms | 63.9 ms |
| 48→16 kHz downsampler (1/3), 1536→512 | 0.694 ms | 1.02 ms | 21.7 ms |
| Full 16→48→16 pair | 2.74 ms | 3.74 ms | 85.6 ms = **8.6% of one core** |
| 44.1 kHz pair (160/147 + 147/160) | 1.46 ms | 2.04 ms | 45.7 ms |
| Audit's exact 44.1→16 shape (160/441), 512→185 | 0.254 ms | 0.35 ms | 21.9 ms |

Resampler construction is 0.116 ms for the 16 kHz pair and 0.49 ms for 44.1 kHz. No speech WAVs ship in this repo (only scipy's own test files), so the gate frequency used synthesized numpy speech-like and chattery chunks; it is a real code-path measurement, not a real-recording measurement. The two denoiser models used by this path are on disk; the live profile has no suppressor enabled, so this cost applies when a neural suppressor is active, not in the current session.

Noise-gate scalar fallback with real `NoiseGate.process()`, 160 chunks per scenario: speech-like audio 0/160, chattery audio 0/160. The peak-hold level estimator smooths the input so a 512-sample chunk never exceeds the vector path's `max(4, n//32)` = 16 state runs. Calling `_state_machine_vector` directly with an alternating level array does delegate to the scalar loop once, so the fallback is reachable but not on ordinary `process()` input.

## A6 — idle

The 5-minute sample covered 60 five-second intervals. Listener PIDs were
confirmed from the sockets: port 56846 → PID 696 (sidecar), port 59792 → PID
26932 (worker). PIDs 18680 and 28484 are 2-thread parent shims, not the
listeners.

| Process | PID | Threads (median / max) | RSS MiB (median / max) | CPU % per 5 s interval (median / p95 / max) |
| --- | --- | --- | --- | --- |
| Tauri host | 9428 | 22 / 23 | 29.5 / 29.5 | 0.0 / 0.3 / 0.9 |
| Sidecar (listener) | 696 | **49 / 51** | 31.7 / 32.0 | 0.6 / 3.0 / 4.2 |
| Sidecar parent shim | 18680 | 2 / 2 | 1.1 / 1.1 | 0.0 / 0.0 / 0.0 |
| Worker (listener) | 26932 | 3 / 3 | 4.8 / 4.8 | 0.0 / 0.3 / 0.3 |
| Worker parent shim | 28484 | 2 / 2 | 1.1 / 1.1 | 0.0 / 0.0 / 0.0 |

Whole-machine CPU over the same window: median 11.05%, p95 23.1%, max 34.3%
(Chrome, other agents). The app itself is event/timer driven at rest, near zero
CPU. Sidecar RSS 31.7 MiB matches the cloud's 27.4 MiB import-only baseline;
there is no large Python heap at rest. The cloud's 20-35 thread estimate was
low: the real sidecar has 49.

Thread **names** are only partly observable: `GetThreadDescription` returned no
OS-level names for these processes, and Python's `threading.Thread.name` is not
readable from another process without in-process instrumentation. Per-thread
Python names are UNVERIFIED; thread counts are MEASURED.

## What the numbers justify

- No Rust rewrite of the text path, pipeline dispatch, IPC/event bus, history DB, config schema, startup imports or bubble publish. Their measured costs are microseconds to low milliseconds.
- Python work worth doing first: the worker whole-buffer copy (1.9 s CPU per 8-minute take when the path is active), and lazy imports for the ~130 ms config/security import share. The teardown poll only matters if a stuck callback is actually observed.
- The resampler inner loop is the only candidate with a real CPU share (8.6% of one core while a suppressor runs). A small native function could help, but it adds a build artifact to the frozen sidecar; measure the audio-thread p99 before deciding.
- The GPUI bubble is orthogonal to Python performance. The missing number is WebView/host paint latency on Windows, not backend time.

**Round 6 update (2026-11-27):** this is the pre-fix decision list. The
whole-buffer copy and resampler items are done (B1/B3 shipped, with byte/oracle
equivalence); the teardown poll and lazy imports were left alone (B2/B4), and
the ranked startup ideas (B5) were not implemented. After B3 a native resampler
is not worth its build cost; no Rust rewrite is supported. See "Round 6 fixes
and verdicts" above for the measured before/after and the reasons.

## UNVERIFIED

1. End-to-end hotkey → bubble visible and stop → text pasted (plugin-owned profile, bubble disabled, no local runtime bundle in the app path).
2. Real local-engine dictation timing for 5 s and 2-3 min takes; only the recorder/streaming path was driven with synthetic/real device audio.
3. Frozen-build startup (no built executable found).
4. WebView/host paint cost and therefore the GPUI decision.
5. Template-file matching with real templates was not re-measured here.
6. Per-thread Python names at rest (OS thread descriptions are empty; Python-level names need in-process instrumentation).

## Exact commands

All from `C:\Users\11\voice-typer`, serial, using `C:\Users\11\voice-typer\.venv\Scripts\python.exe`:

```
& .\.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\r6_imports.py
& .\.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\r6_copy.py
& .\.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\r6_audio.py
& .\.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\r6_audio2.py
& .\.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\r6_misc.py
& .\.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\r6_teardown.py
& .\.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\r6_startlogs.py
& .\.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\r6_idle.py > C:\Users\11\AppData\Local\Temp\opencode\r6_idle.jsonl
& .\.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\r6_idle2.py > C:\Users\11\AppData\Local\Temp\opencode\r6_idle2.jsonl
& .\.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\r6_idle_summary.py
& .\.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\r6_text.py
```


---

## Startup logs, translator preload and Rust/other levers (dated note 2026-11-28)

Plain English first. The owner's two real launches (2026-11-27 22:29 and 22:47,
internal-plugin profile) reach `Startup complete` in **3.1 s** and **2.3 s**.
The Rust host had already spent 2.0 / 1.8 s booting and Python spent 1.4 /
1.0 s importing before the first backend log. Nothing inside the Python startup
phases takes half a second; the only >=0.5 s steps are the native host boot,
Python import, the optional translator runtime load (12.1 / 15.3 s), and
plugin-only Chrome/WMI work that a normal end user never sees.

The translator's 12-15 s is **not** a new regression. The 1.31 GB GGUF was cold
in the OS file cache: Round 5 measured a cold read at 15.47 s (81 MB/s) versus
0.15 s warm, and spawn-to-health at 13.78 s cold versus 2.06-2.70 s warm. The
live `llama-server.log` for the 15.3 s launch shows `loading model` at +0.244 s,
tensor warnings at +1.028 s, the next line at +14.689 s and `model loaded` at
+14.858 s. The exact split between disk read and Vulkan upload inside that gap
is UNVERIFIED; no shader-cache file was found. The request asks for `-fa on`,
but this Vulkan device logs that flash attention is unsupported and disables it.

The owner's second launch had plugin activation 19.7 s with about 14 s outside
the instrumented stages, and `translation ready` landed in that same second.
That is correlation, not causation: the first launch had the same preload
(12.1 s) but only 2.6 s outside stages; the second launch's translator was only
3.2 s slower yet the gap grew by 11.4 s. The plugin activation thread and the
translator loader share no lock, and a live probe measured the plugin's
PowerShell WMI call at ~0.33 s both idle and with a translator load in flight.
The unaccounted time stays inside a chain of up to three
`Get-CimInstance Win32_Process` calls with 10 s timeouts in the dev-only plugin
path. Its exact content in launch B is UNVERIFIED.

### Startup timeline (owner logs, t0 = first backend log)

| Step | Launch A 22:29 | Launch B 22:47 | Class |
| --- | --- | --- | --- |
| Rust host boot -> backend first log | 2.0 s | 1.8 s | Rust host + native/disk |
| Backend spawn -> first log | 1.4 s | 1.0 s | Python import + disk |
| Banner / WS bind / auth / ready | <1 s | <1 s | Python CPU |
| VAD / GTCRN / DPDFNET load | 0.1 / 0.0 / 0.4 s | 0.1 / 0.0 / 0.6 s | native ONNX |
| History DB, native hotkeys, mic enumeration | <0.5 s each | <0.5 s each | C / native child |
| `Startup complete` | **3.1 s** | **2.3 s** | end of Python phases |
| Pack manifest / update 404 checks | background | background | network wait |
| Plugin profile prepared / Chrome launch | +5 s / +7 s | +17 s / +18 s | dev-only plugin |
| Plugin activation stages (daemon/status/prepare/total) | 3.2 / 0.0 / 2.8 / **8.6 s** | 3.1 / 0.0 / 2.6 / **19.7 s** | dev-only plugin |
| Translator spawn -> health | **12.1 s** | **15.3 s** | native child + disk/Vulkan |

Critical path for a normal end user (no plugin): host boot 1.8-2.0 s -> backend
import 1.0-1.4 s -> Python phases to `Startup complete` 2.3-3.1 s. A translator
load runs on a daemon thread after that marker; with Fast Startup on it is
ready about 2-3 s warm or 10-15 s cold later, and with Fast Startup off the wait
moves to the first user press. For the plugin profile, plugin usable was about
10.6 s (A) and 21.5 s (B) from Rust host start; in B the translator was ready
before the plugin, so plugin activation was the critical path.

### Translator preload A/B (real model, real runtime, serial)

Six arms were measured with scratch profiles/ports and the real 1.31 GB GGUF;
`Startup complete` was unchanged in every arm. Free RAM was low because other
sessions were active, so some arms needed a scratch-only guard bypass; those
are labelled *forced-guard* and measure load cost, not end-user guard behavior.

| Arm | Median `translation ready` | p95 / max | Notes |
| --- | ---: | ---: | --- |
| preload ON, guard passed (n=3) | **2.1 s** | 4.1 / 4.1 s | startup unchanged |
| preload OFF (n=4) | never loads | n/a | first dictation would pay the load |
| delayed 20 s, guard passed (n=2) | 2.6 s | 3.1 / 3.1 s | ready wall 24-25 s |
| delayed, forced-guard (n=3) | 16.7 s | 27.8 / 27.8 s | RAM pressure dominates |
| low priority, guard passed (n=2) | 2.35 s | 2.6 / 2.6 s | no plugin gain measured |
| low priority, forced-guard (n=3) | 2.6 s | 4.1 / 4.1 s | same |

Verdict: **no code change shipped.** Delaying or disabling the preload only
moves a 2-15 s load into the first dictation, which Round 7 proved loses the
translation when it happens after stop. Lowering priority slowed loading and
did not improve plugin activation. True cold-cache A/B, exact Vulkan share and
the plugin gap content remain UNVERIFIED.

### Rust / other levers for installer size, startup and loading

The Windows installer measured in CI (2026-11-22, before the migration) is
163.63 MB NSIS / 177.02 MB MSI. It contains a 128.23 MiB `ffmpeg.exe` and a
~119 MB frozen sidecar; the "worker 0.00 MB" gate row is a 63-byte local stub,
not the 117.82 MiB worker artifact from a separate job. The authoritative
onefile extraction measured 264.59 MiB of payload, of which SciPy 65.36 MiB,
retired Python media-decode libraries 64.91 MiB (stale in that build; already
gone from current source), ONNX Runtime 35.16 MiB, NumPy 26.07 MiB, and the
Python runtime + CRT + SSL/SQLite support 24.72 MiB.

| Lever | Expected saving | Verdict |
| --- | --- | --- |
| Rewrite some Python modules in Rust | **0 MB** - CPython stays in both onefiles | NOT WORTH IT |
| Retired Python media-decode dependency removal | ~25-35 MiB installer ESTIMATE; already in source | DO (verify with a real build) |
| Audio-only upstream ffmpeg build | ~45-75 MiB installer ESTIMATE vs 128.23 MiB measured | LATER (owner decision on build ownership) |
| Move ffmpeg/media deps to the runtime pack | ~55-75 MiB installer ESTIMATE | LATER (blocked: pack is not published) |
| Drop ONNX Runtime before a GGUF noise backend exists | ~16-21 MiB installer ESTIMATE, breaks default denoiser | NOT WORTH IT now |
| Deduplicate sidecar/worker frozen runtimes | 0 MB installer (worker not shipped); ~15-25 MiB on-disk ESTIMATE | LATER, not for installer |
| NSIS/MSI compression knobs | ~0 MB (NSIS already LZMA; WiX schema has no key) | NOT WORTH IT |
| Exclude unused stdlib/tests from freeze | <~2 MiB ESTIMATE, import risk in frozen build | NOT WORTH IT |
| Rewriting config/IPC/text/resampler in Rust | microseconds to 0.37% core, already fixed in Python | NOT WORTH IT |
| Native Win32 process enumeration instead of PowerShell WMI | ~0.3 s per call measured; up to 10 s timeout each, dev-only profile | LATER |

Installer savings are derived from a measured 0.45-0.59 raw-payload-to-installer
ratio; no installer was built in this round, and the CI sizes predate
ADR-0031 Phase 1, so a current-code build size is UNVERIFIED. The honest answer
to "would Rust help installer size or startup?" is **no** while any Python
remains: the bytes and the waits are native code, model files, disk and child
processes, not Python functions.
