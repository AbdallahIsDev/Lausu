Cloud audit; unverified in the sandbox: verified or corrected by docs/design/performance-measurements.md

# Rust migration audit — where the Python backend actually costs time

Read-only audit. Date 2026-11-27. Branch `arena/a1b1a30b-lausu`, base commit `ac9fd08`.
No source, test or settings file was changed; the only artifact is this document.

---

## 1. Plain-English summary (read this first)

The owner's idea was: rewrite the most-used Python parts in Rust and the app gets
faster. I measured what the Python backend actually spends time on, and the data does
**not** support a broad rewrite. It supports **one** rewrite, and even that is small.

What the numbers say:

- **The Python backend is not what makes a dictation feel slow.** The whole
  after-recording Python work that comes *after* the speech engine — text cleanup,
  vocabulary, templates, punctuation, the 11-stage dispatch, config checks, the history
  insert, the bubble message — adds up to **well under 1 millisecond** on a typical
  sentence (measured, §5.2). The waits a user feels are the speech model decoding, the
  optional `llama-server` translation, and first-time model/disk loading. None of those
  are Python.
- **Startup Python time is real but small and shrinking in importance.** Importing the
  whole app module graph is **~96 ms median** here (95.7 ms, spread 87.6–100.7 over 7
  runs), and ~115 ms including interpreter launch, on this machine. Of that, ~47% is
  our own code, ~47% is the Python standard library, ~6% is third-party. Rewriting the
  "most-used" functions in Rust cannot touch the standard-library half, and our half is
  mostly file/JSON/security setup that runs once.
- **The one genuinely bad thing I found is a full-buffer copy that grows
  quadratically.** `voice_typer/server/worker_streaming.py:229` converts the *entire*
  recording to bytes on **every** 0.5 s poll, then throws away everything it already
  sent. Measured: at a 480 s dictation that is **5.7 s of pure CPU** spent copying
  (≈1.2% of one core for the whole take, plus GIL contention that stalled other threads
  by up to 25 ms). The correct fix is a 3-line Python change (`[self._sent_samples*4:]`),
  not Rust. **Copying this logic into Rust would make the same mistake faster.**
- **The one candidate that is genuinely both hot and genuinely numpy-bound** is the
  streaming resampler used by the neural noise suppressors
  (`audio_filters/resampler.py:107`): a Python `for` loop doing one tiny `np.dot` per
  output sample. Proxy measurement: **~8 ms of CPU per second of audio** (≈0.8% of one
  core) at 44.1 kHz, and that is on top of the ONNX/RNNoise inference. Replacing that
  inner loop with native code gives a real, repeatable win — and it can be done as a
  tiny PyO3 function, not a rewrite of the audio stack.
- **The overlay bubble is not a Python bottleneck.** Pushing `bubble_show` +
  `bubble_set_state` from Python costs **~8.6 µs median** including the JSON encode and
  the socket write (§5.5). Everything visible happens in the Rust host + WebView, and a
  loopback TCP round trip is ~75 µs. Wiring GPUI would remove **none** of the measured
  Python cost, because there is none to remove.

Ranked recommendation (details in §7): do the resampler inner loop first (small, safe,
measurable), do *not* rewrite the dictation pipeline, text cleanup, IPC/WebSocket layer,
history DB, startup/config, clipboard or the bubble. The biggest actual win in this
audit is a 3-line Python fix, not Rust.

Everything I could not run on this machine is listed in §9 as UNVERIFIED, with the
exact commands in §10 so the same numbers can be reproduced on Windows.

---

## 2. What is already native today (the map)

### 2.1 Already Rust / native / not Python

| Component | Files | Size | What it does |
| --- | --- | --- | --- |
| Tauri host | `src-tauri/src/**` | 15,566 lines of Rust (+18,298 lines of Rust tests) | Owns the process, spawns the Python sidecar, connects to it over a localhost WebSocket, forwards commands (`dispatch`) and events, owns the tray, the main window and the **overlay bubble window** |
| Bubble window management | `src-tauri/src/commands/bubble/*.rs` | ~2,300 lines | Creates/shows/hides the bubble HWND, `WS_EX_NOACTIVATE` + `SW_SHOWNOACTIVATE`, message hooks, work-area clamp, drag persistence, level coalescing 60→30 Hz (`sidecar/bubble_coalesce.rs`) |
| Native hotkey listener | `src-tauri/resources/transcribe-cpp/` + `voice_typer/server/native/binaries.json` | C (`windows-key-listener.c`, `linux-key-listener.c`), Swift (`macos-key-listener.swift`) | A separate OS-level keyboard listener process. Python only spawns it and reads its stdout lines |
| ASR runtime | `transcribe-cpp` native bundle, driven through the worker | — (bundle is a release artifact; `src-tauri/resources/transcribe-cpp/` in this checkout is a `STUB.txt` placeholder) | GGUF whisper/parakeet/qwen inference — entirely native |
| Translation | `llama-server` subprocess (`voice_typer/server/translation/service.py:199+`) | — | All model work happens in a native `llama-server.exe`; Python builds a prompt and reads a response |
| VAD + noise suppression | ONNX Runtime (`voice_typer/server/vad.py:173`, `audio_filters/dpdfnet_backend.py`, `gtcrn_backend.py`, `rnnoise_ctypes.py`) | — | The inference itself is native (ORT / RNNoise C). Python does the framing, buffering and glue around it |
| ffmpeg decode | `voice_typer/server/media_ingest/` | — | Native binary, Python supervises |

So the three things that dominate a dictation — speech recognition, translation and the
overlay — are **already native**. What remains in Python is orchestration.

### 2.2 What is Python, by package (LOC)

Measured with `find … | xargs wc -l`, excluding vendored type stubs:

| Package | Files | LOC | Role |
| --- | --- | --- | --- |
| `voice_typer/server/` (product code) | 694 | **134,470** | The whole backend: recording, pipeline, IPC, config, history, hotkeys glue, tray, clipboard, translation glue, plugins, media ingest |
| `voice_typer/server/` (`test_*.py` inside the package) | — | 1,215 | In-package tests |
| `voice_typer/worker/` | 18 | **3,494** | The runtime-pack ASR worker process (a second Python process, thin: WS server + calls into the native runner) |
| `voice_typer/client/` (TypeScript/React renderer) | — | 194,350 TS/TSX | Not Python; the WebView UI |
| `tests/` | 1,250 files | 334,113 | Test suite |

Biggest server sub-packages, i.e. where the Python mass is:

