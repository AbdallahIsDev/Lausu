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
**Status:** ✅ Fixed headless 2026-10-12 (Rust unit tests unrun — no cargo in sandbox; Python parity 22/22 green as proxy; live stale-pack refusal still needs a real host).
**Description:** The pack manifest schema already carries `min_proto_version` (`server/service/offline_pack/core.py:33`, validated at `:171-212`), and the host resolves a versioned pack dir (`src-tauri/src/platform/worker_path.rs`, default v1, `VOICE_TYPER_PACK_VERSION` override), but nothing enforces compatibility: the spawn path (`src-tauri/src/sidecar/spawn/worker.rs:279` reads the version, `:185` gates only on binary presence) will launch any worker found on disk. A stale pack after an app update loads the wrong protocol and fails obscurely mid-transcription instead of refusing fast with a clear state.
**Fix:** After resolving the pack dir and before spawn, read `pack-manifest.json`, compare `min_proto_version` against the host/sidecar's supported range, and on mismatch refuse to launch while publishing the `outdated` pack state (feeds PK-2) so the UI offers re-download instead of a dead worker. Cover with Rust unit tests (match/mismatch/missing-manifest) + a Python test for the manifest reader. Do NOT change the manifest schema.
**Related Files:** `src-tauri/src/platform/worker_path.rs`, `src-tauri/src/sidecar/spawn/worker.rs`, `voice_typer/server/service/offline_pack/core.py`, `voice_typer/server/service/offline_pack/checksum.py`
**Success:** stale-pack launch refused with an `outdated` signal (not a mid-job failure); new tests green; no schema change.
**Implementation Difficulty:** Low-Medium
**Severity:** Medium (silent protocol mismatch after any pack-format change)
**Priority:** P2

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

---

# DC Session (2026-10-12, Groups 1/2/6/7, INVESTIGATION ONLY, 4 waves)

> Wave 1: 4 parallel investigators (G1/G2/G6/G7). Wave 2: 2 reviewers (REQUEST-CHANGES: 5 false/inflated Wave1 claims dropped, severities recalibrated). Wave 3: 4 verifiers re-checked every survivor at exact lines + hunted new issues. Wave 4: 2 closers (G1/2/6: REQUEST-CHANGES with downgrades; G7: KEEP 8 / DROP 2). Dropped (never re-file): IPCServer 22-mixin, heatmap-1750, timer facade, worker-RAM-unmeasured, per-chunk-resample, double-RMS, cache-clear, isinstance-dead (unlocated), local-catalog-parity-NEW (already pinned), vitest-guard-NEW (thresholds exist), abort-TOCTOU (unproven), P7-06 (owner question), P7-10 (dupe S5-CR-83). Baseline suite run SKIPPED (RUN_BASELINE_TESTS=OFF); no code changed in this session (investigation mode — zero edits).

### DC-8 — `models.ts` (767 lines) owns local catalog + cloud catalog + selection + formatting
**Status:** ❌ Not Fixed
**Description:** One shared utils file owns the local-model catalog, the cloud-provider catalog, active-model predicates, display formatters, and validation helpers — at least four reasons to change, with cloud-vs-local facts able to drift.
**User Impact:** Navigability/edit-coupling only; no runtime bug.
**Root Cause:** Verified (`voice_typer/client/src/renderer/src/lib/utils/models.ts`, 767 lines, ~37% comments).
**Gain vs Trade-off:** A create-first split (catalog / cloud / selection / format + barrel re-export) isolates edit reasons. Must update the parity-test parser path in the same change (`test_cloud_provider_catalogue_parity.py` parses `models.ts`).
**If We Do It:** Models-page edits touch one concern at a time.
**If We Don't:** The catch-all keeps growing.
**My Recommendation:** 🟡 Defer (opportunistic per FV-31: split only when the file is touched anyway; never a bulk move).
**Progress:** `None yet.`
**Related Files:**
- `voice_typer/client/src/renderer/src/lib/utils/models.ts`
**Fix:** Split into `modelCatalog.ts` / `cloudCatalog.ts` / `modelActive.ts` / `format.ts` with re-export barrel (E1 create-first).
**Simplified Fix:** Divide the oversized models helper into one file per job.
**Implementation Difficulty:** 🟡 Medium
**Severity:** 🟢 Low

