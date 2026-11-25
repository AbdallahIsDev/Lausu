# Plugin tabs, Plugins page, and ChatGPT stop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate duplicate plugin browser tabs, make ChatGPT hotkey stop reliable, and remove the Plugins page card wrapper.

**Architecture:** One tab per platform, discovered by URL/domain in the extension; Python starts the profile only at `about:blank`. ChatGPT's live `data-dictation-button="dictating"` toggle becomes the stop control with an empty, non-overlapping cancel selector. The Plugins panel drops its `SettingsSection` wrapper.

**Tech Stack:** Python 3.13 sidecar, Node 26 relay/extension (MV3, `chrome.tabs.*`), React/TypeScript renderer, pytest + node:test + vitest.

**Spec:** `docs/superpowers/specs/2026-11-25-plugin-tabs-ui-and-chatgpt-stop-design.md`

## Global Constraints

- C-ASR-4: commit and discard selectors must never match the same element.
- C-PLUGIN-3: a connected browser resolves its own tabs; a missing tab must not trigger a Chrome URL launch.
- C-UI-16: no bordered card inside a bordered card; C-DESIGN-1 renderer/showcase sync (no Plugins mock exists).
- C-PLUGIN-4: developer surfaces render only when backend `get_plugins.available` is also true; backend keeps refusing regardless.
- Do not touch other sessions' dirty files (snapshot: `C:\Users\11\AppData\Local\Temp\opencode\pre_plugins_audit_gitstatus.txt`, HEAD `0c7989dd`).
- Reuse shared bridge; no third profile, no new transport, no plugin-specific workarounds.

## Review Focus

- A user's unrelated tab with a similar title must never be selected or closed — pinned in Task 2 dedupe tests using URL-pattern-only matching.
- Closing a duplicate must never close the preferred tab or another platform's tab — pinned in Task 2.
- Rapid hotkeys must create at most one tab — pinned by Task 2 coalescing test.
- ChatGPT stop must click the dictating toggle and leave the composer text intact — pinned in Task 1 DOM test.
- Hidden browser mode must produce identical tab behavior — pinned by Task 2 extension-state assertions.

---

### Task 1: ChatGPT stop selector and stop semantics

**Files:**
- Modify: `tools/internal_plugins/_common/bridge/selectors/chatgpt.json` (`stopSelector`, `cancelSelector`)
- Modify: `tools/internal_plugins/_common/bridge/test/content_chatgpt_dictation.test.js` (fixtures/assertions)
- Modify: `tools/internal_plugins/_common/bridge/test/content_stop_empty.test.js`, `content_cancel_optional.test.js` (fake DOM matching)
- Modify: `tests/plugins/test_chatgpt_plugin.py` (selector completeness/distinctness)
- Generate: `tools/internal_plugins/_common/bridge/extension/generated/config.js` via `build-extension.js`; sync stable extension

**Interfaces:**
- Consumes: `content.js` `stopButtons()`/`cancelButtons()`/`recordingState()` (no signature change).
- Produces: `stopSelector` matching `button[data-dictation-button="dictating"]`; `cancelSelector === ""` for ChatGPT.

- [ ] Step 1: Update the DOM fixtures so the recording row exposes only the supplied dictating toggle; assert `stop()` clicks it, reports `committed === true`, and keeps composer text. Update Python selector test to assert commit selector contains `data-dictation-button="dictating"` and cancel is empty/distinct.
- [ ] Step 2: Run `node --test test/content_chatgpt_dictation.test.js test/content_stop_empty.test.js test/content_cancel_optional.test.js` and the Python test; confirm they fail on the old selector.
- [ ] Step 3: Change `chatgpt.json` selectors as specified; no `content.js` behavioral change unless a test proves one is needed.
- [ ] Step 4: Regenerate config (`node tools/internal_plugins/_common/bridge/tools/build-extension.js`) and sync (`node -e "require('./sync_extension').sync({dir:...})"`); verify generated config contains the new selector.
- [ ] Step 5: Re-run the tests; `ruff` touched Python; commit with `git_safe_commit.py`.

### Task 2: Extension-only tab authority with per-platform dedupe

**Files:**
- Modify: `tools/internal_plugins/_common/bridge/extension/tab_resolution.js` (`resolve`, new dedupe helper)
- Modify: `tools/internal_plugins/_common/bridge/test/tab_resolution.test.js`
- Modify: `tools/internal_plugins/_common/bridge/session.py` (`launch_profile_if_due`)
- Modify: `tools/internal_plugins/{anthropic_stt,google_stt,chatgpt_stt}/plugin.py` (launch wrappers)
- Modify: `tests/plugins/test_plugin_cold_start_activation.py`, `tests/plugins/test_plugin_target_tab_resolution.py`

**Interfaces:**
- Consumes: `resolve()` promise and `chromeApi.tabs.remove` from Task 1's unchanged `tab_resolution.js` API.
- Produces: `resolve(platform)` returns `{tabId, created, ready}` after dedupe; `launch_fn(profile, "about:blank")`.

- [ ] Step 1: Add failing node tests: two matching tabs → exactly one `tabs.remove` call for the non-preferred tab; unrelated tab never removed; three concurrent `ensure()` calls → one create; preferred tab survives.
- [ ] Step 2: Add failing Python tests asserting `launch_fn` receives `about:blank` from cold activation and from hotkey relaunch.
- [ ] Step 3: Implement dedupe in `tab_resolution.js` inside the coalesced `resolve()`; `matchesUrl` only; remove surplus matches for that platform; never remove preferred/other-platform tabs.
- [ ] Step 4: Change Python launch URL to `about:blank` in `session.launch_profile_if_due` (stop reading config URL there); keep cooldown and `_profile_missing`.
- [ ] Step 5: Re-run node bridge suite + scoped pytest; commit.

### Task 3: Plugins page wrapper removal and C-PLUGIN-4 leftovers

**Files:**
- Modify: `voice_typer/client/src/renderer/src/components/models/PluginsPanel.tsx:57-77`
- Modify: `voice_typer/client/src/renderer/src/App.tsx` (redirect gate hook)
- Modify: `voice_typer/client/src/renderer/src/components/layout/PageSwitch.tsx` (dead plugins case gate hook)
- Test: `voice_typer/client/src/renderer/src/components/models/__tests__/PluginsPanel.test.tsx`

**Interfaces:**
- Consumes: `usePluginsUnlocked()` from `hooks/usePluginCatalog.ts` (developerMode && serverAvailable).
- Produces: no card wrapper around the three plugin items; one horizontal row.

- [ ] Step 1: Add a failing renderer test: plugin row has no ancestor with `bg-surface-subtle`/`border-border/8`, three cards are siblings in one `grid-cols-3` container.
- [ ] Step 2: Replace cards' `SettingsSection` with plain heading + `grid grid-cols-3 gap-4`; keep error/empty/shared-settings sections.
- [ ] Step 3: Switch remaining single-flag gates to `usePluginsUnlocked`.
- [ ] Step 4: Run `npm run typecheck:ci` and focused vitest; commit.

### Task 4: Full lifecycle verification

**Files:** no production changes; verification only.

- [ ] Step 1: `node --test test/*.test.js`; `pytest tests/plugins tests/tauri/test_internal_plugin_packaging.py -q --no-cov`; `ruff`; `npm run typecheck:ci`.
- [ ] Step 2: Report scenarios A–G honestly: automated coverage where available, live checks only if executed; hidden-mode assertions from extension state.
- [ ] Step 3: Note limitations (signed-in ChatGPT probe; no CDP on plugin profile).