| Sub-package | LOC |
| --- | --- |
| `recording/` | 7,863 |
| `service/` | 7,755 |
| `handlers/` | 5,733 |
| `history_db_internals/` | 4,179 |
| `model_providers/` | 3,803 |
| `ipc/` | 3,736 |
| `server_platform/` | 3,677 |
| `hotkeys/` | 3,424 |
| `security/` | 3,188 |
| `level_monitor/` | 3,103 |
| `audio_filters/` | 3,082 |
| `native_hotkeys/` | 2,928 |
| `media_ingest/` | 2,981 |
| `config/` | 2,797 |
| `dictation_pipeline/` | 1,998 |

The file that matters most for this audit, `recording/audio_pipeline.py`, is 574 lines;
the dictation pipeline package is 1,998 lines; the text-cleanup package is 1,257 lines.

---

## 3. How I measured (and what this machine could and could not run)

- Machine: Linux sandbox, CPython **3.11.2**, 1 vCPU class container, **no numpy, no
  scipy, no sounddevice, no onnxruntime, no websockets**, no Rust toolchain. So:
  * `numpy`-dependent modules (`recording/`, `audio_processor.py`, `audio_filters/*`,
    `filter_divergence.py`) **could not be executed**. I measured the Python overhead
    around them with faithful stand-ins and labelled everything a proxy.
  * Nothing was run against a real microphone, a real model or a real `llama-server`.
  * I did **not** run the full pytest suite (instructed), and I did not run any Windows
    measurement.
- Every reported number is the **median of ≥5 runs** (mostly 7–9, some 40–3,000 for
  micro-benchmarks), with min/max or p95 shown where the spread matters. The machine was
  **noisy** at times: single outlier runs up to ~35 ms appear in the micro-benchmarks
  (identical code, p99 vs median gap), so any number here that is within ~2× of another
  should be treated as the same number.
- `python -X importtime` figures are parsed from 7 fresh subprocesses. The per-module
  numbers below are the **median self time** (time in that module alone, children
  excluded) and **median cumulative**.
- The exact commands are in §10.

---

## 4. Measurement A — app startup

### 4.1 Whole-process startup, fresh subprocess, 7 runs each

| What | median | min..max |
| --- | --- | --- |
| bare interpreter (`-c pass`) | **7.5 ms** | 7.3..8.4 |
| `import voice_typer` | 14.8 ms | 14.5..15.4 |
| `import voice_typer.server` | 17.1 ms | 15.6..17.8 |
| `import voice_typer.server.ipc.entrypoint` (the sidecar's own import graph) | **67.1 ms** | 63.7..68.0 |
| `import voice_typer.server.app` (the full app graph) | **114.6 ms** | 111.1..123.1 |

`python -X importtime` on `voice_typer.server.app` alone: **median total 95.7 ms**
(87.6..100.7), 336 modules.

Split of that 94.5 ms of self time by owner: **voice_typer 44.8 ms (47%)**,
**standard library 44.2 ms (47%)**, **third-party 5.4 ms (6%)**.

That split is the single most important startup fact for this audit: half of the
startup cost is CPython's own import machinery and stdlib modules (`ssl`, `_ssl`,
`typing`, `enum`, `logging`, `http.client`, `email.*`). **No amount of Rust in our
package removes that half.** A Rust rewrite of our own modules can only attack the 47%.

### 4.2 Heaviest 15 imports / startup steps, what each does

`app` graph, median self / cumulative ms:

| # | Module | self | cum | What it is |
| --- | --- | --- | --- | --- |
| 1 | `voice_typer.server.config` | 4.21 | 31.35 | Config facade |
| 2 | `voice_typer.server.config._schema` | 4.07 | 13.69 | The dataclass schema: ~200 typed fields with defaults, built at import |
| 3 | `ssl` (stdlib) | 2.63 | — | Pulled in by `http.client` ← `urllib.request` ← security/URL allowlist |
| 4 | `_ssl` (C stdlib) | 1.82 | — | Actual TLS module load |
| 5 | `typing` (stdlib) | 1.76 | 7.14 | Imported by nearly everything |
| 6 | `voice_typer.server.translation.prompt` | 1.67 | — | Prompt template assembly |
| 7 | `enum` (stdlib) | 1.56 | — | — |
| 8 | `voice_typer.server.media_ingest.jobs` | 1.49 | — | Job manager |
| 9 | `voice_typer.server.gguf_model_registry` | 1.46 | 9.04 | Model catalogue |
| 10 | `ipaddress` (stdlib) | 1.46 | — | SSRF guard |
| 11 | `voice_typer.server.security.secret_patterns` | 1.33 | — | Redaction regex set |
| 12 | `logging` (stdlib) | 1.27 | 4.45 | — |
| 13 | `platform` (stdlib) | 1.16 | — | — |
| 14 | `concurrent.futures._base` (stdlib) | 1.16 | — | — |
| 15 | `voice_typer.server.security.http_safety` | — | 15.97 | URL allowlist / SSRF, imports `http.client` (10.9 ms cum) |

**"Check whether the user enabled X" work at startup**: the config object is built once
(a `Config.load()` with a real config file measured **1.17 ms** median, pure-defaults
1.06 ms), and individual enabled-flags are **free** afterwards (`getattr(config, "x")`
measured **93 ns**). So the "feature-flag checks" are not a startup cost — the cost is
*importing the modules those flags gate*. The two structural offenders are:

1. `config/_schema.py` + `config/_lifecycle.py` + `config_validators/*`: **~31 ms
   cumulative** just to have a config type.
2. `security/*` (via `_security_attributes` → `security.http_safety` → `http.client` →
   `ssl`): **~32 ms cumulative** to validate URLs and build a Win32 DACL that is only
   needed on Windows.

Both are pure-Python *setup* cost paid once at start. The cheap fix is lazy-importing
`security.http_safety`/`ssl` (a Python change), not Rust. A PyO3 extension exporting
"config schema" would save maybe 10–15 ms of a 96 ms import — and would add an extension
module to a Nuitka build that is currently pure Python, for a one-time cost paid per
process launch.

### 4.3 Startup cost that is NOT Python

Not measured here (no GPU, no models): ORT session build for VAD/GTCRN/DPDFNet
(`preload()` threads, `startup_sequence/_phases_early.py` — the GTCRN comment itself says
a synchronous `InferenceSession` build was "~23 s" cold), offline-pack check, model
weight load (74 MB tiny / 463 MB small / 2.4 GB parakeet), and worker spawn. The repo's
own recorded figures: worker startup **913 ms first run / 300 ms median**
(`bench/bench-baseline.json`), cold `llama-server` launch **15.4 s**
(`translation/service.py:57`).

