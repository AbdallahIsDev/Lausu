# tools/internal_plugins — in-house plugin experiments. HIDDEN BY DEFAULT.

This is an internal plugin the team is testing in-house. It is experimental and
released only behind an undocumented owner unlock; neither the Plugins nav item
nor the page exists for a normal user.

The plugin SOURCE is embedded in the compiled app as data files (reversal of the
previous "never packaged" rule, 2026-11-13). Only source + manifests ship:
runtime state is staged out and is written per-user at runtime.

Gate (all of): `config.developer_mode` is `true` — the owner presses
`ctrl+shift+alt+d` three times within 1.5 s, or the breakglass env
`VOICE_TYPER_INTERNAL_PLUGINS=1` — plus a usable workspace plus
`PLUGINS_ENABLED` in that workspace.
`PLUGINS_ENABLED` is gitignored; create it deliberately, never commit it.

## Source location, bundling and backups

This folder IS tracked by the parent repository. At build time
`scripts/build/stage_internal_plugins.py` copies a curated tree into
`build/internal_plugins_bundle/tools/internal_plugins`, and the
`build_sidecar_*.sh` scripts embed it with
`--include-data-dir=...=tools/internal_plugins`. Staging skips runtime state,
tests, `node_modules` and dotfiles. On unlock, `voice_typer/server/plugins/workspace.py`
seeds that tree into `<config dir>/developer_plugins/tools/internal_plugins`, so
the daemon never writes into the extracted bundle. The guard is
`tests/tauri/test_internal_plugin_packaging.py`.

Runtime state stays gitignored: `PLUGINS_ENABLED`, `config.json`,
`settings.json`, `debug/`, `last_error.json`, `extension/generated/`, and
browser profiles. Never commit those.

The earlier private mirror is optional. `backup.ps1` still works from a
checkout that has the nested `.git` directory; a normal clone of the parent
repo does not have one.

## Chrome-extension bridge (every platform)

`anthropic_stt`, `google_stt` and `chatgpt_stt` share ONE MV3 extension, ONE loopback relay,
ONE relay token and ONE Chrome profile. There is no Playwright path any more:
`playwright_runner.js` and Google's old `run.js` are deleted. Playwright's
`launchPersistentContext` forces `--disable-extensions` into Chromium's default
arguments, which is why the Anthropic extension disappeared whenever Google
STT was selected — both plugins now use the same normal Chrome session.

- Shared home: `tools/internal_plugins/_common/bridge/`
  - `run.js` — wiring: config -> generated config -> relay -> HTTP control plane.
  - `relay.js` — loopback WebSocket, extension Origin + token handshake, deadlines.
  - `control_plane.js` — `/start`, `/stop`, `/cancel`, `/status`, `/config`,
    `/warm`, `/probe`, `/shutdown`, all scoped to the owning plugin's platform.
  - `config_store.js` — one config authority: one token, one port, one profile.
  - `extension/` — the SOURCE of truth for ONE MV3 service worker and ONE
    content script, matching `https://claude.ai/*`, `https://gemini.google.com/*`
    and `https://chatgpt.com/*`.
  - `install.json` — the ONE authority for the stable install path, extension
    id, profile relative path and port. `install_paths.js` / `install_paths.py`
    resolve it from `LOCALAPPDATA`; no second literal exists.
  - `sync_extension.js` — copies the source into the stable app-data install
    path on every daemon boot and settings change, removing stale files.
  - `selectors/claude.json`, `selectors/gemini.json`, `selectors/chatgpt.json` —
    per-platform selectors.
  - `tools/build-extension.js` — compiles every selector set + the token into
    `extension/generated/config.js`; `--check` fails on drift.
  - `verify_extension_install.py` — one read-only command that prints the
    stable install path, the registration target and the exact next step.
  - `chrome_profile.py` — the only browser launcher: plain flags only
    (`--user-data-dir`, `--profile-directory`, URL); verified by
    `verify_profile_launch.py`.
  - `session.py`, `keepalive.py`, `daemon_client.py` — shared state machine,
    wake-up keepalive and HTTP client.
- Each plugin directory keeps only `plugin.json`, `plugin.py` (hotkey seam,
  bubble/cues, paste/history), `config.json`, `config.example.json` and its
  `copy.py`. Its `config.json` is a platform descriptor: `platform`
  (`claude` | `gemini` | `chatgpt`), `url`, `port` (17875), `profileDir`,
  `relayToken`.

### Invariants

- **One token.** `_common/bridge/token.json` (gitignored) is the authority. On
  first use it adopts the existing Claude token so a loaded extension keeps
  working; no rotation. Both generated config and both daemons read it.
- **One port.** 17875. Only one plugin is active at a time; the old Google
  daemon's 17874 is retired. A warm/start request from Google never drives a
  Claude tab: the daemon sends `platform` with every command, the service
  worker resolves only that platform's tab, and the content script refuses a
  command for the other platform with `wrong-platform`.
- **One profile.** `C:/Users/11/AppData/Local/voice-typer-internal-plugins/dictation-profile`.
  The name is deliberate — it is already registered and signed in.
