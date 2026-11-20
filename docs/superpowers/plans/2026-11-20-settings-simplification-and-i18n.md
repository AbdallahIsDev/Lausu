# Settings Simplification and i18n Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove two unwanted settings with fixed platform-wide behavior, fix Arabic RTL shell/arrow/live-locale defects, correct one dropdown label, and normalize plugin label capitalization.

**Architecture:** Settings are deleted at all four layers (Python schema, SEC-002 allowlist, renderer type/UI, i18n) so no dead `set_config` path remains; streaming and tray behavior move to fixed host code. Locale correctness is fixed at two seams: an explicit direction pin on the app shell, and `useT()` subscriptions in memoized chrome that previously never re-rendered.

**Tech Stack:** Python 3.11 Config/migrations, IPC allowlist, Tauri v2 Rust tray, React 19 + Zustand + skullet renderer, Vitest/pytest, 8 locale JSON catalogs.

**Spec:** `docs/superpowers/specs/2026-11-20-settings-simplification-and-i18n-design.md`

## Global Constraints

- Windows, Linux and macOS must behave identically for streaming and tray left-click.
- `streaming_transcription` and `tray_left_click_action` must be absent from UI **and** SEC-002 allowlist; no third allowlist.
- `model_idle_unload_minutes`: label-only change; no key, value, option order, tooltip or logic change.
- `VOICE_TYPER_STREAMING=0` developer kill-switch remains; it is not a user setting.
- Right-click tray menu and all its items, including Toggle Dictation, stay unchanged.
- Bare module-level `t()` semantics stay; use component-local `useT()` subscriptions only.
- Every changed user-facing string goes into all 8 locales (`en/zh/hi/es/ar/fr/ru/de`), genuinely translated.
- No task/session IDs in code. Keep focus rings, sidebar structure and existing test contracts intact.
- `cwd` for commands is the repo root unless a step says otherwise.

## Review Focus

1. **Legacy `config.json` containing the two removed keys** must load, ignore them, and not re-emit them on save — pinned by a config load/save test in Task 1, plus the tray case in Task 2.
2. **macOS tray click** must open the app on left-click while right-click still opens the menu — pinned by Rust source-text checks in Task 2 and a manual app check in Task 7.
3. **Arabic RTL** must keep the sidebar physically left with RTL text inside it — pinned by the shell direction test in Task 4 and a manual screenshot in Task 7.
4. **Locale switch on a running app** must re-localize memoized chrome (sidebar/title bar/search) without reload — pinned by the chrome subscription test in Task 5.
5. **Model-memory `0` option** must still mean "kept loaded" with only its label renamed — pinned by the unchanged backend zero test in Task 3.

---

### Task 1: Streaming transcription fixed ON

**Files:**
- Modify `voice_typer/server/streaming_session_coordinator.py` (`streaming_enabled`)
- Modify `voice_typer/server/config/_schema.py` (remove `streaming_transcription`)
- Modify `voice_typer/server/config_validators/allowlist.py` (remove the key; keep the six `streaming_*` tuning keys)
- Modify `voice_typer/client/src/renderer/src/types/config.ts` (remove the required field)
- Modify `voice_typer/client/src/renderer/src/components/settings/GeneralSettingsSection.tsx` (row + search item + handler)
- Modify `voice_typer/client/src/renderer/src/components/settings/settingsTabLabels.ts`
- Modify 8 files `voice_typer/client/src/renderer/src/i18n/translations/*.json` (drop two keys each)
- Modify fixtures in `voice_typer/client/src/renderer/src/components/skullet/sampleConfig.ts`, `.../__tests__/helpers/fixtures.ts` and other `LausuConfig` literals that set the removed field
- Test: `tests/app/test_dictation.py`, `tests/config/test_config_load_save.py`, `tests/test_config_validators_split.py`, `tests/test_config_package_split.py`, `voice_typer/client/src/renderer/src/types/__tests__/config-parity.test.ts`
- Delete `voice_typer/client/src/renderer/src/components/settings/GeneralSettingsSection.streamingTranscription.test.tsx` and replace with an absence test in the existing `GeneralSettingsSection.test.tsx`