**Conclusion for startup:** Python import is ~96–115 ms of a multi-second cold start
dominated by native loads and disk. A Rust rewrite of the top-15 import sites would
plausibly save 10–20 ms; the *risky* half (`config` schema) is exactly the half every
other module imports. **NOT WORTH IT** as a rewrite; worth doing as a Python lazy-import
cleanup.

---

## 5. Measurement B/C — the dictation hot path

### 5.1 What the pipeline is

`build_default_stages()` returns 11 stages in order:
`transcribe → empty_check → translate → clean → vocab → templates → punct → llm →
vocab_auto → store → paste` (`voice_typer/server/dictation_stages.py`).
Stages 1 (`transcribe`) and 3 (`translate`) are the native engine and the native
translator — both explicitly excluded by the brief.

**Dispatch overhead of the 11-stage design: median 4.8 µs total (0.4 µs/stage)** —
measured with every stage replaced by a no-op. The orchestrator is not a cost.

### 5.2 Every Python stage I could run, on realistic text

| Stage | Text | median | p95 |
| --- | --- | --- | --- |
| `text_cleanup.clean_transcribed_text` | 83 chars (typical sentence with "um/uh") | **0.072 ms** | 0.125 ms |
| same | 631 chars | 0.472 ms | 0.535 ms |
| same | 11 chars | 0.007 ms | 0.012 ms |
| `ai_enhancement` (fix_grammar + auto_punctuate + auto_capitalize) | 83 / 236 / 789 chars | 0.022 / 0.048 / 0.151 ms | ≤0.19 ms |
| `VocabularyManager.apply_to_text` (2 phrase rules, 4 word entries) | 79 chars | 0.015 ms | 0.057 ms |
| same | 535 chars | 0.057 ms | 0.089 ms |
| `TemplateManager.match` | no file loaded in sandbox | 0.000 ms | — (UNVERIFIED with real templates) |
| 8× `getattr(config, "…_enabled")` checks | — | 0.58 µs total | — |
| `history_db.add_transcription` (enqueue, async writer) | — | **4.1 µs** | 5.8 µs |
| `i18n.t()` | — | 0.3 µs | 0.4 µs |
| `waveform.apply_visibility("recording")` incl. 2 event publishes + socket writes | — | **8.6 µs** (first call 106 µs) | 40 µs |

Repo's own perf ratchet already encodes the same conclusion:
`bench_dictation_e2e.text_pipeline.total.p99_us = 1000` — a **1 ms p99 budget** for the
whole text pipeline, and my measurements land 10–100× under it.

**So: the entire Python text path of one dictation is ~0.1–0.5 ms.** Against a dictation
whose ASR decode is 1–30 s, this is 0.001–0.05%. Rust cannot win measurable time here.

### 5.3 Where the Python time in a dictation actually goes (and it is not the text)

Two places, both *around* the engine, both already known to the codebase:

1. **Stop → text pasted: a fixed 0.3 s + up to 2.0 s teardown**, not Python compute.
   `recording_lifecycle_stop.py:51-56` documents `recorder.stop()` as "~2.4 s worst case:
   300 ms stream-teardown poll + 2.0 s audio-worker drain + 2.0 s event-worker drain +
   np.concatenate + resample". The teardown poll is
   `time.sleep(min(_TEARDOWN_CALLBACK_POLL_INTERVAL_S, remaining))` with a **5 ms** poll
   interval and a **300 ms** budget (`_audio_constants.py:77-78`,
   `recording/stream_lifecycle.py:601,615`) — i.e. up to 60 wake-ups/s of sleeping, plus
   a drain deadline that is a hard cap. This is a **design/polling cost**, not a Python
   interpreter cost: a Rust version that still polls every 5 ms would be just as slow.
   Replacing the poll with an event is a Python change worth 0–300 ms.
2. **`np.concatenate` + resample of the whole take at stop** (single-digit ms for a
   typical take; grows with length). Native numpy, not Python loops.

### 5.4 The audio path, per second of audio

Chunking: **512 samples per callback** (`_audio_constants.py:26`), i.e. **31.25
callbacks per second** at 16 kHz (32 ms per chunk; the ADR-0009 budget is
"< 32 ms per chunk", and the repo's own ratchet allows up to **50 ms p99** at 16 kHz and
**60 ms p99** at 48 kHz — `bench/bench-baseline.json`).

Per-chunk Python work, measured where possible:

| Item | Measured | Note |
| --- | --- | --- |
| RT callback Python part (append + event set, ×31/s) | **21 µs per second of audio** (0.002% of a core) | numpy copy excluded; the copy is a memcpy of 2 KB |
| Pure-Python 512-output FIR (15 taps) — *if* the resample were a Python loop | 334 µs/chunk → **10.4 ms per second of audio** | proxy for "what a Python loop costs"; the real code uses numpy |
| `_StreamingResampler.process` (`audio_filters/resampler.py:107`), 512→186 outputs, one `np.dot` per output in a **Python `for`** | **0.255 ms/chunk → 8.0 ms per second of audio (≈0.8% of a core)** | proxy (sum-of-products instead of `np.dot`); numpy is unavailable here, so treat as **order-of-magnitude, UNVERIFIED exact** |
| `samples_chunk_count` | 210 ns | trivial |
| `chunk_samples(3 s audio)` (base64 + JSON per 720 KiB) | 0.616 ms | one-off at stop |

Two per-sample Python loops exist in the audio path, and I checked which of them runs on
a normal chunk:

1. **The streaming resampler** — `for j in range(count)` at
   `audio_filters/resampler.py:107`, one tiny `np.dot` per output sample. Runs on every
   chunk whenever a neural suppressor is active (`noise_suppressor.py:326`,
   `dpdfnet_backend.py:358-359`). This is candidate 1 in §7.
2. **The noise gate's scalar state machine** — `_state_machine_scalar` at
   `noise_gate.py:229` (the `for i in range(n)` at :246). It is **not dead code**: the
   vectorized twin `_state_machine_vector` (:312) delegates to it only when a chunk has
   more state runs than `max(4, n // 32)` (:326), and
   `tests/test_noise_gate_vector_equivalence.py::test_typical_chunk_uses_vector_path`
   asserts a typical speech chunk does *not* take the scalar path. So on ordinary audio
   the vector path runs and the scalar loop is a rare fallback (chattery gate input), but
   it is reachable. I could not measure either path (no numpy here), which is why it is
   ranked **LATER** rather than dismissed — see §9 item 1.

Every other filter (high-pass, EQ, compressor, limiter, notch) calls `scipy.signal`
(`sosfilt`/`lfilter`) or vectorized `np.maximum/minimum/where` — no Python per-sample
loop.

