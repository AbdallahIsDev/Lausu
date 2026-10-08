## High Priority

These items are the highest-priority remaining work for the project. They block the Tauri migration, fix core functionality, or address critical infrastructure gaps. Items in this section are ordered by priority (top = most urgent).

> **Won't Fix tasks live in `WONT_FIX.md`**: deliberately not solved. Do NOT fix them (AGENTS.md C-REVIEW-1). See that file for the full list.

### AUD-14 — Production files over the 500-line C-STRUCT-3 threshold (13 left, Waves 1–6 shipped)
**Status:** SPLIT INTO 5 TASKS (2026-10-03) — AUD-14a…e below. **WAVES 1–6 SHIPPED (reviewer-verified green, commits `05eef343`, `b02b40fd`, `65d1d226`, `f52bc848`, `000403b5` (Waves 1–6): AUD-14c and AUD-14d complete; AUD-14e all but 6 files done. Per-wave evidence (counts, gates) in git history.** Remaining scope is the task list below (all DISJOINT file sets, E16).
**User Impact:** None directly. The cost is change risk: each edit touches a file with several unrelated reasons to change, so unrelated behavior is coupled to unrelated edits.
**Root Cause:** Verified by line count — organic growth without the create-first split (E1) that C-STRUCT-3 requires.
**Gain vs Trade-off:** Large, mechanical, regression-prone work. Best done incrementally, never as a batch. Split by subsystem so no two tasks touch the same file.
**Related Files:** `scripts/comment_ratio_metrics.py` (re-measure after each task)

**Remaining scope (original 2026-10-03 inventory minus shipped waves):**

| Task | Scope | Files left |
|---|---|---|
| **AUD-14a** | Four largest god files (P2) | 4 |
| **AUD-14b** | `server/recording/` package | 3 |
| **AUD-14e** | Tail: `startup_tasks.py`, `qwen_engine.py`, `worker_client.py`, `cloud/_engine.py`, `log/setup.py`, `ipc/validation.py` | 6 |

---

### AUD-14a — Split the four largest god files (E1/C-STRUCT-3 create-first)
**Status:** NOT DONE (2026-10-03, split from AUD-14)
**Description:** The four worst offenders are single-class files with 20-29 methods each and multiple unrelated reasons to change. Each violates C-STRUCT-1 (one concern per file) and C-STRUCT-2 (SRP):

| File | Lines | Classes | defs | Concern to extract |
|---|---|---|---|---|
| `server/hotkey_dispatcher.py` | 1,094 | 1 | 29 | native backend pool lifecycle / registration / matching / dispatch |
| `service/model/_downloads.py` | 942 | 1 | 20 | split the 4 concerns behind the `DownloadsMixin` |
| `recording_lifecycle.py` | 874 | 1 | 25 | **27 broad `except Exception`** in the recording hot path (lines 86-979) |
| `worker/_ws_server.py` | 823 | 2 | 24 | `_handle_connection` alone is ~494 lines |

**Why first:** Highest change-risk density in the package. `recording_lifecycle.py` carries real behavioral risk — 27 catch-alls in the recording hot path make a failure in any stage indistinguishable in logs from every other (undercuts C-LOG-1's diagnostic-value rule).
**Fix:** Create-first (E1): add the new focused modules complete + green, keep re-exports so existing import paths resolve, THEN trim the original. Never delete before the replacement exists. Narrow a broad `except Exception` only where its intended behavior is already pinned by a test — do NOT blanket-convert (E13: fixing blind changes behavior).
**Related Files:** the four files above + `tests/test_hotkeys*.py`, `tests/test_recorder_*.py`, `tests/test_worker_*.py`
**Success:** no file >500 lines; full suite green; the `except Exception` count drops with each narrowed handler traceable to a test.
**Implementation Difficulty:** 🟠 Medium
**Severity:** 🟡 Medium
**Priority:** P2

---

### AUD-14b — Recording subsystem: `server/recording/` (3 files, 1,901 lines)
**Status:** NOT DONE (2026-10-03, split from AUD-14)
**Description:** 3 files over the threshold: `device_manager.py` (746), `capture.py` (623), `recording_lifecycle.py` (532). Note `recording_lifecycle.py` ALSO appears in AUD-14a — **this task owns only the `server/recording/` package copy; AUD-14a owns the `server/` root copy (874 lines).** Do not run both against the same file.
**Why separate:** Device enumeration, capture, and lifecycle each change for different reasons, so a mic-driver fix currently risks the capture path.
**Fix:** Create-first split per C-STRUCT-4: when touching any of these, split first, then land the fix on the clean structure.
**Related Files:** `server/recording/{device_manager,capture,recording_lifecycle}.py`, `tests/recording/`
**Success:** no file >500 lines; `pytest tests/recording/` green.
**Implementation Difficulty:** 🟠 Medium
**Severity:** 🟡 Medium
**Priority:** P3

---

### AUD-14d — Security subsystem `server/security/` (DONE 2026-10-06, Wave 6: `redaction.py` 905→82, `file_io.py` 740→42, 8 focused siblings, order-equivalence byte-identical, reviewer-verified green)
**Status:** DONE. Shipped this wave; only the task definition below is kept for the record.
**Description:** Split create-first into 8 focused siblings with facade re-exports; pattern application order verified byte-identical; `tests/test_module_split_reexports_wave6.py` pins the contracts.

---

### AUD-14e — Tail: 6 remaining `server/` root modules
**Status:** OPEN. `startup_tasks.py` (686), `qwen_engine.py` (514), `worker_client.py` (613), `cloud/_engine.py` (583), `log/setup.py` (527), `ipc/validation.py` (527). Everything else in this task shipped in Waves 1–5 (see AUD-14 top status).
**Description:** The remaining long tail. Each carries a pin — moves only, no behavior change:

- `startup_tasks.py`: carries C-CONF-2's startup mic reconciliation — re-verify after any move.
- `qwen_engine.py`: carries RACE-032 (lock release during inference).
- `worker_client.py`: C-WS-2 TEXT frames + C-WS-3 generation stamps.
- `cloud/_engine.py`: SEC-002/005/011/030 + consent gates — later wave with security focus.
- `log/setup.py` + `ipc/validation.py`: C-LOG-1 log format + SEC-002 allowlist — moving code must alter neither.

**Fix:** Create-first throughout (E1).
**Related Files:** the modules listed above.
**Success:** no file >500 lines; related suites green unchanged.
**Implementation Difficulty:** 🟠 Medium
**Severity:** 🟡 Medium
**Priority:** P3


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