**Interfaces:**
- Consumes: `Config` from `_schema.py`; `VOICE_TYPER_STREAMING` env var.
- Produces: `StreamingSessionCoordinator.streaming_enabled(controller) -> bool` returning `True` unless env is `"0"`; config object with no `streaming_transcription` attribute.

- [ ] **Step 1: Write failing backend tests**

In `tests/app/test_dictation.py`, delete the case that sets `config.streaming_transcription = False` to disable streaming; replace it with a case asserting a streaming session starts when no such attribute exists on the config, and keep the existing `VOICE_TYPER_STREAMING=0` kill-switch case. In `tests/config/test_config_load_save.py`, add a test that loading a config dict containing `streaming_transcription: false` yields a `Config` with no such field, and that saving it does not re-emit the key.

- [ ] **Step 2: Run backend tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/app/test_dictation.py tests/config/test_config_load_save.py -q --no-cov --tb=short`
Expected: FAIL (attribute still present / `streaming_enabled` still reads it).

- [ ] **Step 3: Implement fixed-on streaming**

In `streaming_session_coordinator.py`, make `streaming_enabled()` return `False` only for the env kill-switch, otherwise `True`. Remove `streaming_transcription` from `_schema.py` and from `config_validators/allowlist.py`. Leave the six tuning fields, their coercion and their allowlist entries untouched. Unknown keys in old `config.json` files are dropped on the next save by the existing `asdict` path; do not add a new config field or version bump.

- [ ] **Step 4: Run backend tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/app/test_dictation.py tests/config/test_config_load_save.py tests/test_config_validators_split.py tests/test_config_package_split.py -q --no-cov --tb=short`
Expected: PASS.

- [ ] **Step 5: Write failing renderer test**

In `GeneralSettingsSection.test.tsx`, add a test rendering the General section with a config containing no `streaming_transcription` and assert `queryByText(t("settings.streamingTranscription"))` is null and no toggle writes that key. Update `config-parity.test.ts` to remove the field from its expected parity list.

- [ ] **Step 6: Run renderer test to verify it fails**

Run: `cd voice_typer/client && npx vitest run src/renderer/src/components/settings/GeneralSettingsSection.test.tsx src/renderer/src/types/__tests__/config-parity.test.ts`
Expected: FAIL (row still present).

- [ ] **Step 7: Remove the UI and type surface**

Remove the streaming label/info constants, search item, write handler and `<Switch>`/`<SettingRow>` block from `GeneralSettingsSection.tsx`; remove the field from `types/config.ts`, all fixture literals, `settingsTabLabels.ts` and the two i18n keys from all 8 catalogs. Delete the superseded dedicated test file.

- [ ] **Step 8: Run renderer tests and typecheck**

Run: `cd voice_typer/client && npx vitest run src/renderer/src/components/settings src/renderer/src/types/__tests__/config-parity.test.ts && npm run typecheck:ci`
Expected: PASS.

- [ ] **Step 9: Commit**

`git add -A <paths touched in this task> && git commit -m "fix(settings): make streaming transcription always on"`

---

### Task 2: Tray left-click always opens the app; setting removed

**Files:**
- Modify `src-tauri/src/tray.rs`
- Modify `voice_typer/server/config/_schema.py`, `voice_typer/server/config_validators/allowlist.py`
- Modify `voice_typer/server/tray_menu.py` (remove config-driven bold default + unused `left_click_action` parameter)
- Modify renderer `types/config.ts`, `GeneralSettingsSection.tsx`, `settingsTabLabels.ts`, 8 locale catalogs (including the unused `settings.trayLeftClick` duplicates), fixtures
- Test: `tests/test_tray_menu.py`, `tests/tauri/test_tray_menu.py`, `tests/tauri/mig19/test_tray_menu.py`, `tests/server/test_dispatch_config.py`, `tests/test_config_warnings_surface.py`, `tests/test_config_validators_split.py`, `tests/test_config_package_split.py`, renderer `config-parity.test.ts`

