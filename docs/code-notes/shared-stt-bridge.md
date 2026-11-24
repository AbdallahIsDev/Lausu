# Shared Chrome-extension STT bridge

Both internal STT plugins (`anthropic_stt` = Claude, `google_stt` = Gemini)
use ONE transport under `tools/internal_plugins/_common/bridge/`. The plugin
directories own only the hotkey seam, copy module, platform descriptor and
settings. No plugin carries a second copy of the extension, relay or launcher.

## Install and load (the trap that broke the bridge)

Chrome registers an unpacked extension by **absolute path**. When the old
`anthropic_stt/extension/` directory was moved into the shared bridge, Chrome's
`extensions.settings` entry silently disappeared; no error was raised and the
old running window kept serving the old Claude-only manifest, which made it
look like two profiles. The fix is to never register a path inside the git tree.

- `install.json` is the single authority for `extensionRelativePath`,
  `extensionId`, `profileRelativePath`, `profileDirectory` and `relayPort`.
  `install_paths.js` (Node sync + instructions) and `install_paths.py`
  (verifier + user hint) both resolve it from `LOCALAPPDATA`.
- `sync_extension.js` copies the SOURCE `bridge/extension/` into the stable
  app-data path resolved from `install.json` (the verifier prints the exact
  path) on every daemon boot and after a settings change, writes
  `generated/config.js` there, and
  removes stale files so a renamed asset cannot linger. The source tree stays
  the only thing edited by developers.
- If the registration points back into the repo, the daemon logs the exact
  stable path to load from and `/status`/`/warm` and start-failure hints carry
  the same actionable message. Nothing falls back to Playwright or CDP.