### 5.5 IPC / WebSocket throughput and latency for the bubble messages

Measured with a real `socket.socketpair` subscriber attached to the real event bus,
publishing the real message shapes (`ipc/sender.py:144` does
`json.dumps(..., separators=(",",":"))` + `write` + `flush`):

| Operation | median | p95 |
| --- | --- | --- |
| `event_bus.publish({"type":"bubble_show"})` → subscriber → socket write | **3.7 µs** | 25.5 µs |
| `event_bus.publish({"type":"bubble_set_state",…})` | **4.2 µs** | 25.9 µs |
| `event_bus.publish({"type":"bubble_level",…})` | **4.5 µs** | 25.5 µs |
| `json.dumps` of one bubble message | 1.9–2.3 µs | 2.8 µs |
| full `WaveformBubble.apply_visibility` (2 publishes) | **8.6 µs** | 40 µs |
| loopback TCP round trip, same wire shape | **75 µs** | 100 µs |
| `_validate_dict_payload` (per IPC command) | 0.79 µs | 0.92 µs |
| registry dict lookup | 120 ns | — |
| `event_bus.publish` with 1 / 4 / 16 / 64 subscribers | 0.67 / 0.67 / 1.58 / 5.15 µs | p99 ≤ 11 µs |

Repo ratchet agrees: `bench_ipc.push_throughput … publish_latency.p99_us = 5`,
`streaming_round_trip p99 = 10 µs`, `tcp_loopback p99 = 200 µs`.

**IPC is not a bottleneck at any rate the app produces.** Even the 125 Hz level stream
(`waveform_bubble_wiring.py:73`) costs ~0.6 ms of CPU per second at worst.

### 5.6 History DB, media ingest, clipboard — do they show up?

- **History DB**: `add_transcription` enqueue **4.1 µs**; a 3,000-row drain took 61 ms
  (**20 µs/row**); FTS5 `search` **0.50–0.56 ms**; `get_recent(50)` **0.41 ms**. The
  paste path does not wait on the writer (fire-and-forget queue, `crud_writes.py:33+`).
  Not significant, and it is SQLite (C) doing the work anyway.
- **Media ingest**: native ffmpeg + native ASR. Python is supervision. Not measured
  (no ffmpeg/audio here) — UNVERIFIED, but by construction it cannot be a Python-loop
  cost.
- **Clipboard/paste**: one `SendInput` batch via `ctypes` + a Windows clipboard write.
  `ctypes` call overhead measured **342 ns**; the real cost is the OS and the
  save/restore delay (`clipboard/restore.py:88`, `cb.time.sleep(delay)`), not Python.
  UNVERIFIED end-to-end (no Windows here).

### 5.7 The one real algorithmic defect: the whole-buffer copy in `worker_streaming`

`voice_typer/server/worker_streaming.py:229`:

```python
snapshot = self._recorder.snapshot()
raw = _np.asarray(snapshot, dtype=_np.float32).reshape(-1).tobytes()   # ENTIRE buffer
total_samples = len(raw) // 4
...
if total_samples > self._sent_samples:
    self._push_bytes(raw[self._sent_samples * 4 :])                    # ...sends only the tail
```

`snapshot()` is documented (and test-pinned) as a zero-copy **view** of the whole
recording (`recording_snapshot.py:91-118`, view contract at `:104-110`, `tests/test_recorder_snapshot_view.py`), so
the `tobytes()` allocates and copies the entire take **every 0.5 s poll**
(`worker_streaming.py:31`). Measured cost of exactly that copy (memcpy; numpy
`tobytes()` is the same memcpy):

| Recording length | polls | whole-buffer copy CPU | O(delta) equivalent | share of one core during the take |
| --- | --- | --- | --- | --- |
| 5 s | 10 | 0.9 ms | 0.12 ms | 0.02% |
| 30 s | 60 | 18.8 ms | 0.77 ms | 0.06% |
| 60 s | 120 | 69.2 ms | 1.45 ms | 0.12% |
| 120 s | 240 | 268 ms | 3.0 ms | 0.22% |
| 480 s | 960 | **5,692 ms** | 17 ms | **1.19%** |

It is quadratic in take length (a 480 s take does ~480× more copying than it needs: 14.8 GB
copied instead of 31 MB). And because the copy holds the GIL in chunks, it **stalls other
Python threads**: an idle thread's 1 ms timer slipped **max 25 ms** while another thread
repeated that 30 MB copy (baseline max 0.35 ms).

Consequence for this audit: **this specific hot spot should be fixed in Python, first,
before anything is rewritten.** Doing it in Rust would preserve the O(n²) copy.

---

## 6. Measurement D/E — idle cost

- **Threads**: 101 `threading.Thread(...)` construction sites and 138 distinct thread
  names in `voice_typer/server/` (75 `while True` / `while not …is_set()` loops).
  At rest the important periodic loops are: heartbeat **15 s**
  (`ipc/rate_limiter.py:205`, `ipc/lifecycle.py:270`), microphone watcher **12 s idle /
  3 s active** (`microphone_watcher/_core.py:38-39`), bubble-level pusher
  `queue.get(timeout=0.5)` (`waveform_bubble_wiring.py`), history retention **600 s**,
  worker reconnect backoff 0.5→30 s (`worker_client.py:30-31`). Rust host side: bubble
  reconciler **2 s**, renderer watchdog (`platform/renderer_watchdog.rs:111`).
  Nothing spins; the app is event/timer driven. I could not boot the real app here, so
  the **actual thread count at rest is UNVERIFIED** (estimate: 20–35 threads + the
  native listener + worker + llama-server when loaded).
- **RAM**: importing `voice_typer.server.app` in a fresh process peaks at **27.4 MB**
  RSS (bare interpreter 7.8 MB; `ipc.entrypoint` 21.9 MB; `sidecar_ws` 23.5 MB), median
  of 5. The repo's own ratchet allows **100 MB** for cold import
  (`bench_memory.cold_import.peak_rss_mb`), so the Python baseline is comfortable. Real
  idle RSS with a model loaded is dominated by mmapped model weights and the ORT arenas,
  not Python objects — for a Rust rewrite, the removable Python overhead is **roughly
  20 MB of interpreter + 27 MB of import graph**, i.e. ≤ ~30 MB, against a
  multi-hundred-MB-to-2.4 GB process. UNVERIFIED for the full app.
- **Idle CPU**: not measurable here (no mic, no ORT). The Python loops listed above are
  all sleeping timers; expected near-zero. UNVERIFIED.

---

## 7. Ranked candidates