**Interfaces:**
- Consumes: Tauri `TrayIconEvent::Click { button: MouseButton::Left, .. }` via `is_focus_main_window_event`.
- Produces: tray config with no `tray_left_click_action`; `build_tray_menu_model` without the unused parameter; Rust tray where left-click only raises the window and right-click opens the unchanged menu.

- [ ] **Step 1: Write failing Rust source tests**

In `tests/tauri/test_tray_menu.py` and `tests/tauri/mig19/test_tray_menu.py`, replace the macOS-conditional expectation with assertions that `tray.rs` contains `show_menu_on_left_click(false)` unconditionally, contains no `cfg!(target_os = "macos")` early return in `on_tray_icon_event`, and still dispatches `on_menu_event` clicks. Add an assertion that the right-click menu item ids are unchanged.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/tauri/test_tray_menu.py tests/tauri/mig19/test_tray_menu.py -q --no-cov --tb=short`
Expected: FAIL (source still has conditional/early return).

- [ ] **Step 3: Fix the host tray behavior**

In `src-tauri/src/tray.rs`, set `show_menu_on_left_click(false)` for all platforms and delete the macOS early return inside `on_tray_icon_event`. Keep menu events, template icon and all menu items unchanged. Run `cargo check` (C-TDEV-1: use the tracked GNU toolchain path, no new static server).

- [ ] **Step 4: Write failing Python tray tests**

In `tests/test_tray_menu.py`, assert that building the menu no longer reads `tray_left_click_action` and that all previously present menu items still exist with unchanged ids. Update `tests/test_config_warnings_surface.py` and `tests/server/test_dispatch_config.py` so they no longer expect the removed enum value to be accepted.

- [ ] **Step 5: Run Python tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_tray_menu.py tests/test_config_warnings_surface.py tests/server/test_dispatch_config.py -q --no-cov --tb=short`
Expected: FAIL (field still read/accepted).

- [ ] **Step 6: Remove the Python/settings surface**

Remove the field from `_schema.py` and the allowlist; remove the `getattr(tray._config, "tray_left_click_action", ...)` branches in `tray_menu.py` and the unused `left_click_action` argument at its call site; remove the two UI options, label/info/search item, write handler, TS field, fixtures and all eight locale keys (including `settings.trayLeftClick*` duplicates). Update the parity test.

- [ ] **Step 7: Run all Task 2 checks**

Run: `.venv\Scripts\python.exe -m pytest tests/test_tray_menu.py tests/tauri/test_tray_menu.py tests/tauri/mig19/test_tray_menu.py tests/server/test_dispatch_config.py tests/test_config_warnings_surface.py tests/test_config_validators_split.py tests/test_config_package_split.py -q --no-cov --tb=short`
Then: `cd voice_typer/client && npx vitest run src/renderer/src/components/settings src/renderer/src/types/__tests__/config-parity.test.ts && npm run typecheck:ci`
Expected: PASS.

- [ ] **Step 8: Commit**

`git add -A <paths touched in this task> && git commit -m "fix(tray): left-click always opens app, remove click setting"`

---

### Task 3: Correct the contradictory idle-unload option label

**Files:**
- Modify 8 files `voice_typer/client/src/renderer/src/i18n/translations/{en,zh,hi,es,ar,fr,ru,de}.json` — key `settings.modelIdleUnload.never`
- Test: `voice_typer/client/src/renderer/src/components/settings/GeneralSettingsSection.modelIdleUnload.test.tsx`
- Reference only (do not modify): `voice_typer/server/model_manager/_lifecycle.py:138-151`, `voice_typer/client/src/renderer/src/lib/utils/modelIdleUnload.ts`

