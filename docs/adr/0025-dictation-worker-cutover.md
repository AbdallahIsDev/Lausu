# ADR 0025: Dictation cutover to the runtime-pack worker

## Status

Accepted (design + implementation plan, 2026-09-26). Closes the SCOPE
FINDING recorded in ADR-0024 Step 7. **Implementation status 2026-09-27:**
C1–C7 are code-complete in-tree (all four sites, C6 worker streaming
session, C7 engine move + `WorkerBackedAsr` + Nuitka ASR exclusions).
Unit-level cutover is verified (127 focused tests + slim-ML ratchet 0);
the remaining host/CI gates are listed in
`docs/code-notes/dictation-worker-cutover-status.md`. **No production
behaviour changes shipped until those host gates pass.**

## Context

ADR-0024 verified the worker hop end to end (`scripts/verify_worker_handoff_live.py`,
including `--respawn`: `RESULT_OK=True`, text byte-identical to the Step 0
in-process baseline on both the original and the replacement worker).
What the hop does NOT yet do is carry the live dictation path. Four
slim-core call sites still obtain the in-process `TranscriptionEngine`
through `app.models.active_transcriber()` and therefore still import
`faster_whisper` / `ctranslate2` in the sidecar process:

| # | Site | What it needs from the engine |
|---|------|--------------------------------|
| 1 | `voice_typer/server/dictation_pipeline/transcribe_step.py:98` | `transcribe_with_fallback(audio, audio_stats=, local_engine=)`, `device_info`, `clear_abort`/`request_abort`, and the `session.finalize(audio)` streaming branch |
| 2 | `voice_typer/server/dictation_pipeline/orchestrator.py:67` | `request_abort()` only (cancel path) |
| 3 | `voice_typer/server/streaming_session_coordinator.py:83,104` | `transcribe_words` word-level timestamps; builds `StreamingTranscriptionSession(transcriber=active, ...)` whose overlap/tail-dedup design is documented in `docs/duplicated-text.md` |
| 4 | `voice_typer/server/media_ingest/engine_loop.py:76` | `transcribe_with_fallback(audio)` per 30 s window, plus `request_abort()` on cancel, with progress callbacks and a resumable `WindowsState` |

The current worker contract is `transcribe_offline {audio_path,
sample_rate, language}` -> `transcribe_offline_result {text, latency_ms}`
(`voice_typer/worker/_ws_server.py:392`, `voice_typer/server/worker_client.py:73`).
Four properties of that contract are insufficient for the sites above:

1. **In-memory audio.** Sites 1, 3 and 4 pass numpy arrays, not file
   paths. `transcribe_offline` takes `audio_path` only.
2. **No id echo.** The worker does not echo the request `id`
   (`_ws_server.py:392`), so `route_frame` can only route by frame
   `type` (`worker_client.py:73-87`). Two in-flight requests cannot be
   told apart; today that is masked because only one request is ever
   outstanding.
3. **No streaming/word timestamps.** Site 3 needs word-level timestamps
   and the stateful overlap/tail dedup that lives in
   `voice_typer/server/streaming.py`. A whole-file request/response
   cannot express a stateful per-window assembler.
4. **No abort, no device info.** Sites 1/2/4 abort mid-inference;
   site 1 renders `active.device_info`.

`active` may also be a `CloudEngine` (`transcribe_step.py:143,174`), a
network provider under C-DATA-1. Cloud backends must keep their
in-process path; only LOCAL backends (whisper / parakeet / qwen) move.


## Decision

### 1. Scope: all four sites, cut in dependency order

All four move, but NOT together. Site 3 is the long pole and the only
one that blocks the slimming, because `transcribe_words` is what pins
`faster_whisper` into the sidecar. Order (each step gated on the
previous being green and evidenced):

- **C1 - id correlation (additive, no behaviour change).** Worker echoes
  the request `id` on the result; `WorkerClient` routes by `id` and
  falls back to type-routing when `id` is absent, so an older worker
  still works. Backward compatible with the frozen
  `transcribe_offline_result` shape (the `id` is a sibling of `type`,
  exactly like every other frame in the hop).
- **C2 - sync bridge.** `WorkerClient.request_transcribe(audio_path, ...)`
  returns a `Future`-like handle resolved by the `id` router, with a
  bounded timeout and a cancel hook. Reuses the EXISTING single client
  and the EXISTING `worker_pending` queue (E7: no second store, no
  second queue).
- **C3 - in-memory audio command.** New additive worker command
  `transcribe_samples` carrying base64 float32 PCM + sample rate,
  reusing `WorkerTranscriber`. Chosen over temp-file materialization
  because a 30 s window is ~1.9 MB of float32, already materialised in
  RAM, and a temp file per window adds a disk round-trip plus a cleanup
  obligation. Base64 adds ~33% over the 1 MiB frame cap, so the command
  is chunked at 1 MiB of raw PCM and the worker reassembles before
  inference.
- **C4 - abort + device_info.** New additive `abort_request {id}`
  command; `device_info` is folded into the result payload as an
  optional field so the frozen `transcribe_offline_result` keys stay
  intact.
- **C5 - site 1 + site 4 + site 2 cutover** (dictation batch, media
  windows, cancel). Behind a fallback: the in-process engine runs if
  the worker path is unavailable or returns an error.