### DC-9 — `TitleBar.tsx` (732 lines) owns glyphs + three button layers + layout
**Status:** ❌ Not Fixed
**Description:** One file owns caption glyph paths, the title-bar button, toolbar and chevron buttons, and the full bar layout — three widget layers sharing a file.
**User Impact:** Review/ownership granularity only; cohesive and working.
**Root Cause:** Verified (`voice_typer/client/src/renderer/src/components/layout/TitleBar.tsx`, 732 lines).
**Gain vs Trade-off:** Extracting glyph/button primitives leaves a ~200-line composition with zero visual change. Must preserve C-SIDEBAR-2/3 (single shared ThemeSwitch), RTL pinning, focus ring, C-UI-10 gaps.
**If We Do It:** Bar chrome edits touch one layer at a time.
**If We Don't:** The file keeps growing as one unit.
**My Recommendation:** 🟡 Defer (opportunistic; never bulk-move).
**Progress:** `None yet.`
**Related Files:**
- `voice_typer/client/src/renderer/src/components/layout/TitleBar.tsx`
**Fix:** Extract `captionGlyphs.tsx` + `titleBarButtons.tsx`; `TitleBar.tsx` stays composition-only (E1 create-first, no behavior change).
**Simplified Fix:** Move the button artwork into their own files, leaving the bar as pure layout.
**Implementation Difficulty:** 🟡 Medium
**Severity:** 🟢 Low