**Interfaces:**
- Consumes: option value `0` = idle timer disarmed = model kept loaded.
- Produces: renamed visible label only; option list, value, order, tooltip, config key and backend logic unchanged.

- [ ] **Step 1: Write failing renderer test**

In `GeneralSettingsSection.modelIdleUnload.test.tsx`, change the English expectation for `settings.modelIdleUnload.never` to exactly `Always (Keep Loaded)`; keep the existing all-8-locale key-presence and no-English-in-translations assertions. Assert the option value stays `0` and the list order stays `[15, 30, 60, 90, 120, 0]`.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd voice_typer/client && npx vitest run src/renderer/src/components/settings/GeneralSettingsSection.modelIdleUnload.test.tsx`
Expected: FAIL (English label still "Never (keep loaded)").

- [ ] **Step 3: Change only that label in all 8 catalogs**

Set `settings.modelIdleUnload.never` to: en `Always (Keep Loaded)`, zh `始终（保持加载）`, hi `हमेशा (लोड रखें)`, es `Siempre (mantener cargado)`, fr `Toujours (garder chargé)`, de `Immer (geladen lassen)`, ru `Всегда (не выгружать)`, ar `دائمًا (إبقاء التحميل)`. Do not touch any other key, option, tooltip or code.

- [ ] **Step 4: Run the label test and the unchanged backend zero test**

Run: `cd voice_typer/client && npx vitest run src/renderer/src/components/settings/GeneralSettingsSection.modelIdleUnload.test.tsx`
Then: `.venv\Scripts\python.exe -m pytest tests/test_model_idle_unload.py -q --no-cov --tb=short`
Expected: PASS; backend behavior unchanged.

- [ ] **Step 5: Commit**

`git add -A <8 locale files and the test> && git commit -m "fix(settings): clarify keep-loaded dropdown label"`

---

### Task 4: Sidebar pinned left in RTL; title-bar arrows unmirrored

**Files:**
- Modify `voice_typer/client/src/renderer/src/App.tsx` (shell row `dir`, main column `dir`, logical border classes)
- Modify `voice_typer/client/src/renderer/src/components/layout/Sidebar.tsx` (nav container `dir="rtl"`)
- Modify `voice_typer/client/src/renderer/src/components/layout/titlebar/titleBarButtons.tsx` (remove `nav-directional-icon` from the two chevrons)
- Modify `voice_typer/client/src/renderer/src/__tests__/TitleBar.rtl-pinning.test.tsx`
- Create `voice_typer/client/src/renderer/src/i18n/__tests__/rtl-shell-layout.test.tsx`
- Reference only: `index.css` `[dir="rtl"] .nav-directional-icon` rule and the Settings back-chevron stay unchanged.

**Interfaces:**
- Consumes: `isRtlLocale(locale)` from `@/i18n/rtl` (re-exported from `@/i18n/i18n`); `getLocale()`.
- Produces: shell row `dir="ltr"` in all locales; main column `dir="rtl"` only for RTL locales; sidebar nav `dir="rtl"`; no mirror class on title-bar chevrons.

- [ ] **Step 1: Write failing shell layout test**

Create `rtl-shell-layout.test.tsx`: render the App shell (or a minimal harness with the same row/main/sidebar structure) with `document.documentElement.dir = "rtl"`, then assert (a) the row wrapper has `dir="ltr"`, (b) the main column has `dir="rtl"`, (c) the sidebar is the row's first element child, and (d) the main column uses `rounded-s-lg border-s` rather than `rounded-l-lg border-l`.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd voice_typer/client && npx vitest run src/renderer/src/i18n/__tests__/rtl-shell-layout.test.tsx`
Expected: FAIL (no direction pins, physical border classes).

- [ ] **Step 3: Pin the shell direction**

