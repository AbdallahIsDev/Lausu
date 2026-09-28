# Dictation worker cutover — status (ADR-0025 C5–C7)

Recorded 2026-09-27 after the T3 gap pass. Scope: what is code-complete
in-tree, what the unit tests pin, and which host gates remain before the
slim-sidecar Nuitka ASR exclusions are shippable.

## Code-complete (verified in this pass)

All four `active_transcriber()` sites are cut over. Local backends go
through the pack worker; `CloudEngine` stays in-process (C-DATA-1: cloud
audio never re-routes to the offline worker).

| Site | File | Behaviour |
|------|------|-----------|
| 1 batch | `voice_typer/server/dictation_pipeline/transcribe_step.py` | `WorkerBackedAsr` → `transcribe_with_fallback` via the C3 samples hop; `WorkerAbortedError` → cancelled cycle; `WorkerTranscriptionError` → `BackendNotLoadedError` (never silent `""`). `CloudEngine` branch unchanged (in-process + local-engine fallback). |
| 2 abort | `voice_typer/server/dictation_pipeline/orchestrator.py` | `request_abort()` calls `get_shared_client().abort_all_outstanding()` AND `active.request_abort()` (shim forwards to the same client). |
| 3 streaming | `voice_typer/server/streaming_session_coordinator.py` | `_try_start_worker_session` first. `WorkerBackedAsr` has no `transcribe_words`, so a failed worker open SKIPS streaming (`supported: False`) and never constructs in-process `StreamingTranscriptionSession`. In-process engines still fall back to the word session when the gate is off. |
| 4 media | `voice_typer/server/media_ingest/engine_loop.py` | `WorkerWindowBackend` (C3 samples + abort) with in-process fallback when the hop fails. |

Supporting surface (also complete):

- `WorkerBackedAsr` (`server/worker_backed_asr.py`): `load`/`unload`,
  `is_loaded`, `device_info`, `loaded_via`, `clear_abort`/`request_abort`,
  `transcribe_with_fallback`, and `transcribe` (TranscriberProtocol alias
  used by mic-test and `CloudEngine`'s local-engine fallback).
  Deliberately NO `transcribe_words`.
- C6 hop: `worker_streaming.py` `WorkerStreamingSession`
  (open → push driver → finalize) against `worker/_ws_server.py`
  `streaming_session_open|push|finalize`; `transcription_partial` frames
  are republished on the slim event bus by `worker_client.route_frame`.
- C7 move: engine at `voice_typer/worker/whisper/`; slim registry maps
  `"whisper"` → `WorkerBackedAsr` (`asr_registry.py`); worker registry
  repoints the spec at the real engine (`worker/_transcribe.py`).
- Nuitka: `--nofollow-import-to` for `faster_whisper`/`ctranslate2` in the
  sidecar invocations; `slim-core-ml-baseline.json` total=0.

## Unit coverage (what the green suite proves)

Command used (all green, 127 passed):

```bash
python -m pytest tests/test_worker_streaming_session.py \
  tests/test_worker_backed_asr.py tests/test_worker_path_cutover.py \
  tests/test_slim_no_asr_imports.py tests/test_nuitka_asr_exclusions.py \
  tests/test_transcription_split_wiring.py tests/test_media_worker_backend.py \
  tests/test_mic_test_degradation.py tests/test_worker_streaming.py \
  tests/test_worker_transcribe.py tests/test_worker_samples_abort.py \
  -q --no-cov
```

| Concern | Tests |
|---------|-------|
| Site 1 batch cutover, abort-as-empty, gate-off stays in-process | `test_worker_path_cutover.py` (16) |
| Site 2 abort fan-out | `test_worker_path_cutover.py::TestRequestAbortSite2` |
| Site 3 worker session preferred; WorkerBackedAsr skips in-process on worker failure; WorkerBackedAsr uses worker session when gate open | `test_worker_streaming_session.py::TestCoordinatorSwitch` |
| C6 open/push/finalize/cancel + assembler parity vs slim | `test_worker_streaming_session.py` (15) |
| WorkerBackedAsr load/transcribe/abort/`transcribe` alias | `test_worker_backed_asr.py` (11) |
| Slim import closure has no FW/CT2 | `test_slim_no_asr_imports.py` |
| Nuitka exclusion pins | `test_nuitka_asr_exclusions.py` (8) |
| Engine-split wiring | `test_transcription_split_wiring.py` (9) |
| Media windows via worker | `test_media_worker_backend.py` (11) |
| Mic-test degradation + worker-backed `transcribe` | `test_mic_test_degradation.py` (5) |

Ratchet: `python scripts/slim_core_ml_ratchet_check.py` →
`ok (total=0 <= 0, {'faster_whisper': 0, 'ctranslate2': 0})`.

## Remaining host gates (NOT verified here)

These need a real Windows host / CI; this lane cannot freeze Nuitka.

1. **Local frozen slim boot.** Build the sidecar with the ASR exclusions
   and launch it; confirm no `ModuleNotFoundError` for
   `faster_whisper`/`ctranslate2` at import time.
   How: run the existing sidecar freeze script used by
   `.github/workflows/tauri-windows-build.yml` (the Nuitka invocation that
   carries `--nofollow-import-to=faster_whisper,ctranslate2`), then start
   the frozen exe and watch `lausu.log` for a clean `[STARTUP]` banner.
2. **VAD + transcription flow in the frozen exe.** VAD/GTCRN stay in the
   slim core (`onnxruntime` is a slim dep by ownership decision). Record a
   short dictation and confirm Silero VAD still warms and a worker-backed
   whisper transcription returns text through the hop.
   How: `npm run tauri:dev` is NOT enough (dev sidecar is source). Use the
   frozen binary + a present offline pack, then dictate once and check
   `[VAD] Silero VAD model preloaded + warmed` and a
   `[WORKER] offline transcription complete ... <duration>` line
   (C-LOG-2).
3. **185 MB sidecar size gate.** The CI hard-fail is
   `timeout`/size check in `tauri-windows-build.yml` §11.4 (185 MB
   sidecar hard-fail). Confirm the frozen sidecar is under the gate.
4. **Full CI re-run of `tauri-windows-build.yml` (C-CI-2).** The workflow
   already carries the Nuitka exclusions + ratchet step; it is unvalidated
   until a real `workflow_dispatch` run completes. Do NOT edit the
   workflow as a first-line fix. Dispatch from the Actions UI and wait for
   the full job (timeout-minutes: 240).

Until all four pass, ADR-0024 Step 7 stays open and the ASR exclusions
must not be treated as release-ready.

## Gaps closed in this pass

- `WorkerBackedAsr` had no `transcribe()`. Mic-test
  (`service/microphone_test.py`) and `CloudEngine`'s local-engine fallback
  (`cloud/_engine.py`) both call `engine.transcribe(...)`; with the shim
  as the whisper backend those paths would have raised `AttributeError`
  and silently marked transcription unavailable. Added the alias (same
  worker hop, `audio_stats` accepted for signature parity).
- Site 3 regression tests added: WorkerBackedAsr + failed worker open
  must NOT construct an in-process `StreamingTranscriptionSession`, and
  must publish `supported: False`.