- Branded Chrome 137+ refuses `--load-extension`
  (https://developer.chrome.com/blog/extension-news-june-2025). Do not add the
  flag or suppress `DisableLoadExtensionCommandLineSwitch`.
- Run the read-only verifier (one command) to see the expected path, files,
  generated-config drift check, current registration and the exact next step:
  `.venv/Scripts/python.exe tools/internal_plugins/_common/bridge/verify_extension_install.py`.
- After any extension change: reload the unpacked extension from
  `chrome://extensions`, then restart the dictation Chrome window so the
  multi-site manifest takes effect in already-open tabs.

## Pieces and data flow

```
plugin.py (hotkey/bubble/paste/history)
  -> _common/daemon.py spawns ONE bridge/run.js with --plugin-dir + --platform
     -> config_store.js  (platform descriptor + one token + one port + one profile)
     -> build-extension.js regenerates extension/generated/config.js on boot
     -> relay.js         (ws://127.0.0.1:17875/extension, Origin + token hello)
     -> control_plane.js (/status /start /stop /cancel /clear /warm /probe)
        -> extension/service_worker.js resolves tab by opts.platform
           -> extension/content.js resolves selectors by location.host
```

`chrome_profile.py` is the ONLY browser launcher and may pass exactly three
arguments: `--user-data-dir`, `--profile-directory=Default`, and the URL.
`_assert_plain` rejects every other switch (C-START-3, pinned by
`anthropic_stt/verify_profile_launch.py`).

## Invariants

- **Why `--disable-extensions` was fatal.** `playwright-core`'s
  `chromiumSwitches()` always includes `--disable-extensions`; with no
  `ignoreDefaultArgs`, `launchPersistentContext` disabled EVERY extension in
  Google's window. The shared profile already had the unpacked extension
  registered — it simply never loaded there. Playwright is gone.
- **One token.** `_common/bridge/token.json` is gitignored and authoritative.
  It adopts the existing Claude token on first load, so no rotation and no
  extension reload is forced. The build step writes the same token into
  generated config. Never log it.
- **One port.** 17875 for both platforms; 17874 is retired. One plugin is
  active at a time, and deactivating it shuts the shared daemon down.
- **One profile.** `.../dictation-profile`, shared by every plugin. The former
  `google-stt-profile` folder is moved once by `installPaths.migrateProfile()`
  on daemon boot; the move is atomic and is skipped while Chrome holds the
  profile, so sign-ins and the extension registration survive the rename.
- **Per-platform targeting.** Every command carries `platform`; the service
  worker queries only that site's tab; the content script throws
  `wrong-platform` for a mismatched command and `selectors-missing` when its
  live selectors are unverified. `/status` reports the connected tab's actual
  platform so a Google snapshot can never satisfy a Claude daemon.
- **Generated config.** Staging skips `generated/` and `token.json`; the daemon
  regenerates config on every boot and after a settings change. `--check` is a
  drift gate, never a writer.
- **Delivery-only formatting.** First-letter case and separator space are
  applied by `_common/delivery.py` at paste time; history/recovery/events keep
  the decoded text byte-identical (C-TRANS-2). Do not change that logic here.
- **Commit vs discard.** Claude's "Finish dictation" and "Cancel dictation"
  keep separate selectors; the shared content script's stop path uses only the
  commit control (C-ASR-4).

## Clearing the prompt box (never navigate)

After a delivered transcript the composer is cleared **in place**. Clicking the
platform's own "New chat" control navigates, which reloads the view and throws
away the page state the user is working in, so it is only a fallback for an
editor that refuses every in-place strategy.

The ladder lives in `clearComposer()` and is ordered by what actually works:

| # | Strategy | Works when |
|---|---|---|
| 1 | focus + select contents + `execCommand('delete')` | the tab owns OS focus |
| 2 | `execCommand('selectAll')` + delete | focused |
| 3 | `execCommand('selectAll')` + `insertText ''` | focused |
| 4 | `innerHTML = '<p><br></p>'` + `beforeinput`/`input`/`change` | always (framework editors) |
| 5 | `textContent = ''` + the same events | always |

Strategy 1-3 are the cheap, correct path but they are **no-ops when the window
is in the background** — which is the normal case, because the user is typing
in another app while the dictation window sits behind it. That is why the DOM
strategies exist and why they run before any navigation: measured live on
Gemini (Quill-backed `rich-textarea`), the composer stayed dirty with the
editing commands alone and cleared immediately through the DOM path.

`clean()` returns `{cleaned, via}` (`clear` | `new-chat`) and the daemon logs
`cleanup-failed` only when even New chat could not empty the box. `cancel()`
also clears in place (discard = drop the text), falling back to New chat.
Ensuring a clean box before a start uses the same ladder, so a leftover draft
never costs a page navigation either.

## Gemini adapter (live-measured 2026-11-20)

Measured in the dictation profile with the account signed in, by driving the
platform's own controls (no synthetic events, nothing typed into the page).

| Selector | Value | Evidence |
|---|---|---|
| `composer` | `div[role="textbox"][contenteditable="true"][aria-label="Enter a prompt for Gemini"]` | probe PASS |
| `micSelector` | `button[aria-label^="Dictate"]` | probe PASS (count 2: toolbar + composer) |
| `stopSelector` | `button[aria-label^="Stop dictation"]` | live: exactly 1 while capturing |
| `cancelSelector` | empty | Gemini has NO discard control |
| `idleSlot` | `div[data-node-type="speech_dictation_mic_button"], speech-dictation-mic-button` | probe PASS |
| `newChatNames` | `["New chat"]` | probe PASS |

What Gemini actually does, measured: clicking `Dictate` relabels the SAME
control to `Stop dictation (^shift+D)` and the composer area is replaced for
the duration of the capture. There is no `Listening` placeholder and no
`aria-live` node, so the toggle label is the only recording signal — the
existing `classifyRecordingState` already treats "stop control present" as
recording, which is why the label flip is sufficient.

Two consequences that are now pinned in code and tests:

1. **A discard control is optional.** `SELECTORS_READY` requires composer,
   mic, stop and idle slot only. `cancel()` still prefers a real discard
   control whenever one exists and never clicks the commit control as a
   substitute (C-ASR-4); with no discard control it clicks stop and then runs
   `newChat()` so the text is dropped.
2. **The verifier trusts the live bridge.** Chrome flushes
   `Secure Preferences` lazily, so a freshly loaded unpacked extension looks
   "not registered" on disk while it is demonstrably working. The verifier
   therefore PASSes the registration check when the daemon answers
   `/status` with `browser: connected`, and says so explicitly.

Re-measuring after a Gemini redesign: open the app and the profile, run
`node tools/internal_plugins/_common/bridge/probe.js`, update
`selectors/gemini.json`, then
`node tools/internal_plugins/_common/bridge/tools/build-extension.js` and
reload the extension.
