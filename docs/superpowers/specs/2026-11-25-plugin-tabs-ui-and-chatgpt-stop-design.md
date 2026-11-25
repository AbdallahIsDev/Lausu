# Plugin tab lifecycle, Plugins page, and ChatGPT stop — design

## Intent / why

Three problems share one root: browser tabs are created by two uncoordinated layers, and the ChatGPT live dictation toggle is wired to the wrong selector. The Plugins page also nests card-in-card. Owner wants no unnecessary tabs across Anthropic, Google and ChatGPT, a wrapper-free plugin row, and a reliable hotkey stop.

## Goals

- One tab per platform, reused forever; no duplicate tabs on activation, hotkey, or switching.
- Hidden browser mode works identically (verified through extension state, not visuals).
- Hotkey stop commits/stops ChatGPT's live dictation using the supplied live button.
- Plugins render as three aligned items with no enclosing card surface.
- C-PLUGIN-4 gate everywhere developer-only surfaces render.

## Non-goals / anti-goals

- No third Chrome profile, no new transport, no plugin-specific bridges.
- No global single-active-tab policy: never close another plugin's tab or a user tab.
- No changes to dictation delivery/paste/history semantics.

## Constraints

- C-ASR-4: commit and discard selectors must not overlap.
- C-PLUGIN-3: a connected browser resolves its own tabs; missing tab != launch Chrome.
- C-UI-16: no bordered card inside a bordered card.
- C-DESIGN-1: renderer/design-system.html stay in sync (no Plugins mock exists there).
- Shared checkout is dirty with other sessions' work; snapshot at `C:\Users\11\AppData\Local\Temp\opencode\pre_plugins_audit_gitstatus.txt`, HEAD `0c7989dd`. Do not touch those files.

## Approaches (chosen)

- **One tab per plugin (owner-approved)** over global one-active-tab: bounds growth at 3, reuses the existing domain resolver, and never closes user content. The alternative saves 2 tabs but needs close/handoff lifecycle and risks unsent drafts.
- **Extension-only tab authority** over Python URL launch: Python starts the profile at `about:blank`; the extension's `resolve()` discovers/creates the platform tab.
- **Attribute-based ChatGPT stop** over the older label/glyph selector: the supplied `data-dictation-button="dictating"` is the live stable control; `cancelSelector` becomes empty for ChatGPT so commit/discard never collide.

## Implementation outline

1. `extension/tab_resolution.js`: after `find()`, collect all URL-pattern matches; keep the preferred tab, `chrome.tabs.remove` only surplus matches for that platform; never touch other platforms/unrelated tabs. Keep per-platform `inflight` coalescing. Add tests for survive/reuse/dedupe/no-unrelated-close.
2. `session.py::launch_profile_if_due` and all three `plugin.py` wrappers: pass `about:blank` as launch URL; drop config URL from the launch path. Keep profile-start cooldown and `_profile_missing` bypass. Tests pin blank launch + one tab after cold start.
3. `selectors/chatgpt.json`: prepend `button[data-dictation-button="dictating"]` to `stopSelector`; set `cancelSelector` to `""`. Update `content.js` ranking if needed; update JS DOM fixtures and `test_chatgpt_plugin.py` selector tests. Regenerate `generated/config.js` + sync stable extension; owner must reload the extension.
4. `PluginsPanel.tsx`: replace the cards' `SettingsSection` with a plain `<h2>` (same classes as `SettingsSection`) plus `grid grid-cols-3 gap-4` (no `p-2`). Keep error/empty states and shared settings section. Add a test pinning no card wrapper on the plugin row.
5. C-PLUGIN-4 leftovers: switch `App.tsx` redirect and dead `PageSwitch` plugins case to the dual gate hook.
6. Full lifecycle audit tests: plugin switching, repeated hotkeys, hidden mode (extension-state assertions), manual tab close recovery.

## Verification

- `node --test test/*.test.js` bridge suite; `pytest tests/plugins` + packaging; `npm run typecheck:ci` and focused vitest for the renderer edit; `ruff`.
- Live scenario results will be reported honestly; no signed-in automation is available.

## Left to builder

- Exact test names and fixture edits; whether `recordingState()` needs a chatgpt-specific signal after `cancelSelector` empties (prefer reusing `stopSelector`, already counted).
