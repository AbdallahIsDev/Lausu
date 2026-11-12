# tools/internal_plugins — in-house plugin experiments. NEVER SHIP.

This is an internal plugin the team is testing in-house. It is experimental,
not released, and not wired into the UI, Settings or the tray. Accidentally
shipping it is a P0 incident.

Gate: the plugin workspace (or `VOICE_TYPER_INTERNAL_PLUGINS=1`) +
`tools/internal_plugins/PLUGINS_ENABLED` + never frozen.
`PLUGINS_ENABLED` is gitignored; create it deliberately, never commit it.

## Source location and backups

This folder IS tracked by the parent repository: the source is visible on
GitHub, but every packaging input excludes it, so a built app ships none of
it. The guard is `tests/tauri/test_internal_plugin_tools_absent.py`.

Runtime state stays gitignored: `PLUGINS_ENABLED`, `config.json`,
`settings.json`, `debug/`, `last_error.json`, `extension/generated/`, and
browser profiles. Never commit those.

The earlier private mirror is optional. `backup.ps1` still works from a
checkout that has the nested `.git` directory; a normal clone of the parent
repo does not have one.

## anthropic_stt (Chrome-extension transport)

Drives the Claude web composer from a normal Chrome window on the dictation
profile, through a small MV3 extension. No DevTools endpoint, no Playwright, no
automation switches: the browser is an ordinary session, and the extension only
clicks the platform's own controls. The profile is started by
`chrome_profile.py` (activation, or the first hotkey press when it is closed)
with exactly `--user-data-dir`, `--profile-directory` and the Claude URL.

Same hotkey, bubble, sound cues, clipboard, paste and History as the local
model. The daemon listens on `127.0.0.1:17875`; the extension connects back to
it over a token-authenticated WebSocket on `/extension`. The shared Chrome
profile is still the one both internal plugins use, so keep the Claude window
open while dictating. (The Google STT plugin still launches Chrome with
Playwright and will report `profile-busy` while that window is open.)

### Pieces

- `plugin.py` — in-app session: hotkey seam, bubble/cues, paste, history.
- `run.js` — wiring: config -> relay -> HTTP control plane.
- `relay.js` — loopback WebSocket, handshake/token/origin checks, deadlines.
- `control_plane.js` — the `/start`, `/stop`, `/cancel`, `/status`, `/warm`,
  `/probe`, `/shutdown` shapes `plugin.py` consumes.
- `config_store.js` — one authority for `config.json` (token generated once) and for merging the Plugins page's `settings.json` over it.
- `tools/build-extension.js` — compiles `selectors.json` + token into
  `extension/generated/config.js`; `--check` fails on drift.
- `extension/` — MV3 service worker + content script.
- `chrome_profile.py` — the only code allowed to start a browser: plain flags
  only, refused otherwise (`verify_profile_launch.py`).
- `setup/occlusion.ps1` — Chrome policy values for covered-window capture.
- `setup/launch-claude-profile.ps1` — starts plain Chrome on the profile.
- `setup/install-shortcut.ps1` — puts "Claude Dictation" in the Start menu with
  the same argument shape.
- `probe.js` — PASS/FAIL selector check through the running bridge.

### One-time setup, in this order

1. Install the Node dependency outside the repo (this is the `NODE_PATH` the
   app passes to the daemon):
   ```powershell
   npm install --prefix "$env:LOCALAPPDATA/voice-typer-internal-plugins/node-deps" ws
   ```
2. Generate the extension config (creates `config.json` and the gitignored
   `extension/generated/config.js`):
   ```powershell
   node tools\internal_plugins\anthropic_stt\tools\build-extension.js
   ```
3. Open `chrome://extensions` **in the dictation profile** -> enable Developer
   mode -> Load unpacked -> `tools\internal_plugins\anthropic_stt\extension`.
   Confirm the service worker is active and reload the Claude tab once.
   (If no Chrome window is open yet, run step 4 first, then return here.)
4. Put the profile in the Start menu once, so you never hunt for the path:
   ```powershell
   powershell -File tools\internal_plugins\anthropic_stt\setup\install-shortcut.ps1
   ```
   Searching "Claude Dictation" then opens the profile as a normal browser.
   (`setup/launch-claude-profile.ps1` does the same from a shell.)
5. Sign in to `claude.ai` by hand. Finish any security check by hand. When
   Chrome asks for the microphone, allow it. Leave the window open.
6. Apply the occlusion policy, then restart Chrome once:
   ```powershell
   powershell -File tools\internal_plugins\anthropic_stt\setup\occlusion.ps1
   ```
7. Enable the in-app gate (`tools/internal_plugins/PLUGINS_ENABLED`) and start
   the app normally.
8. Select Anthropic STT on the Plugins page.
9. Press the product hotkey (Settings -> Hotkey) in any app. The bubble shows,
   Claude records, and the transcript is pasted when you press the hotkey
   again.

Remapping the hotkey in Settings needs no restart and no plugin change; the
product hotkey is the only trigger.

### Everyday use

Keep the extension loaded. The window does not have to be in front (covered by
another app is fine after step 6): the plugin opens the profile itself when it
is closed — on activation and on the first hotkey press — and waits up to 15 s
for the tab to answer. One launch per 30 s window, so a dead extension cannot
spawn a tab on every press; the press then fails honestly with
`browser-not-open`. The knobs on the Plugins page apply on the next hotkey
press — no daemon restart.