Scoring: **frequency** (every dictation / every startup / rare) × **measured share** ×
**expected Rust gain** ÷ **risk**.

| # | Candidate | location, LOC | Frequency | Measured share | Integration | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Streaming resampler inner loop | `audio_filters/resampler.py:107` (the `for j in range(count)` block; ~10 lines of a 141-line file) | every chunk (~31/s) **when a neural suppressor is on** | **~8 ms CPU per second of audio** (≈0.8% of one core), proxy | PyO3 extension module (`_lausu_audio`), pure function: `(samples, taps, up, down, phase, hist) -> out`; Python keeps the state machine and falls back if the import fails | **DO FIRST** |
| 2 | *(not Rust)* `worker_streaming` whole-buffer copy | `worker_streaming.py:229` (and `:140` in `finalize`) | every 0.5 s **while recording**, worker-backed + streaming | up to **5.7 s CPU per 480 s take**, 25 ms GIL stalls | 1-line Python slice; no Rust | **DO FIRST (Python fix)** |
| 3 | Noise-gate scalar state-machine loop (`for i in range(n)`) | `audio_filters/noise_gate.py:229` (`_state_machine_scalar`, loop at :246) | **rare fallback** — only when a chunk has more runs than `max(4, n//32)`; `test_typical_chunk_uses_vector_path` pins the normal path to the vector twin | unmeasured (no numpy here) | a native kernel could serve both this and candidate 1 | **LATER** — only if Step 3's harness shows it firing on real office noise |
| 4 | Text cleanup + ai_enhancement + vocabulary + templates | `text_cleanup/*` 1,257 LOC, `ai_enhancement.py`, `vocabulary_apply.py` | every dictation | **0.07–0.5 ms total** | n/a | **NOT WORTH IT** |
| 5 | 11-stage pipeline dispatch | `dictation_stages.py` + `dictation_pipeline/*` 1,998 LOC | every dictation | **4.8 µs** | n/a | **NOT WORTH IT** |
| 6 | IPC / WS encode + event bus | `event_bus.py` 524, `event_bus_delivery.py` 217, `ipc/sender.py` 316, `sidecar_ws.py` 490 | every bubble message; 125 Hz levels | **3.7–8.6 µs per message**; 0.6 ms CPU per second at 125 Hz | n/a | **NOT WORTH IT** |
| 7 | History DB | `history_db.py` 514 + `history_db_internals/` 4,179 | every dictation (write), UI reads | **4.1 µs** enqueue, 0.5 ms search | n/a | **NOT WORTH IT** |
| 8 | Startup import graph | the 15 sites in §4.2, `config/*` 2,797 LOC, `security/*` 3,188 | every launch | **96 ms total**, of which ~45 ms is *our* code | would be a Python→PyO3 schema/config module | **LATER / mostly not worth it** — do the Python lazy-import first |
| 9 | Audio callback + ring buffer + VAD framing | `recording/capture.py` 467, `audio_pipeline.py` 574 | every chunk | **21 µs per second of audio** (Python part) | n/a | **NOT WORTH IT** |
| 10 | Bubble overlay render | `commands/bubble/*` (already Rust) + `waveform_bubble_wiring.py` 236 | every dictation | Python side **8.6 µs** | n/a | **NOT WORTH IT** (see §8) |
| 11 | Clipboard/paste | `clipboard/manager/*` ~900 LOC | every dictation | `ctypes` call 342 ns; cost is OS + a `time.sleep(delay)` | n/a | **NOT WORTH IT** |
| 12 | Config schema / validation → Rust | `config/_schema.py`, `config_validators/*` 2,127 | every start + every `set_config` | part of the 31 ms config import; `_validate_dict_payload` 0.79 µs per command | PyO3 or a Tauri-side schema | **LATER** (only if startup becomes a product goal) |

### 7.1 Candidate 1 in detail (the only DO-FIRST rewrite)

- **What**: `voice_typer/server/audio_filters/resampler.py:107-112`
  ```python
  for j in range(count):
      m = self._phase + j * down
      bank = self._banks[m % up]
      s  = (m - (m % up)) // up + base
      lo = s - len(bank) + 1
      out[j] = float(np.dot(bank, ext[lo : s + 1]))
  ```
  About 10 lines, inside a 141-line file, inside a 3,082-line package.
- **Why Rust helps here and nowhere else**: this is the one remaining place where a
  Python-level loop runs per output sample and calls a numpy function whose operands are
  ~28 floats. The numpy call overhead (argument parsing, dispatch, allocation of the
  slice view) dominates the arithmetic by an order of magnitude. Native code removes the
  per-sample interpreter dispatch entirely and can keep the FIR taps and history in
  contiguous memory.
- **Expected gain**: from ~0.255 ms/chunk to a small constant per chunk; realistically
  **5–10× on that stage**, i.e. ~7 ms CPU recovered per second of audio (≈0.7% of one
  core) while a neural suppressor is active. It does **not** make dictation feel faster;
  it makes the audio thread safer (less chance of missing the 32 ms chunk budget on a
  busy machine), which is the actual product risk.
- **Integration**: **PyO3 extension module**, not a helper binary and not the Tauri host.
  Reasons: (a) it is called ~31×/s per active suppressor from inside a Python object
  that owns state; a process hop would add ~50–300 µs per call (measured cross-thread
  hand-off: 55 µs median round trip, 55–310 µs for an `Event`-based wake), which is
  *worse* than the 255 µs it replaces; (b) the Tauri host runs in a different process
  from the sidecar and would need yet another socket hop; (c) PyO3 keeps the Python
  object model intact so tests that patch `_StreamingResampler` keep working.
  Ship a Python fallback and import the extension inside a `try/except ImportError`.
- **Frozen Windows build (Nuitka) + installer impact**: `scripts/build/build_sidecar_windows.sh`
  runs `python -m nuitka … "${NUITKA_ARGS[@]}"`. Adding a compiled extension means:
  (1) the CI build machine needs a Rust toolchain for the extension target (the Tauri
  build already needs Rust, so this is not a new dependency class, but it *is* a new
  build step and a new artifact); (2) the extension must be listed in the Nuitka
  `--include-package`/data-file set and in `MANIFEST.in`/`artifact_names.py`; (3) the
  wheel/`.pyd` must be signed and covered by the same integrity checks the app already
  applies to native binaries (`voice_typer/server/native/binaries.json` pattern); (4) the
  installer's "no extra runtime" story is unaffected (no new DLLs beyond the `.pyd`).
  Budget: a small, real build-system change — this is the main risk of the candidate.
