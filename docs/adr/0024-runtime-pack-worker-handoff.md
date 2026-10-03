# ADR 0024: Runtime-pack worker handoff end-to-end

## Status

Accepted (execution plan, 2026-09-26). Work not started. This ADR freezes the order + the Step-2 wire contract so Steps 1-2 (Rust) and 3-4 (Python) can run as disjoint parallel slices.

## Context

Goal (master plan `docs/plan-runtime-pack-split.md`): slim core (UI, recording, hotkeys, IPC, no ML imports) + worker/pack (ONNX, Parakeet, Qwen, VAD, ~180 MB pack). Slim core never touches ML code; it asks the worker "transcribe this" over a connection.

Trap: slimming the Nuitka build now (excluding onnxruntime/ctranslate2) while the app still imports ML in-process = `ModuleNotFoundError` on launch / silent VAD death. Slimming is gated on the runtime handoff working first.

## Decision

Order is fixed:

1. Wire the runtime handoff (Steps 0-6 below), verify on a real machine.
2. Only then slim the build (Step 7).
3. Then `.nsi` pack checkbox + full-offline installer.

Step-2 wire contract (frozen before Step 3, E9): host pushes `worker_started {pid:int, version:str, port:int}` to the slim-core sidecar over the existing host<->sidecar WS hop. `port` is additive to the current `{pid, version}` shape (`voice_typer/server/event_bus.py:181`); event name already in all allowlists, no allowlist churn. Slim core connects `ws://127.0.0.1:<port>` as WS client.

Placement rules: `main.rs` stays wiring-only (C-ARCH-1) — new module for worker init (parallel to `initialize_sidecar`); no `block_on` on runtime workers (C-TOKIO-1); worker hop reuses C-WS lessons (str/TEXT frames, numeric id echo, generation-stamped respawn); `[WORKER]` log lines carry `format_duration()` suffixes (C-LOG-2).

## Consequences