In `App.tsx`, set `dir="ltr"` on the `<div className="flex min-h-0 flex-1">` row. Replace `dir={sidebarVisible ? undefined : "ltr"}` on the main column with an explicit locale-derived direction (`isRtlLocale(getLocale()) ? "rtl" : "ltr"`), independent of `sidebarVisible`. Change `rounded-l-lg border-t border-l` to `rounded-s-lg border-t border-s`. In `Sidebar.tsx`, add `dir="rtl"` to the nav's inner container (the `<div className="min-h-0 flex-1 overflow-y-auto p-2">`), leaving the `<aside>` unpinned.

- [ ] **Step 4: Write failing arrow test**

In `TitleBar.rtl-pinning.test.tsx`, change the chevron assertion so that under `html dir=rtl` the SVG must **not** carry `nav-directional-icon` and must not receive the mirrored transform. Keep the existing pin that the title bar root itself stays `dir="ltr"`.

- [ ] **Step 5: Run arrow test to verify it fails**

Run: `cd voice_typer/client && npx vitest run src/renderer/src/__tests__/TitleBar.rtl-pinning.test.tsx`
Expected: FAIL (class still present).

- [ ] **Step 6: Remove the title-bar mirror opt-in**

In `titleBarButtons.tsx`, delete `nav-directional-icon` from the back/forward chevron SVGs only. Leave `index.css` and `Settings.tsx` untouched.

- [ ] **Step 7: Run Task 4 checks**

Run: `cd voice_typer/client && npx vitest run src/renderer/src/i18n/__tests__/rtl-shell-layout.test.tsx src/renderer/src/__tests__/TitleBar.rtl-pinning.test.tsx src/renderer/src/components/layout src/renderer/src/__tests__/pages/skullet-contracts.test.tsx && npm run typecheck:ci`
Expected: PASS (sidebar collapse/identity tests still green).

- [ ] **Step 8: Commit**

`git add -A <paths touched in this task> && git commit -m "fix(rtl): keep sidebar left and title-bar arrows fixed"`

---

### Task 5: Live language updates for memoized chrome

**Files:**
- Modify `voice_typer/client/src/renderer/src/components/layout/Sidebar.tsx`
- Modify `voice_typer/client/src/renderer/src/components/layout/TitleBar.tsx`
- Modify `voice_typer/client/src/renderer/src/components/layout/GlobalSearchBar.tsx`
- Modify `voice_typer/client/src/renderer/src/components/layout/ModelsTabSwitcher.tsx`
- Modify `voice_typer/client/src/renderer/src/components/layout/AnalyticsRangeSwitcher.tsx`
- Create `voice_typer/client/src/renderer/src/i18n/__tests__/chrome-live-locale.test.tsx`
- Reference only: `i18n/__tests__/rtl-render.test.tsx` negative pin for bare `t()` stays unchanged.

**Interfaces:**
- Consumes: `useT()` from `@/i18n/i18n` (a `useSyncExternalStore` subscription returning the stable `t` function); `setLocale(locale)` from the same module.
- Produces: five memoized components that re-render on locale revision change while module-level `t()` keeps its call-time semantics.

- [ ] **Step 1: Write failing chrome subscription test**

