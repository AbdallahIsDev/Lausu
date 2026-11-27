# Partial dictation recovery — research only (no production changes)

## Evidence available

- Content script `extension/content.js`: `composerText()` reads textarea
  `.value` and ProseMirror paragraphs; `status()` exposes only `has_text`
  (boolean), `page`, `micCount`, `selectorsReady`; `probe()` reads
  `navigator.permissions.query({name:'microphone'})`. There is NO production
  command that reads live text during a recording; `diagnostics-draft-read`
  is dev-only and reads the settled composer, not a recording overlay.
- Platform selectors: `selectors/chatgpt.json`, `claude.json`, `gemini.json`
  define mic/stop/composer anchors, not a live-transcript anchor.
- Firecrawl (Chrome docs): `webRequest` needs the `webRequest` permission plus
  host permissions, and does not expose WebSocket frames; observing WebSocket
  traffic legitimately requires the `debugger` API, a broad permission with a
  store-review/privacy cost. Web Speech `SpeechRecognition` supports
  `interimResults`, but only for a recognition object the page owns — an
  extension cannot attach to a page's existing instance.
- Owner's manual findings (not independently reproduced here): ChatGPT/Claude
  show live text in a DOM recording component; Gemini shows none until stop.

## Per platform

| Platform | Live text mechanism | Readable without new permission? | Verdict |
|---|---|---|---|
| ChatGPT | claimed DOM recording component | likely via DOM, but NOT PROVEN | UNVERIFIED — no controlled speech input available to this agent; owner report only |
| Claude | claimed DOM recording component | likely via DOM, but NOT PROVEN | UNVERIFIED — same reason |
| Gemini | owner reports no DOM text until stop, probably server-side final result | no DOM path proven; network path needs `debugger` | NOT FEASIBLE with current permissions (owner report + code absence of any live-text API); live proof UNVERIFIED |

## Design sketch (conditional on a DOM path existing)

Poll or use `MutationObserver` on the active recording component from the
content script while a cycle is active; keep the last non-empty snapshot in
RAM only, cleared at stop/cancel/success. A temp file is NOT recommended: the
snapshot is dictated text, and an on-disk copy survives crashes and leaks.
On browser death, recover the last snapshot into History and paste only if a
validated target snapshot exists; the final stop text always wins. Esc discards
the snapshot. A bridge-only drop with live page must re-read the full composer
before giving up. Coordinate with ITEM 2 so the critical notice fires once.

## Risks (REGRESSION-PRESERVATION)

Page-ready gate and verified click must not depend on the live-text node;
stop scrape and clipboard/paste flow must remain the authority; no polling may
run while idle; no text content may be logged. Estimated size: moderate
(shared content-script poller + session snapshot + History/paste branch),
but blocked on proving a DOM path.

## Recommendation

Do not implement until a real capture proves a stable, complete live-text
node for at least one platform; ChatGPT/Claude need that capture, Gemini does
not look feasible without broad permissions.

## Follow-up evidence (real-path driver + fake audio, research only)

- Dev-only command channel now calls the REAL wrapped `toggle_dictation` (no key injection, C-HOOK-1): `voice_typer/server/plugin_dev_driver.py`, gated by the existing `DEVELOPER_DIAGNOSTICS` marker/frozen check, files under `debug/dev-command` (never staged). Live `22:56:42` run proved `caller=hotkey-start` and one real start.
- Firecrawl verified Chromium flags: `--use-fake-device-for-media-stream` + `--use-file-for-fake-audio-capture=<wav>%noloop` feed a 16-bit PCM WAV as mic input; `--use-fake-ui-for-media-stream` is a global consent bypass and must NEVER ship (our profile already pre-grants mic for the three origins). Launcher `_assert_plain` still allows only three args in production.
- Cached speech WAVs already on disk: `~/.cache/huggingface/tts/samples/magpie-Aria-en-US-v2-d810ff70.wav` (16-bit, 22050 Hz, 4.09 s) and `audio8-default-en-US-v1-d810ff70.wav` (16-bit, 44100 Hz, 4.04 s), both from `SAMPLE_TEXT`. No download needed.
- Live DOM capture during a real dictated sentence was NOT completed: the plugin profile window is only paintable after the dictation is already running, so user-style close at sub-second startup stages could not be reproduced reliably. ChatGPT/Claude live-text mechanism therefore stays UNVERIFIED with that reason; Gemini NOT FEASIBLE without broad permissions. Production recovery code NOT written.