- **Install path is stable and outside the repo.** Chrome registers unpacked
  extensions by ABSOLUTE PATH: moving or deleting the registered directory
  silently removes the extension. The daemon therefore syncs the source into
  the path printed by the verifier (derived from `install.json` +
  `LOCALAPPDATA`) and never asks Chrome to load from the git tree. A registration
  pointing into the repo is detected and reported with the fix. Branded Chrome
  137+ refuses `--load-extension`
  (https://developer.chrome.com/blog/extension-news-june-2025), so do not try it
  and do not smuggle in `--disable-features=DisableLoadExtensionCommandLineSwitch`.
- **Generated config is runtime state.** Staging skips `generated/` and
  `token.json`; the daemon regenerates `extension/generated/config.js` on each
  boot and after a settings change. `--check` still catches drift.
- **Plain flags only.** The bridge never uses Playwright, CDP, DevTools,
  `--remote-debugging` or automation switches. The extension only clicks the
  platform's own controls; commit and discard keep distinct selectors (C-ASR-4).

### One-time setup

1. Install the one Node dependency outside the repo:
   ```powershell
   npm install --prefix "$env:LOCALAPPDATA/voice-typer-internal-plugins/node-deps" ws
   ```
   (Only `ws`. Playwright is no longer installed by this project.)
2. Check the install (read-only) and copy the path it prints:
   ```powershell
   .venv\Scripts\python.exe tools\internal_plugins\_common\bridge\verify_extension_install.py
   ```
   Start the app once first so the daemon has synced the extension into that
   stable app-data path. The verifier prints it, confirms the files and
   generated config, and says whether Chrome is registered there.
3. In the dictation profile open `chrome://extensions` -> Developer mode ->
   Load unpacked -> **the stable path printed by the verifier** (never a path
   inside this repository). Confirm the service worker is active, then reload
   the Claude and Gemini tabs. (If no window is open yet, run step 4 first.)
   The single manifest covers both origins; one load serves both plugins.
4. Optional Start-menu shortcut for the profile (Claude-oriented, but the same
   profile serves both sites):
   ```powershell
   powershell -File tools\internal_plugins\anthropic_stt\setup\install-shortcut.ps1
   ```
5. Sign in to both sites by hand. Finish any security check by hand. Allow the
   microphone when Chrome asks. Leave the window open.
6. Apply the occlusion policy and restart Chrome once (Windows capture):
   ```powershell
   powershell -File tools\internal_plugins\anthropic_stt\setup\occlusion.ps1
   ```
7. Unlock the hidden Plugins page (three `ctrl+shift+alt+d` presses in 1.5 s),
   create `tools/internal_plugins/PLUGINS_ENABLED` if needed, then select either
   Claude STT or Google STT. Selecting one shuts the other's bridge down.

### Everyday use

The product hotkey drives whichever plugin is selected. The bubble, sound
cues, clipboard/paste (including first-letter case and separator), history and
live level meter are the same for both. `visible` hides/shows the profile
window without launching flags; `notify` controls error toasts. One launch per
30 s cooldown prevents a dead extension from spawning tabs on every press.

### Gemini-specific state

Both selector sets are live-verified (Gemini measured 2026-11-20 in the
dictation profile). Gemini exposes NO separate discard control: the Dictate
button relabels itself to `Stop dictation` while it captures, so
`cancelSelector` is intentionally empty and cancel degrades to "stop, then
discard the text". A discard control is therefore OPTIONAL in the shared
content script — requiring one made Google permanently answer
`selectors-missing`. Never reuse the commit control as a cancel target
(C-ASR-4), and never add a selector from memory: measure it on the live page
and re-run the probe.

### Troubleshooting

- **Extension missing / bridge not connected.** Check `chrome://extensions` in
  the dictation profile and reload it from the shared path. The daemon
  regenerates `generated/config.js` on boot; if you changed `config.json` or
  selectors, re-run the build and reload the extension.
- **Token drift.** Re-run the build and reload the extension. Never delete
  `token.json` unless you intend to rotate and reload.
- **Selector drift.** Run `node tools/internal_plugins/_common/bridge/probe.js`
  with the app running and the extension connected. It prints PASS/FAIL per
  selector and a redacted composer dump. Update `selectors/<platform>.json`,
  re-run the build and reload the extension.
- **Signed out / security check.** Finish it by hand in that window.
- **`wrong-platform`.** The wrong site's tab is connected; open the platform
  matching the selected plugin and press again.

### Undo

```powershell
powershell -File tools\internal_plugins\anthropic_stt\setup\occlusion.ps1 -Revert
# remove the unpacked extension in chrome://extensions
powershell -File tools\internal_plugins\anthropic_stt\setup\install-shortcut.ps1 -Remove
Remove-Item tools\internal_plugins\PLUGINS_ENABLED
```

Runtime state (`config.json`, `token.json`, `extension/generated/`, `debug/`,
the profile) is never committed and is never deleted by a build.
