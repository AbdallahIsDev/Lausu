## High Priority

These items are the highest-priority remaining work for the project. They block the Tauri migration, fix core functionality, or address critical infrastructure gaps. Items in this section are ordered by priority (top = most urgent).

> **Won't Fix tasks live in `WONT_FIX.md`**: deliberately not solved. Do NOT fix them (AGENTS.md C-REVIEW-1). See that file for the full list.

### Windows/macOS host validation. All fixes tested on Linux sandbox only
**Status:** ⚠️ Partial (2026-09-21 FV session: no further headless slice exists; every remaining item requires a real desktop host, so nothing was changed. Recorded as a host-only gate.) (2026-09-15 wave): headless slices fixed + green headless (signal-handler escalation counter, `binary_path` dead-code cleanup, host-validation workflow import fixes, manifest docstring; focused runs green, ruff + branding clean). Live behavior still needs real hosts per the runbooks.
**Description:** Many platform-specific fixes (Win32 console handler, macOS clipboard restore, native key-listener binaries) have been implemented but only tested on a Linux sandbox. They must be validated on real Windows/macOS hardware.
**User Impact:** Platform-specific regressions may exist on Windows/macOS that are invisible on Linux.
**Root Cause:** No real Windows/macOS desktop session in this sandbox; GHA hosted runners cover only the headless subset.
**Progress:** Headless subset automated in `.github/workflows/host-validation.yml` (undispatched; 2026-09-15 search-first wave extended it: Windows kill-path contracts + safe-handler routing probes, macOS `swiftc` compile + smoke, bundle parity via `plutil`, toolchain presence; contract pins now 8). Real defects fixed headless: `_signal_handler` never incremented `_signal_count`, so second-signal `os._exit(1)` was dead code (one-line fix + `tests/test_signal_delivery_count.py`, 3 passed); `TerminateProcess`-raise handle leak in `teardowns/electron.py` (`try/finally`) + discarded `taskkill` exit now debug-logged (`electron_launcher.py`), covered by 4 new tests; macOS `ClipboardSnapshot` capture/restore edge cases pinned (`tests/test_clipboard_macos_capture.py`, 8 passed) + bundle preflight (`tests/tauri/test_macos_bundle_preflight.py`, 9 passed). Aggregate focused run 129 passed; ruff + branding clean. Live gates blocked on host access + manual dispatch. Known pre-existing (not introduced, left to owner): Windows-fallback teardown test passes solo but fails after controller tests (early `is_windows` stub bind in `teardowns/electron.py`).
**Related Files:** `docs/migration/windows-validation-runbook.md`, `docs/migration/macos-validation-runbook.md`
**Fix:** Run the platform validation runbooks on real Windows and macOS hosts.
**Severity:** 🔴 High
**Priority:** P0

### S1-CR-146, `StartupWMClass=Lausu` may not match Tauri window class
**Status:** ❌ Not Fixed — host-only gate (`VALIDATE ON LINUX HOST` via `xprop WM_CLASS`); intentionally not rewritten blind (2026-09-21 FV session: left unchanged). (mismatch re-confirmed live 2026-09-15: template:28 `StartupWMClass=Lausu` vs `Cargo.toml:15` bin `lausu-tauri`; wiring intact via `tauri.conf.json:98` desktopTemplate + `Exec=lausu-tauri`). Deliberately NOT rewritten blindly; `host-validation.yml` records it as a `::warning` until `xprop WM_CLASS` on a visible Tauri window decides the value. `VALIDATE ON LINUX HOST`.
> - **2026-08-24 audit:** plausible-true (space+case in productName makes default tao WM_CLASS match unlikely vs binary prgname `lausu-tauri`): verify via `xprop WM_CLASS` on a real Linux desktop, then set the matching class in `src-tauri/lausu.desktop.template`.
- Location: `src-tauri/lausu.desktop.template:9`
- Evidence: Binary is `lausu-tauri` (per `Cargo.toml:15`). Tauri v2 sets WM_CLASS based on binary name. If actual WM_CLASS is `lausu-tauri` but `StartupWMClass=Lausu`, WM may show duplicate icon.
- Fix: Verify actual WM_CLASS via `xprop WM_CLASS` on a running Tauri window; set `StartupWMClass` to match. `VALIDATE ON LINUX HOST`. · **Found by**: R15

- **WM-6 / WM-7 / WM-8 / WM-11 / WM-12 / WM-13**, headless slice green 2026-09-15 (`test_clipboard_restore_args` + `test_clipboard_borrow_restore` + `test_sidecar_ws_ready_ordering` + `test_timeout_utils`, 57 passed); live desktop runs (X11/Wayland paste, toasts, hooks, logon) still need real hosts.
- **WM-14**: Windows `taskkill` behavior. **2026-09-17:** Electron-tree kill path (`electron_launcher.py` + `teardowns/electron.py`) was removed with the Electron host; the synthetic `taskkill /T /F` probe remains in `host-validation.yml`. Live Electron-tree kill is N/A post-removal; Tauri sidecar kill paths are owned by `src-tauri/src/sidecar/`.
- **GP-7**: macOS notarization. Preflight verified (`Info.plist` mic/notification keys + entitlements + secrets-gated workflow step); full sign + notarize + staple + clean-Mac Gatekeeper check needs a real macOS host with Developer ID + notary credentials.
- **GP-135**: cross-platform native binaries. Manifest/lookup/source verified headless (x86_64 shas match disk bytes; empty aarch64/macOS shas are fail-closed BY DESIGN; mirror tables match). Open host work: per-platform hash population, `build_native_listener_windows.sh` vs `compile_native.ps1` output-dir mismatch to confirm on Windows Git Bash, arch-aware `get_expected_sha256` gap (owned elsewhere), live per-OS runs.
- **VT-1**: Windows host validation. Code verified present (`config/loader.py` warnings registry, `_timeout_utils` TIMEOUT runner, `tray_lifecycle.py:151-177` degradation) + imports/unit green (`test_timeout_utils` 34 passed); live Windows terminal re-run needs a real host.

### WL-1 - Load the no-pack whisper model in the worker, not the sidecar (multi-round)
**Status:** ✅ Fixed (2026-10-15, Windows host. Round A: `load_whisper_model` WS command + `request_load_whisper_model` client, unit + stress suites green. Round B: `_try_system_whisper_fallback` worker-first with in-process fallback, fallback-matrix tests green; 42 focused tests passed. Round C live: real no-pack cold boot (`offline_pack_exists("1.0.0")=False`, large-v3/cuda, real 3GB weights) — source worker loaded large-v3 in 10.8s, sidecar `get_status`/`get_config` polls during the whole `ModelLoad` window all ≤0.01s (0 over 15s, 0 failures), served `idle/worker/large-v3`, zero `faster_whisper` import sidecar-side, config/recovery untouched. Frozen worker bundle ships faster_whisper/ctranslate2 verified by inspection only (`build_worker_windows.sh` nofollows torch + lazy modules, never faster_whisper/ctranslate2 — the sidecar freeze is the one that excludes them); re-confirm with a live frozen-exe run at packaging time. Full timings in `worklog.md`.)
**Description:** On installs without the offline pack, the sidecar loads `faster_whisper.WhisperModel` in-process (`asr/registry.py:235` `_try_system_whisper_fallback` → `system_whisper.py:49` `try_load_system_whisper` → `WhisperModel(...)` on the `ModelLoad` thread started by `model_manager/_loading.py:211` `start_background_load`). The 3GB weight read + ctranslate2 float16→float32 conversion saturates the sidecar process, and the UI gets zero IPC answers for minutes. Observed 2026-10-11 on a live dev boot: host-side `get_config`/`get_status` 15s timeouts from 08:56:27 to 08:57:39 (note `get_status` is pure in-memory reads — this is process starvation, not slow probes), ctranslate2 conversion warning at 09:01:12, model ready minutes later. Renderer mitigations already shipped (6-min bridge wait, mount re-races, probe prewarm, escalating backoff) only make the storm survivable; this task removes it for no-pack installs. With the pack installed the problem does not exist (`WorkerBackedAsr.load` loads nothing in-process).
**Why separate from the pack split:** the Phase-2 split (slim core + downloadable pack) is unshipped with no published manifest; this task fixes the no-pack path that every current install actually runs.
**Round A — worker-side load command (backend-only, headless-testable).** Add a worker WS command (e.g. `load_whisper_model`) that loads the named model in the worker process and reports `{loaded, backend, device, error}`; extend the sidecar `worker_client` with a matching call + timeout; cover with worker unit tests using a stubbed engine (no 3GB weights in tests — mock `WhisperModel`). Files: `worker/_ws_commands.py`, `worker/whisper/` (holder), `server/worker_client.py`, `tests/worker/`. Success: command round-trips load/success/failure shapes; focused worker + client suites green; ruff + mypy clean.
**Round B — sidecar cutover with safe fallback (backend, headless-testable).** Route `system_whisper.try_load_system_whisper` (or its registry call site) through the Round-A command when the worker is connected; the sidecar `ModelLoad` thread then only waits on the worker and the sidecar loop stays responsive throughout. Keep the in-process path as fallback when the worker is unreachable or the load fails (no behavior loss vs today). Pin the fallback order with registry tests. Files: `server/system_whisper.py`, `server/asr/registry.py`, `server/model_manager/_loading.py` (untouched/WebSocket-wait only), `tests/test_*registry*` + `tests/test_system_whisper*`. Success: worker-connected → zero `faster_whisper` import in sidecar (assert via `sys.modules` in test); worker-down → legacy path serves as today; full related suites green.
**Round C — release + live validation (needs Windows host).** Confirm the Nuitka worker bundle already ships `faster_whisper`/`ctranslate2` (C-CI-8 constrains the sidecar freeze, not the worker — verify, do not assume); then on a real Windows host WITHOUT the pack: cold-boot with large-v3, assert `get_config`/`get_status` answer <15s for the whole load, assert tray/model states match today's, assert fallback still triggers with the worker killed. Record timings in `worklog.md`. Success: no IPC blackout during load; installer size unchanged by this task (no new bundled deps — `faster_whisper` moves processes, not packages).
**Related Files:** `voice_typer/server/system_whisper.py`, `voice_typer/server/asr/registry.py`, `voice_typer/server/worker_backed_asr.py`, `voice_typer/server/worker_client.py`, `voice_typer/worker/_ws_commands.py`, `voice_typer/worker/whisper/`, `voice_typer/server/model_manager/_loading.py`, `docs/plan-runtime-pack-split.md` (Phase 2 context)
**Success:** Rounds A+B headless-green; Round C live evidence (IPC latency log across a no-pack cold boot, no 15s timeouts); renderer changes: none required (6-min wait + re-races stay as backstop).
**Implementation Difficulty:** High (cross-process protocol + fallback matrix + live validation)
**Severity:** High (multi-minute UI blackout on every no-pack cold boot with a large model)
**Priority:** P1 (below P0 host validation; above polish)