- **Tests that protect the behaviour now**: `tests/test_noise_suppressor_resampler.py`,
  `tests/test_streaming_resampling_fixes.py`, `tests/test_concurrent_resample_safety.py`,
  `tests/test_audio_pipeline_vad_fir_cache.py`, `tests/test_audio_filters*.py`,
  `tests/test_worker_streaming.py` (12 tests) and
  `tests/test_worker_streaming_session.py` (17 tests) for the streaming consumers.
- **Parity test needed**: a golden-vector test — for a fixed set of
  `(up, down, input chunk, history)` cases, assert the Rust output equals the Python
  output to **bit-identical float32** (not "close"), plus a property test that
  `sum(in) vs sum(out)` sample counts match the existing length contract
  (`_in_total`, `_out_total`, phase carry), plus a long-run drift test over 10,000
  chunks. Add a benchmark test that fails if the native path is slower than the Python
  one.
- **Risk**: medium-low algorithmic risk (the math is simple and already documented),
  medium build risk (new compiled artifact in a frozen Windows pipeline). Do not change
  `audio_filters/noise_suppressor.py`'s framing, carry, or fallback logic.

---

## 8. The overlay bubble: what Python does, and would GPUI help?

### 8.1 How the bubble is shown today

1. **Python decides.** `WaveformBubble.apply_visibility(state, reason)`
   (`waveform.py:66`) is the single visibility policy; it decides visible/hidden from
   `bubble_behavior` and the state, then calls `show(force=True)` + `set_state(state)`
   (`waveform.py:104`, `:141`).
2. **Python publishes a JSON line.** The listeners installed by
   `waveform_bubble_wiring.py` (`_push_bubble_show` at :63, `_push_bubble_set_state` at
   :152) call `event_bus.publish({"type": "bubble_show"})` etc. `event_bus.publish`
   (`event_bus.py:438`) fans out to the IPC server's `push` (`ipc/sender.py:99`), which
   `json.dumps` + `sendall`s one line (`ipc/sender.py:144`).
3. **The Rust host receives and shows.** `src-tauri/src/sidecar/ws` reads the frame,
   `wants_bubble_show()` (`commands/bubble/window.rs:21`) matches `bubble_show`, and
   `show_bubble_window()` (`window.rs:175`) applies `WS_EX_NOACTIVATE` +
   `SW_SHOWNOACTIVATE`, clamps to the work area, calls `window.show()`, force-presents if
   tao's tracked flag disagrees, and re-applies chrome hardening.
4. **The WebView renders the pill.** The `bubble` window is declared in
   `src-tauri/tauri.windows-x86_64.conf.json` as `visible: false`, `transparent: true`,
   `alwaysOnTop: true`, `skipTaskbar: true`, and the React bubble UI in the renderer
   paints the pill from the same event stream.
5. Levels are throttled twice: Python to ~125 Hz (`waveform_bubble_wiring.py:73`), then
   the Rust host coalesces 60→30 Hz (`sidecar/bubble_coalesce.rs`).

### 8.2 Python vs webview share of "hotkey → bubble visible"

Measured Python share of the whole chain:

| Step | Measured |
| --- | --- |
| decide + publish `bubble_show` + publish `bubble_set_state` (incl. 2× `json.dumps` + 2 socket writes) | **8.6 µs median** (40 µs p95) |
| worst realistic extra: the log line at INFO with a file handler | **+6.4 µs per line** (measured 3.2 µs with no handler, 6.4 µs with a real `FileHandler`) |
| kernel loopback transport floor | 75 µs round trip (one-way is less) |

So **Python contributes single-digit microseconds to a latency that the user perceives
in tens to hundreds of milliseconds.** The rest is: the native listener's line write and
Python's reader thread (one cross-thread wake-up, measured 55 µs median / 310 µs for a
condition-variable hand-off), then the Rust host's window show (a Win32 `ShowWindow` +
DirectComposition present), then the WebView's first paint of the pill.

