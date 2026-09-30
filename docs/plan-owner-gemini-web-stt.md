# Owner-only spike: Gemini web STT via Playwright

**Status:** Phase 0 exit passed (24h survival) — Phase 1 live probing
**Audience:** owner (private). **Never ship to users.**
**Date:** 2026-09-28 (rev 2) + owner update 2026-09-29 (Phase 1 note + §14 future owner settings)

## 1. Goal

One global hotkey → speak → text pasted into the focused app (e.g. WhatsApp),
using Google Gemini web’s free streaming mic as the STT engine.

```
hotkey #1  → remember paste target hwnd → start Gemini mic (page off-screen)
speak
hotkey #2  → stop mic → wait for stable transcript → restore focus → paste
```

## 2. Non-goals (hard)

| Non-goal | Why |
|---|---|
| Ship in any release / CI artifact / installer | Account-ban + ToS risk for end users |
| UI, Settings, tray, i18n for this feature | Must be invisible outside owner builds |
| Replace local/cloud dictation | Optional owner experiment only |
| Tiny/consumer mini-browsers | Not programmable |
| Attach to daily Chrome (CDP) | Must be isolated from daily browser |
| Clipboard `Ctrl+C` from the Gemini page | Racy; scrape DOM text |
| Toast/email body containing transcript | Privacy — speech is sensitive |
| `tools/owner` in any repo `package.json` script | Discoverability leak |

**Release rule:** accidental ship = P0 incident.

## 3. Decisions (locked)

| Topic | Decision |
|---|---|
| Host browser | **Playwright `channel: "chrome"`** (real Chrome binary) + **own** persistent `userDataDir`. Fall back to bundled Chromium only if Chrome channel fails. Never the daily profile. |
| Account | Burner Gmail only (ban = that account). |
| Paste | **Import product paste** (`voice_typer.server.clipboard` manager path — snapshot/restore, target gates, RDP delay, UIPI fail-closed). No reimplementation. |
| Alerts | **Desktop toast + local log only.** No email/webhook. Toasts never include dictated text. |
| Isolation | `tools/owner/` process; not wired into Tauri until spike passes §11. |
| Toolchain | Node deps **outside repo** (see §4). |

## 4. Hard ship gates (must all hold)

1. Code lives under `tools/owner/` — **not** in `voice_typer/`, **not** in Nuitka inputs, **not** in `tauri.conf.json` bundle/externalBin/resources.
2. Enabled only when **all** of:
   - env `VOICE_TYPER_OWNER_TOOLS=1`, **and**
   - gitignored `tools/owner/OWNER_ENABLED` exists, **and**
   - process is not a frozen/release sidecar.
3. No new `IPC_CONFIG_ALLOWLIST` / `set_config` / renderer / i18n / tray surface.
4. **Proof-of-absence test** `tests/tauri/test_owner_tools_absent.py` (wired into the C-CI-7 drift set) asserts:
   - `tools/owner` appears in no Nuitka `--include` / package list
   - not in `tauri.conf.json` externalBin/resources
   - not in NSIS/MSI file lists
   - gitignore covers `OWNER_ENABLED`, `gemini-profile/`, `debug/`, `last_error.json`
   - no root/client `package.json` script references `owner`
5. Node/Playwright deps install to `%LOCALAPPDATA%/voice-typer-owner/node-deps` — **never** repo-root `node_modules`.
6. Profile dir: `%LOCALAPPDATA%/voice-typer-owner/gemini-profile` — never `~/.lausu`.
7. Network egress is **C-DATA-1**-justified: owner-configured, owner-initiated, owner-only gated, browser navigation to Google only (not product code paths). Documented here so future agents do not “clean it up” as telemetry.

## 5. Architecture

```
tools/owner/gemini_stt/     (never packaged)
  run.js                    entry (node, NODE_PATH → %LOCALAPPDATA%/voice-typer-owner/node-deps)
  playwright_runner.js      persistent Chrome channel, selectors.json, scrape
  controller.py             hotkey, hwnd capture/restore, product paste import
  breakwatch.py             toast (no transcript) + last_error.json + screenshot
  selectors.json            data-only UI map (locale-scoped)
  config.example.json
```