### PK-3 - Rehearse the pack/worker failure table on all three systems
**Status:** ⚠️ Partial 2026-10-12 (headless matrix 5/5 + stress 6/6 in worklog.md; Windows/macOS/Linux live runs still open).
**Description:** The pieces exist but were never run as a matrix: `scripts/build/verify_worker_bridge_live.py`, `verify_worker_degrade_live.py`, `verify_worker_handoff_live.py` rehearse worker failure modes, and `.github/workflows/host-validation.yml` (manual dispatch) owns host runs — yet no recorded run covers the pack failure table: worker killed mid-transcription, corrupt pack download (checksum must catch + re-offer), pack folder deleted by hand (noticed + reinstall offered), first launch with no internet (app works, voice politely unavailable), stale pack after app update (feeds PK-1). Untested matrix entries are where the next multi-minute blackout hides.
**Fix:** Run the matrix on Windows, macOS, and Linux (real hosts or dispatched CI): each cell records app behavior + logs in `worklog.md`; file every deviation as a follow-up entry (fix or Won't Fix with rationale, never silent). Split across sessions by OS if too big for one round; do NOT mark complete on partial matrices.
**Related Files:** `scripts/build/verify_worker_*.py`, `.github/workflows/host-validation.yml`, `docs/migration/windows-validation-runbook.md`, `docs/migration/macos-validation-runbook.md`
**Success:** matrix green on all three systems with log evidence, or deviations filed; the "genuinely complete" bar from the architecture report is met.
**Implementation Difficulty:** Medium (mostly execution time on real hosts, not code)
**Severity:** High (unverified failure handling is what produced the last two outages)
**Priority:** P1 (after PK-1/PK-2 land; the matrix tests them)

### SP-1 - Ship the split: slim installer + downloadable offline pack (owner-approved 2026-10-11)
**Status:** OPEN.
**Description:** Owner approved the split as-is: worker moves out of the installer into the background-downloaded offline pack (real build numbers 2026-10-04: sidecar 96.8MB + worker 124MB = 226MB installer; post-split slim installer ≈102MB by subtraction, pack ≈124MB — beats the plan's 180-200MB guess). No subsystem moves in this phase: detector, filters, engines stay sidecar-side; the installer just stops bundling the worker. PK-1 (handshake), PK-2 (state machine/Settings screen), PK-3 (failure matrix) are the component tasks; this entry tracks the build + publish + first-launch wiring that makes them shippable.
**Fix:** (1) Build split: slim installer config (host + sidecar only) alongside the full-offline installer which keeps bundling the pack (see plan §4.1/§11.9, scripts/windows/full-offline-installer.nsi); verify `tauri.windows-x86_64.conf.json` narrowing + no-non-Windows-binaries assertion still hold. (2) Run the publish pipeline once by hand (runtime-pack-publish.yml, manual dispatch); confirm manifest + pack download from a clean machine. (3) First-launch flow: fresh install works offline on day one (cloud engines usable immediately), pack downloads quietly, features unlock with honest states (no silent dead buttons). (4) Update plan §5 numbers to the real 96.8/124/226 measurements.
**Related Files:** `src-tauri/tauri.windows-x86_64.conf.json`, `.github/workflows/runtime-pack-publish.yml`, `scripts/release/publish_pack_release.py`, `scripts/release/build_pack_manifest.py`, `scripts/windows/full-offline-installer.nsi`, `voice_typer/server/service/offline_pack/`, `docs/plan-runtime-pack-split.md` §4/§5/§11
**Success:** clean-machine install ≈102MB; pack downloads in background and unlocks offline transcription; full-offline installer still one-file-installs; PK-1/2/3 all green on top.
**Implementation Difficulty:** High (build + release + first-launch across three systems)
**Severity:** High (the approved prize: every update halves)
**Priority:** P1 (top of the pack program; WL-1 stays independent)

### SP-2 - Move the sound filter chain to the worker (phase two, owner-approved 2026-10-11)
**Status:** OPEN.
**Description:** Owner-approved follow-up after SP-1 ships: move the sidecar's audio filter chain (denoise/pyrnnoise + enhancement, scipy-backed ≈29MB compressed) into the worker, same message-pattern as transcription; brain forwards raw audio. Detector + engines stay sidecar-side until this proves itself. Known accepted gap: mic-test quality scoring can't run until the pack arrives (shows an honest "engine still downloading" state, per PK-2 machine).
**Fix:** New worker command(s) for filter+score (keep brain-side fallback until proven, then remove per E15); slim the sidecar freeze to nofollow what moved with a loud build failure if anything still imports it; mic-test and live paths use the worker path when the pack is ready, fallback before that; regression tests for filtered/unfiltered parity.
**Related Files:** `voice_typer/server/audio_filters/`, `voice_typer/worker/_ws_commands.py`, `voice_typer/server/worker_client.py`, `scripts/build/build_sidecar_windows.sh`, `voice_typer/client/src/renderer/src/pages/microphone/`
**Success:** slim installer ≈73MB (102 − 29); filtered-audio parity byte-identical or within tolerance; mic test honest pre-pack, scoring post-pack; suites green.
**Implementation Difficulty:** High (timing-sensitive pipeline over a process boundary)
**Severity:** Medium (single biggest remaining installer saving)
**Priority:** P2 (starts after SP-1 ships; do NOT interleave with the split)

---

### FV-31 — tests/ root holds 716 flat test files (243 already live in 26 domain subdirs)
**Status:** ❌ Not Fixed (2026-09-21 FV session: re-confirmed 727 flat root files; the entry's own recommendation is 🟡 Defer — opportunistic migration only when a file is already being edited, since a bulk move is churn-for-churn. No bulk move performed.)
**Description:** Newer test domains get subdirectories, but 716 legacy files still sit flat at the tests/ root. The largest sampled files are single-domain, but that sample missed mid-sized catch-alls: `tests/test_platform_fix_regressions.py`, `tests/test_perf_clipboard_cred_security_fixes.py`, `tests/test_service_vocab_template_privacy_fixes.py` and `tests/test_config_group_fixes.py` mix unrelated domains (see RH-18), so E3 mixing IS present — though the 🟡 Defer guidance still rules out a bulk move. Navigability and ownership cost, not a correctness risk.
**User Impact:** None directly; contributors spend time finding the right test file in a 716-file flat directory.
**Root Cause:** Verified — legacy files never migrated as the subdirs evolved.
**Gain vs Trade-off:** Pure organization; risk-free if done opportunistically (migrate files only when already touched, per E1 create-first).
**If We Do It:** Test layout matches the domain structure that already exists.
**If We Don't:** Navigability cost persists and grows.
**My Recommendation:** 🟡 Defer — opportunistic migration only when files are touched anyway; a bulk move is churn-for-churn.
**Progress:** `None yet.`
**Related Files:**
- `tests/` (716 flat root files vs 243 in 26 subdirs)
**Fix:** Opportunistic migration of root files into existing subdirs when touched (no bulk move). Manual/ scripts stay uncollected by design (no test_ prefix).
**Simplified Fix:** Most new test files are organized into folders by topic, but hundreds of old ones sit loose at the root. Moving them only when already editing them avoids churn while slowly tidying.
**Implementation Difficulty:** 🟡 Medium
**Severity:** 🟢 Low

### FV-37 — Entry modules carry module-top test-seam re-exports (`# noqa: F401`) that attract new patch sites
**Status:** ❌ Not Fixed (2026-09-21 FV session: re-confirmed (`ipc_server.py` 18, `app.py` 10 `noqa: F401`). The entry requires an incremental, never-batch migration tied to E1 create-first; no file in this session's scope needed it. Left for opportunistic migration.)
**Description:** The backend entry modules re-export 15+ names purely so old tests can patch them at the entry-module path, with noqa noise on each. The split was meant to remove this coupling; the re-exports keep the entry module a patch attractor, so every new test is incentivized to patch the wrong place, re-growing the coupling.
**User Impact:** None; maintainability cost.
**Root Cause:** Verified — historical patch sites left pointing at the entry module when the god-module was split.
**Gain vs Trade-off:** Incremental migration (only when already touching a file, rewriting the pinned tests in the same change per E1) vs the current silent growth. Batch-swap is explicitly wrong.
**If We Do It:** Entry modules shrink toward the wiring-only budget and the patch surface stops growing.
**If We Don't:** The attractor persists.
**My Recommendation:** 🟡 Defer — opportunistic, never batch.
**Progress:** `None yet.`
**Related Files:**
- `voice_typer/server/ipc_server.py:11-41`
- `voice_typer/server/app.py:8-83`
- Cross-reference: FV-38 (app.py line budget — the same re-export blocks)
**Fix:** Incremental (only when already touching a file): migrate patch sites to the owning submodule per the C-ARCH-2 shape and drop the re-export; each migration must rewrite the pinned tests in the same change (E1 create-first); do NOT batch-swap.
**Simplified Fix:** Old tests reach into the app's front-door modules to swap out internals. Migrating them to the modules that own those internals — one file at a time, only when already editing it — keeps the front doors thin.
**Implementation Difficulty:** 🟡 Medium
**Severity:** 🟢 Low

---

## RH session — 2026-11-18 (Investigation, Groups 1/2/6/7)

Findings were investigated by four sub-agents, audited by two independent reviewers, then RH-1..RH-10 were implemented by four disjoint sub-agents (RH-1 completed via a continuation) and re-reviewed to APPROVE. Entries RH-1..RH-10 and RH-11, RH-14, RH-16, RH-17, RH-18, RH-19, RH-20 carry `✅ Fixed` statuses (RH-11 by owner decision, the rest with platform-qualified verification); RH-12, RH-13, RH-15 and RH-21..RH-36 were `❌ Not Fixed` at the start of the 2026-11-19 decision round. Corrections from all review waves are applied below. All observations are from the current Windows working tree unless stated otherwise.

### Wave 3 — deeper pass (IPC/config parity, lifecycle/resources, test hermeticity, packaging/docs)

Wave 3 returned 21 findings. The final Review Wave dropped 2 as false claims (pack-publish API idempotency and draft rolling-tag — release-create `already_exists` is handled at `publish_pack_release.py:552-574`, `--clobber` is present at `:172,487`, the manifest is uploaded once, and `runtime-pack-publish.yml` is `workflow_dispatch`-only with intentional `draft=true`), merged 3 into one doc-drift entry, and corrected severities/numbers. 16 canonical entries follow.

### RH-21 — Mic-level worker slot cleared while its thread is still alive
**Status:** ❌ Not Fixed

**Description:** `voice_typer/server/level_monitor/mic_level_push.py:118` unconditionally clears `_state._mic_level_worker_thread = None` and unregisters after a `join(timeout=1.0)`, even if the thread is still alive; `:94` then resets the shared stop bool to `False` and spawns a new worker. The two sibling paths guard correctly: `level_monitor/worker.py:128-136` returns early while the worker is alive, and `recording/capture_audio_worker.py:266-269` clears the slot only when `not is_alive()`.

**User Impact:** A rapid stop→start with a slow `event_bus.publish` can leave two live consumers on the shared coalesce queue, an untracked daemon thread for the session, and a stale thread-registry entry. Level values stay correct thanks to the queue lock — this is CPU/handle hygiene, not wrong data.

**Root Cause:** Verified code shape; the slow-publish reachability is suspected (needs the 1s join to expire before the 0.25s backstop).

**Gain vs Trade-off:** Gain: one worker per session, deterministic cleanup. Trade-off: a generation token adds a small amount of state.

**If We Do It:** A restart cannot resurrect a stopped-but-still-running worker.

**If We Don't:** Repeated start/stop cycles can accumulate threads.

**My Recommendation:** ✅ Implement — mirror the existing sibling pattern.

**Progress:** `None yet.`

**Related Files:**
- `voice_typer/server/level_monitor/mic_level_push.py:92-100,110-124`
- `voice_typer/server/level_monitor/worker.py:119-143`
- `voice_typer/server/recording/capture_audio_worker.py:253-269`

**Fix:** Clear `_mic_level_worker_thread` only when `not t.is_alive()`, exactly as `worker.py:128-136` does, and give each worker a generation token checked at the loop top so a late restart cannot undo a stop. Add a stop→restart test with a deliberately slow `event_bus.publish` asserting exactly one live worker. Keep C-MIC-16/22 semantics intact.

**Simplified Fix:** Do not forget an old microphone-level worker until it has actually stopped, and tag each worker so a new one cannot cancel an old stop.

**Implementation Difficulty:** 🟡 Medium

**Severity:** 🟢 Low

---

### RH-22 — Prewarm timeout bounds the waiter, not the PortAudio stream
**Status:** ❌ Not Fixed

**Description:** `voice_typer/server/recording/device_prewarm.py:213-226` spawns a nested daemon that opens/starts/stops/closes an `sd.InputStream` (close only in its own `finally`, `:197-201`). The outer thread waits `result["done"].wait(timeout=2.0)` and returns on timeout with no cancel handle. C-MIC-23 records real WASAPI opens blocking ~12s after idle.

**User Impact:** On a stuck device the OS microphone indicator stays lit after the "prewarm timed out" log, and the late stream open can overlap the first dictation's own open.

**Root Cause:** Verified code shape; a cancel token is absent, so the timeout only controls the observer.

**Gain vs Trade-off:** Gain: no privacy-visible orphan stream. Trade-off: raising the timeout alone would hide the symptom without bounding the resource.

**If We Do It:** A timed-out prewarm closes (or never starts) its stream, so the indicator goes dark.

**If We Don't:** The documented worst case keeps producing an unbounded visibility window.

**My Recommendation:** ✅ Implement — C-MIC-23 already supplies the motivation.

**Progress:** `None yet.`

**Related Files:**
- `voice_typer/server/recording/device_prewarm.py:185-226`
- `tests/fixtures/sleep_seam.py`

**Fix:** Add a cancel flag checked immediately before `stream.start()`; when the outer wait times out, set it so the inner thread closes without starting. Register the inner thread with a stop event and keep the `finally` close. Add a fake-`sd.InputStream` test whose `start()` blocks past the timeout, asserting no started/unclosed stream remains. Keep the 2s timeout unless host evidence justifies changing it.

**Simplified Fix:** If prewarming the microphone takes too long, make sure the attempt is actually abandoned rather than just reporting a timeout while the stream keeps opening.

**Implementation Difficulty:** 🟠 Hard

**Severity:** 🟢 Low

---

### RH-23 — Startup daemons lack a uniform cancellation contract
**Status:** ❌ Not Fixed

**Description:** `voice_typer/server/startup_sequence/_phases_late.py:178-188,213-219,228-234,243-249,290-299,315-321` and `_phases_early.py:132-136,160-164` spawn roughly ten fire-and-forget daemon threads (autostart-sync, pack-check, extractor-refresh, probe-prewarm, desktop-shortcut, mic-guard, VAD/GTCRN preload, history-retention). Only `_pack_check_task` and `_extractor_refresh_task` receive `_shutdown_event` (`_phases_late.py:204,211,226`); the others have no stop event, no `ThreadRegistry` registration, and no join, so `ThreadRegistry.shutdown_all()` cannot signal them. RACE-020's `_shutting_down` re-checks exist between phases, not inside these threads. `_phases_early.py:388-409` registers `history-retention-apply`, proving the pattern is available but applied inconsistently.

**User Impact:** Best-effort startup work (registry writes, disk sweeps, network probes) can keep mutating OS/config state after `_shutting_down` is set, racing teardown. All are daemons, so process exit is the backstop — bounded but not deterministic, and there is no shutdown log for them.

**Root Cause:** Verified — per-thread ad-hoc spawning added incrementally without a uniform contract. Not a claim that RACE-020 is missing.

**Gain vs Trade-off:** Gain: deterministic drain and shutdown observability. Trade-off: touching startup threads is timing-sensitive; keep the existing phase ordering and daemon semantics.

**If We Do It:** Every startup worker is cancellable and bounded-joined at shutdown.

**If We Don't:** The daemon backstop remains the only guarantee.

**My Recommendation:** 🟡 Try and revert — startup timing changes need careful regression testing.

**Progress:** `None yet.`

**Related Files:**
- `voice_typer/server/startup_sequence/_phases_late.py`
- `voice_typer/server/startup_sequence/_phases_early.py:388-409`
- `voice_typer/server/thread_registry.py:208-218`

**Fix:** Use `ThreadRegistry.spawn_and_register` (or register immediately after start) for every startup daemon, pass `_shutdown_event` uniformly, and check it at each thread's first I/O boundary. Keep the two already-signalled tasks unchanged. Add a shutdown test asserting each registered worker is signalled and bounded-joined. Preserve RACE-020 and C-START-1 ordering.

**Simplified Fix:** Register all the little startup helper threads with the same shutdown tracker, so app exit can tell them to stop instead of relying on them being daemons.

**Implementation Difficulty:** 🔴 Very Hard

**Severity:** 🟢 Low

---

### RH-24 — Permission tests assert callback counts after fixed sleeps
**Status:** ❌ Not Fixed

**Description:** `tests/test_permissions.py:1014-1131` uses `time.sleep(0.10)` at 1030/1050/1082 against `Timer(interval=0.01)`, and `sleep(0.002)`/`0.05`/`0.03` at 1115/1123/1128 against `interval=0.005`. Assertions such as `assert callback.call_count == 0` (1032) and `assert timer_count["n"] == 1` (1085) depend on those sleeps; `wait_until` appears zero times in the file although `tests/fixtures/wait_helpers.py:34-40` provides it. This is an instance of C-TEST-16 ("do not assert a cross-thread transition with a fixed short wait").

**User Impact:** On a loaded CI worker the 0.10s budget can expire before the Timer fires, so a cancellation-guard test passes trivially (the callback never ran) and the baseline test can flake red.

**Root Cause:** Verified code shape; the false-green consequence is suspected (no reproduced flake).

**Gain vs Trade-off:** Gain: a real race guard. Trade-off: instrumenting a fired-marker event is a small test change.

**If We Do It:** "Not fired yet" can no longer masquerade as "the guard worked".

**If We Don't:** The DE-32 cancellation guard keeps a false-green mode.

**My Recommendation:** ✅ Implement — direct C-TEST-16 compliance.

**Progress:** `None yet.`

**Related Files:**
- `tests/test_permissions.py:1014-1131`
- `tests/fixtures/wait_helpers.py:34-40`

**Fix:** Add a `threading.Event` fired-marker set by the callback/Timer, and `wait_until(marker.is_set, timeout=5.0)` before asserting call counts. Use the same deadline helper for the positive case. Prove the negative by the worker still being in-flight (or the marker never being set after a provable fire), not by elapsed time. No production change.

**Simplified Fix:** Wait for the timer to actually fire with a generous deadline before counting calls, so a slow CI machine cannot make the test pass without testing anything.

**Implementation Difficulty:** 🟢 Easy

**Severity:** 🟡 Medium

---

### RH-25 — numpy lazy-import guard is a no-op in the full suite
**Status:** ❌ Not Fixed

**Description:** `tests/test_numpy_lazy_import.py:21-22` returns `False` from `_purge_numpy_and_targets()` when `"numpy" in sys.modules`, and both guard tests gate their entire assertion on `if clean_baseline:` (`:46-49,82-92`). Full-suite collection imports numpy via `tests/fixtures/ipc_test_helpers.py:9`, itself imported by `tests/handlers/conftest.py:7-10`. Therefore under CI's `pytest tests/ -n auto` the numpy-absence assertions never execute; only an isolated single-file run activates them. This is the C-TEST-9 class (hermeticity depending on ambient import state).

**User Impact:** The cold-start guard against reintroducing eager `import numpy` in the audio/transcription path is a no-op in CI; a regression can ship green.

**Root Cause:** Verified.

**Gain vs Trade-off:** Gain: a guard that actually runs everywhere. Trade-off: each test must own its `sys.modules` seam via monkeypatch, or use a subprocess.

**If We Do It:** The import guard fails on a real eager-import regression in any run mode.

**If We Don't:** The regression it was written for is unguarded in CI.

**My Recommendation:** ✅ Implement — makes an existing guard real.

**Progress:** `None yet.`

**Related Files:**
- `tests/test_numpy_lazy_import.py:19-25,81-92`
- `tests/fixtures/ipc_test_helpers.py:9`
- `tests/handlers/conftest.py:7-10`

**Fix:** Stop conditioning assertions on ambient import state: patch the `sys.modules` seam per test with monkeypatch `setitem`/`delitem` (restored in teardown), or run the import in a fresh subprocess. Add a self-check that seeds a deliberately eager import and asserts the guard fails, so a no-op guard cannot persist. Do not rely on `if "<pkg>" in sys.modules` skip guards (C-TEST-9).

**Simplified Fix:** Make each test set up its own clean import state instead of skipping when numpy was already imported by another test during collection.

**Implementation Difficulty:** 🟡 Medium

**Severity:** 🟡 Medium

---

### RH-26 — Collection-time bare `MagicMock` modules carry a pytest-9.2 undo hazard
**Status:** ❌ Not Fixed

**Description:** `tests/conftest.py:15-23` uses `sys.modules.setdefault("pystray", _mock_pystray_collection)` with a bare `MagicMock()`, plus `MagicMock(name="collection_pynput")` for pynput/pyperclip, and mutates `_mock_pystray_collection.Menu.SEPARATOR = "SEP"` globally. `tests/test_logging_formatting.py:19-20` uses the same bare-`MagicMock` pattern. The repo already ships the correct stand-in (`tests/fixtures/mock_modules.py:20-35`, children in real `__dict__`). pytest 9.2 snapshots `target.__dict__` for undo, so patching an auto-created mock child can abort `monkeypatch.undo()` (web-confirmed: `github.com/pytest-dev/pytest/issues/15287`). This is C-TEST-15.

**User Impact:** Order-dependent hermeticity — a child patch on a collection mock can poison later tests on the same xdist worker. Fixtures currently replace these mocks before test bodies, so no failure was reproduced.

**Root Cause:** Verified pattern + documented mechanism; reproduced failure not observed.

**Gain vs Trade-off:** Gain: stable undo semantics across pytest versions. Trade-off: none — the correct helper already exists.

**If We Do It:** All stubbed third-party modules round-trip patch/undo like real modules.

**If We Don't:** The exact failure class behind the 8323-failure CI incident stays reachable.

**My Recommendation:** ✅ Implement — delete the duplicate pattern, use the existing helper.

**Progress:** `None yet.`

**Related Files:**
- `tests/conftest.py:15-23`
- `tests/test_logging_formatting.py:12-20`
- `tests/fixtures/mock_modules.py:20-35`

**Fix:** Register `mock_module(name)` stand-ins at collection via `setdefault`, or delete the collection-time mocks and rely on `mock_heavy_imports_session` / `mock_heavy_imports` which already use `mock_module`. Remove the global `MagicMock` class mutation. Keep C-TEST-14/C-TEST-15 semantics; no `sys.modules` patch of dynamically-proxied package names.

**Simplified Fix:** Use the project's proper fake-module helper at import time instead of dropping raw mock objects into `sys.modules`.

**Implementation Difficulty:** 🟡 Medium

**Severity:** 🟢 Low

---

### RH-27 — conftest is a catch-all with silently swallowed teardown errors
**Status:** ❌ Not Fixed

**Description:** `tests/conftest.py` is 632 lines mixing heavy-import mocks, env/config/HF isolation, log and event-bus state, and multiple independent teardown drainers. Six drainers use `with contextlib.suppress(Exception)` (around lines 362-431) and five more use `except Exception`; an ImportError inside a drain is silently swallowed. The diagnostic thread at `:522-527` is a `daemon=True` thread with no RACE-008 why-comment.

**User Impact:** A leaked thread or failed teardown can survive into later tests without a signal; one edit fans out across unrelated concerns. No user-facing failure.

**Root Cause:** Verified — one cleanup fixture added per past leaked-thread incident, never consolidated (C-STRUCT-1/3, RACE-008).

**Gain vs Trade-off:** Gain: narrow error handling and a discoverable fixture layout. Trade-off: splitting conftest must keep every autouse fixture resolving via re-exports (E1 create-first).

**If We Do It:** Teardown failures are visible and fixtures are organized by concern.

**If We Don't:** The catch-all keeps growing and hides its own failures.

**My Recommendation:** 🟡 Defer — opportunistic split only; narrow the `suppress` blocks when touching this file.

**Progress:** `None yet.`

**Related Files:**
- `tests/conftest.py:1-632` (drains ~356-436, diagnostic thread ~522-527)
- `tests/fixtures/`

**Fix:** Split drain/diagnostic fixtures into focused `tests/fixtures/` modules re-exported by conftest; narrow each `contextlib.suppress(Exception)` to the expected import/teardown exceptions and log anything else; add a thread-leak assertion; add the required one-line RACE-008 why-comment to the daemon snapshot thread. Do not remove protected tags or suppressions that pin real false positives without a documented reason (E13).

**Simplified Fix:** Break the giant test-setup file into topic files, stop silently ignoring all teardown errors, and say why the diagnostic thread is a daemon.

**Implementation Difficulty:** 🟠 Hard

**Severity:** 🟢 Low

---

### RH-29 — "Torch-free" bundle gate only detects dotted module names
**Status:** ✅ Fixed (verified)

**Description:** `scripts/build/check_bundle_torch_free.sh:59-74` sets `PATTERNS=("torch\\.")`, a regex for a literal dot. It matches dotted forms (`torch.nn`, `torch._C`) but not Nuitka's slash-form paths such as `torch/__init__.py`, which the comment at `:59-62` says it is meant to catch. The same pattern is used by the Python fallback at `:117`. The gate is hard-fail in `tauri-windows-build.yml:308`, `tauri-macos-build.yml:141,302`, `tauri-linux-build.yml:436`.

**User Impact:** A regression that reintroduces `import torch` in slash form can ship a ~150 MB larger sidecar and re-expose the NU-106 VAD degradation while CI stays green. Dotted forms are still caught, so this is partial coverage — not total blindness.

**Root Cause:** Verified regex shape; the production occurrence of a slash-form path is suspected until a built-binary probe is run.

**Gain vs Trade-off:** Gain: the gate matches what its own comment promises. Trade-off: none — strengthening the pattern cannot weaken the check.

**If We Do It:** Both dotted and slash-form module paths fail the gate.

**If We Don't:** The documented failure mode stays undetected.

**My Recommendation:** ✅ Implement — one-line fix plus a unit probe.

**Progress:** Fixed 2026-11-21. `PATTERNS` now uses `torch[./\\]`, so both the GNU grep ERE scanner and the Python `re` fallback reject dotted, slash and backslash forms; the dotted match and case-insensitivity are preserved. Five black-box tests against the real script cover slash, dot and clean binaries; `bash -n`, ruff, and review clean. Workflows untouched.

**Related Files:**
- `scripts/build/check_bundle_torch_free.sh:59-74,117`
- `.github/workflows/tauri-windows-build.yml:308`
- `.github/workflows/tauri-macos-build.yml:141,302`
- `.github/workflows/tauri-linux-build.yml:436`

**Fix:** Use `torch[/\\]` in the ERE path and the equivalent escaped pattern in the Python `re` path, keeping case-insensitivity; do not weaken the existing dotted match. Add a unit test feeding a synthetic binary containing `torch/__init__.py` and asserting exit 1, plus one for `torch.nn`. Keep the workflow wiring unchanged (C-CI/CD sign-off applies only if workflows change).

**Simplified Fix:** Make the check look for both slash-style and dot-style torch module names, and test it with a fake binary containing each.

**Implementation Difficulty:** 🟡 Medium

**Severity:** 🟡 Medium

---

### RH-30 — Full-offline installer reports success on failed extraction or slim-core failure
**Status:** ✅ Fixed (verified)

**Description:** `scripts/windows/full-offline-installer.nsi:99-105` checks `Expand-Archive`'s exit code with only a `DetailPrint` warning, then deletes the zip unconditionally at `:105`. The slim-core installer's `ExecWait` exit code in `$0` is only warned about (`:146-148`), so the wrapper still exits 0. Meanwhile `installer-state.json` is written with `pack_bundled: true` (`:118-126`), telling the app to skip the silent download.

**User Impact:** A corrupt/interrupted extraction leaves a partial or empty pack marked as bundled, so offline transcription is silently unavailable; a failed slim-core install still looks successful. PowerShell's non-terminating error behavior may make the exit code 0 on a corrupt zip — suspected, not confirmed.

**Root Cause:** Verified non-fatal code paths; the PowerShell exit-code behavior is suspected.

**Gain vs Trade-off:** Gain: honest install outcome and no premature zip deletion. Trade-off: `Abort` changes wrapper UX on genuinely recoverable warnings — restrict it to real failures.

**If We Do It:** Failed extraction or slim-core install fails the wrapper and leaves the zip for retry.

**If We Don't:** Broken installs look successful and offline transcription is unavailable with no download fallback.

**My Recommendation:** ✅ Implement — install correctness.

**Progress:** Fixed 2026-11-21. PowerShell extraction now fails hard (`-ErrorAction Stop` + `$ErrorActionPreference`), a nonzero extract or slim-core exit aborts the wrapper, and the downloaded zip is deleted only after a successful extraction check. The `pack_bundled: true` state write moved last, so it is only written on full success. OutFile name and state schema unchanged; 5 new source/order pins, 52 installer tests green, review clean. Windows `makensis` compile/install smoke test remains owed (host lacked makensis).

**Related Files:**
- `scripts/windows/full-offline-installer.nsi:99-126,144-148`
- `voice_typer/server/service/offline_pack/core.py`

**Fix:** Add `$ErrorActionPreference = 'Stop'` / `-ErrorAction Stop` to the PowerShell extraction command; `Abort` on nonzero extraction or slim-core exit; delete the zip only after extraction success plus a file/size assertion. Keep the documented autostart and quoting rules (C-CROSS-1/2). `VALIDATE ON WINDOWS HOST`.

**Simplified Fix:** Treat a failed pack extraction or failed main installer as a failed install, and keep the download file until extraction is proven good.

**Implementation Difficulty:** 🟡 Medium

**Severity:** 🟡 Medium

---

### RH-31 — NSIS wrapper forwards `$CMDLINE` instead of the parameter string
**Status:** ✅ Fixed (verified)

**Description:** `scripts/windows/full-offline-installer.nsi:144-145` does `ExecWait '"$PLUGINSDIR\slim-core-setup.exe" $CMDLINE' $0` with a comment claiming `/S` and `/D=path` propagate. NSIS's `$CMDLINE` includes the installer executable's own path, and `/D=` is explicitly excluded from it (NSIS reference §4.2.2, web-verified).

**User Impact:** A silent install with a custom directory can place the pack in `$LOCALAPPDATA\lausu` while the app lands elsewhere, so pack discovery fails — compounding RH-28.

**Root Cause:** Verified — wrong NSIS variable, false comment.

**Gain vs Trade-off:** Gain: correct silent/custom-dir installs. Trade-off: `/D=` cannot be forwarded via `$CMDLINE`, so it needs explicit handling or documentation.

**If We Do It:** `/S` and the requested install directory reach the slim-core installer.

**If We Don't:** Custom-directory silent installs keep diverging.

**My Recommendation:** ✅ Implement — one-file fix.

**Progress:** Fixed 2026-11-21. The wrapper now includes `FileFunc.nsh`, calls `${GetParameters} $R0`, and forwards `$R0` (parameters only) to the slim-core installer; the false `/S`+`/D=` comment was replaced and `/D=`'s wrapper limitation documented. The old `"$CMDLINE" in text` test pin was replaced with four independent assertions blocking the old contract. NSIS semantics verified against official docs; 52 installer tests green, review clean. Windows compile/install smoke test still owed.

**Related Files:**
- `scripts/windows/full-offline-installer.nsi:144-145`
- `scripts/windows/installer-hooks.nsh:137-139`

**Fix:** Use `${GetParameters} $R0` (FileFunc) and forward `$R0`; handle `/D=` explicitly or document that it cannot propagate through this wrapper. Update the misleading comment. Add a source-level test asserting `$CMDLINE` is no longer forwarded. `VALIDATE ON WINDOWS HOST`.

**Simplified Fix:** Pass only the installer's arguments to the inner installer, not the full command line including the wrapper's own path.

**Implementation Difficulty:** 🟡 Medium

**Severity:** 🟡 Medium

---

### RH-32 — Release and architecture docs drifted from the shipped pack flow and IPC surface
**Status:** ✅ Fixed (verified)

**Description:** Three related doc gaps. (1) `RELEASING.md:113-123` claims tag push triggers `build.yml` to build and upload installers, but `build.yml:38` states it is quality gates only (`docs/code-notes/ci-workflows.md:65` confirms legacy packaging jobs are retired); there is no step to dispatch `runtime-pack-publish.yml` (which is `workflow_dispatch`-only), and the `tauri-` tag wording has been stale since the 2026-09-17 cutover. (2) Six docs still cite "85-command / 51-event" (`docs/API.md:11`, `docs/README.md:23`, `docs/adr/README.md:40`, `docs/migration/tauri-sidecar-bridge.md:16,204`, `docs/cutover-playbook.md:350-351`, `docs/modules/sidecar_ws.md:13,26`); the live surface is 109 commands, 105 Rust-allowlisted, 61 events, 73 typed push events. (3) `docs/adr/README.md:51-52` skips the accepted ADR-0029, and `docs/README.md:58,63-67` links a removed ADR-0014 and says the range is `0000..0020`.

**User Impact:** A release engineer following `RELEASING.md` can ship a slim installer without publishing the pack manifest/zip, leaving the silent downloader with no asset and offline transcription unavailable. Contributors get a wrong IPC surface and cannot find an accepted ADR.

**Root Cause:** Verified — docs never reconciled with the approved pack split (SP-1) and the 2026-11-02/+ IPC additions. The unsubstantiated "hardcoded brand" sub-claim was removed by review.

**Gain vs Trade-off:** Gain: a runbook that ships the right artifacts and docs that match code. Trade-off: none — doc-only; avoid hard-coded counts that drift again.

**If We Do It:** The release flow names the real artifact workflows and the mandatory pack dispatch; docs link the canonical counts instead of restating them.

**If We Don't:** Releases can omit the pack and docs keep teaching a retired flow.

**My Recommendation:** ✅ Implement — doc-only, high operational value.

**Progress:** Fixed 2026-11-21. RELEASING.md now names tauri-*-build.yml as artifact producers, build.yml as quality gates only, and the mandatory manual runtime-pack-publish.yml dispatch for both the release and offline-pack tags; slim/full-offline installers documented. Stale counts in six docs replaced with links to canonical `docs/ipc-reference.md` values (110 commands = 105 Rust + 5 host, 61 events, 73 typed push events); ADR-0029 row, ADR range 0000..0030 and removed-ADR-0014 note added. Doc-count tests/checker reconciled; 120 focused tests green, review clean. Workflows and historical ADR-0020 pins untouched.

**Related Files:**
- `RELEASING.md:4-11,113-123`
- `docs/API.md:11`, `docs/README.md:23,58,63-67`
- `docs/adr/README.md:40,51-52`
- `docs/ipc-reference.md:45,315` (canonical counts)
- `docs/code-notes/ci-workflows.md:65`

**Fix:** Rewrite `RELEASING.md` §4/§9 to name `tauri-{windows,macos,linux}-build.yml` as artifact producers and add a mandatory manual `runtime-pack-publish.yml` dispatch for both the primary release and the `offline-pack` rolling tag; document slim + full-offline installers. Replace hard-coded command/event counts with links to `docs/ipc-reference.md` / `registry.py` (or update to 109/105/61/73) and add a cheap doc-count parity check. Add the ADR-0029 row, fix the range, and annotate the removed ADR-0014 link.

**Simplified Fix:** Update the release guide to match the actual build and pack-publish workflows, and stop repeating old command counts in six documents.

**Implementation Difficulty:** 🟢 Easy

**Severity:** 🟢 Low

---

### RH-33 — Release publisher is a 789-line module with two transports
**Status:** ✅ Fixed (verified)

**Description:** `scripts/release/publish_pack_release.py:1-789` holds gh command builders (`:102-207,447-505`), a full urllib REST backend (`:218-324,508-612`), asset validation, a result dataclass, and the CLI. Two independent upload transports share only the data shape, which is above C-STRUCT-3's ~500-line budget.

**User Impact:** Maintenance cost — a change to upload semantics must be made in two places. No runtime defect today.

**Root Cause:** Verified — the API backend was added in place as a fallback without extraction.

**Gain vs Trade-off:** Gain: one upload implementation, easier testing. Trade-off: a create-first split must keep every workflow and test import resolving via re-exports (E1).

**If We Do It:** One publisher with pluggable backends; re-exports keep callers unchanged.

**If We Don't:** Transport drift stays a standing risk.

**My Recommendation:** 🟡 Defer — structural, no user impact; do it when the publisher is next touched.

**Progress:** Fixed 2026-11-21. `publish_pack_release.py` is now a thin facade at the workflow-pinned path; implementation split into `result.py`, `backends/gh.py`, `backends/api.py`, `publisher.py` and `cli.py`. All 14 public names plus the four private patch seams are re-exported/migrated to owning modules; identity pins and upload semantics unchanged. 73 scoped tests green, E1 imports and CLI entry verified, review clean. No workflow changes.

**Related Files:**
- `scripts/release/publish_pack_release.py`
- `.github/workflows/runtime-pack-publish.yml`

**Fix:** Create-first split into `release/backends/gh.py`, `release/backends/api.py`, `release/publisher.py`, `release/cli.py`; re-export all public names from `publish_pack_release.py` so workflow/test imports keep resolving (E1), verify, then trim. Pin upload semantics with a test against both backends. Do not change release behavior as part of the split.

**Simplified Fix:** Split the big release-publishing script into small files — one per upload backend, one for shared logic, one for the CLI — keeping the old import path working.

**Implementation Difficulty:** 🔴 Very Hard

**Severity:** 🟢 Low

---

### RH-34 — Renderer request types lag the command allowlist
**Status:** ❌ Not Fixed

**Description:** `voice_typer/client/src/renderer/src/types/ipc/requests.ts:539-642` defines 93 typed `type:` literals while the Rust renderer allowlist (`src-tauri/src/commands/sidecar_cmds/allowlist.rs:40-179`) has 105 commands. Twelve live commands (including `set_output_volume`, `microphone_test_status`, `provider_list/models/test/set_key/clear_key/set_domain`, `quit_app`, `restart_app`) go through the loose `type: string` overload at `usePython.ts:167`. Server↔Rust IPC parity tests already exist (`tests/test_ipc_command_parity.py`, `test_rust_allowlist_parity.py`, `test_ipc_protocol_cross_language_parity.py`); the gap is only renderer type documentation, which AGENTS.md explicitly says is NOT an allowlist.

**User Impact:** Command-name typos and wrong `data` shapes on those 12 calls compile clean. No runtime break — a type-safety and documentation gap, not a defect.

**Root Cause:** Verified — the union grew incrementally and the loose overload silently absorbs gaps.

**Gain vs Trade-off:** Gain: editor/compile-time checking for the remaining calls. Trade-off: MUST NOT create a third allowlist — parity stays server `_COMMAND_REGISTRY` ↔ Rust `allowed_commands()` only.

**If We Do It:** The typed union covers all renderer-reachable commands; the loose overload remains only for the documented escape-hatch cases.

**If We Don't:** Type drift continues on the 12 calls.

**My Recommendation:** ✅ Implement — type-only change, no runtime behavior.

**Progress:** `None yet.`

**Related Files:**
- `voice_typer/client/src/renderer/src/types/ipc/requests.ts:539-642`
- `voice_typer/client/src/renderer/src/lib/python-bridge/usePython.ts:149-167`
- `src-tauri/src/commands/sidecar_cmds/allowlist.rs:40-179`

**Fix:** Add typed request interfaces for the 12 missing commands and append them to `PythonRequest`. Add a test that parses `requests.ts` literals and asserts they cover the commands the renderer actually calls — do NOT assert equality with the Rust allowlist or introduce a new renderer-side allowlist (critical IPC contract; renderer `types/ipc/` is documentation). Keep the existing server↔Rust parity tests as the only allowlist gate.

**Simplified Fix:** Give the remaining untyped renderer calls proper TypeScript request shapes, without turning the type file into a new permission list.

**Implementation Difficulty:** 🟠 Hard

**Severity:** 🟢 Low

---

### RH-35 — Config pruning runs before migrations and backup, killing legacy branches
**Status:** ❌ Not Fixed

**Description:** `voice_typer/server/config/loader.py:225` calls `_filter_unknown_keys_impl` (which returns only dataclass fields at `:163` and physically rewrites `config.json` at `:162,186`) BEFORE `_run_migrations` (`:243`) and `_backup_before_migration_impl` (`:246`). Migration source keys `sound_volume`, `push_to_talk_hotkey`, `runtime_pack_consent`, `silence_rms_threshold`, `normalize_audio` are absent from the current `Config` dataclass and from `_KNOWN_EXTERNAL_CONFIG_KEYS` (`:112-119`), so the `if key in data` branches in `_migrate_to_v3/v4/v5/v7` (`config_internals/migrations.py:99-205`) are dead on real loads. `tests/config/test_config_schema_migration.py:283-317` calls migrators directly with hand-made dicts and never asserts the load-level warning, giving false confidence. Only `offline_pack_consent` is force-healed (`:255`).

**User Impact:** Users with legacy configs get the generic "ignoring N unrecognized settings" warning instead of the specific per-version explanation, and the pre-migration `.bak` contains already-pruned data, so it cannot restore the original keys. This is data-integrity adjacent and was upgraded to High by the final review.

**Root Cause:** Verified — the unknown-key filter was inserted ahead of the migration runner and nothing preserves migration-source keys.

**Gain vs Trade-off:** Gain: migrations actually execute and backups are meaningful. Trade-off: run migrations on raw parsed data and filter only afterwards, preserving C-CONF-5's single-profile and explicit-migration rules.

**If We Do It:** Legacy configs migrate with their specific warnings and the backup captures the pre-migration file.

**If We Don't:** Those migration branches remain dead code and the backup is misleading.

**My Recommendation:** ✅ Implement — config data integrity.

**Progress:** `None yet.`

**Related Files:**
- `voice_typer/server/config/loader.py:112-119,135,162-186,225,243-255`
- `voice_typer/server/config_internals/migrations.py:99-205`
- `tests/config/test_config_schema_migration.py:283-317`

**Fix:** Compute `unknown_keys` against `cls.__dataclass_fields__ | _KNOWN_EXTERNAL_CONFIG_KEYS | <migration-source keys>`, and run `_run_migrations` on the raw parsed dict with the backup taken before any destructive rewrite; filter only after migrations+backup. Add a load-level test asserting the v7 `_load_warnings` string for a v6 config carrying `sound_volume`, and a test that the `.bak` still contains the removed key. Respect C-CONF-5 (no runtime overwrite of valid settings without a documented reason).

**Simplified Fix:** Migrate old config files before deleting settings the current version no longer knows, and make the backup copy the original file.

**Implementation Difficulty:** 🟠 Hard

**Severity:** 🔴 High

---

### RH-36 — `dictation_lost` event is published with no consumer, contradicting silent recovery
**Status:** ❌ Not Fixed

**Description:** `voice_typer/server/crash_recovery/_store.py:195-209` publishes `{"type": "dictation_lost", ...}` (triggered via `check_on_startup` at `:154` from `startup_sequence/_phases_early.py:345`). The event is registered in `event_bus.py:248`, forwarded by `src-tauri/src/sidecar/ws/event_protocol.rs:73`, and pinned by `tests/test_dictation_lost_message.py`, but grep of the renderer finds zero subscribers and no TS interface or `KNOWN_EVENT_TYPES` entry. Meanwhile `_phases_early.py:348-352` describes startup recovery as "fully silent ... no event-bus notification", and `tests/test_notifications.py:48` / `tests/test_recovery_startup_notify.py:65` pin the user-visible silence.

**User Impact:** One wasted WS frame per recovery detection and a contradictory contract in code. User-visible silence is intact — this finding does NOT claim the owner's silent-recovery decision is violated.

**Root Cause:** Suspected — the event/wire/test were added after the silence decision was recorded; resolution needs an owner choice.

**Gain vs Trade-off:** Gain: one truth for the event. Trade-off: deleting the publish also removes its test and allowlist entry; wiring a consumer would change the silent UX and needs owner approval.

**If We Do It:** Either the dead event is removed everywhere, or it is deliberately wired with a real subscriber and the startup text corrected.

**If We Don't:** A no-op frame stays and maintainers read two conflicting statements.

**My Recommendation:** 🟡 Try and revert — owner decision required; do not "fix" by editing only the comment.

**Progress:** `None yet.`

**Related Files:**
- `voice_typer/server/crash_recovery/_store.py:154,195-209`
- `voice_typer/server/startup_sequence/_phases_early.py:345-352`
- `src-tauri/src/sidecar/ws/event_protocol.rs:73`
- `tests/test_notifications.py:48`, `tests/test_recovery_startup_notify.py:65`

**Fix:** Ask the owner which truth governs. If silence stands, delete the publish, its test, the Rust allowlist entry, the `EVENT_TYPES` entry, and the ipc-reference row. If the event is wanted, add a TS interface, `KNOWN_EVENT_TYPES` entry, and a real renderer subscriber, and correct the startup text. Never resolve by editing only the comment or only the test.

**Simplified Fix:** Decide whether the "dictation was recovered" message should exist at all; if not, remove the dead notification end to end, and if yes, actually show it.

**Implementation Difficulty:** 🟢 Easy

**Severity:** 🟢 Low


## 2026-11-19 decision round — additional notes

- **RH-11:** owner decided to KEEP the soft type-check gate; no workflow or baseline change.
- **Storybook removal:** `.storybook/`, 8 `*.stories.tsx`, story-only decorators, scripts, deps, lock entries, config references and the Storybook icon catalog entry were removed. Case-insensitive `storybook|stories` search in source files is now 0 (the only remaining hits are historical evidence under `.tmp-evidence/`). Mixed-purpose files were surgically cleaned, not deleted.
- **License:** root `LICENSE` is the exact official PolyForm Strict 1.0.0 text (fetched from the `polyformproject/polyform-licenses` tag `1.0.0`) plus `Required Notice: Copyright 2026 Abdallah IsDev`. Declarations updated in pyproject (text form — not an official SPDX id), Cargo.toml, client package.json, README and website, installer license text and third-party notices. Project is described as **source-available**, never open source. Third-party attributions preserved.
- **Runner migration (own note, not a review finding):** all 8 functional `macos-14` jobs moved to `macos-15` (Apple Silicon) / `macos-15-intel` (x86_64), verified against official GitHub runner docs. Risks unverified until CI: Python 3.13 on Intel, Xcode/SDK deployment target, codesign/notarize on macOS 15, and universal2 `lipo` merge across two runner types. Historical `BUILD-N03` evidence comment intentionally left untouched.
- **License compatibility (report only):** pystray 0.19.5 (LGPL-3.0-or-later) and PyAV's bundled FFmpeg (LGPL 2.1+) carry relink/source-offer obligations that need the owner's legal review under a source-available distribution. No dependency was changed for this.


## 2026-11-20 follow-up verification (RH-11..RH-20 round)

- **RH-12 lock chain (verified):** `requirements-lock.txt` markers put `cryptography==50.0.0`, `secretstorage==3.5.0` and `jeepney==0.9.0` on Linux only (`# via keyring -> secretstorage -> {cryptography, jeepney}`). Marker evaluation for linux-x86_64 / macos-x86_64 / macos-arm64 / windows-amd64 shows `cryptography` present only on Linux; `cffi` is cross-platform because sounddevice/soundfile also need it. No macOS x86_64 set pulls cryptography >=49. OSV queries for 50.0.0/50.0.1/50.0.2 returned no advisories (3552 fixed in 50.0.0, 3553/3554 in 49.0.0); latest 50.0.2 is a wheel/toolchain refresh, not a security patch. No floor raise, no lock regeneration, no suppression; `pip-audit --strict --require-hashes -r requirements-lock.txt` exits 0.
- **RH-12 fixtures (verified, not circular):** all four encrypted constants in `tests/test_text_crypto_compat.py` were re-derived byte-for-byte from the OLD `cryptography` AESGCM implementation retrieved with `git show HEAD:voice_typer/server/_text_crypto.py` (old module first added in af143fe1dd576af7a91a939099a0308b00b2fcfb). Preserved format: `enc:v1:` + base64(nonce[12] || ciphertext || tag[16]), AAD=None, 32-byte DEK from OS keyring. Failure behavior matches old (placeholder `<decryption failed>`; bad nonce length raises ValueError).
- **RH-12 regression classification:** `tests/test_history_db_encryption.py` -> 1 failed / 19 passed; the only failure is the schema assertion `assert '6' == '5'` at line 407 (encryption tests pass when deselected). Same for `tests/test_history_db_trigram_cjk.py:82`. Both classified (b): the test files are unchanged from HEAD while another session's `schema.py` sets `_CURRENT_SCHEMA_VERSION = 6`. No failure caused by this round. Scoped runs: tests/server 397 passed/1 skipped, tests/packaging 2 passed, tests/tauri 1035 passed/597 skipped, crypto 70 passed.
- **Frozen bundle (Part D):** all three sidecar Nuitka scripts use `--include-package=Crypto`; all three worker scripts use `--nofollow-import-to=Crypto`; `test_crypto_import_reachability.py` pins both boundaries and confirms no retired `cryptography` claim. Real frozen `Crypto.Cipher.AES` import remains **UNVERIFIED** (no Nuitka/PyInstaller/pybs locally; only stub binaries). CI/owner probe command recorded in worklog.
- **License identifier (Part E):** verified against the current SPDX list that `PolyForm-Strict-1.0.0` is NOT official (spdx.org JSON 404; only PolyForm-Noncommercial and PolyForm-Small-Business exist). Project manifests now use `LicenseRef-PolyForm-Strict-1.0.0` (PEP 639 in pyproject), `SEE LICENSE IN LICENSE` (package.json), `license-file = "../LICENSE"` (Cargo.toml). Build backend floor raised to setuptools>=77; real metadata generation produced `License-Expression: LicenseRef-PolyForm-Strict-1.0.0` and `License-File: LICENSE`.
- **Client (Part F):** clean re-run of full vitest 416 files / 4805 passed / 7 skipped; typecheck:ci, build and `npm audit --audit-level=high` all exit 0. All 11 overrides audited with `npm ls`; 3 non-Storybook orphans retained per AGENTS.md. `npm run lint` remains exit 1 (18 errors / 18 warnings), inventory in worklog; CI gate at `.github/workflows/client-ci.yml:72`.
- **Intel runner horizon (Part G, research only):** `macos-15-intel` is scheduled to retire Aug/Fall 2027 (runner-images issue #13045; GitHub changelog 2025-09-19); `macos-26-intel` is the current newer Intel label. Moving the x64 leg to Apple Silicon needs an x86_64 python-build-standalone plus `arch -x86_64` around Nuitka, otherwise an arm64 binary could be named x86_64. No workflow changed.


## 2026-11-20 (round 3) — runner horizon note

Official GitHub sources DISAGREE on the end of Intel macOS runners: actions/runner-images issue #13045 says `macos-15-intel` is available "until August 2027" and is "the last available x86_64 image from Actions", while the GitHub changelog (2025-09-19) says x86_64 will not be supported after the macOS 15 image retires in Fall 2027, and the current runner-images README still lists newer x64 labels (`macos-26-intel`, `macos-26-large`, `macos-latest-large`). The Intel-runner plan is therefore DEFERRED — no workflow was changed this round. Keep `macos-15-intel` until the owner chooses between `macos-26-intel` and an Apple-Silicon-hosted x86_64 build (which needs an x86_64 python-build-standalone plus `arch -x86_64` around Nuitka; otherwise an arm64 binary can be named x86_64).


## 2026-11-20 (round 4) — FFmpeg/PyAV licence settled from the binary

Verified from the ACTUAL locked binary, not from websites: `av==17.1.0` (`requirements-lock.txt:11`), installed `av.__version__ = 17.1.0`, wheel `cp311-abi3-win_amd64`. All six bundled FFmpeg DLLs return `LGPL version 3 or later` verbatim from `avutil_license()`, `avcodec_license()`, `avformat_license()`, `swresample_license()`, `swscale_license()` and `avfilter_license()`, and all six report the identical configuration string (no `--enable-gpl`, no `--enable-nonfree`, but libx264/libx265 present). The authoritative licence answer is therefore **LGPL version 3 or later**; the flag/codec discrepancy is not resolvable from the binary and upstream build-documentation claims are labelled as such. `docs/THIRD_PARTY_NOTICES.md` was rewritten from these binary facts; source offer and replaceability remain **pending owner decision**. A drift test (`tests/packaging/test_third_party_notices_av_version.py`) pins the notice version to the lock. Windows runbook unsigned-build instructions and the ytdlp_log ffmpeg comment were corrected.


## 2026-11-20 (round 5) — bundled DLL licences and PyAV dependency facts

Binary/wheel facts: `av.libs` contains **25** DLLs, not 24. `av-17.1.0.dist-info/METADATA` states only PyAV's own `License-Expression: BSD-3-Clause` plus `License-File` entries; there is no per-DLL licence field and no licence text inside `av.libs/` or `av/`. Embedded DLL strings give `libav* license: LGPL version 3 or later` followed by `FFmpeg version 8.1.1`; `libx265` states `GPLv2 or commercial`; `libiconv` states LGPL in its VersionInfo comment. Upstream documentation (URLs in THIRD_PARTY_NOTICES.md) supplies the remaining licences: libx264 GPL v2, libx265 GPL v2-or-commercial, libmp3lame LGPL v2, libiconv LGPL v2.1+, the two GCC runtimes GPLv3 with Runtime Library Exception, and the rest permissive (BSD/MIT/Apache/zlib/winpthreads). Both GPL DLLs are LOAD-TIME imports of `avcodec-62` — always loaded, not lazy. Upstream pyav-ffmpeg 8.1.1-2 patches `configure` to move libx264/libx265 from the GPL list to the version3 list, which explains the LGPL v3+ string without `--enable-gpl`; patches are not echoed into the printed configuration. faster-whisper imports `av` at module scope (`faster_whisper/audio.py:15`), so av must be installed for `import faster_whisper` to work; our own Media decoder uses av lazily (`media_ingest/decoder.py:31,131,162,200`) and our ASR path accepts pre-decoded float32 (`worker/_transcribe.py:330`). No compliance claim made; source offer and replaceability **pending owner decision**.

### PLUGIN-ARCH-3, A completed dictation cleared the prompt box by navigating (New chat), reloading the platform view every time
**Status:** ✅ Fixed (2026-11-20, Orchestrator, verified live with real speech and the window in the BACKGROUND). Cause: after a delivered transcript `run.js` fires the async `clean` command, and `clean()` clicked the platform's "New chat" control — in-page navigation that reloads the platform view and discards the user's page state. A second, latent defect rode along: `content.js` carried TWO `clearComposer()` definitions (a dead sync one shadowed by the async one), and `ensureCleanComposer()` clicked New chat *before* trying to clear in place, so even the "dirty box" path navigated. Fix: ONE `clearComposer()` with a five-step ladder (`execCommand` select+delete, selectAll+delete, selectAll+insertText '', `innerHTML='<p><br></p>'` + input events, `textContent=''` + input events) and both `clean()` and `ensureCleanComposer()` try in place FIRST, New chat only as a fallback; `cancel()` also clears in place. The DOM strategies are the ones that matter in practice: `execCommand` silently does nothing when the tab does not own OS focus, and the dictation window is normally in the background while the user types in another app — measured live on Gemini (Quill `rich-textarea`): with the window focused the composer cleared at step 1, with another window focused it stayed dirty through the editing commands and cleared through the DOM path. Evidence (live, Chrome backgrounded): `POST /start` -> recording; SAPI speech -> `POST /stop` returned "background cleanup verification sentence"; 4 s later `/status` showed `has_text:false` with the URL still `https://gemini.google.com/app` (no navigation, no reload); `probe` all PASS. Pinned by `test/content_clean_in_place.test.js` (4 cases: in-place with no New chat click, unfocused DOM path, New chat fallback only when every strategy fails, already-empty no-op). Suite: node bridge 55 pass, `tests/plugins` + packaging 157 pass, `ruff check .` clean, `build-extension --check` up to date.
**Description:** (owner report 2026-11-20) "the page is being reloaded after each dictation session is completed and the text is delivered, presumably to clear the prompt box ... clear the prompt input field programmatically without reloading the page."
**User Impact:** Every dictation threw away the platform view (scroll position, open thread, in-progress draft) and looked like a page reload.
**Root Cause:** `content.js::clean()` (and `ensureCleanComposer()`) used the New chat control as the clearing mechanism; the in-place clear was either shadowed by a duplicate definition or never tried first.
**Related Files:** `tools/internal_plugins/_common/bridge/extension/content.js`, `tools/internal_plugins/_common/bridge/run.js` (async cleanup), `tools/internal_plugins/_common/bridge/test/content_clean_in_place.test.js`, `docs/code-notes/shared-stt-bridge.md`.
**Fix:** in-place-first clearing with a focus-independent DOM ladder; navigation only as a last-resort fallback.
**Severity:** 🟠 Medium (user-visible disruption every dictation)
**Priority:** P1


## 2026-11-20 (round 6) — decode-only claim narrowed; GGUF/noise dependency map

Verified: every `av.open()` in app source is read-mode (decoder.py:40,135,167); zero `add_stream`/`OutputContainer`/`.mux(`/encoder contexts/`ffmpeg` subprocess calls in `voice_typer/**/*.py`. yt-dlp options (downloader.py:93-110, url_resolver.py:32/76-92, subtitles.py:34-43) request `bestaudio/best`, `skip_download`, no postprocessors, no `-x`/audio_format/merge_output_format/ffmpeg_location. Runtime trace of repo WAV fixture (pcm_s16le), temp mpeg4+aac MP4 and rawvideo AVI (created outside the repo with PyAV, NOT x264/x265, then deleted): every stream has `is_decoder=True`, `is_encoder=False`; `decode_chunks` ignores video and a video-only file raises `no_audio`. Verdict: PARTLY PROVEN — no code path opens libx264/libx265 (proven); the wheel still ships those DLLs as load-time imports of avcodec; stdlib `wave` writes PCM WAV in cloud/_transport.py:30, level_monitor/test_recording.py:203,212 and scripts/build/generate_beeps.py:109; live URL/YouTube behavior untested.
Dependency map: `av` remains in S1-S4 (today; Whisper off CTranslate2; RNNoise removed; other noise removed) because pyproject.toml:112 declares it directly for decoder.py. Scenario closure removes faster-whisper+ctranslate2+setuptools in S2, +21 entries in S3, no further av requirer change in S4. Noise: DPDFNet (default) and GTCRN are bundled ONNX + onnxruntime, no av/audiolab; pyrnnoise imports audiolab.av -> av at import time (pyrnnoise/pyrnnoise.py:19-20), so removing RNNoise drops audiolab and its 17-entry closure but av survives via the direct declaration. transcribe.cpp (upstream documentation) accepts 16 kHz mono float32 raw samples in Python (`session.run(pcm_float32_16k_mono)`) and does NOT decode containers, so Media still needs a decoder.
Read-only filesystem scan: Nuitka onefile cache `%LOCALAPPDATA%/lausu/onefile-tmp/av.libs` holds 25 DLLs, FFmpeg 8.1.2 build (different hashes from the locked 17.1.0 wheel's 8.1.1 DLLs); installed `%LOCALAPPDATA%/Voice Typer/` sidecar/worker show no av strings and no av.libs cache. No published-installer FFmpeg DLLs found.
One doc fix: THIRD_PARTY_NOTICES.md sentence now reads `GPLv3 with the GCC Runtime Library Exception 3.1 for the two GCC runtimes`, matching the table. `pytest tests/packaging -q --no-cov` -> 3 passed.


## 2026-11-20 (round 7) — GPL-DLL-free release planning; research only

Owner decisions recorded, not reopened: replace PyAV decoder with subprocess of official LGPL-only ffmpeg; RNNoise stays; ~1 Jan 2027 release must contain no libx264/libx265/other GPL DLL; GGUF migration not guaranteed before release; yt-dlp stays.

Verified: three av links into the installer — (1) our decoder.py:31,131,162,200 (only direct av imports under voice_typer/); (2) faster-whisper/audio.py:15 `import av` at module scope (only call-time uses at :37,46,87,92; our code has ZERO decode_audio calls, all transcribe paths pass np.ndarray), upstream 1.2.1 still requires av, no documented optional/release; (3) pyrnnoise/__init__.py:15 -> pyrnnoise/pyrnnoise.py:19-20 -> audiolab/av/__init__.py:17 `import av`; `import pyrnnoise.rnnoise` STILL triggers it via package __init__, but loading rnnoise.py by file path via find_spec bypasses it (probe: av/audiolab not in sys.modules, process_frame works). This also RESTORES RNNoise, which is currently broken in this venv (PyAV 17.1.0 removed av.option; audiolab 0.5.1 expects it) and silently degrades to GTCRN.
Freeze facts: `--include-package=av` at build_sidecar_windows.sh:172, macos:175, linux:285; worker scripts already `--nofollow-import-to=pyrnnoise/audiolab` (windows:239-240, macos:241-242, linux:284-285); no --noinclude-dlls anywhere; freeze uses build-env site-packages (`$PY -m nuitka`), not requirements-lock.txt — CI installs `-e ".[dev,test]"` without the lock, so the 8.1.1-locked notice can drift from an 8.1.2-era build env. No build-time gate rejects x264/x265/avcodec today.
Local ffmpeg 9.0.1 on this machine is GPL (`--enable-gpl --enable-libx264 --enable-libx265`, `ffmpeg -L` says GPLv3) — NOT a usable LGPL candidate. LGPL-only candidates (upstream documentation): BtbN FFmpeg-Builds LGPL win64/linux64/linuxarm64 with per-asset sha256; dfloresc macOS lgpl with SHA256SUMS; serversideup (decoder whitelist fails our formats); mt-mograph (no ffprobe). Throwaway parity prototype in TEMP (deleted): ffmpeg subprocess vs PyAV decode_chunks produced bit-exact output — 7 sources, max_abs_diff=0.0, identical chunk counts/shapes/dtype/sample counts, including 44.1 kHz stereo resample and -ss seek; no_audio and decode_failed classifications matched; truncated WAV decoded to 0.125 s and the existing validation gate rejects it.
No code/dependency/lock/workflow changes. Source-offer and replaceability remain pending owner decisions; no legal conclusion.

### PLUGIN-ARCH-4, Hotkey press steals focus (and may reveal a blank Chrome window): the profile "visibility" call shows/activates windows on every press
**Status:** ✅ Fixed (worker implementation + orchestrator live verification; two follow-ups in Verified)
**Description:** (owner report 2026-11-20) With the Gemini plugin selected, pressing the dictation hotkey in a Tauri/WebView target app drops the target app's active state immediately (taskbar shows nothing active, the app's own unfocused opacity kicks in), a THIRD Chrome window with a black surface appears, and at stop time the pasted text lands somewhere other than the field that was focused. Owner also reports that a field whose content already ends in a space still receives a second space.
**User Impact:** Auto-paste is unreliable in Tauri/WebView targets (the main paste use case), the app looks broken while idle-dictating, and spacing duplications corrupt text.
**Root Cause (partially verified by the Orchestrator; the worker must confirm each):**
1. `_common/bridge/chrome_profile.py::set_window_visible()` enumerates EVERY top-level window of the recorded pid and calls `ShowWindow(hwnd, SW_SHOW)`. `SW_SHOW` **activates**, and the plugin calls this on every hotkey press (`plugin.py::_ensure_browser`). That is a focus thief in the dictation start path, plugin-only, and it explains why the paste (which targets the foreground window at paste time, C-PASTE-1 Option A) no longer reaches the original field.
2. The same function shows ALL windows of that pid, including helper windows (`Chrome_WidgetWin_0`, `Base_PowerMessageWindow`, IME/CTF windows measured at 0x0 on the live instance) and any window Chrome created but never painted — the prime suspect for the blank window that appears exactly on the hotkey press and can be closed without consequence.
3. The pid it trusts is whatever `Popen` returned, written to `<plugin>/chrome_pid.json`. Both plugins write that file for the SAME Chrome profile, and `anthropic_stt/chrome_pid.json` currently holds `4028`, which is a **dead** pid (the live dictation browser is `2300`) — a recycled pid would make `set_window_visible` show an unrelated process's window.
4. Not yet verified: whether the Tauri **bubble** window (`src-tauri/tauri.conf.json` bubble: `visible:false`, `alwaysOnTop`, `skipTaskbar`, no `focus:false`/`focusable:false`) also activates on show. If it does, the focus theft affects every provider, not just plugins.
5. Spacing case 3: the shared `delivery_text_for_target` DOES handle a trailing-space prefix (`verdict=trailing-space` -> no separator, lowercase first letter), so a doubled space means the caret read lost the trailing whitespace (providers trim block text) or the path bypasses the helper — the `[CLIPBOARD] delivery verdict=…` DEBUG line in `lausu.log` answers which.
**Related Files:** `tools/internal_plugins/_common/bridge/chrome_profile.py` (`set_window_visible`, `_windows_for_pid`, `launch`, `_record_pid`), `tools/internal_plugins/*/plugin.py` (`_ensure_browser`), `tools/internal_plugins/_common/bridge/session.py`, `src-tauri/tauri.conf.json` (bubble window), `src-tauri/src/commands/bubble/*`, `voice_typer/server/clipboard_target_safety/caret_text.py`, `tools/internal_plugins/_common/delivery.py`, `voice_typer/server/dictation_pipeline/paste_step.py`, `voice_typer/server/clipboard/*`.
**Fix:** never show/activate a window on the dictation path (hide-only at launch, `SW_SHOWNOACTIVATE` at most), identify the real browser window (class/title/rect + validated fresh pid, resolved via the profile in the command line), expire stale pid files, verify the bubble does not activate, add a bounded "restore the window captured at start" paste guard (owner request; conflicts with C-PASTE-1 Option A -> owner decision), and read the single character before the caret so trailing whitespace survives.
**Verified (orchestrator, 2026-11-20):**
- Spacing cases 1/2/3 proven LIVE in real Chrome inputs for English AND Arabic (verdicts `empty` / `needs-space` / `trailing-space`; field contents read back as `Dictated words`, `hello dictated words`, `hello dictated words` and the Arabic equivalents, exactly one U+0020 or none). `caret_text.py` reads the field's own `DocumentRange` first and rejects escaping blocks.
- No window is shown or activated on a press: both `_ensure_browser` implementations only call `session.ensure_browser`; `set_window_visible` is hide-only there and uses `SW_SHOWNOACTIVATE` on a `Chrome_WidgetWin_1` frame; measured `GetForegroundWindow()` unchanged across a call; pid validation rejects a recycled pid (the owner's own Chrome fails `is_valid_browser_pid` for the dictation profile).
- Bubble: `focus:false` + `focusable:false` plus `WS_EX_NOACTIVATE` on every show (`cargo test --bin lausu-tauri` 796 passed).
- Suites: 378 passed / 1 skipped scoped python, 55/55 node, ruff clean, packaging 22 passed.
- Follow-ups: (a) `_spans_document` skips its containment test for blocks <=256 chars, so a SMALL escaping block is still trusted when the field is non-empty (removing the gate breaks 8 pins that model a single-paragraph field where block == document; the real rule is control-type based, not size based); (b) `_is_browser_window` accepts a 48x48 zero-title `Chrome_WidgetWin_1` helper measured on live Chrome. The C-PASTE-1 narrowing (bounded restore of the start-time target) stays an owner decision.
- Extension registration false FAIL fixed during this review: Chrome derives an unpacked id from the path SPELLING, so the live profile registers `flppnpcgilbgogcddcgahibcjdeflneb` while `install.json` still names `kkinik...`; `install_paths.py`/`install_paths.js` now match by PATH first (tested) and `verify_extension_install.py` reports the install healthy again.
**Severity:** 🔴 High
**Priority:** P0


## 2026-11-20 (round 8) — implementation: RNNoise fix, ffmpeg subprocess decoder, Windows LGPL binary

Part A: RNNoise now runs through our own minimal ctypes binding (`audio_filters/rnnoise_ctypes.py`), loading the native library from its package directory WITHOUT importing pyrnnoise/audiolab/av. Proof in this venv: `effective_method: rnnoise`, `is_degraded: False`, `pyrnnoise/audiolab/av in sys.modules: [False, False, False]`, input RMS 0.248421 -> output RMS 0.000634 (-51.86 dB). Missing library still falls back to GTCRN with one WARNING. Freeze scripts include the native library as data per platform.
Part B: `media_ingest/decoder.py` now calls ffmpeg as a subprocess with argv `ffmpeg -hide_banner -loglevel error -nostdin -protocol_whitelist file|http,https,tcp,tls,crypto [-ss S] -i SRC -vn -map 0:a:0 -ac 1 -ar 16000 -c:a pcm_f32le -f f32le -`, bounded 64-line stderr tail, bounded stdout reads, 80,000-sample chunks, scoped cancel_event, terminate+reap on close/cancel/failure. Parity vs the retired PyAV reference: identical chunk counts/shapes/dtype/sample counts and max_abs_diff 0.0 (repo fixture, 44.1 kHz resample, 12 s, seek). yt-dlp now pins `fixup: "never"` because it auto-detects ffmpeg and would otherwise start FFmpegFixup postprocessors.
Part C: pinned BtbN LGPL win64 static build, immutable tag `autobuild-2026-11-20-12-40`, SHA-256 `0322fe632c4f6e1fb92c3a3648e100fec702bf86792c4440b4dfda22f7b95b82`; manifest + verifying fetch script + 20 network-free tests. All 32 accepted extensions have decoders. Part D: Windows x64 full/slim Tauri configs declare ffmpeg/ffprobe externalBin; base/macOS/Linux unchanged. Part E: notices updated from verified facts.
Verification: ruff clean on all touched Python; bash -n OK; combined scoped pytest 695 passed. `cargo check` passes with MSYS2 mingw64 bin on PATH. Full `tests/tauri` has 3 failures about `bubble_host_hidden` command parity from another workstream — not touched here. No workflow/lock/dependency edits, no commit/push.


## 2026-11-20 (round 9) — round-8 fixes, release-branch ffmpeg pin, ffprobe removal, consolidated notices

Part A: strict ffmpeg gate restored (`_ffmpeg_usable` exists + executable); tests inject only real executable paths. EOF-race stress test: 600 real spawns (corrupt/truncated/video-only x200) -> 0 misclassified, 0 orphan PIDs; it exposed a real bug (ffmpeg's bracketed hex context mimicking HTTP 403/500) now fixed by stripping `[...@addr]` before classification. pyrefly errors in our tests fixed properly (0 errors, no suppressions/baseline). yt-dlp source: ffmpeg presence does not reroute typical YouTube audio (HttpFD / DashSegmentsFD / HlsFD; only live HLS uses FFmpegFD); `fixup: never` already short-circuits FFmpegFixup postprocessors.
Part B: pinned release-branch LGPL build n9.0.2-61-gd59078794d-20261120 (tag autobuild-2026-11-20-12-40, sha256 814c62c35ca7e2b15d85b0a2a5b79bbf21783176520154f26a6df1e9df72761e, archive 171,850,189 B). Duration parity ffmpeg-vs-ffprobe 7/7 on real dev and pinned binaries; ffprobe removed from shipped set and both Windows x64 configs. probe_remote ported to ffmpeg stderr parsing too. `probe_remote` no longer needs ffprobe in the frozen app. BtbN retention: daily 14 days, month-end 2 years; manifest has empty mirror TODO fields.
Part C: consolidated notices generated from local audit facts (46 catalog components, 138 npm production packages, 310-crate Windows Rust graph, 16 license groups, 24 distinct license texts), shipped as a Tauri resource and reachable from About & Privacy in all 8 locales. FFmpeg/PyAV hand-written sections preserved and updated to the release build. Full license texts emitted once per identifier; 17 items marked UNVERIFIED where the shipped file alone cannot establish the license.
Verification: ruff clean, pyrefly 0 on touched files, 724 scoped pytest passed, notice generator deterministic, client typecheck passed (worker). No commits/pushes/workflow/lock changes.


## 2026-11-20 (round 10) — CI wiring signed off; nothing executed in GitHub yet

Part A: verified owner mirror asset (live `gh api`: 171850189 B, sha256:814c62c35ca7e2b15d85b0a2a5b79bbf21783176520154f26a6df1e9df72761e, byte-identical to BtbN pin). Manifest mirror fields filled; `fetch_ffmpeg_lgpl_win64.sh --fetch-plan` prints mirror then fallback with the same hash; gh-auth/Bearer-token support added for private mirrors; license gates kept. i18n: the reported 7 failures were ALREADY fixed in HEAD (commit 8dc20a3c3 moved theme.switchTitle/media.metaYoutube to exact-value LANGUAGE_NEUTRAL_VALUES); 47 tests pass and no locale edits were needed — forcing translations would break the gate (E12/E13).
Part B (owner sign-off, ONLY tauri-windows-build.yml edited; caller unchanged): fetch step in all three x64 legs (sidecar freeze, worker freeze, slim Tauri build); hash-locked freeze env (`pip install --require-hashes -r requirements-lock.txt` then `--no-deps -e ".[dev,test]"`) with pip-freeze evidence artifact; post-build gate `scripts/verify_windows_bundle.py` (bundle contents, frozen-sidecar self-check, single ENFORCE_NO_GPL_DLLS soft switch default 0, $GITHUB_STEP_SUMMARY sizes, notices artifact). Added sidecar `--self-check` entry point (inert on normal startup). Unsigned path needs no signing secrets and never passes tauri.windows-signed.json (steps gated on SIGN_ENABLED=true); signed steps unchanged. `ENFORCE_NO_GPL_DLLS=1` MUST be set in the round that removes PyAV; PyAV and its GPL DLLs intentionally still ship this round.
Validation: ruff clean, pyrefly 0, 861 scoped pytest passed, gate --self-test PASS, YAML parse OK (actionlint unavailable). NOTHING WAS RUN IN GITHUB — no workflow trigger, no installer built, no CI result yet.


## 2026-11-21 (round 11) — onefile-aware GPL gate, self-check robustness, CI step order

Part A: `verify_windows_bundle.py` now scans BOTH the exe bytes (labeled 'exe string scan (blind to compressed onefile payloads)') and the Nuitka onefile extraction dir by filename (authoritative for ENFORCE_NO_GPL_DLLS=1), reporting all DLLs under av.libs. Freeze script pins `--onefile-tempdir-spec="{CACHE_DIR}/lausu/onefile-tmp"`; Nuitka docs say a static spec is a cached, non-deleted dir, so it is deterministically `%LOCALAPPDATA%\lausu\onefile-tmp`; override via `--onefile-extract-dir` / LAUSU_ONEFILE_EXTRACT_DIR; PID/TIME specs are refused. Soft-switch semantics unchanged; synthetic-dir tests cover hit under 0/1 and a clean dir.
Part B: `ffmpeg_binaries.bundled_bin_dir()` is now the single base used by both the resolver and selfcheck. Nuitka docs confirm sys.executable is the original onefile exe, so the base is correct (no production bug). NoiseSuppressor already had public read-only properties is_degraded/degraded_reason/effective_method; selfcheck now uses them. Dev self-check with a temp LGPL ffmpeg: env-override-outside-exe-dir correctly FAILS adjacency; simulated frozen adjacency PASSES bundled-ffmpeg/decode-samples=16000/rnnoise-active with ALL PASS.
Part C (authorized two workflow edits only): post-build verification gate moved AFTER installer/SHA256SUMS/notices uploads but still hard-fails; gate output tee'd to gate-output.txt and uploaded with `if: always()` as Lausu-Windows-Gate-Output (pipefail preserves exit code, proved rc=7). No other workflow/gate changed.
Part D: read-only classification written to C:/Users/11/lausu-commit-plan.md: 38 paths = 34 ours, 0 uncommitted other-session paths (their work is in 13 local-only commits), 4 unknown deleted screenshots. Branch must be cut from local HEAD, not origin/main. Earlier `review-*.diff` files are gone from the repo root (removed externally). No git state changes.
Verification: ruff clean, pyrefly 0, gate --self-test PASS, 592 scoped pytest passed. Nothing was run in GitHub.

## 2026-11-21 — round 13/14: Nuitka onefile resolver and frozen detection (CORRECTION)

CORRECTION of the round-11 statement that `sys.executable` was correct in a Nuitka onefile: that statement was wrong. A real Nuitka 2.8.10 onefile probe (not documentation) in all four launch modes (absolute path from another cwd, relative from own folder, bare name via PATH, Python subprocess spawn) printed `sys.executable` inside `C:\Users\11\AppData\Local\lausu\ONEFIL~1\python.exe` and `__compiled__.containing_dir` at the ORIGINAL exe directory. `sys.frozen` was `None`; `NUITKA_ONEFILE_DIRECTORY` held the original directory. `__compiled__.containing_dir` is the correct base in all four modes. A second onefile containing a byte-identical copy of `ffmpeg_binaries.py` confirmed `is_frozen_build() == True`, `bundled_bin_dir()` at the original exe dir, and resolution of the sibling `ffmpeg.exe` while a GPL ffmpeg on PATH was ignored.

`bundled_bin_dir()` now prefers `__compiled__.containing_dir` (dev fallback: `sys.executable.parent`); `is_frozen_build()` covers both Nuitka (`__compiled__`) and PyInstaller (`sys.frozen` / `_MEIPASS`). Frozen builds have NO PATH fallback. `selfcheck.py` now requires five markers: frozen-build, no-path-fallback, bundled-ffmpeg, decode-samples=16000, rnnoise-active; the gate requires all five and fails closed on an empty/missing onefile extraction dir under `ENFORCE_NO_GPL_DLLS=1`.

FINDING (not fixed here): `voice_typer/server/autostart/tauri_spawn.py:196` uses `Path(sys.executable).resolve().parent` for its manifest lookup. The probe proves that is the onefile extraction dir, so that path has the same latent onefile issue as the old ffmpeg resolver. It needs a separate fix; it is deliberately out of scope this round.

CI run 44834921579 failed at `cargo test` because base `tauri.conf.json` declares `bin/lausu-worker` while the slim job downloaded only the sidecar and generated only slim stubs. Fix: drop `--slim` from the stub step (the full registry creates the worker stub; the slim `tauri build` overlay still excludes the worker, so the post-build "no worker in bundle" assertion holds). Probes were deleted after use; no dependency/lock/workflow changes beyond that step.


## 2026-11-21 — round 18: cached onefile isolation, non-fail-fast gate, notice hygiene
- PART A probe (Nuitka 2.8.10, `--onefile-tempdir-spec={CACHE_DIR}/lausu-probe-r18/onefile-tmp`): v1 printed `A.txt = v1`, `B.txt = MISSING`; after rebuilding v2 with A=v2 plus B.txt it printed `A.txt = v2`, `B.txt = new-in-v2`; after v3 removed B from the payload it still printed `B.txt = new-in-v2`. Two exes on the same spec mixed files (worker saw A/B plus C). Verdict: changed/new files are re-extracted, so a stale dir alone does NOT explain the missing local rnnoise.dll; REMOVED files DO survive a cached-mode update, and sharing a spec mixes payloads. `{VERSION}` with `--product-version` and `{PRODUCT}` with `--product-name` produced distinct static cached dirs per product/version: `LausuSidecar/1.0.2611.1635` and `LausuWorker/1.0.2611.1635`, no mixing.
- All six freeze scripts now use per-product + per-build-stamp extraction paths (Windows spec `{CACHE_DIR}/{PRODUCT}/{VERSION}/onefile-tmp`, product names LausuSidecar/LausuWorker, `BUILD_STAMP` from UTC date/time). `verify_windows_bundle.py` resolves the versioned cached dir by product root + newest `*/onefile-tmp`; tests updated. Frozen proof needs the rebuild in this round's run.
- `selfcheck.py` and the gate are non-fail-fast: all five SELFCHECK markers and all gate sections (bundle, self-check, GPL tables, sizes) are produced even when one fails; final `FAILED CHECKS` line and exit 1. Removed the `shutil.which == resolved` rejection that misread the staged `ffmpeg.exe` as a PATH hit on Windows.
- `generate_third_party_notices.py` strips trailing whitespace from every emitted line; regenerated notices pass `--check` and zero trailing-whitespace lines.