I could not measure the Windows-side show/paint path in this sandbox: **the "hotkey →
bubble visible" end-to-end number is UNVERIFIED**, and it is the only number that would
justify work here. The correct next step is a *measurement* on Windows (log timestamps at
`[HOTKEY] dictation`, `apply_visibility`, the WS frame arrival in the host, and the
renderer's first paint), not a rewrite.

### 8.3 Would the (unwired) GPUI bubble remove the bottleneck?

**No — not on the evidence available.** The GPUI prototype
(`tools/overlay-gpui/`, 373 lines of Rust) would replace step 4/5 (the WebView pill) with
a native GPU-rendered window. That can plausibly remove *WebView* cost (window creation,
JS bundle load, first paint, per-frame compositing) — but:

- The Python cost it might remove is **8.6 µs**, i.e. nothing.
- The measurement that would justify GPUI (WebView first-paint + per-frame cost on
  Windows) has **not been taken** here and is not in the repo.
- `docs/design/gpui-overlay.md` already documents the real blockers
  (no always-on-top / transparency / hit-test fields in GPUI `WindowOptions`, AccessKit
  gaps, mixed-DPI bugs) and recommends "a local spike, not a go decision". Nothing in my
  measurements changes that conclusion.

Verdict: **GPUI is orthogonal to the Rust-migration question in this audit.** It is a
renderer-choice/binary-size/accessibility question, not a Python-speed question. Do not
wire it on the strength of "the backend is slow" — the backend bubble path is not slow.

---

## 9. UNVERIFIED list (do not treat these as facts)

1. **No numpy/scipy/onnxruntime/sounddevice in this sandbox** → the real per-chunk cost
   of `audio_processor.process_chunk`, `FilterChain.process`, `noise_gate._scan_gate_state`
   **and `noise_gate._state_machine_scalar`** (the reachable fallback in §5.4),
   `noise_suppressor` (RNNoise 480-sample loop, GTCRN hop loop), `filter_divergence`, and
   `resampling.resample_audio` were **not** measured. The 8.0 ms/s figure for
   `_StreamingResampler` is a stand-in (sum-of-products instead of `np.dot`) and should be
   re-measured; the real number may be 2–4× different in either direction.
2. **No real template file loaded** → `TemplateManager.match` measured 0.000 ms with an
   empty manager. With real templates it is still bounded by one regex/regex-alternation
   pass, but the number is unmeasured.
3. **No Windows measurements at all** — no real `SendInput` paste, no real `ShowWindow`
   bubble show, no real Nuitka build, no MSVC Rust toolchain, no `.pyd` load. The
   build-system impact in §7.1 is a *reasoned* impact, not a measured one.
4. **End-to-end "hotkey → bubble visible"** (the number that would justify GPUI or a
   host-side change) is unmeasured.
5. **Idle CPU and idle RAM of the running app** (with models loaded, tray, dashboard) are
   unmeasured; only the import-time baseline (27.4 MB) is measured.
6. **The real thread count at rest** is unmeasured (101 construction sites / 138 distinct
   names counted statically; est. 20–35 live).
7. **Everything about ASR and translation latency** is taken from the repo's own records
   (`bench/bench-baseline.json`, `docs/design/translation-chunking.md`,
   `translation/service.py:57`), not re-measured.
8. The 480 s simulated recording in §5.7 assumes 16 kHz float32 throughout; a real
   native-rate (48 kHz) device would store more bytes, so the copy cost is a lower bound
   if the processor is not resampling every chunk.
9. Machine noise: the benchmark container showed p99/median gaps of ~10× on
   micro-benchmarks; several numbers here are within 2× of each other and should be
   considered equal.

---

## 10. Exact commands used (so the numbers can be repeated)

All run from the repo root, CPython 3.11.2, Linux; medians computed with
`statistics.median`.

```bash
# --- startup: whole-process wall clock, 7 fresh subprocesses each (scripted in /tmp/m_meta.py)
python3 -c "import time,subprocess,sys,statistics; ..."   # /tmp/m_meta.py
# --- import graph (§4.2), 7 runs, parsed with the regex below
for i in $(seq 7); do python3 -X importtime -c "import voice_typer.server.app" 2>&1; done
#   parser regex:  import time:\s+(\d+)\s*\|\s*(\d+)\s*\|\s*(.+)$   # /tmp/parse_imp.py, /tmp/m_split.py
python3 -X importtime -c "import voice_typer.server.ipc.entrypoint"     # /tmp/m_entry.py
python3 -X importtime -c "import voice_typer.server.sidecar_ws"

# --- RSS (§6)
python3 -c "import voice_typer.server.app,threading; [print(l.strip()) for l in open('/proc/self/status') if l.startswith(('VmRSS','VmHWM'))]"   # /tmp/m_rss.py

# --- dictation text stages (§5.2)
python3 /tmp/b_clean.py          # text_cleanup.clean_transcribed_text, 4 text lengths, 60 iters
python3 /tmp/m_ai.py             # ai_enhancement 3-step
python3 /tmp/m_vocab2.py         # VocabularyManager.apply_to_text
python3 /tmp/m_stages.py         # 11-stage dispatch with no-op stages
python3 /tmp/m_cheap.py          # i18n.t, config attr read, samples_chunk_count, chunk_samples
python3 /tmp/m_httpload.py       # 8 config "_enabled" reads
python3 /tmp/m_hist.py           # history add/flush/search/get_recent (3000 rows)
python3 /tmp/m_log.py            # logging cost per line, no handler vs FileHandler

# --- IPC (§5.5)
python3 /tmp/m_publish2.py       # event_bus.publish -> socket sendall, 3 message shapes
python3 /tmp/m_bubble.py         # wavebubble.apply_visibility end to end
python3 /tmp/m_tcp.py            # loopback TCP round trip
python3 /tmp/m_validate.py       # _validate_dict_payload, registry lookup
python3 /tmp/run_ipc.py          # reuses bench/bench_ipc.py functions (auth/push/streaming/rate-limit)
python3 bench/bench_ipc.py       # NOTE: crashes here at the TCP step (socketpair has no TCP_NODELAY)

# --- the worker-hop encode/decode (§5.7)
python3 /tmp/m_memcpy.py         # memcpy throughput
python3 /tmp/m_delta2.py         # whole-buffer vs O(delta) copy, 5..480 s, 0.5 s polls
python3 /tmp/m_roundtrip.py      # full base64+JSON encode + decode round trip, 5..480 s
python3 /tmp/m_hop.py            # encode-only per audio length
python3 /tmp/m_gil.py            # cross-thread scheduling delay during 30 MB copies
python3 /tmp/m_hop2.py           # python->thread->python hand-off (RoundTrip)
python3 /tmp/m_cp.py             # Event.wait wake-up + ctypes FFI call cost

# --- audio-path stand-ins (§5.4)
python3 /tmp/m_cb.py             # RT callback Python part, 31 callbacks/s
python3 /tmp/m_resample_proxy.py # pure-Python 512-output FIR
python3 /tmp/m_dot.py            # _StreamingResampler per-output loop proxy

# --- config (§4.2)
python3 /tmp/m_cfg2.py           # Config.load with a real config.json vs defaults
```

Repo scripts I deliberately used as reference ratchets rather than re-running:
`bench/bench-baseline.json` (budgets), `bench/bench_memory.py`, `bench/bench_ipc.py`,
`bench/bench_dictation_e2e.py`, `bench/bench_audio_filter_chain.py`,
`bench/COLDSTART_REPORT.md`, `docs/design/gpui-overlay.md`, `docs/adr/0009-*.md`,
`docs/adr/0024-*.md`, `docs/adr/0025-*.md`.

Not run, on purpose: the full pytest suite (heavy runs would distort the timings and it
was explicitly out of scope), any Windows build, any model download.

---

## 11. Proposed order: one area per night

Each step is small, reversible, behind a flag, behaviour-identical, and has a parity test.
Step 0 and step 1 are Python-only and should happen regardless of the Rust question.

**Step 0 (night 1) — Python, not Rust: fix `worker_streaming` O(n²) copies.**
`voice_typer/server/worker_streaming.py:229` and `:140`: slice the delta off the
snapshot *before* converting, or keep a per-chunk byte buffer. Guard: does not change what
bytes are sent (identical payload sequence), so parity = existing
`tests/test_worker_streaming.py` (12) + `tests/test_worker_streaming_session.py` (17) +
`tests/test_worker_samples_atomic_send.py` + a new test asserting that the total copied
bytes scale linearly with audio length. Expected: up to 5.7 s CPU per 480 s take, fewer
GIL stalls.

**Step 1 (night 2) — Python: replace the 5 ms teardown poll with an event.**
`recording/stream_lifecycle.py:601,615` + `_audio_constants.py:77-78`. Keep the 300 ms
budget as the *timeout* only. Guard: flag `VOICE_TYPER_TEARDOWN_EVENT_WAIT=1`, default
off for one release. Tests: `tests/recording/test_recorder_start_critical_path.py`,
`tests/test_recorder_snapshot_view.py`, `tests/test_audio_pipeline_*`. Expected: 0–300 ms
off every stop.

**Step 2 (night 3) — Python: lazy-import `security.http_safety` / `ssl` and split the
config schema import.** Expected 15–30 ms off startup. Tests:
`tests/test__security_attributes.py`, `tests/test_ipc_*`, `tests/test_config*`.

**Step 3 (night 4) — Rust, the only real rewrite: resampler inner loop as a PyO3
extension** (`_lausu_audio.streaming_resample`), with the Python implementation kept as
the default and the native path behind `VOICE_TYPER_NATIVE_RESAMPLER=1` (default off in
the first release). Parity: golden float32 vectors + a 10,000-chunk drift test + the
existing resampler/noise-suppressor tests. Extend the Nuitka build to ship the `.pyd`
and add it to the integrity manifest. Expected: ~5–10× on that stage, ~7 ms CPU recovered
per second of audio with a neural suppressor active.

**Step 4 (night 5+) — stop.** Do not proceed to text cleanup, IPC, history, startup
rewrites. Re-measure on Windows first: if the "hotkey → bubble visible" and "stop → text
pasted" numbers are still dominated by WebView/host work, that is a *host* question, and
the GPUI decision belongs to `docs/design/gpui-overlay.md`, not to a Python rewrite.

### Rules a rewrite prompt must contain

1. **No behaviour change.** Same inputs → same outputs, byte-identical where the data is
   bytes (float32 audio, JSON envelopes, event names/order). The only accepted behaviour
   changes are *listed real bugs*; enumerate them explicitly, with the test that proves
   the old behaviour was wrong.
2. **Public interfaces stay.** No renamed functions, no changed signatures, no changed
   module paths, no changed log lines/messages (tests and log-contract checks resolve
   them), no changed thread names, no changed event types
   (`event_bus.EVENT_TYPES` and the Rust `ALLOWED_EVENT_TYPES` must keep agreeing).
3. **The existing tests must stay green without edits.** If a test needs changing, the
   rewrite is wrong (or the test change must be justified line-by-line in the PR).
4. **Never weaken a test.** No skips, no loosened tolerances, no `pytest.mark.xfail`
   without an expiry date, no deleting assertions, no `--no-verify`.
5. **Always keep a working Python fallback**, selected by a flag, default = current
   behaviour, and the fallback must be exercised by at least one test.
6. **Same concurrency contract.** Same thread names, same locks, same lock order (see
   `tests/test_lock_order_contract.py`), no new blocking on the RT audio callback, no GIL
   assumptions that stop holding.
7. **Same failure modes.** A failing native call must degrade exactly as the Python code
   does today (e.g. a resampler failure drops the chunk and logs at the same level), not
   raise a new exception type.
8. **Measured, not asserted.** The PR must show a before/after measurement on the target
   platform with the same harness, medians of ≥5 runs, and must show the p99 (not just the
   median) for anything on the audio thread.
9. **Build-system changes are part of the task**: Nuitka flags, `MANIFEST.in`,
   `artifact_names.py`, the binary integrity manifest, and the installer all updated in
   the same PR, or the PR is not mergeable.
10. **No new runtime dependency** in the shipped app beyond the single compiled artifact;
    no network, no Cargo workspace restructure, no changing the existing GNU dev
    toolchain (`AGENTS.md` C-TDEV-1).

---

## 12. Final report to the owner (plain English)

**The idea, tested.** Rewriting the most-used backend parts in Rust will *not* make the
app noticeably faster, because the parts that run most often are already cheap or already
native. The speech engine, the translator and the overlay are native. The Python that
remains is orchestration measured in **microseconds and sub-milliseconds per dictation**.

**Top 5 candidates, with the numbers:**

1. **Streaming resampler inner loop** — `audio_filters/resampler.py:107`, ~10 lines.
   Python `for` + one tiny `np.dot` per output sample. **~8 ms CPU per second of audio
   (~0.8% of a core)** while a neural noise suppressor is on (proxy measurement). A
   PyO3 function is the right shape. **DO FIRST** (but it is a CPU-safety win, not a
   felt-latency win).
2. **`worker_streaming` whole-buffer copy** — `worker_streaming.py:229` (and `:140`).
   Copies the *entire* recording every 0.5 s to send only the new tail. **5.7 s of CPU on
   a 480 s take; 25 ms stalls of other Python threads.** Fix in **Python, one line** —
   this is the single biggest real win in this audit and Rust would only make the wrong
   algorithm faster.
3. **Text cleanup + grammar + vocabulary + templates** — 0.07–0.5 ms for a typical
   sentence, 0.47 ms even at 631 characters. **NOT WORTH IT.**
4. **IPC / event bus / WebSocket encode** — **3.7–8.6 µs per bubble message**, 0.6 ms CPU
   per second at the 125 Hz level rate. **NOT WORTH IT.**
5. **Startup imports** — **96 ms** of import time; ~47% of it is CPython's own stdlib,
   ~6% third-party, ~47% ours (config schema ~31 ms, security/SSL ~32 ms cumulative).
   A Rust config/schema module might save 10–15 ms of a multi-second cold start that is
   dominated by model and ORT loading. **LATER / mostly not worth it** — fix it with
   Python lazy imports first.

**What I recommend NOT rewriting, and why:**

- **The dictation pipeline** (`dictation_pipeline/`, 1,998 LOC): 11-stage dispatch is
  **4.8 µs**; each stage is sub-millisecond. Rewriting it would be a large, risky change
  for a rounding error.
- **Text cleanup / vocabulary / templates** (1,257 + ~500 LOC): under 1 ms total.
- **IPC / event bus / sidecar WS** (`event_bus*`, `ipc/`, `sidecar_ws.py`, ~1,800 LOC):
  microseconds per message, far below any rate the UI produces.
- **History DB** (`history_db*`, 4,693 LOC): 4 µs enqueue, 0.5 ms search, and SQLite (C)
  does the actual work.
- **Startup/config/security** (5,985 LOC): half the cost is the standard library, and the
  rest is one-time setup.
- **Clipboard/paste**: the cost is the OS and a deliberate restore delay, not Python.
- **The bubble**: Python contributes **8.6 µs**; everything the user sees is the Rust
  host + WebView. **The GPUI bubble would not remove a bottleneck**, because there is no
  measured Python bottleneck to remove — and `docs/design/gpui-overlay.md` already says
  the GPUI decision needs a local spike for window/DPI/a11y reasons, not for speed.

**Proposed first area:** not a rewrite at all. **Night 1: fix the O(n²) copy in
`worker_streaming.py`; Night 2: replace the 5 ms teardown poll with an event; Night 3:
lazy-import `security.http_safety`/`ssl`; Night 4: the resampler as a PyO3 extension
behind a flag with the Python fallback.** After that, stop and re-measure on Windows —
specifically the two unmeasured numbers that would actually justify more work:
**hotkey → bubble visible** and **stop → text pasted**.