## 2026-11-27 — controlled fake-audio captures (Chrome 158.0.8127.38)

Harness: `scripts/dev/fake_audio_chrome.ps1` (marker-gated, never staged, never
in the production launcher). It relaunches the ALREADY signed-in dictation
profile with `--use-fake-device-for-media-stream` and
`--use-file-for-fake-audio-capture=<absolute wav>` plus
`--remote-debugging-port=9223` for dev-only CDP inspection. It never uses
`--use-fake-ui-for-media-stream`; mic permission comes from the profile's own
pre-grant. WAV: `magpie-Aria-en-US-v2-d810ff70.wav` (mono 16-bit 22050 Hz,
4.09 s, neutral sample text from `voice_typer/server/tts/samples.py:27`).
Chromium docs via Firecrawl: `<path>` loops by default, `<path>%noloop` stops
at EOF; paths are literal (no URL encoding); 8/16/32-bit PCM or float WAV is
converted to the audio bus, so no resample was needed
(`media/base/media_switches.cc`, `media/audio/wav_audio_handler.cc`).

### Claude — FEASIBLE (cumulative contenteditable)

Live capture 01:20:22–01:20:28 while a real fake-audio dictation ran:
`div[data-testid="chat-input"].tiptap.ProseMirror > p > span`,
kind = text inside a `contenteditable="true"` ProseMirror box (no `aria-live`).
Lengths grew 31 → 68 → 100 → 137 chars; text was prefix-stable (cumulative,
not rewritten). Earlier 01:18:40–01:19:11 capture reached 569 chars. The box
reports `isContentEditable=true`; after Esc cancel the composer was empty
(`data-doc-empty="true"`), so the recovery snapshot must live in RAM.

### ChatGPT — FEASIBLE (cumulative contenteditable)

Live capture 01:26:52–01:27:07:
`div[aria-label="Ask ChatGPT"].ProseMirror` (also
`form[data-chatgpt-composer] ... [contenteditable="true"][role="textbox"]`),
kind = contenteditable, lengths 81 → 201 → 233 → 288 → 324 chars, prefix-stable.
A separate interim chip (`div.ComposerLayoutInput-…`) rewrote single words
("This" → "dictated" → "sounds"); it is NOT a recovery source.

### Gemini — NOT FEASIBLE with current permissions (capture proof)

Fake-audio dictation ran for 15 s (`state=recording`, dev status seq 335/336)
on `https://gemini.google.com/app`, signed in ("Dictate (^⇧D)" visible).
Scanner read once per second: 315 samples over 21 distinct candidates,
including input/textarea `.value`, text nodes, `[aria-live]`,
`contenteditable`, shadow roots and same-origin iframes. Zero candidates had
changing text; the only contenteditable composer stayed empty. No DOM path to
live words exists, and the network path needs `debugger`/`webRequest` (broad
permissions, rejected). Recovery for Gemini is therefore not implemented.

### Final design (implemented)

- Per-platform `liveTextSelector` in `selectors/<platform>.json`; ChatGPT and
  Claude only. Read-only `/draft-snapshot` route in `control_plane.js` →
  `content.js` `draftSnapshot()`; no new permission, no network reading.
- `session.py` takes a baseline before `/start`, then polls once per second
  only while `state == "recording"` (one HTTP round-trip/s, no observer, no
  idle cost), keeping the longest cumulative text in RAM. Interim chips are
  ignored; a replaced composer rebases the baseline instead of capturing
  someone else's text.
- Browser/profile death or bridge drop mid-cycle: re-read the page once if it
  answers, else use the last RAM snapshot; deliver through the existing
  `deliver_transcription` (clipboard + validated paste target + History) with
  `method="recovered (partial)"`; one critical notice with word count only.
  No snapshot text is logged or written to a file. Esc and successful final
  stop clear it; the final stop text always wins; a cycle can be recovered at
  most once.