### What this design does and does not guarantee

- It removes the automation flags, the DevTools-pipe control and Playwright's
  plugin-owned cold browser. The platform sees a normal Chrome session on the
  owner's own profile, started the way a shortcut starts it.
- It does not make automating the platform UI compliant with Anthropic's
  terms, and detection is probabilistic rather than a boolean. A challenge can
  still appear; when it does, the tab stops and a human must finish it in that
  window.
- It does not change Claude's own dictation lifecycle. A covered or off-screen
  window and a background tab can still stop capture; window placement and the
  occlusion policy are the owner's knobs, not the plugin's.

### Troubleshooting

- **"The Claude browser window is closed, or the dictation extension is not
  loaded."** The plugin could not reach the tab (a launch inside the 30 s
  cooldown, or a profile that never answered). Open "Claude Dictation" from the
  Start menu, check `chrome://extensions` for the unpacked extension, and press
  the hotkey again.
- **Signed out / security check.** Finish it by hand in that window.
- **Selectors drifted after a Claude redesign.** Run `node probe.js` (app must
  be running and the extension connected). It prints PASS/FAIL per selector
  and writes a redacted composer dump to `debug/probe-composer.html`; update
  `selectors.json`, then re-run `tools/build-extension.js` and reload the
  extension.
- **Token drift.** The token lives in `config.json` and in
  `extension/generated/config.js`. Re-run `tools/build-extension.js` and
  reload the extension in `chrome://extensions`.

### Undo

```powershell
powershell -File tools\internal_plugins\anthropic_stt\setup\occlusion.ps1 -Revert
# remove the unpacked extension in chrome://extensions
# close the dictation-profile Chrome window
powershell -File tools\internal_plugins\anthropic_stt\setup\install-shortcut.ps1 -Remove
Remove-Item tools\internal_plugins\anthropic_stt\extension\generated\config.js
Remove-Item tools\internal_plugins\anthropic_stt\config.json   # rotates the token
Remove-Item tools\internal_plugins\PLUGINS_ENABLED             # back to the local model
```

`occlusion.ps1 -Revert` removes exactly the three values it added and asks for
a Chrome restart. Nothing else in the profile is touched.

## google_stt (plan: `docs/plan-internal-plugin-google-stt.md`)

Burner Gmail only. Ban risk sits on that account. Automating the Google web
UI is a ToS gray area — in-house experiment, never in a release
(P0 incident if it ships).

### How it runs now (in-app)

The plugin lives INSIDE the app. `voice_typer/server/internal_plugin_hook.py`
is a gated seam called from `LausuApp.__init__`; when the gate is closed it
does nothing (import-level check, no side effects). When open, it wraps
`app.toggle_dictation` / `_stop_dictation` / `_cancel_dictation` so the
app's own hotkey (caps lock, or whatever you set in Settings) drives the
Google session, and the app's own bubble + sound cues + clipboard +
history are used. Changing the hotkey in Settings is picked up
automatically (the backend re-registers and the wrappers stay in place).

The plugin is active while `tools/internal_plugins/PLUGINS_ENABLED` exists.
Rename or delete that file to get normal local dictation back; re-create it
for the Google STT plugin.

### Pieces

- `plugin.py` — in-app session: daemon control, bubble/cues via
  event_bus, paste via app.clipboard, history via app.history_db.
- `run.js` / `playwright_runner.js` — Node daemon: persistent Chrome
  profile, mic toggle, stable transcript scrape, prompt-box cleanup
  (`New chat` after every successful copy), toast-free error records.
- `selectors.json` — data-only UI map. Fix after a Google redesign here;
  no code changes needed.
- `config.example.json` — copy to `config.json` (gitignored) and edit:
  `visible: false` parks the browser off-screen (silent background);
  `true` shows the window so you can watch/click it.
- `check.js` — one-shot: is the session still logged in?
- `login.js` — one-shot manual login into the isolated profile.
- `probe.js` — one-shot selector re-verification: loads the page, clicks the
  mic toggle, asserts every selector in `selectors.json` still resolves
  (idle → recording → idle). Redacted aria snapshots land in `debug/`.
- `app_test.py` — harness: boots the app with the gate open, toggles
  start/stop without the GUI (writes a STOP marker file to end).
- `debug/` — screenshots, aria snapshots, daemon logs (gitignored).

### Setup once

1. `setx VOICE_TYPER_INTERNAL_PLUGINS 1` (or export it in your dev shell).
2. `New-Item tools/internal_plugins/PLUGINS_ENABLED` (gitignored marker).
3. Install Playwright deps outside the repo:
   `%LOCALAPPDATA%/voice-typer-internal-plugins/node-deps`.
4. Run the app normally (`cd voice_typer/client && npm run tauri:dev`).
   The daemon auto-starts with the app.

### Caveats

- Google hears your SPEAKERS. Mute or close media before dictating, or
  it will transcribe what is playing.
- Modes: one thing at a time. While the Google STT session runs, the local
  recorder stays idle; press ESC (or your cancel key) to abort without
  pasting.
- Reset profile: close Chrome, delete
  `%LOCALAPPDATA%/voice-typer-internal-plugins/google-stt-profile`, rerun
  `login.js`, log in again.