**Paste (owner decision: import product):**
`controller.py` imports the existing clipboard manager paste path
(`voice_typer.server.clipboard` / `ClipboardSnapshot` borrow + restore,
target-safety, IME, RDP `paste_delay`, elevated/UIPI fail-closed).
Run via the project venv (`uv` / `.venv`) so the import resolves.
Do **not** copy `_paste.py` logic into the spike.

**Not in spike:** writing into product diagnostics logs, IPC commands, tray.

## 6. Spike phases

### Phase 0 — Profile + login viability (gate for everything else)

1. Launch Playwright persistent context with **`channel: "chrome"`**:

```js
const ctx = await chromium.launchPersistentContext(profileDir, {
  channel: 'chrome',
  headless: false,
  viewport: { width: 1280, height: 800 },
  args: ['--window-position=32000,32000'], // off-screen; headed so mic works
});
```

2. `context.grantPermissions(['microphone'], { origin: 'https://gemini.google.com' })`.
3. Open `https://gemini.google.com/app`. Manual **burner** Gmail login once.
4. Confirm session persists: close → relaunch → still logged in.
5. **24h survival check** (manual checklist): next day relaunch still authenticated.
6. Locale pin: record Gemini UI language in `selectors.json` (`"locale": "en"`). Change of locale = new selector set.

**STOP rules (fail-closed):**
- “This browser or app may not be secure” / OTP loop / captcha → **stop the spike** (§11 checkpoint 2). One fallback allowed only: retry once with `channel: 'chrome'` after clearing profile if first attempt used bundled Chromium. No further bypass.
- Phone-verify demand on burner → stop; owner may switch burner account once, then stop if it recurs.

**Exit:** logged-in Gemini in isolated Chrome profile; mic permission granted; 24h relaunch OK.

### Phase 1 — Selector discovery (live)

Do not hardcode guessed selectors. Discover on the live page and store in `selectors.json`:

| Control | Notes |
|---|---|
| Login-state / account chip | Fastest logged-out detector (before redirect) |
| Mic / voice button | May need to open prompt box first |
| Recording-active indicator | Start/stop actually happened |
| Prompt box (contenteditable/textarea) | Transcript source |
| Stop / done affordance | If different from mic toggle |

Rules: prefer role/aria-label/visible text; on failure dump screenshot + aria snapshot to `debug/`.

**Exit:** mic on/off confirmed in UI.

### Phase 2 — Transcript scrape

1. After stop, poll prompt box text.
2. **Stability:** unchanged across **two consecutive** `stableMs` windows (default 800 ms each) AND length ≥ 1 non-whitespace char. Log discarded-interim cases (Gemini post-polishes after stop — a single plateau is not final).
3. Timeout `timeoutMs` (default 15000) → fail to breakwatch (empty/too-unstable).
4. Read `textContent`/`innerText` only. Never Ctrl+C.

**Exit:** spoken sentence → Python string.

### Phase 3 — Hotkey + focus choreography + paste

1. Hotkey default `ctrl+shift+space` — does **not** collide with product `DEFAULT_HOTKEY = "<caps_lock>"` (`voice_typer/server/config/_defaults.py`). Still **runtime-check** user-remapped product hotkeys and refuse on conflict.
2. **Hotkey #1:** record foreground hwnd (`GetForegroundWindow`) as `paste_target`; then start mic (page already off-screen from Phase 0).
3. **Hotkey #2:** stop mic → scrape (Phase 2) → `SetForegroundWindow(paste_target)` → product paste.
4. **Fail-closed paste target** (mirror `_paste.py` gates): if target hwnd died / is elevated / is unsafe / IME composing / not a text field → **do not paste**; leave text on clipboard and toast “paste blocked” (no transcript in toast). Import path already implements these — call it, don’t duplicate.
5. Clipboard: product `ClipboardSnapshot` borrow/restore around the paste (owner accepted product paste import). Owner clipboard is **not** permanently clobbered.
6. Mic contention: if product recording session is active (lockfile / product state the sidecar already owns), **refuse** owner hotkey + toast. Do not open the same input device.

**Exit:** Notepad/WhatsApp receive text; hwnd before #1 == successful paste target; clipboard restored.

### Phase 4 — Break detection + owner alert

Toast (no transcript text) + `last_error.json` + screenshot in `debug/` when:
- mic button / login chip / prompt box selector missing
- start click did not produce recording indicator
- transcript empty or failed stability within timeout
- login chip shows signed-out / accounts redirect
- page crash / context closed
- paste blocked (elevated/unsafe target)