Positive: smaller installer unlocked safely; worker crash independent of sidecar breaker (§7.2); queued `transcribe_offline` actually completes.
Negative: new second WS hop to own (auth, heartbeat, reconnect/backoff); real-machine verification mandatory (frozen worker exe can't be faked in unit tests).
Neutral: `worker_started` payload gains `port`; new module `voice_typer/server/worker_client.py`; long-lived worker policy (§7.3).

## Verified state (2026-09-26, code, not claims)

Built:

- Worker Python side: `voice_typer/worker/_ws_server.py` (`transcribe_offline` dispatch → thread → `transcribe_offline_result`), `_transcribe.py` (lazy cached ASR), `_auth.py`, `_single_instance.py`, `__main__.py`. Handshake `{"event":"worker_started","port":N}` on stdout.
- Rust spawn: `src-tauri/src/sidecar/spawn.rs:198` `spawn_worker_and_get_port_with_shutdown`, `:219` `initialize_worker`; `src-tauri/src/sidecar/spawn/worker.rs` `spawn_worker_release` / `spawn_worker_dev_mode` + `:170` `on_pack_verified` trigger (stop-first, then `initialize_worker`; skips quietly when binary missing/quitting).
- `WorkerState` managed `src-tauri/src/main.rs:121`; worker shutdown wired `src-tauri/src/sidecar/lifecycle.rs:157`.
- IPC surface in all allowlists + parity tests; pack downloader, launch existence check, degradation matrix (`voice_typer/server/ipc/lifecycle.py:368` stub ack: `queued:False+degraded` when pack missing, `queued:True` otherwise), early-transcribe queue (`mark_ready`) live.

Missing (the gap this ADR closes):

- `main.rs:213` setup spawns only `initialize_sidecar_guarded`; worker start fires solely via the `offline_pack_verified` → `on_pack_verified` path. No cold-start call, no supervisor/respawn yet (`initialize_worker` success path logs "WS client + respawn supervisor are the next phase", `spawn.rs:257`).
- Port-relay hole: only Rust sees the worker port (stdout). `worker_started` on the sidecar bus is `{pid, version}` with no `port` (`event_bus.py:181`); `worker_port`/`worker_client` = zero hits in `voice_typer/server`. No mechanism for the sidecar to learn the port.
- Slim-core sidecar has no WS client to the worker (`_handle_transcribe_offline` acks only, `lifecycle.py:368` docstring says so explicitly).

Correction to the session note: `main.rs` is NOT "zero worker references" — `WorkerState` manage + worker shutdown are wired; what is missing is the spawn trigger outside the pack-verified path + the port relay + the WS client + the real handler.

## Current status (2026-09-26, reverified)

- Wire handoff — code done, **verification CLOSED 2026-09-26**. Steps 0–6 all signed off on a real Windows host: the live `scripts/verify_worker_handoff_live.py` harness reproduced the Step 0 in-process text **byte-for-byte through the real worker** (`text_matches: true`), the pack-missing degradation matrix passed on a real pack root, and the C-LOG-2 duration suffix was observed in the worker's own log. Row (b) peer-death was exercised (the Rust backoff engine is `cargo test worker` 61/61). Evidence under `%TEMP%/vt_verify/`. **Trap status: DISARMED FOR onnxruntime ONLY (VAD/GTCRN stay in slim core by decision). The ASR exclusions are NOT safe yet - excluding faster_whisper/ctranslate2 still crashes the app until the Phase-1 dictation cutover lands (see Step 7).**
- Slim build — **ownership decision RESOLVED + gate landed 2026-09-26; the Nuitka ASR exclusions remain BLOCKED on the dictation cutover (below).** Step 7 asks to move "every in-process ML import" behind the worker hop and add `--nofollow-import-to` for onnxruntime/ctranslate2/faster_whisper to the *sidecar* build. That is only safe once the slim core has NO live in-process consumer of those libraries. Recomputed against the current tree, three live consumers remain in the sidecar, so excluding the libs now reproduces the ADR trap (`ModuleNotFoundError` / silent VAD death — exactly C-CI-8's failure mode):
  1. **The live dictation path still runs the engine in-process.** `voice_typer/server/dictation_pipeline/transcribe_step.py:98` calls `self._app.models.active_transcriber()` → `AsrBackendRegistry` → `TranscriptionEngine` → `faster_whisper`/`ctranslate2`. `transcribe_offline` is a *parallel* request path (renderer media-ingest / mic-test auto-transcribe), NOT the dictation engine. Verifying the worker hop does not yet replace the in-process engine is the whole point of a cutover that has not been done.
  2. **VAD runs on the sidecar's audio-processing thread.** `recording/audio_pipeline.py:343` calls `compute_vad_prob(...)` → `vad.py:139` `import onnxruntime`. It is RT-safe only because it runs on the worker/processing thread, NOT the PortAudio callback (`RT-SAFE-001`, `tests/test_recording_and_audio.py:971-997`). Moving VAD behind a per-chunk IPC hop would put a network round-trip on the streaming path — an architectural regression, not a slimming win.
  3. **The noise filter chain runs in-process.** `audio_filters/noise_suppressor.py:227` → `gtcrn_backend.py:39/50` `import onnxruntime` (the `noisy_room` preset), and `parakeet_engine/_load.py`, `qwen_onnx_model.py`, `asr_utils.py`, `resource_probe.py`, `transcription_device.py`, `transcription_fallback.py` are all imported by slim-core modules.
  13 confirmed live import sites (recomputed, supersedes the draft's list which omitted `qwen_onnx_model.py:109`): `asr_utils.py:42`, `qwen_onnx_model.py:109,194`, `resource_probe.py:66`, `transcription.py:239`, `transcription_device.py:33`, `transcription_fallback.py:58`, `vad.py:104,139`, `audio_filters/gtcrn_backend.py:39,50`, `parakeet_engine/_load.py:35,61`. Note the worker build (`build_worker_windows.sh:93,179`) *intentionally bundles* onnxruntime + faster_whisper/ctranslate2 — the split is "ML in the pack", not "ML nowhere".
  **Ownership decision (RESOLVED 2026-09-26, user decision):** option (a) - the slim core KEEPS `onnxruntime` for VAD + gtcrn. They run on the real-time audio path, so streaming them to the worker would add a network round-trip for no meaningful size win. Only the ASR libs (`faster_whisper`, `ctranslate2`) are the worker's. Consequence: the sidecar CANNOT drop onnxruntime, and the only in-scope Nuitka exclusions are the two ASR ones.
- `.nsi` checkbox + full-offline + Step 8 publish job — drafted, not implemented. No `pack-<version>.zip` / `pack-manifest.json` artifact exists in Releases and no CI job publishes one, so the silent always-on downloader currently has nothing to fetch (users get `offline_pack_missing` + degraded transcription).

## Execution plan + progress

- [x] Step 0 — Baseline (VERIFIED 2026-09-26, real host): in-process transcription of a real SAPI-synthesized WAV, `faster-whisper-large-v3` on cpu/int8, integrity-checked (4 pinned files). Reference text: "The quick brown fox jumps over the lazy dog. This is a runtime pack worker handoff verification test." (`latency_ms=27561`, error `null`). Regression reference: `step0_baseline.json`. This is the exact string Step 6 (a) must reproduce through the worker.
- [x] Step 1 — Rust wiring (done 2026-09-26): `src-tauri/src/sidecar/worker_init.rs` (`initialize_worker_cold_start` + `initialize_worker_guarded`), `spawn/worker.rs` `should_start_worker`/`start_worker_if_ready`, `main.rs:214-219` one spawn line (246 lines, wiring-only). `cargo check` Finished exit 0; `cargo test worker` 61 passed.
- [x] Step 2 — Port relay (done 2026-09-26, contract frozen): `worker_started {pid,version,port}` host→sidecar; `voice_typer/server/worker_relay.py` single store + `get_worker_port()`; `docs/code-notes/worker-port-relay.md`. `tests/test_worker_relay.py` 28/28.
- [x] Step 3 — Sidecar WS client (done 2026-09-26): `voice_typer/server/worker_client.py` (`WorkerClient`, auth/heartbeat/result-route/generation guard). `tests/test_worker_client.py` 24/24.
- [x] Step 4 — Real handler (done 2026-09-26): `lifecycle.py` forwarder + `voice_typer/server/worker_pending.py` canonical queue (cap 64). `tests/test_transcribe_offline_forward.py` 18/18. NOTE: `make_ipc_server_with_fakes()` constructs fine; the "registry drift" report was refuted (handlers live in `handlers/` mixins, all wired in `IPCServer` bases).
- [x] Step 5 — Lifecycle policy (done 2026-09-26): `src-tauri/src/sidecar/worker_supervisor.rs` backoff engine + exit watcher; `docs/code-notes/worker-lifecycle-policy.md`; `cargo test worker_supervisor` 9/9.
- [x] Step 6 — Real-machine verification (SIGNED OFF 2026-09-26, real Windows host, dev worker = `python -m voice_typer.worker`): static preflight 5/5 + `tests/test_worker_handoff_preflight.py` 7/7. Live harness `scripts/verify_worker_handoff_live.py` spawned the REAL worker, read its real `worker_started` handshake (`port=55774 protocol=1`), pushed it through the REAL `worker_relay.handle_host_frame` (accepted, stored 55774), connected the REAL `WorkerClient` (token auth OK), and got a REAL `transcribe_offline_result` — `latency_ms=25093`, `error=null`, text **byte-identical to the Step 0 in-process baseline** (`text_matches: true`, `result_ok: true`). Degradation matrix proven on a REAL pack root by `scripts/verify_worker_degrade_live.py`: missing → `{queued:false, degraded:true, reason:"offline_pack_missing"}`; pack present → `{queued:true, forwarded:false, reason:"worker_not_ready"}` (NOT degraded); removed again → degrades again. `[WORKER] offline transcription complete (len=101 chars) 25.1s` confirms the C-LOG-2 duration suffix in the canonical C-LOG-1 format. Peer-death (row b) was later PROVEN host-supervised under `npm run tauri:dev` (kill -> `respawn succeeded on attempt 1 (port=53378) 2.6s` -> `worker_started relay sent` -> `host relayed worker port=53378` -> `connected to worker at 127.0.0.1:53378`), which exposed and fixed FOUR real defects (respawn never relayed the new bind; nothing ever called `update_from_worker_started` so the client learned no port at all; sidecar and worker were given different auth tokens so every auth frame was rejected; `set_port` reused a live superseded connect thread). Post-respawn TRANSCRIPTION (row b2) is proven too: `verify_worker_handoff_live.py --respawn` returned `RESULT_OK=True` with `text matches expected: True` twice - once through the original worker (port 65204, `latency_ms=32448`) and once through the replacement after a real kill+rebind (port 65222, `latency_ms=25404`), both byte-identical to the Step 0 baseline. Backoff engine: `cargo test worker` 62/62. `tests/test_worker_client.py`+`test_worker_relay.py`+`test_worker_handoff_preflight.py` = 59/59. Evidence artifacts under `%TEMP%/vt_verify/` (`step6_evidence.json`, `step6c_degrade.json`, `worker.log`).
- [ ] Step 7 — Slim the build. **Ownership decision resolved + gate landed 2026-09-26; Nuitka ASR exclusions still gated on the dictation cutover.** (1) Decision: VAD (`vad.py`) + GTCRN filter (`gtcrn_backend.py`) STAY in the slim core — they run on the real-time audio path (RT-SAFE-001), so `onnxruntime` remains a slim-core dep (plan §5.3). The ASR libs (`faster_whisper` + `ctranslate2`, 4 import sites) move to the worker. (2) Gate landed: `scripts/slim_core_ml_ratchet_check.py` + committed `slim-core-ml-baseline.json` (total=4: `faster_whisper`×2, `ctranslate2`×2 in `transcription.py`, `qwen_onnx_model.py`, `transcription_device.py`, `transcription_fallback.py`), wired as an additive fail-fast step in `tauri-windows-build.yml` after the drift pytest + before stub gen (C-CI-7 order preserved). Tests `tests/test_slim_core_ml_ratchet.py` 10/10 (incl. a BOM-prefixed-import case proving the gate fails on a genuinely new import). (3) Size gates already enforced in CI (§11.4: 185 MB sidecar hard-fail, 200 MB pack hard-fail, 45 MB NSIS informational). **SCOPE FINDING 2026-09-26 (blocks Step 7, NOT guessed): cutting ONLY the dictation engine would NOT remove faster_whisper/ctranslate2 from the slim core, so it would add risk to the primary dictation path while shrinking nothing. `active_transcriber()` (which returns the in-process `TranscriptionEngine`) is consumed by FOUR slim-core sites, not one: (1) `dictation_pipeline/transcribe_step.py:98` (the transcribe step); (2) `dictation_pipeline/orchestrator.py:67` (abort path); (3) `streaming_session_coordinator.py:83,104` - builds `StreamingTranscriptionSession(transcriber=..., ...)` and requires `transcribe_words` word-level timestamps, with the whole overlap/tail-dedup design documented in `docs/duplicated-text.md`; (4) `media_ingest/engine_loop.py:76` calls `backend.transcribe_with_fallback(...)` per chunk window. Site (3) is the blocker for a file-based worker hop: the current worker contract is request/response over whole files (`transcribe_offline` -> `transcribe_offline_result`), which cannot carry a streaming word-timestamp assembler with stateful overlap dedup. A correct cutover therefore needs its own ADR covering: a request-id-correlated sync bridge (the worker does not echo the id today), a streaming/word-timestamp worker command, and the `model_manager` registry/backend-construction surface (which still builds backends and drives tray status + idle unload). Consequence: the ASR `import faster_whisper` / `import ctranslate2` sites and the Step-7 exclusions stay as they are until that work lands. (`dictation_pipeline/transcribe_step.py:98` → `active_transcriber()`) onto the worker hop, and the `--nofollow-import-to` ASR exclusions. Those are the actual slimming work; the gate above is the reversible measurement layer that precedes them.**
- [ ] Step 7 — C7 implementation (landed 2026-09-27; unit-level cutover verified 2026-09-27, host gates open): engine moved to `voice_typer/worker/whisper/` (device/fallback with it, byte-identical), `WorkerBackedAsr` shim mapped in the registry (now also exposes `transcribe` for mic-test / CloudEngine local-fallback parity), Qwen mel filterbank vendored (parity-tested), ratchet baseline regenerated 4→0, Nuitka exclusions in all four sidecar invocations + pin test. All four `active_transcriber()` sites cut over (batch, abort, streaming coordinator prefers the C6 worker session and skips in-process word-engine construction when `WorkerBackedAsr` is active, media windows). 127 focused unit tests green (`tests/test_worker_*`, `test_slim_no_asr_imports`, `test_nuitka_asr_exclusions`, `test_transcription_split_wiring`, `test_media_worker_backend`, `test_mic_test_degradation`). Status + host-gate runbook: `docs/code-notes/dictation-worker-cutover-status.md`. PENDING (host/CI, see that doc): local frozen slim boot, VAD + transcription flow in the frozen exe, 185 MB gate, and a full CI re-run of the edited `tauri-windows-build.yml` (C-CI-2) — the workflow edit is required but unvalidated until dispatched.

### Host-gate runbook + harness (2026-10-03)

`scripts/verify_frozen_slim_live.py` is the gate driver (new, with
`tests/test_frozen_slim_live_gate.py` — 10 unit cases over the parts that are
deterministic offline: the minimal-pack writer against the product's own
`offline_pack_exists` / `_verify_manifest_files`, the log scanners, and the
C-LOG-2 duration regex). It exists because `verify_worker_handoff_live.py`
(Step 6) drives `worker_relay` / `WorkerClient` **in-process from source**, so
it structurally cannot see a surviving in-process `faster_whisper` /
`ctranslate2` import inside the frozen binary. The gate instead launches the
frozen exe, reads its real `server_started` handshake, authenticates on the
real host↔sidecar WS hop, relays a REAL worker `worker_started` frame in,
drives `microphone_test_start` (recorder init → Silero VAD warm) and
`transcribe_offline` (real WAV → worker → text) **through the frozen dispatch
surface**, then asserts the transcript and greps the frozen sidecar's own
`<config>/logs/lausu.log`.

`--source-sidecar` is the harness self-check: the identical protocol against
the SOURCE sidecar, so a red gate can be attributed to the freeze rather than
to the harness. It is **not** a substitute for the frozen run.

**Pre-flight GREEN against the source sidecar (2026-10-03, real Windows host,
`faster-whisper-large-v3` cpu/int8, SAPI-synthesised 16 kHz WAV carrying the
Step 0 reference sentence, exit 0, `FROZEN_SLIM_GATE_OK`):**

```text
[frozen-gate] frozen sidecar server_started: port=59303 pid=24484
[frozen-gate] authenticated on sidecar WS port=59303, first frame type='ready'
[frozen-gate] relayed worker_started pid=14312 port=59300 into the frozen sidecar
[frozen-gate] microphone_test_start -> microphone_test_result {"success": true, ... "duration": 10.0, "sample_rate": 44100}
[frozen-gate] transcribe_offline ack -> ack {"queued": true, "forwarded": true}
[frozen-gate] transcribe_offline_result: text_len=101 latency_ms=17334 device='cpu (int8)'
[frozen-gate] [VAD] marker lines in frozen sidecar log: 1
[frozen-gate]   VAD> 2026-10-03  19:12:03  INFO  [VAD] Silero VAD model loaded from local ONNX, preloaded + warmed 0.1s
[frozen-gate] [WORKER] marker lines in frozen sidecar log: 1
[frozen-gate]   WORKER> 2026-10-03  19:12:21  INFO  [WORKER] *** (len=101 chars) 17.3s
[frozen-gate] FROZEN_SLIM_GATE_OK
```

`text_len=101` is byte-exact against the Step 0 reference sentence, and the
result line carries the C-LOG-2 duration suffix `17.3s`.

Three facts this pass established that the harness had to absorb:

1. **The ``log`` marker cannot be the command name.**
   `security/redaction.py::redact_api_keys` rewrites the token
   `transcribe_offline_result` to `***` (it treats the trailing `_result` as a
   secret-ish key), so the worker's own completion line loses its identity in
   `lausu.log`. Reproduced directly:
   `redact_api_keys('[WORKER] transcribe_offline_result (len=101 chars) 16.6s')`
   → `'[WORKER] *** (len=101 chars) 16.6s'`. The gate matches the stable
   `(len=N chars)` shape instead. **The redaction defect is recorded, not
   fixed here** (out of this ADR's scope).
2. **The scratch config must be seeded through `Config.save()`**, not
   `write_text`. A hand-written `config.json` that a later in-process save
   then replaces leaves a file this process can no longer open on this host
   (empty DACL; `stat()` works, `open()` raises `PermissionError`, and
   `takeown` + `icacls /reset` is needed to remove the tree). Seeding via
   `Config.load()` → set fields → `save()` uses the same path a real install
   uses and stays readable. `Config.save()` itself is healthy — verified
   `SAVE OK` in both a fresh dir and the live `%APPDATA%\lausu`.
3. **`Popen` stdout and a parent reader must not share one handle.** The child
   inherits the same OS file description, so both sides share a file offset:
   once the child writes `server_started` the parent's reader is parked at
   EOF forever (observed: a 300 s timeout against a log that already contained
   the line). The gate reads the handshake back **by path**.
- [x] Step 8 — CI publish job (shipped 2026-09-27): `.github/workflows/runtime-pack-publish.yml` freezes the worker per triple (`scripts/build/build_worker_*.sh`), zips `lausu-runtime-pack-<pack_version>-<triple>.zip`, writes `pack-manifest.json` via `scripts/release/build_pack_manifest.py` (schema-validated against `OfflinePackManifest`), and uploads both via `scripts/release/publish_pack_release.py` (canonical naming from `scripts/build/artifact_names.py`; signing stays in CI per C-CI-11). ALSO publishes a rolling `offline-pack` tag so `.../releases/download/offline-pack/pack-manifest.json` stays valid across app-only releases; `update_check.pack_manifest_url_candidates()` tries `latest` then the rolling tag. PENDING host acceptance: download-install-verify round-trip on a real machine against a draft release.

---

## C7 host gates — dispatched CI validation (2026-10-03, run 37128596808)

`gh workflow run tauri-windows-build.yml --ref main -f sign=false` against
`HEAD == origin/main == 70528cb90`, i.e. the workflow **with** the C7 Nuitka
ASR exclusions and the ratchet step, no workflow file edit (C-CI-2: diagnose
first; nothing was changed in the workflow).

Sidecar + worker are separate jobs (the 2026-09-29 split), both Nuitka
freezes, both finished green:

```text
$ gh run view 37128596808 --json jobs --jq '.jobs[] | (.databaseId|tostring)+" | "+.name+" | "+(.conclusion // .status)'
111218934501 | build-worker-exe (x86_64, x86_64-pc-windows-msvc, windows-2022, tauri.windows-x86_64.conf.json) | success
111218934648 | build-sidecar-exe (x86_64, x86_64-pc-windows-msvc, windows-2022, tauri.windows-x86_64.conf.json) | success
```

**ITEM 1c (185 MB sidecar gate) + the torch-free gate — PASS.** Step-level
conclusions from the same run:

```text
1  | Set up job                                                    | success
2  | Checkout                                                       | success
3  | Cache Nuitka build artifacts (ccache)                          | success
4  | Cache Nuitka scons build dir (incremental C builds)           | success
5  | Download + verify python-build-standalone                      | success
6  | Build the sidecar with Nuitka (ADR-0020 §4.2)                 | success
7  | Assert sidecar size <= 185 MB (plan §11.4, Phase 1c target)   | success
8  | Verify sidecar is torch-free (Phase 1c gate, plan §11.3)      | success
9  | Upload sidecar binary (intermediate)                          | success
```

**C-CI-7 pre-build gate order + the Step 7 ratchet — PASS** in the
`tauri-windows-build` job (steps 15-20, i.e. after the sidecar/worker
downloads and before stub-dependent steps):

```text
15 | Verify version lockstep across layers (fail fast)                    | success
16 | Verify config drift guards (icons, identity, binaries) (fail fast)   | success
17 | Assert slim-core ML-import ratchet (Step 7 fail-fast gate)          | success
18 | Generate Tauri binary stubs                                         | success
19 | Verify bundle.icon icons are present + valid (fail fast)            | success
20 | cargo test (Tauri Rust host unit tests — Windows-gated branches)    | success
```

Step 17 green is the ratchet proven on a real runner with the exclusions in
the build. Step 18/19 green is C-CI-7's ordering (drift pytest → stubs →
icon check) preserved.

**Still open on this run:** step 29 `Smoke test sidecar binary (--version)`,
which is the ITEM 1a frozen-boot check (a GUI-subsystem PE launched via .NET
`Process` + `WaitForExit`, C-CI-14), plus steps 22-38. The run was still in
`Install tauri-cli (v2)` when this record was written, so no claim is made for
those steps.

**Wrong repo slug — this alone made the first publish impossible, so it is a
prerequisite, not a nit.** `branding.APP_REPO` was `"AbdallahIsDev/lausu"` and
`publish_pack_release.DEFAULT_REPO` repeated the same literal. That repository
does not exist:

```text
$ gh repo view AbdallahIsDev/lausu
GraphQL: Could not resolve to a Repository with the name 'AbdallahIsDev/lausu'.
```

Three contracts pointed at the 404 repo: the publisher's upload target,
`update_check.DEFAULT_OFFLINE_PACK_MANIFEST_URL` +
`ROLLING_OFFLINE_PACK_MANIFEST_URL` (both f-string `APP_REPO`), and
`media_ingest/mini_update.py`'s extractor URL. The live sidecar log proves the
downloader half was broken in the field:

```text
[UPDATE] remote pack manifest not published yet (HTTP Error 404: Not Found):
  github.com/AbdallahIsDev/voice-typer/releases/latest/download/pack-manifest.json
[UPDATE] remote pack manifest not published yet (HTTP Error 404: Not Found):
  github.com/AbdallahIsDev/voice-typer/releases/download/offline-pack/pack-manifest.json
```

(The 404 host reads `voice-typer` because the renderer release constants and
`tests/test_update_check.py::fake_manifest_url` already used `voice-typer`;
only `APP_REPO` was stale — the tree was internally inconsistent.)

Fix, forward, one authoritative source (E7, no second literal):
`branding.APP_REPO = "AbdallahIsDev/voice-typer"`, and
`publish_pack_release.DEFAULT_REPO` now **derives** from it
(`from voice_typer.server.branding import APP_REPO`) so the upload target and
the downloader URL cannot drift apart again. Both `__init__.py` files on that
import path are trivial, so it stays importable from a CI job with no
`pip install` step. Pins updated in the same change:
`tests/test_update_publish.py::TestDefaults::test_default_repo` (now also
asserts `DEFAULT_REPO == branding.APP_REPO`),
`tests/test_update_check.py::test_default_manifest_url_is_github_releases_latest`,
and `docs/auto-update-feature.md` (which also named a
`DEFAULT_PACK_MANIFEST_URL` constant that does not exist — corrected to
`DEFAULT_OFFLINE_PACK_MANIFEST_URL`).

Also fixed in the same pass: `publish_pack_release.py` printed its success line
with a U+2713 check mark, which raises `UnicodeEncodeError` on a cp1252 Windows
console and turned a SUCCESSFUL publish into a traceback + exit 1. Stdout and
stderr are now reconfigured to UTF-8 with `errors="replace"` at CLI start.
Verified end to end: the publisher created a real draft against the corrected
slug (which is what proved the fix), and that draft was then deleted.

Execution shape: Steps 1-2 (Rust) and 3-4 (Python) are disjoint once the Step-2 contract above is frozen — two parallel sub-agents, then joint Step 5/6. Tests per step (E6).

## References

- Master plan: `docs/plan-runtime-pack-split.md` (§7 worker IPC, §7.2 breaker, §7.3 lifecycle, §7.4 events, §8.10 degradation, §11.5 size gate).
- Guards: C-ARCH-1 (main.rs wiring-only), C-TOKIO-1 (no `block_on`), C-WS-1/2/3 (wire discipline), C-LOG-2 (duration suffix), C-DATA-1 (pack download allowed egress), E9 (frozen wire shape), E6 (tests per step).
