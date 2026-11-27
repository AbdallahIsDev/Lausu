# Dictation Gate Log Color — Short Design

**Intent:** Give the `[DICTATION-GATE]` terminal log label its own ANSI color so gate decisions are easy to spot among plugin and dictation lines. Owner approved teal `38;5;80`.

**Goals:** INFO and DEBUG lines starting with `[DICTATION-GATE]` render in teal in the terminal.

**Non-goals:** No change to the line template, message text, log levels, file logs, or renderer UI. WARN/ERROR stay full-line yellow/red (level color wins by design). No behavior change to the gate itself.

**Constraints:** C-LOG-1 — ANSI only in terminal wrappers; stripped text must match the template byte-for-byte; no ANSI in files. Python `_TOPIC_COLOR` and Rust `TOPIC_COLOR` must stay identical (parity test enforces this). `NO_COLOR` > `FORCE_COLOR` > isatty remains unchanged. No new dependencies.

**Approaches:** (1) Add a topic entry to both palettes — one line each, uses existing extraction, parity test protects drift. Recommended. (2) Special-case the label in the formatter — duplicates topic logic and bypasses the parity test; rejected. (3) Add a JS constant — the dev orchestrator uses named constants, not topic lookups, so it would not affect this label; rejected.

**Design:** Add `"DICTATION-GATE": "38;5;80"` after `"DICTATION"` in `voice_typer/server/log/formatters.py` and `("DICTATION-GATE", "38;5;80")` after the matching entry in `src-tauri/src/platform/logging/color.rs`. Add one Python test pinning the code and an INFO render. Existing Rust parity test covers the cross-language contract.