**Exit:** forced selector break → toast within one action.

### Phase 1 exit note (2026-09-29, verified live)

- Burner chip confirmed in live screenshot + `debug/aria.txt`:
  `link "Google Account: <burner> (<burner-address>)"` — matches
  `selectors.json` `loginChip` (address lives only in the private plugin
  repo, never in this public doc). No warning/banner in screenshot or aria
  snapshot (no `accounts.google.com`, captcha, `not be secure`, or
  `Something went wrong` tokens).
- Dictate affordance: `button "Dictate (^⇧D)"`; prompt box:
  `textbox "Enter a prompt for Gemini"`. Both pinned in `selectors.json`.
- Still open: `recordingIndicator` + `stopButton` need a live mic-click
  capture (Phase 1 remaining). `discover.js` window parked for probing.
- **2026-09-30 probe (Playwright clicks ARE safe):** `probe.js` clicked
  `button "Dictate (^⇧D)"` → label swapped to
  `button "Stop dictation (^⇧D)"`, dotted waveform appeared in prompt
  box, stop-square + Send rendered, burner chip stayed, no challenge.
  Verdict: idle survival + safe-under-use both hold for clicks.
  `selectors.json` now pins all 5 (mic/stop = same toggle).
- **Profile free:** no `voice-typer-owner` Chrome process alive; no
  `Default/Singleton*` lock; `check.js` headless SESSION-ALIVE earlier
  same day. Safe to launch Playwright clicking (Phase 1 rule:
  idle survival ≠ safe-under-use; verdict comes from clicks).

### Phase 5 — Owner packaging + hygiene

1. Single entry `tools/owner/gemini_stt/run.js`.
2. `tools/owner/README.md`: burner-account warning, ToS gray area, **do not ship**, re-login, profile reset, selector update procedure.
3. Gitignore as in §4.4 (enforced by test, not just documented).
4. No root `package.json` `owner:gemini-stt` script — use a machine-local alias.
5. Daily-use log template (§11 appendix).

## 7. Config (owner-only, gitignored)

`tools/owner/gemini_stt/config.example.json`:

```json
{
  "hotkey": "ctrl+shift+space",
  "profileDir": "C:/Users/11/AppData/Local/voice-typer-owner/gemini-profile",
  "chromeChannel": "chrome",
  "locale": "en",
  "stableMs": 800,
  "stableWindows": 2,
  "timeoutMs": 15000,
  "geminiUrl": "https://gemini.google.com/app",
  "notify": "toast"
}
```

No secrets in git. Session lives only in the Playwright profile.

## 8. Mic ownership

While Gemini records, product recorder must not open the same device.
Spike **refuses** to start if product recording is active (Phase 3.6). Product wins.

## 9. Residual risks (owner accepts in writing)

- Burner ban/lockout; possible phone-verification demand.
- Google redesign / captcha / rate-limit downtime; no SLA; owner labor.
- ToS gray area of automating the web UI (personal, never shipped).
- Transcript bytes at rest in profile + `debug/` on the owner machine.
- Chrome channel may still be fingerprint-flagged; isolation ≠ invisibility.

## 10. Acceptance criteria

- [ ] Cold start → Gemini logged in (burner) via `channel: "chrome"` isolated profile.
- [ ] 24h relaunch still authenticated (manual Phase 0 exit).
- [ ] Hotkey #1 records `paste_target` hwnd and starts mic (UI confirms).
- [ ] Hotkey #2 stops; text in focused app; focus round-trip OK; clipboard restored.
- [ ] Works with daily Chrome **closed**.
- [ ] Product dictation unaffected when owner tool idle; owner tool refuses while product records.
- [ ] Forced selector failure → toast without transcript text.
- [ ] Elevated/unsafe target → paste blocked, text on clipboard (product gates).
- [ ] `test_owner_tools_absent.py` green; `tools/owner` absent from release/CI lists.
- [ ] No i18n / Settings / tray / `set_config` changes.

## 11. Decision checkpoints + trial log

1. Full day WhatsApp/Notepad use without babysitting?
2. Any Google challenge/captcha/lock? **One unexpected challenge during trial week → log and continue. Account lockout or second challenge → stop spike.**
3. Selector maintenance cheaper than Deepgram Live / local interim text? If no → stop.

**Policy on login failure (owner):** real Chrome + isolated profile first; if Google still refuses, **stop**. No long bypass campaign.