- **C6 - site 3 streaming cutover** (the blocker). New additive
  `streaming_session_open` / `streaming_session_push` /
  `streaming_session_finalize` commands, with the window planner,
  overlap dedup and tail merge MOVED into the worker (they already live
  in `voice_typer/server/streaming.py`; the slim core stops constructing
  `StreamingTranscriptionSession` and instead subscribes to the
  `transcription_partial` pushes it already publishes via
  `_publish_eligible`).
- **C7 - remove the in-process engine** (E15) and only then flip the
  ratchet baseline down and add the Nuitka exclusions (ITEM 3).

### 2. Fallback policy

The in-process path stays live as a FALLBACK through C5-C6 and is
deleted at C7. A request takes the worker path only when: a pack is
present, the worker client is connected, AND the local backend is not a
`CloudEngine`. Any of those failing falls back to the in-process engine
and logs one rate-limited line. A worker crash therefore degrades
latency, never correctness.

### 3. model_manager registry surface

`app.models.registry` stays in the slim core and keeps owning: backend
selection, tray status, the busy flag, and idle-unload bookkeeping.
What it must STOP doing is instantiating a real ASR backend
(`AsrBackendRegistry.load_with_fallback` -> `TranscriptionEngine`).
C7 replaces the loaded-backend object with a thin `WorkerBackedAsr`
shim exposing `transcribe_with_fallback`, `request_abort`,
`clear_abort`, `device_info`, `is_loaded`, `load`/`unload` by
forwarding to the worker hop. It deliberately does NOT expose
`transcribe_words`: word-level streaming goes through the C6 worker
session, and the coordinator branches on `isinstance(active,
WorkerBackedAsr)` (not a duck-typed flag read, which MagicMock doubles
would defeat). Callers keep their code unchanged
(`active_transcriber()` still returns something with the same surface)
and the cutover stays confined to one new module. `device_info` is
answered by C4 (refreshed from each result, `"pack worker"` before the
first one). Worker failure raises `WorkerTranscriptionError` (never
silent `""`); user cancel propagates as `WorkerAbortedError` so the
pipeline's cancelled-cycle path owns the UX.

### 4. C6 latency budget (decision)

A streaming window must finish before the next one is due, or lag
accrues without bound. The cadence is `step_seconds` (default 5 s);
the per-window cost is framing + WS + one inference slice over a
`chunk_seconds` (default 12 s) window. Audio crosses the hop ONCE
(pushes append to the worker-side buffer; windows are sliced
worker-side), so there is no per-window re-transfer.

Measured on a desktop CPU (this lane, stdlib only, no model):

| Cost | Value |
|------|-------|
| base64 encode + decode, 12 s float32 window (768 KB) | ~2 ms |
| Silence-boundary RMS scan over the trailing 1 s | <10 ms |
| Assembler commit of one window's words | <1 ms |
| `transcription_partial` frame (loopback WS, ~100 B) | sub-ms |

Estimated (published faster-whisper benchmarks, not measured here):
small int8 on desktop CPU runs at ~0.4x real-time factor with beam 5
(faster-whisper README bench on i7-12700K; independent tables agree
at ~0.4x for small on Intel i7 CPU). This app decodes with beam 1 /
greedy (`beam_size=1, best_of=1`), which is several times faster than
beam 5, so a 12 s window is expected at ~1-2.5 s including the
`word_timestamps=True` + VAD overhead the streaming path pays. CUDA
is an order of magnitude faster again (small at ~0.08x RTF).

Verdict: the budget CLOSES on estimate, with roughly 2x margin on
desktop CPU (5 s cadence vs ~1-2.5 s cost) and more on CUDA. It is
still an estimate: no model is loaded in this lane, so the number
MUST be re-measured on the target host during the C5 byte-equality
proof and again on the C6 streaming path before any slim-side
cutover. If the measured per-window cost ever exceeds the step
cadence on supported hardware, C6 stays on the in-process fallback
(§2) and this section is revised, laggy designs do not ship.


## Consequences

Positive: the sidecar stops importing `faster_whisper`/`ctranslate2`,
which is the precondition for ITEM 3's `--nofollow-import-to` and the
185 MB size gate; dictation latency stops paying in-process model load.

Negative: C6 needs a real latency budget (per-window round trips on the
streaming path) and moves the streaming assembler across a process
boundary - the single riskiest part of this plan.

Neutral: the frozen `transcribe_offline` shapes are unchanged; every
addition is a new command or an optional field, so an older pack still
works against a newer slim core.

## Apply precondition

C1-C4 are additive and independently testable. C5-C6 require the
Step-0 reference audio byte-equality proof on the worker path before C7
removes anything.

## References

- ADR-0024 `0024-runtime-pack-worker-handoff.md` - the handoff, the
  Step 0-6 verification, and the Step-7 SCOPE FINDING this closes.
- `docs/plan-runtime-pack-split.md` section 7 (worker IPC),
  section 8.10 (degradation).
- `docs/duplicated-text.md` - the overlap/tail-dedup design C6 moves.
- `docs/code-notes/worker-port-relay.md` - the relay hop C1 rides on.