- Privacy: snapshot lives in process memory for the cycle lifetime only;
  logs carry word/char counts; History row is user-visible data, not a debug
  artifact; no second storage root, no new permission.
- Regression guards: page-ready gate/verified click unchanged, stop scrape and
  clipboard flow unchanged, `tests/plugins/test_partial_recovery.py` covers
  tab close, profile kill, bridge drop, no speech, Esc, normal stop and
  no-disk leakage; `test_critical_notices.py` still pins one OS + one in-app
  notice; `test_dev_fake_audio_harness.py` pins harness gating and that the
  production launcher and packaging scripts contain no fake-audio flags.

## 2026-11-27 follow-up — Claude hidden span, stale drafts, quiet polling

### Claude hidden-span capture (root cause of "recovery does not save")

Live Claude dictation DOM (real app, fake-audio harness, dir=ltr here):
`<div data-testid="chat-input" contenteditable="false" aria-readonly="true"><p dir="auto"><span data-dictation=""><span data-dictation-words="hidden" class="hidden">TEXT</span></span><span data-dictation-words="end" contenteditable="false" class="ProseMirror-widget"></span><img class="ProseMirror-separator"><br></p></div>`
Measured once per second while a real dictation ran:

| extraction | result |
|---|---|
| outer `innerText` | `"\n"` (truthy, empty after trim) |
| outer `textContent` | grows 17 → 32 → 54 → 69 chars, cumulative |
| `span[data-dictation]` `innerText` | `""` |
| `span[data-dictation]` `textContent` | same cumulative text |
| `span[data-dictation-words="hidden"]` `textContent` | same cumulative text |
| `span[data-dictation-words="end"]` | empty |
| `selectors/claude.json` old `liveTextSelector` + `innerText` | empty → daemon `/draft-snapshot` returned `{"text":"","source":"none"}` |

Root cause: `content.js:244-260` (commit `349326d99`) read `box.innerText || box.textContent`; Claude’s outer box returns a newline for `innerText`, so `textContent` was never used; the fallback `composerText()` requires `contenteditable="true"` and finds nothing while Claude is read-only. Earlier capture (31→569 chars) worked because the composer was still editable and text lived in a normal paragraph; the later redesign moved live text into hidden spans. Fix: `selectors/claude.json` declares `liveText` = `span[data-dictation-words]` + `textContent` + DOM-order concatenation; no `dir` attribute is used (tests cover rtl, ltr and absent, English/Arabic/mixed/emoji/long). ChatGPT keeps its verified extraction unchanged.

### Stale-draft investigation (hypothesis B proven)

Real order with a typed 21-word draft before start (Claude, `20:15:10`):
`start requested` → `draft snapshot read (21 words, source=live-selector)` → `recording started` → browser-lost with no usable snapshot. ChatGPT with a persisted 50-word draft (`20:16:43`): first read saw 50 words before `recording started` (`20:16:46`), then reads saw 7→9→13→17 dictated words and recovery delivered 17 words — no old text. Code order: `session.py:800` baseline read happens before `/start` (`:814`); `content.js:550` `ensureCleanComposer()` clears before the verified click (`:580`); watcher starts after `recording started` (`session.py:871`). Hypothesis B (a pre-clear read) is real, but the baseline gate means old text never enters the recovered partial. Decision: no baseline correctness code added; the pre-start read is now silent so the log cannot be misread.

### Quiet polling decision (measured)

MutationObserver attached to the live composer fired 1 mutation for an inserted phrase and 0 during 5 s of silence; 1 Hz polling does 5 reads in the same silence. Observer would need a new page→Python event channel (no such wire exists), so the chosen policy is adaptive polling: 1 s while text changes, 3 s after 3 unchanged reads, back to 1 s on change (30 s silence: ~10 reads instead of 30). Status polling stays 1 s for death detection. Logs are DEBUG only, counts only, at most one line per 5 s per kind; one `draft snapshot summary (cycle=#N): reads=R, changes=C, final=W words` per cycle. Item 4: the watcher never starts before `recording started`; refused/cancelled cycles cannot leak a snapshot (tests pin this).
