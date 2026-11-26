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