### Daily-use log template (append to `tools/owner/gemini_stt/trial_log.md`)

| Date | Dictations | OK | Fail mode | Selector change? | Notes |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

## 12. Explicit non-rollout

Even if the spike is perfect:

> This feature stays owner-only forever unless the user explicitly reverses that decision in writing in this file and `AGENTS.md` Hard Don'ts.

No public experimental toggle. Not in README/CHANGELOG.

## 13. Review disposition (rev 2)

| Review item | Disposition |
|---|---|
| B1 Google login in automation Chromium | Taken. Phase 0 uses `channel: "chrome"` + isolated profile + stop rules. |
| B2 Focus choreography | Taken. hwnd capture / off-screen / SetForegroundWindow / fail-closed. |
| B3 Clipboard restore | Taken. Import product `ClipboardSnapshot` path. |
| B4 Node deps leak | Taken. `%LOCALAPPDATA%/voice-typer-owner/node-deps`. |
| B5 Absence test | Taken. `tests/tauri/test_owner_tools_absent.py` in drift set. |
| H1 Interim text | Taken. two stability windows + length floor. |
| H2 Mic contention | Taken. refuse while product recording. |
| H3 UIPI/elevated | Taken via product paste gates. |
| H4 RDP delay | Taken via product paste (`_compute_paste_delay`). |
| H5 Artifact hygiene | Taken. gitignore test; no transcript in toasts. |
| H6 C-DATA-1 | Taken. §4.7. |
| Nits (hotkey, login chip, locale, no diagnostics tail, no npm script) | Taken. |
| Q2 clipboard | Owner: use product restore. |
| Q3 alerts | Owner: toast + local log only. |
| Q1/Q5 login/challenge policy | Owner: chrome channel; stop if still blocked; one challenge log-and-continue; lockout = stop. |
| Q4 paste coupling | Owner: **import product paste** (overrides reviewer’s standalone preference). |

## 14. Future owner-only settings (NOT implemented — main feature first)

Owner request 2026-09-29. Documented so any dev/agent can pick up later.
None of this changes the spike gates (§4) or the non-rollout (§12).

### 14.1 Product-parity behavior (main feature scope, not future)

- Trigger → Gemini transcript → inject into the focused input via the
  **imported product paste path only** (§5 paste rule).
- Save every Gemini transcript via `history_db.add_transcription(text,
  duration=…, model="gemini-web", …)` + `transcription_final` publish so
  History/copy/repaste behave like any standard model.
- Dictation widget renders normally (`bubble_show` + start/stop audio cues
  via the product paths); static visualizer (no PCM routed) is accepted.
- No renderer/i18n/tray/`set_config` surface: owner config stays a
  gitignored file (`config.json`, see §7 + 14.2).

### 14.2 Owner-only settings surface (gitignored, owner machine only)

- Dedicated owner settings file only (e.g. `config.json` next to
  `config.example.json`, gitignored): **never** `config.json` product
  store, never `IPC_CONFIG_ALLOWLIST`, never renderer Settings.
- First setting: `headless` / `visible` profile toggle —
  `visible:true` = headed window the owner can watch/click;
  `visible:false` = silent background (`--window-position=32000,32000`,
  still headed so mic works; true headless kills mic).
- Future keys slot in here without touching product config.

### 14.3 Deferred: prepend/append prompt text (NOT implemented)

- Optional `prepend_text` / `append_text` applied around the scraped
  transcript before paste+history (paste what the user sees; history
  stores the final string).
- Use case: strip-then-add instruction verbs, force-target-language
  framing, signatures. Simple string ops, no product text-cleanup change.

### 14.4 Deferred: spoken-command prefix + auto audio-clip injection (NOT implemented)

- Background: Gemini voice input is context-aware — a leading spoken
  instruction (e.g. "translate everything to English") steers the whole
  session's output language; the instruction itself lands at the head of
  the transcript and is removed with a prefix-strip.
- Future: `prefix_strip` (remove N chars/verbatim instruction head) +
  `audio_clip_path` (1–2s owner-recorded WAV of the command phrase)
  auto-played into the mic at session start via virtual audio routing,
  with `audio_clip_enabled` toggle. Owner speaks freely (AR/EN/mixed),
  gets back the target language without saying the command each time.
- Requires virtual-mic plumbing + prefix-strip tests; explicitly out of
  main-feature scope.
