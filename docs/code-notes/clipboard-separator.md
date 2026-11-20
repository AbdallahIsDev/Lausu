# Delivery formatting: block-scoped caret reads

`voice_typer/server/clipboard_target_safety/caret_text.py` exposes one entry
point, `delivery_text_for_target(text, *, auto_capitalize=True)`, used by both
the local paste step and the plugin delivery helper. It applies two
delivery-only decisions from ONE caret verdict: the separator space and the
first-letter case. The clipboard copy and paste keystroke carry both; the
transcript, history row, crash-recovery entry, `_last_transcription` and
`transcription_final` stay byte-identical (C-TRANS-2).

## Rule table

| Prefix verdict | Case | Separator | Reason |
|---|---|---|---|
| `empty` (empty field, caret at position 0 with text after, invisible-only) | first letter UPPERCASE (gated by `config.auto_capitalize`) | none | `empty-field` / `auto-capitalize-off` |
| `needs-space` (prefix ends in normal text) | first letter lowercase (always) | one leading space | `has-content` |
| `trailing-space` (prefix ends in whitespace) | first letter lowercase (always) | none | `has-content` |
| `unknown` / unreadable / page-scoped | text untouched | none | `unknown` |
| any verdict, uncased first letter or leading URL | text untouched (case) | separator rule still applies | `caseless` |

Only the first eligible letter changes: scan for `ch.isalpha()` (skipping
leading quotes/brackets/spaces, and honouring the leading-URL guard from
`ai_enhancement`), then apply `ch.upper()`/`ch.lower()` to that one character.
`capitalize()`/`title()` are forbidden — they lowercase the rest and destroy
`iPhone`/`USA`. A character that is neither `islower()` nor `isupper()` has no
case in Unicode (Arabic/Chinese/Hindi/Hebrew, digits) and is left alone.
Lowercase is a correctness rule for an existing field; only the capitalize
direction respects the user's `auto_capitalize` setting.

`str.isspace()` is `False` for the four invisible characters (U+200B, U+FEFF,
U+2060, U+00AD), so they are stripped explicitly before classifying. The safe
default is always "no changes": a space or case edit we cannot justify is worse
than two words touching.

## Page-scoped vs block-scoped read

The trap: Chromium's window-level `DocumentRange` is the **whole page**, not
the focused composer. On OpenCode its text begins
`Home\nSearch sessions\nNew session\n...` (4003 chars). Reading the character
before the caret from that range reads page chrome and injects a space into an
empty composer. Even scoped to a small range, an empty Electron composer
exposes a zero-width marker (U+200B) rather than `""`, which the old
single-character path treated as real text.

The fix clones the caret range, expands with
`ExpandToEnclosingUnit(TextUnit_Paragraph)` (fallback `TextUnit_Line`), and
takes only the text **before** the caret start via
`MoveEndpointByRange(End, caret, Start)`, capped at 256 chars. A block that
matches the document's endpoints — or is implausibly large — is UNKNOWN.

The caret read logs one DEBUG line with the answering element's ControlType
and ClassName, the raw prefix as hex codepoints (max 8), all three scope
lengths, and a one-word verdict. Formatting logs one further DEBUG line with
the same prefix verdict, the case verdict (`upper`/`lower`/`unchanged`), the
reason, text length and hex codepoints. User text is never logged.

## Electron / accessibility limitation

Chromium enables its accessibility tree only after detecting an assistive
client (`NotifyWinEvent(EVENT_SYSTEM_ALERT, ..., OBJID_CUSTOM)` answered by a
`WM_GETOBJECT`), and Electron gates its support on
`app.setAccessibilitySupportEnabled`. With AX off, only the window-level
document is reachable; a plain `<input>` uses ValuePattern and is unaffected.
That is why the bug reproduced in Electron but not in Chrome or our Tauri
search box. The AX handshake is deliberately **not** implemented here.
