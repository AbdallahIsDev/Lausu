# Settings simplification + localization/layout consistency

Date: 2026-11-20
Status: Approved by owner (approach + design); implementation pending plan.

## Intent and why

The owner is trimming Settings to options people actually change, and fixing three
localization defects seen in the running app: Arabic switches the sidebar from
left to right, chrome text stays English after a locale switch, and title-bar
arrows mirror under RTL. The goal is a simpler Settings page with fixed, sensible
behavior for removed options, and one language state that updates the whole UI
immediately without moving the layout.

## Goals

1. Streaming transcription is permanently ON on Windows, Linux and macOS; no UI
   switch. Internal developer kill-switch stays (see non-goals).
2. Tray left-click always opens/focuses the app on every OS; right-click menu is
   untouched; no Tray Click setting.
3. Only the contradictory `Never (Keep Loaded)` dropdown label changes. No other
   change to the model-memory setting — not its key, values, tooltip or logic.
4. Sidebar is physically left in every locale; Arabic text still renders RTL.
5. Locale switch updates sidebar, title bar, search placeholder, switches,
   dialogs and plugin UI immediately, with no restart or reload.
6. Title-bar back/forward arrows keep their LTR orientation under RTL.
7. Plugin setting labels and other sentence-cased settings labels use Title Case.

## Non-goals / anti-goals

- No extension of idle-unload to TTS, translation or LLM polish. Owner explicitly
  froze that work; it needs a separate decision.
- No removal of the right-click tray context menu or its Toggle Dictation item.
- No removal of the `VOICE_TYPER_STREAMING=0` developer kill-switch (it is not a
  user setting; it is the emergency off-ramp for broken workers).
- No change to module-level `t()` semantics, no global reactive translation store,
  no new i18n library.
- No removal of the six `streaming_*` tuning fields: they are internal config, not
  exposed in the UI, and load-time coercion/tests depend on them.
- No change to the Settings back-chevron mirroring (owner scoped arrow fix to the
  title bar).

## Constraints

- `C-CONF-1`: `config.json`/`Config` is the only settings authority.
- `C-CONF-5`: do not silently overwrite valid persisted settings. Removed keys
  are intentionally ignored and disappear on the next save; no value is repurposed.
- SEC-002: anything removed from the UI must also leave
  `config_validators/allowlist.py`, so `set_config` cannot still write it.
- `C-I18N-1` / `C-I18N-2`: every changed user-facing string in all 8 locales,
  genuinely translated.
- `C-UI-1`: copy names the real state; no vague labels.
- `C-FOCUS-1/2/5`, `C-SIDEBAR-*`: focus rings and sidebar structure/identity stay
  intact while making chrome reactive.
- `E1` wiring checks, `E6` tests with the change, `E14` regression checks,
  `C-TEST-7` behavioral tests over structural pins.
- Cross-platform: Windows, Linux, macOS. Rust tray code is compiled on all three.

## Approaches considered (owner picked these)

### Removed settings: delete fields, not hide rows
Keeping deprecated-but-writable fields would leave dead settings reachable via
`set_config` (SEC-002). Delete `streaming_transcription` and
`tray_left_click_action` from the Python schema, the allowlist, the renderer type,
the Settings rows, search-label registry, i18n keys and test fixtures.
`StreamingSessionCoordinator.streaming_enabled()` returns True except for the env
kill-switch; it stays platform-neutral. Tray behavior moves entirely to Rust.

### Tray: fix the host, leave the menu alone
`tray.rs` currently sets `show_menu_on_left_click = cfg!(target_os = "macos")`
and returns early for macOS icon events. Set it to `false` everywhere and delete
the early return; official Tauri v2 docs confirm the right-click menu still opens
when `show_menu_on_left_click(false)` is used. Remove the now-dead Python branch
that bolds a menu item from `config.tray_left_click_action`. Only the setting goes
away — the menu and all its items remain.

### RTL shell: pin direction, don't reverse flex
`App.tsx`'s shell row inherits `html[dir=rtl]`, so flex row paints [sidebar, main]
right-to-left. Give that row an explicit `dir="ltr"` and give the main column an
explicit locale-derived direction. Keep the Sidebar's nav container `dir="rtl"`
so `justify-start`, `rtl:translate-x-3` and label motion keep their meaning while
the `<aside>` stays left. Convert the physical `rounded-l-lg border-l` on the
main column to logical `rounded-s-lg border-s`. Chosen over `rtl:flex-row-reverse`,
which reverses DOM order and leaves the physical border on the wrong side.

### Live locale: subscribe the frozen chrome
`Sidebar`, `TitleBar`, `GlobalSearchBar`, `ModelsTabSwitcher` and
`AnalyticsRangeSwitcher` are `memo`-wrapped and import bare `t()`; App's
re-render cannot pierce their memo boundary. Each calls `useT()` so the locale
subscription re-renders it. Bare `t()` stays a call-time function for everyone
else (pinned by `i18n/__tests__/rtl-render.test.tsx`). Chosen over threading a
locale prop through every memoized subtree or making `t()` globally reactive.

### Title-bar arrows: scope the CSS opt-in
Chevrons in `titlebar/titleBarButtons.tsx` carry `nav-directional-icon`, which
`index.css` mirrors under any `[dir=rtl]` ancestor. Remove that class from those
chevrons only. The shared CSS rule and the Settings back-chevron stay as they are.

### Model-memory label: one string, eight locales
Change `settings.modelIdleUnload.never` from "Never (Keep Loaded)" to
"Always (Keep Loaded)" (genuine translations). Value `0` means the idle timer is
disarmed, i.e. the model is kept loaded, so the new label matches the code at
`model_manager/_lifecycle.py:138-151`. Nothing else in that setting changes.

### Typography: labels only
Title Case plugin setting labels in both plugin manifests, and sentence-cased
settings labels in the English catalog. Descriptions/tooltips stay prose; other
locales use their own capitalization conventions (no English pasted in).

## Build order

1. Settings removals (schema, allowlist, types, UI, i18n, fixtures, tests) and
   fixed streaming/tray behavior, including Rust tray changes.
2. Model-memory `never` label in all 8 locales.
3. RTL shell pin + title-bar arrow fix + tests.
4. Locale subscriptions for the five memoized chrome components + tests.
5. Title Case copy sweep + tests.

Each step keeps its own focused tests green; full suite + `cargo check` +
`typecheck:ci` at the end on the final state.

## What is left to the builder

Mechanical choices: exact migration logging shape for removed keys, exact
component-local placement of `dir="rtl"`, and the precise set of English labels
whose sentence case needs fixing (audit, then change only genuine label strings).
No product decisions remain.