### DC-10 — backend factory takes bare `dict` kwargs with no pinned keys
**Status:** ✅ Fixed (2026-10-13: 4 total=False TypedDicts + literal call sites; 114 green, pyrefly scoped 0, negative control flags misspelling; kwargs_map uses Mapping (prompt's dict-form would not type-check — invariance); 4 dict() sites in asr/registry.py:359 + worker/_transcribe.py still un-pinned, need authorization)
**Description:** The backend factory accepts untyped `whisper_kwargs`/`qwen_kwargs` dicts passed straight into engine constructors, so a typo'd key fails only at runtime inside `__init__` and the type checker cannot flag it.
**User Impact:** Misconfigured engine options surface late as runtime errors instead of type errors.
**Root Cause:** Verified (`voice_typer/server/asr_registry.py:96-104,115-120`); contrast `model_registry.py` which uses a frozen dataclass. Weak confidence per Wave 4 (needs exact type + sites at implementation).
**Gain vs Trade-off:** `TypedDict`s (or dataclasses) pin the known keys with a type-only change. Touches `_BACKEND_SPECS` + lifecycle tests.
**If We Do It:** Bad option keys fail at type-check time.
**If We Don't:** Runtime-only failures persist.
**My Recommendation:** ✅ Implement (opportunistic, Easy-Medium)
**Progress:** Done 2026-10-13 (independently verified incl. negative control `"devic"` → bad-argument-type; probe reverted clean).
**Related Files:**
- `voice_typer/server/asr_registry.py:96-120`
**Fix:** Add per-backend `TypedDict`s; annotate `kwargs_map: dict[str, Mapping[str, object]]` (NOT `dict[str, dict[str, object]]` — TypedDict invariance rejects that). Type-only.
**Simplified Fix:** Give the engine option bags named, checked shapes instead of anything-goes dicts.
**Implementation Difficulty:** 🟢 Easy
**Severity:** 🟢 Low

### DC-11 — skipped mic-lost wiring tests pin a renamed API (partial coverage only)
**Status:** ✅ Fixed (2026-10-13: 3 skips re-pinned to new API and unskipped + stop/start semantics updated to match implementation; 1 skip honestly kept with updated reason; 13 passed + 1 intentional skip ON WINDOWS sandbox)
**Description:** Four skip markers pin old private names (`_on_device_lost`, `_cancel_on_mic_lost`, `_mic_device_id_provider`) that exist nowhere in the server tree — only inside the skipped bodies, which would fail if unskipped. Three wiring tests stay active and green; the renamed behavior is partly covered by `test_recording_controller_fixes.py:159`.
**User Impact:** Renamed-API drift goes partially unpinned on C-MIC-16 territory.
**Root Cause:** Verified (`tests/test_active_mic_lost_wiring.py:48,116,203,281` skips vs `recording_controller.py:108-126` + `mic_lifecycle_hooks.py:41-49` new names; Wave 2 false-claim corrected: not "zero assertions").
**Gain vs Trade-off:** Rewriting skip reasons + bodies to the new names restores the pins. Never delete the skipped tests to manufacture green (C-TEST-6).
**If We Do It:** The DJ-65 init-wiring contract is pinned against the current API.
**If We Don't:** Stale skips linger as honest-but-unexecuting placeholders.
**My Recommendation:** ✅ Implement (Low; opportunistic rewrite)
**Progress:** Done 2026-10-13 (init-wiring renames + opened-device/start + after-stop ordering + callback renames; 1 cached-_microphones case kept skipped with honest reason; file green).
**Related Files:**
- `tests/test_active_mic_lost_wiring.py:48-340`
- `voice_typer/server/recording_controller.py:108-126`
- `voice_typer/server/mic_lifecycle_hooks.py:39-49`
**Fix:** Re-pin skipped bodies to `on_device_lost` / `on_active_mic_lost` / `_list_active_mic_ids` per TDD Prove-It, then unskip.
**Simplified Fix:** Update the skipped tests to the current function names so they run again.
**Implementation Difficulty:** 🟢 Easy
**Severity:** 🟢 Low

### DC-12 — suite-size comment pins understate the suite 2-4x (docs-only)
**Status:** ❌ Not Fixed
**Description:** Three comments pin old suite sizes (`pyproject.toml` 544-file / 309-file / 14660-test prose, `vitest.config.ts:28` 237-file, `coverage-baseline.json` 14976 tests) vs measured 811 root test files / 376 vitest files / 17574 collected. PERF-007 arithmetic stays directionally true, magnitudes wrong. Coverage floor 80.0 (baseline 84.84%) is conservative + lockstep-tested — no drift, merged here, no separate filing. FV-31 counts refreshed in place (811 vs 716/727 strengthens its Defer).
**User Impact:** None runtime; stale magnitudes mislead capacity math.
**Root Cause:** Verified read-only counts (C-COMMENT-5 stale-comment class).
**Gain vs Trade-off:** Refresh the three numbers opportunistically when those files are touched. Never edit `AGENTS.md` (user-only) and never a standalone churn edit.
**If We Do It:** Comments match the tree again.
**If We Don't:** Magnitudes keep drifting.
**My Recommendation:** 🟡 Defer (opportunistic docs-only)
**Progress:** `None yet.`
**Related Files:**
- `pyproject.toml:584-586,386-391,604-627`
- `voice_typer/client/vitest.config.ts:28`
- `coverage-baseline.json`
**Fix:** Refresh comment numbers in place; leave C-TEST-1/2/3 settings untouched (threads/importlib/xdist verified intact).
**Simplified Fix:** Update the outdated test-count comments to today's sizes.
**Implementation Difficulty:** 🟢 Easy
**Severity:** 🟢 Low

### DC-13 — pytest timeout skew: local 60 s vs CI 120 s (docs-level)
**Status:** ✅ Fixed (2026-10-13: split documented in pyproject comment, values untouched; comment-only)
**Description:** Local addopts and Makefile use `--timeout=60` while CI overrides `--timeout=120`, so a 60-120 s test fails locally but passes CI. `test_mypy_ratchet.py:325` already needs a 600 s override, proving the skew bites at the slow end.
**User Impact:** Latent asymmetric flake window; no test observed in it today.
**Root Cause:** Verified (`pyproject.toml:660-690`, `Makefile:59-74`, `build.yml:191-196`).
**Gain vs Trade-off:** Document when-to-use-what (Makefile 60 = fast loop per C-TEST-4; pipeline canonical 120). Do NOT unify blindly and do NOT touch `build.yml` as a first-line fix (C-CI-2).
**If We Do It:** Contributors know which timeout governs their run.
**If We Don't:** The asymmetry persists silently.
**My Recommendation:** ✅ Implement (docs-only note)
**Progress:** Done 2026-10-13 (comment added, 60/120 values intact).
**Related Files:**
- `pyproject.toml:660-690`
- `Makefile:59-74`
- `.github/workflows/build.yml:191-196`
**Fix:** Document the 60-vs-120 split in the pyproject comment; no workflow change.
**Simplified Fix:** Write down why local and CI time-outs differ so nobody "fixes" the wrong one.
**Implementation Difficulty:** 🟢 Easy
**Severity:** 🟢 Low

### DC-14 — Windows NSIS uninstaller leaves the Startup-folder `.bat` orphan
**Status:** ⚠️ Partial (2026-10-13: code done — both .bat schemes enumerated in uninstaller.nsh + sweep widened + 3 new sweep pins green ON WINDOWS sandbox; live uninstall run on a real host still owed)
**Description:** The uninstaller removes HKCU Run values, scheduled tasks, and `%APPDATA%\lausu`, but never the Startup-folder `.bat` (`com.Lausu.autostart_<hash>.bat`) — and the runtime legacy sweep only globs `Lausu*.bat`, which cannot match the current `com.Lausu.*` name. On tertiary-mechanism machines the orphan fires a deleted target at every logon after uninstall.
**User Impact:** Uninstalled app keeps a logon entry pointing at a deleted binary (rare path: only when Task Scheduler failed).
**Root Cause:** Verified: `scripts/windows/uninstaller.nsh:67-155` has zero Startup handling; `.bat` path `autostart_windows.py:385-392`; sweep mismatch `_autostart_windows_sweep.py:179-214` vs `_paths.py:27,32`. Linux closed (`prerm:101`); macOS tracked as S5-CR-83 (distinct, not merged).
**Gain vs Trade-off:** A best-effort Startup-folder delete loop in `customUnInstall` closes the orphan. Script-only, no workflow touch (C-CI-2 safe), keep autostart order (C-CROSS-2).
**If We Do It:** Uninstall removes all three autostart mechanisms.
**If We Don't:** Orphan logon entries persist on fragile machines.
**My Recommendation:** ✅ Implement
**Progress:** Code done 2026-10-13 (both schemes enumerated + sweep widened + 3 sweep pins green); live uninstall host run still owed.
**Related Files:**
- `scripts/windows/uninstaller.nsh:67-155`
- `voice_typer/server/server_platform/autostart_windows.py:385-392`
**Fix:** Enumerate `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\com.Lausu.autostart_*.bat` + legacy `Lausu_*.bat` in `customUnInstall`. `VALIDATE ON WINDOWS HOST`.
**Simplified Fix:** Make the uninstaller delete the startup-folder shortcut it currently forgets.
**Implementation Difficulty:** 🟢 Easy
**Severity:** 🟡 Medium

### DC-15 — per-arch Tauri confs drop base window fields (array-replace)
**Status:** ⚠️ Partial (2026-10-13: content done — 4 confs repeat the 5 fields, drift-pinned, 87 tauri tests green ON WINDOWS sandbox; visual chrome check on real Win/macOS hosts still owed)
**Description:** Per-arch configs re-specify `app.windows` but omit base-only `center`, `hiddenTitle`/`titleBarStyle`/`trafficLightPosition`, and `additionalBrowserArgs` (autoplay + WebOOUI hardening flags). Tauri merges `--config` per RFC 7396: arrays replace wholesale, so omitted fields fall back to defaults, not base values. No test pins these fields (0 hits in `tests/`).
**User Impact:** Shipped Windows/macOS windows lose centering and hardening flags; macOS loses traffic-light position. Size/`decorations` deltas look intentional and stay.
**Root Cause:** Doc-verified (v2.tauri.app configuration-files: "arrays are replaced as a whole… Repeat everything you want to keep") + field diff vs `tauri.conf.json:21-58`.
**Gain vs Trade-off:** Repeat the dropped hardening/geometry fields per-arch (content-only JSON; C-CI-10 narrowing + assertion intact; do NOT touch workflow `--config` wiring).
**If We Do It:** Per-arch windows match the intended chrome and flags.
**If We Don't:** Silent divergence from the base window spec ships.
**My Recommendation:** ✅ Implement
**Progress:** Content done 2026-10-13 (4 confs repeat the 5 fields, drift-pinned, 87 green); visual host check still owed.
**Related Files:**
- `src-tauri/tauri.windows-x86_64.conf.json`
- `src-tauri/tauri.macos.conf.json`
- `src-tauri/tauri.conf.json:21-58`
**Fix:** Re-add `center` / `hiddenTitle` / `titleBarStyle` / `trafficLightPosition` / `additionalBrowserArgs` per-arch where intended; document intentional deltas. `VALIDATE ON WINDOWS HOST` + `VALIDATE ON MACOS HOST`.
**Simplified Fix:** Copy the missing window settings from the base config into each platform config.
**Implementation Difficulty:** 🟢 Easy
**Severity:** 🟡 Medium

### DC-16 — migration runbooks still live-voice the retired prewarm flow
**Status:** ✅ Fixed (2026-10-13: section-level HISTORICAL banners + checklists/tables struck; 3 residual VALIDATE lines sit inside bannered-retired sections only; linux zero live prewarm VALIDATEs)
**Description:** Build sections banner prewarm HISTORICAL (Linux `:148-154`, Windows `:435-442`) but live-voiced steps remain: Linux Step-11/systemd + check #7 + capture items; Windows §5/§6.7/§7.2/troubleshooting/tables referencing deleted `server/prewarm/__main__.py` and removed `build_prewarm_*` scripts. `tauri-build-runbook.md:347-348` already marks prewarm RETIRED — the migration runbooks must match.
**User Impact:** A host validator following the runbook burns a Nuitka build of a deleted module.
**Root Cause:** Verified half-retired docs (C-CI-13/16 unaffected — docs-only).
**Gain vs Trade-off:** Banner the remnants HISTORICAL like Step 2. Pure docs, zero code/workflow risk.
**If We Do It:** Runbooks stop sending validators down a deleted path.
**If We Don't:** Wasted host-validation builds recur.
**My Recommendation:** ✅ Implement (docs-only)
**Progress:** Done 2026-10-13 (banners + struck tables) + nits round same day (residual §2/§6.7 VALIDATE + pass-criteria lines struck-through; :1314 uninstall-deregistration kept as legitimate legacy-cleanup; zero live-voiced prewarm VALIDATEs outside retired sections). Open product call (owner): gate still reads "all 9 must pass" while point 7 is retired — 9 vs 8.
**Related Files:**
- `docs/migration/linux-validation-runbook.md:393-423,651,745-747`
- `docs/migration/windows-validation-runbook.md:435-481,562,666,987-1050,1221-1247,1389-1390,1859-1893`
**Fix:** Apply the Step-2 HISTORICAL banner treatment to every live-voiced prewarm section/row.
**Simplified Fix:** Mark the leftover prewarm instructions as retired everywhere, not just in one section.
**Implementation Difficulty:** 🟢 Easy
**Severity:** 🟢 Low

### DC-17 — macOS dev-path LaunchAgent omits `--hidden/--delay` + stale platform rows/hints
**Status:** ❌ Not Fixed
**Description:** The non-packaged macOS registration builds `ProgramArguments` without the `--hidden --delay` flags the packaged path, Linux, and Windows all pass (launcher honors them). Same entry bundles three verified-narrowed docs issues: PLATFORM_STATUS single-instance row omits the Tauri plugin authority (`main.rs:103` owns it under the host; Python mutex skipped in sidecar mode `ipc/entrypoint.py:277`); the Wayland hint suggests wtype/ydotool "for hotkey support" though wtype only injects paste and ydotool is probed but never consumed (native evdev already covers Wayland hotkeys); power.rs keeps only unnamed `4/7/18/10` constants (Windows PBT_* mapping verified in the `GetMessageW` loop — the "dead mapping" half of Wave1 was false, stub documented-deliberate).
**User Impact:** Dev-checkout Macs launch visible with no I/O-settle delay; docs mislead Wayland/single-instance/power readers.
**Root Cause:** Verified (`autostart_macos.py:80-129` vs `:71-73` + `autostart.py:127` + `launcher:113-141`; `PLATFORM_STATUS.md:18`; `i18n.py:71-74,240-244` + `clipboard/linux.py:177-205`; `power.rs:181-188,265-316`). Apple man-page shape otherwise matches.
**Gain vs Trade-off:** Append the two flags on the dev path only (keep macOS array shape; Windows `list2cmdline` untouched per C-CROSS-1); docs rows are one-line/copy fixes (P7-08 touches all 8 locales per C-I18N-1/2 with genuine translations; power constants only if the file is touched anyway per E13).
**If We Do It:** Dev Mac logons behave like packaged ones; platform docs match code.
**If We Don't:** Visible dev logons + misleading hints persist.
**My Recommendation:** ✅ Implement
**Progress:** `None yet.`
**Related Files:**
- `voice_typer/server/server_platform/autostart_macos.py:80-129`
- `docs/PLATFORM_STATUS.md:18`
- `voice_typer/server/i18n.py:71-74`
- `src-tauri/src/platform/power.rs:181-188`
**Fix:** Dev-path `program_args += ["--hidden", "--delay", delay_str]`; PLATFORM_STATUS single-instance row note; Wayland hint reword to evdev/input-group; name PBT_* constants opportunistically. `VALIDATE ON MACOS HOST` (plist lint + logon cycle) + `VALIDATE ON LINUX HOST` (Wayland matrix).
**Simplified Fix:** Give dev Mac logons the same hidden/delayed start as packaged ones and correct three small docs rows.
**Implementation Difficulty:** 🟢 Easy
**Severity:** 🟢 Low

### DC-18 — stale unreferenced `voice-typer.desktop.template` (pre-rename twin)
**Status:** ✅ Fixed (2026-10-13: all 5 twins deleted, zero refs repo-wide, drift/naming green; .deb content check still owed on a Linux host)
**Description:** `src-tauri/voice-typer.desktop.template` carries pre-rename branding (`Name=Voice Typer`, `StartupWMClass=Voice Typer`) and is referenced nowhere — every config/test/doc pins `lausu.desktop.template` (`tauri.conf.json:107`, mig17/18 tests). Same twin pattern unreferenced: `00-voice-typer-capslock.conf`, `99-voice-typer.rules` (per-arch resources list `lausu.*` only). Risk: a wrong-file fix for S1-CR-146 and template-glob confusion.
**User Impact:** None today; a future editor fixes the wrong template.
**Root Cause:** Verified reference grep (1 hit = the other file).
**Gain vs Trade-off:** Delete the twin (+ twin confs/rules) and confirm `.deb` contents unchanged. Keep `bundle.resources` narrowing + assertion (C-CI-10); do NOT touch `lausu.desktop.template:28` (owned by S1-CR-146 host gate).
**If We Do It:** One template, no wrong-file risk.
**If We Don't:** The stale twin keeps inviting a misdirected fix.
**My Recommendation:** ✅ Implement (Trivial)
**Progress:** Done 2026-10-13 (5 files deleted; .deb check owed on Linux host).
**Related Files:**
- `src-tauri/voice-typer.desktop.template`
- `src-tauri/lausu.desktop.template`
**Fix:** Delete unreferenced twin files; re-grep for references at implementation time. `VALIDATE ON LINUX HOST`: per-arch build, menu entry `Name=Lausu`, no `Voice Typer` string in `.deb`.
**Simplified Fix:** Delete the leftover pre-rename desktop template nobody uses.
**Implementation Difficulty:** 🟢 Easy
**Severity:** 🟢 Low
