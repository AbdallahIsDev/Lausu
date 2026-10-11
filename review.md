## High Priority

These items are the highest-priority remaining work for the project. They block the Tauri migration, fix core functionality, or address critical infrastructure gaps. Items in this section are ordered by priority (top = most urgent).

> **Won't Fix tasks live in `WONT_FIX.md`**: deliberately not solved. Do NOT fix them (AGENTS.md C-REVIEW-1). See that file for the full list.

## 🚫 E. Cannot Verify (needs real host)
**19 findings require Windows / macOS / Linux desktop runtime.** The
headless-provable slices were fixed + tested 2026-09-15 (4-lane wave, see
per-item notes); the interactive cores still need real hosts (see
`docs/migration/windows-validation-runbook.md`,
`docs/migration/macos-validation-runbook.md`,
`docs/migration/linux-validation-runbook.md`). New automation:
`.github/workflows/host-validation.yml` (manual dispatch, scope
all/windows/macos/linux; undispatched as of this edit) + contract pins
`tests/tauri/test_host_validation_workflow.py`. These items are partially
verifiable headless, not fully fixable: re-check the noted host
observations before marking anything done.

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
**Status:** OPEN.
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

### PK-1 - Enforce the pack min_proto_version handshake at worker launch
**Status:** OPEN.
**Description:** The pack manifest schema already carries `min_proto_version` (`server/service/offline_pack/core.py:33`, validated at `:171-212`), and the host resolves a versioned pack dir (`src-tauri/src/platform/worker_path.rs`, default v1, `VOICE_TYPER_PACK_VERSION` override), but nothing enforces compatibility: the spawn path (`src-tauri/src/sidecar/spawn/worker.rs:279` reads the version, `:185` gates only on binary presence) will launch any worker found on disk. A stale pack after an app update loads the wrong protocol and fails obscurely mid-transcription instead of refusing fast with a clear state.
**Fix:** After resolving the pack dir and before spawn, read `pack-manifest.json`, compare `min_proto_version` against the host/sidecar's supported range, and on mismatch refuse to launch while publishing the `outdated` pack state (feeds PK-2) so the UI offers re-download instead of a dead worker. Cover with Rust unit tests (match/mismatch/missing-manifest) + a Python test for the manifest reader. Do NOT change the manifest schema.
**Related Files:** `src-tauri/src/platform/worker_path.rs`, `src-tauri/src/sidecar/spawn/worker.rs`, `voice_typer/server/service/offline_pack/core.py`, `voice_typer/server/service/offline_pack/checksum.py`
**Success:** stale-pack launch refused with an `outdated` signal (not a mid-job failure); new tests green; no schema change.
**Implementation Difficulty:** Low-Medium
**Severity:** Medium (silent protocol mismatch after any pack-format change)
**Priority:** P2

### PK-2 - User-visible pack state machine (Settings screen + global states)
**Status:** OPEN.
**Description:** Pack states today are fragmented: an `OfflinePackPreparingBanner` near mic-test/transcription areas plus an About-page update check (`check_offline_pack_update`), backend events in `server/service/offline_pack/events.py`, consent gates in `gates.py` — but no Settings screen and no single source for the states users actually hit: downloading (with progress), ready, missing, broken (checksum/incomplete), outdated (see PK-1). Users currently discover pack problems only when transcription fails.
**Fix:** Add one Settings section backed by a single status query (state + version + progress, reusing the existing events/check commands, no new IPC surface unless the status query cannot be composed): ready/missing/downloading(progress %)/broken/outdated, each with its action (download/retry/repair/remove). Keep the existing banner as the point-of-use surface; it reads the same status. New renderer tests per state + i18n keys in all 8 locales (C-I18N-1/2).
**Related Files:** `voice_typer/client/src/renderer/src/pages/settings/`, `voice_typer/client/src/renderer/src/components/feedback/OfflinePackPreparingBanner.tsx`, `voice_typer/server/service/offline_pack/events.py`, `voice_typer/server/service/offline_pack/gates.py`
**Success:** every pack state reachable in Settings with a working action; banner + Settings never disagree (shared status); locale-complete; suites green.
**Implementation Difficulty:** Medium (renderer-heavy, needs real download runs to verify progress display)
**Severity:** Medium (pack problems surface today only as failed transcriptions)
**Priority:** P2

### PK-3 - Rehearse the pack/worker failure table on all three systems
**Status:** OPEN.
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

# FV Session

### FV-31 — tests/ root holds 716 flat test files (243 already live in 26 domain subdirs)
**Status:** ❌ Not Fixed (2026-09-21 FV session: re-confirmed 727 flat root files; the entry's own recommendation is 🟡 Defer — opportunistic migration only when a file is already being edited, since a bulk move is churn-for-churn. No bulk move performed.)
**Description:** Newer test domains get subdirectories, but 716 legacy files still sit flat at the tests/ root. Largest sampled files are single-domain (no catch-all mixing found — the E3 violation pattern is absent), so this is navigability cost, not a correctness risk.
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