Create `chrome-live-locale.test.tsx`: render `GlobalSearchBar` (plus small harnesses mounting `Sidebar`, `TitleBar` with their existing test mocks) in English, capture a nav label, a title-bar aria-label and the search placeholder; call `setLocale("ar")`; assert all three become the Arabic catalog values without remount. Restore locale in `afterEach`.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd voice_typer/client && npx vitest run src/renderer/src/i18n/__tests__/chrome-live-locale.test.tsx`
Expected: FAIL (strings stay English).

- [ ] **Step 3: Subscribe the five chrome components**

Replace the bare `import { t }` with `import { useT }` (keep other named imports) and call `const t = useT()` inside `SidebarInner`, `TitleBarInner`, `GlobalSearchBar`, `ModelsTabSwitcher` and `AnalyticsRangeSwitcher` bodies. Do not change helper signatures that call `t()` at render time. Do not add global locale state or a key to memo props.

- [ ] **Step 4: Run the new test and the locale contract tests**

Run: `cd voice_typer/client && npx vitest run src/renderer/src/i18n/__tests__/chrome-live-locale.test.tsx src/renderer/src/i18n/__tests__/rtl-render.test.tsx src/renderer/src/i18n/__tests__/setLocale-propagation.test.ts src/renderer/src/components/layout && npm run typecheck:ci`
Expected: PASS.

- [ ] **Step 5: Commit**

`git add -A <paths touched in this task> && git commit -m "fix(i18n): re-localize memoized chrome on language switch"`

---

### Task 6: Title Case plugin setting labels

**Files:**
- Modify `tools/internal_plugins/anthropic_stt/plugin.json`
- Modify `tools/internal_plugins/google_stt/plugin.json`
- Test: `voice_typer/client/src/renderer/src/pages/plugins/__tests__/PluginDetail.test.tsx` (or the existing plugin settings test that reads manifest labels)

**Interfaces:**
- Consumes: `PluginInfo.settings[].label` from the manifest, rendered by `PluginSettingRow`.
- Produces: `"Show The Browser Window"` label in both manifests; `Notifications` unchanged.

- [ ] **Step 1: Write failing renderer test**

In the existing Plugins-page test that renders plugin settings, assert the visible label is `Show The Browser Window` for both plugins. Keep existing behavior assertions for the toggle.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd voice_typer/client && npx vitest run src/renderer/src/pages/plugins`
Expected: FAIL (label still sentence case).

- [ ] **Step 3: Change the two manifest labels**

Set `settings[0].label` to `Show The Browser Window` in both manifests. Do not touch `description`, `key`, `default` or any other settings label. The audit of `en.json` found the other settings labels already Title Case; the entire model-memory setting is excluded by owner instruction.

- [ ] **Step 4: Run plugin tests**

Run: `cd voice_typer/client && npx vitest run src/renderer/src/pages/plugins && npm run typecheck:ci`
Expected: PASS.

- [ ] **Step 5: Commit**

`git add tools/internal_plugins/anthropic_stt/plugin.json tools/internal_plugins/google_stt/plugin.json <test> && git commit -m "style(plugins): use title case for setting labels"`

---

### Task 7: Whole-tree verification and manual evidence

**Files:** no product code. Writes `worklog.md` and, if needed, `docs/audit/settings-i18n-manual-2026-11-20.md`.

**Interfaces:**
- Consumes: all six task commits.
- Produces: recorded green gates and manual UI evidence.

- [ ] **Step 1: Run static gates**

Run, in order: `.venv\Scripts\python.exe -m ruff check voice_typer tests` → `.venv\Scripts\python.exe -m pytest --import-mode=importlib --co -q` → `npm run typecheck:ci` in `voice_typer/client` → `cargo check` → `python scripts/sync_versions.py --check` → `python scripts/check_branding.py`.

- [ ] **Step 2: Run full suites on the final state**

Run `cd voice_typer/client && npx vitest run > <temp>/vitest-final.txt 2>&1` and `.venv\Scripts\python.exe -m pytest tests/ -n auto --dist=loadgroup -q --no-cov --tb=short > <temp>/pytest-final.txt 2>&1`, both detached with output redirected. Read summaries from those files only; do not re-run to rediscover failures.

- [ ] **Step 3: Manual UI verification**

Start the app with `npm run tauri:dev`, open Settings/General in English and confirm Streaming and Tray Click rows are gone. Switch App Language to Arabic and verify: sidebar stays left with RTL labels, content text is Arabic, search placeholder/title-bar labels/tooltips update without reload, title-bar arrows keep their LTR orientation, and the idle-unload option reads `دائمًا (إبقاء التحميل)`. Right-click the tray icon and confirm the context menu still opens; left-click and confirm the app opens/focuses. Record screenshots and exact observations in `worklog.md` under `## Validation Performed`.

- [ ] **Step 4: Final commit of evidence**

`git add worklog.md docs/audit/... && git commit -m "docs: record settings and i18n verification"`
