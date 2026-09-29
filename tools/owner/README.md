# tools/owner — private owner experiments. NEVER SHIP.

Gate: `VOICE_TYPER_OWNER_TOOLS=1` + `tools/owner/OWNER_ENABLED` + never frozen.
`OWNER_ENABLED` is gitignored; create it deliberately, never commit it.

## gemini_stt (plan: docs/plan-owner-gemini-web-stt.md)

Burner Gmail only. Ban risk sits on that account. Automating the Gemini
web UI is a ToS gray area — personal experiment, never in a release
(P0 incident if it ships).

Reset profile: close Chrome, delete
`%LOCALAPPDATA%/voice-typer-owner/gemini-profile`, rerun `login.js`,
log in again. Selector fix after a Google redesign: edit
`gemini_stt/selectors.json` only (data fix, no code rewrite).
