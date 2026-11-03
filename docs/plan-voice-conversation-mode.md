# Voice conversation mode — missing pieces and implementation plan

**Status:** Planning only — no code exists for this feature.
**Date:** 2026-11-03
**Related:** [ADR-0027](adr/0027-voice-only-loop-cua-deferred.md) (voice-only loop, proposed),
[plan-model-providers-local-and-hosted.md](plan-model-providers-local-and-hosted.md) (provider registry).

## 1. Verdict

The app cannot hold a conversation today. It has all three ingredients — speech-to-text,
a provider-agnostic LLM client, and text-to-speech that accepts arbitrary text — but nothing
connects them, and there is no chat surface, command, event, or conversation state.

ADR-0027 ("STT → LLM → TTS") is marked *Proposed, no code yet*, and that is still accurate:
a repo-wide search for `chat_send`, `chat_state`, `chat_message`, or a conversation manager
returns **zero** matches.

## 2. What already exists (verified)

| Capability | Evidence | Notes |
|---|---|---|
| Speech → text | `server/dictation_pipeline/__init__.py:46` (`DictationPipeline`), `server/dictation_stages.py` (`build_default_stages`) | Hotkey → record → transcribe → clean → paste. Single-shot, single-flight. |
| Standalone buffer transcription | `server/service/microphone_test.py:14` (`_transcribe_with_engine`) | Precedent for "transcribe audio without the dictation/paste pipeline". |
| LLM contract | `server/model_providers/contracts/llm.py` (`ChatMessage`, `LlmClient.complete/stream`) | Messages in, text out; `stream` always available. |
| LLM resolution | `server/model_providers/routing.py:205` (`resolve_llm`) | Call-time resolution, typed `ProviderError` failures, consent + auth checks. |
| LLM providers | `server/model_providers/builtin.py:229-330` | `local_onnx`, `ollama`, `lmstudio`, `openrouter`, `cloud_direct` all serve the LLM domain. |
| LLM config | `server/config/_schema.py:179-182` | `llm_provider`, `llm_model_id`, `llm_provider_consent`, `llm_provider_fallback` already exist. |
| LLM consumer | `server/dictation_pipeline/enhancement_steps.py:217` (`_apply_llm_polish`) | The ONLY caller today; polish, not chat. |
| Text → speech | `server/tts/manager.py:270` (`speak`), `server/service/tts.py:43`, `server/handlers/tts_handlers.py:89` | `tts_speak` accepts arbitrary `text` (non-sample path), plays asynchronously, returns immediately. |
| Playback control | `tts_stop` command, `tts_playback_state` event | Stop glyph + natural-end reporting already work. |
| TTS master switch | `server/config/_schema.py:93-95`, `server/tts/prewarm.py:29` | `tts_enabled` gates runtime start. |
| Chat UI | `client/src/renderer/src/pages/` has no `Chat` page or panel | Nothing renders a conversation. |
| Chat IPC | `server/ipc/registry.py:214-226` lists only `tts_*` and `provider_*` | No `chat_*` command in either allowlist. |

## 3. Missing pieces

Each item is required for a working conversation mode. "Done when" is the acceptance test.

### M1 — Conversation state and turn manager
No object owns messages, role alternation, or history. **Done when** a manager holds
`[system, user, assistant, …]`, caps the window by turn count and token estimate, can
`reset()`, and is safe against two concurrent turns.

### M2 — LLM chat call path
`resolve_llm()` has no chat consumer. **Done when** the manager builds `ChatMessage`s,
calls `client.complete(...)`, maps every `ProviderError` to a stable code, and works with
`local_onnx`, `ollama`, `lmstudio`, `openrouter`, and `cloud_direct` without branching on
provider identity.

### M3 — Reply-to-speech wiring
Nothing sends the assistant text to TTS. **Done when** a reply is spoken through the
active engine (`tts_speak`), respects `tts_enabled`, survives a TTS failure by keeping the
text visible, and never blocks the turn while audio plays.

### M4 — Chat IPC commands and events
No command or event exists. **Done when** the new commands are in **both** allowlists
(`server/ipc/registry.py` and `src-tauri/src/commands/sidecar_cmds/allowlist.rs`), have rate
costs and matching TS request/event types, and the parity tests pass. No third allowlist.

### M5 — Chat surface (renderer)
No page, transcript, mic control, or speaking state. **Done when** a surface lists turns,
offers push-to-talk (start/stop), shows transcribing / thinking / speaking states, a stop
control for speech, and a reset action.

### M6 — Config and validators
No chat settings. **Done when** `chat_enabled`, `chat_history_turns`, `chat_max_reply_tokens`,
and `chat_system_prompt` are in `Config`, the SEC-002 allowlist, the TS config type, and the
parity test, with safe clamping (history 1–50, tokens 32–1024).

### M7 — Turn-taking and echo policy
Nothing coordinates mic vs speakers. **Done when** v1 is explicitly **half-duplex**:
starting a turn stops any playing clip, the mic control is disabled while speaking, and the
state machine cannot record and speak at once. Full-duplex/barge-in is out of scope (needs
AEC).

### M8 — Error, consent, and privacy handling
No chat-specific failure UX. **Done when** consent-required opens the shared just-in-time
gate (`openConsentGate`, C-MIC-3), auth-required points at Settings → Providers, a provider
outage keeps the transcript and offers retry, and no partial/streamed LLM text is spoken.

### M9 — Reply shaping for speech
Nothing constrains replies to speakable text. **Done when** the default system prompt asks
for 1–3 short spoken sentences with no markdown/lists/URLs, `chat_max_reply_tokens` caps
length, and a markdown-stripping pass runs before TTS (TTS reads `**` literally).

### M10 — i18n
No chat strings. **Done when** every new key exists in all 8 locales (`en/zh/hi/es/ar/fr/ru/de`)
and the locale parity test passes.

### M11 — Logging and observability
No chat logging contract. **Done when** each turn logs one start line and one outcome line
(`completed` / `cancelled` / `failed` with the error code) with the C-LOG-2 duration suffix,
and no per-frame/IPC wire traces are added.

### M12 — Tests and documentation
No coverage and no IPC reference entries. **Done when** backend manager tests use fake
LLM/TTS clients (no network, no real audio), renderer tests use `renderApp()`, IPC parity
tests pass, and `docs/ipc-reference.md`, `docs/code-notes/event-catalogue.md`,
`docs/ARCHITECTURE.md` counts, and ADR-0027's status are updated.

## 4. Minimal v1 design

Push-to-talk, half-duplex, non-streaming. No wake word, no VAD endpointing, no barge-in.

```
[mic button / hold-to-talk]
        │
        ▼
 record (existing recorder + device-health path)
        │
        ▼
 transcribe once (engine path, NOT the paste pipeline)
        │
        ▼
 messages += user text
        │
        ▼
 resolve_llm(config) → client.complete(messages, max_tokens=chat_max_reply_tokens)
        │
        ├──► chat_message push (text rendered in the transcript)
        │
        ▼
 tts_speak(reply)  (fires and returns; playback is async)
        │
        ▼
 idle → next turn
```

**Turn states:** `idle → listening → transcribing → thinking → speaking → idle`, plus
`cancelled` and `error`. Only one turn may be active; a second start request is refused
(C-CONC-1 single-flight). `cancel` stops capture, aborts the LLM call via `abort_event`, and
calls `tts_stop`.

**Two implementation options for capture** (pick one at implementation time):

1. **Dedicated chat commands** (`chat_turn_start` / `chat_turn_stop`) driving the existing
   recorder and the `microphone_test._transcribe_with_engine` seam. Keeps dictation and chat
   pipelines isolated; no change to `DictationPipeline`.
2. **Pipeline mode** — run `DictationPipeline` with a chat stage that replaces
   `PasteStage`/`StoreResultStage`. Reuses more code, but touches the single-flight dictation
   invariants and the paste contract.

Option 1 is recommended for v1: smaller blast radius, and dictation keeps its current
guarantees (C-TRANS-1, C-PASTE-1).

## 5. Proposed IPC surface

| Command / event | Payload | Notes |
|---|---|---|
| `chat_status` | `{}` | Returns `{ enabled, provider, model, state, turns }`; read-only. |
| `chat_turn_start` | `{}` | Starts capture; refuses unless state is `idle`. |
| `chat_turn_stop` | `{}` | Ends capture, queues the turn, returns `{ turn_id }`. |
| `chat_cancel` | `{}` | Stops capture/LLM/TTS for the current turn. |
| `chat_reset` | `{}` | Clears history; keeps the system prompt. |
| `chat_state` (push) | `{ state, turn_id? }` | One event per state transition. |
| `chat_message` (push) | `{ turn_id, role, text, duration_s? }` | Fires for the user turn and the assistant reply. |
| `chat_error` (push) | `{ code, turn_id }` | Codes map to plain-language copy; raw detail stays in the log. |

Wiring checklist for every command/event: `registry.py`, `allowlist.rs`,
`rate_limiter.COMMAND_COSTS`, `types/ipc/requests.ts`, `types/ipc/push_events.ts`,
`lib/python-bridge/known-event-types.ts`, `tests/test_ipc_command_parity.py`, and
`docs/ipc-reference.md`.

## 6. Config additions

| Field | Type / default | Validation |
|---|---|---|
| `chat_enabled` | `bool = False` | master switch for the surface |
| `chat_history_turns` | `int = 8` | clamp 1–50 |
| `chat_max_reply_tokens` | `int = 200` | clamp 32–1024 |
| `chat_system_prompt` | `str = ""` | empty → built-in spoken-reply prompt |

Reuse `llm_provider`, `llm_model_id`, `llm_provider_consent`; do not add a second provider
selection. `chat_enabled` with no usable provider is a warning, not a hard error.

## 7. UI surface

- New sidebar entry **Chat** (`pages/chat/Chat.tsx`), nav-only sidebar rules still apply.
- Transcript list: user text + assistant text, newest at the bottom; no partial text while
  recording (C-TRANS-1).
- Primary control: push-to-talk button (press to start, press again to stop) with explicit
  `listening` / `transcribing` / `thinking` / `speaking` states; `tts_stop` while speaking.
- Empty state names the missing prerequisite ("Select an LLM provider in Settings") instead
  of a generic failure.
- Loading uses the page's own skeleton (C-SKELETON-1); no conditional removal of actions
  (C-CACHE-6).

## 8. Turn-taking and audio rules

- Half-duplex v1: `chat_turn_start` calls `tts_stop` first and is disabled while `speaking`.
- The mic indicator is expected to light while listening; this is a user-initiated action,
  so C-BG-1 is not implicated (no hidden/autostart listening).
- Never record while speaking and never speak while recording. Full-duplex/barge-in needs
  echo cancellation and is a separate project.

## 9. Errors, consent, privacy

- `ProviderConsentRequiredError` → `openConsentGate()` at turn start, then retry the turn.
- `ProviderAuthRequiredError` → inline "Add an API key" action opening Settings → Providers.
- `ProviderUnavailable` / runtime errors → toast with retry; the user turn stays in the
  transcript.
- Local providers (`ollama` on loopback, `lmstudio`, `local_onnx`) make no network call;
  remote providers remain behind the existing consent gate (C-DATA-1).
- TTS failure is non-fatal: text is shown, a "spoken reply unavailable" line appears, and
  the failure code is logged.

## 10. Logging

One line per turn at INFO (`[CHAT] turn started provider=… model=…`) and one outcome line
(`[CHAT] turn completed turn=… chars=… 1.2s` / `failed code=…` / `cancelled`), using the
shared C-LOG-2 duration format. No token-by-token or per-IPC traces (C-LOG-3).

## 11. Tests

- `tests/chat/` — manager: history cap, reset, single-flight refusal, provider error mapping,
  consent path, TTS failure keeps text, abort/cancel. Fake LLM + fake TTS only.
- IPC: registry/allowlist parity, command costs, request/event type coverage.
- Renderer: `pages/chat/__tests__/` with `renderApp()` and mocked bridge — state transitions,
  send/receive rendering, stop, error copy, disabled states.
- i18n: locale key parity (automatic once keys are added).
- No real audio device, network, or model load in unit tests (E6, C-TEST-8).

## 12. Docs to update when implemented

- `docs/ipc-reference.md` — command/event rows.
- `docs/code-notes/event-catalogue.md` — new push events.
- `docs/ARCHITECTURE.md` — command/event count note.
- `docs/adr/0027-voice-only-loop-cua-deferred.md` + `docs/adr/README.md` — status to
  Implemented (or Partially implemented) with the shipped scope.
- `worklog.md` — closure entry with commands and counts.

## 13. Implementation order

1. Config fields + validators + TS config parity.
2. `ConversationManager` + fake-client tests.
3. Chat IPC commands/events + both allowlists + rate costs + parity tests.
4. Renderer page + bridge types + tests.
5. TTS reply wiring + half-duplex policy + cancellation.
6. Locale keys, docs, logging, end-to-end manual pass.

## 14. Decisions needed before implementation

1. **Brain default:** local ONNX (offline, CPU-bound) vs Ollama/LM Studio (fast, user runs a
   server) vs OpenRouter (best quality, data leaves the device). The registry supports all.
2. **Surface:** dedicated Chat page vs a panel inside Home vs bubble-only.
3. **Input model:** push-to-talk only (v1) vs also route the existing dictation hotkey into
   chat when the Chat page is active.
4. **Persistence:** in-memory history only, or persist turns in History (new column/table).
5. **Streaming:** keep v1 non-streaming (recommended, avoids speaking partial text) or stream
   assistant deltas to the UI.

## 15. Out of scope for v1

- Wake word / always-listening.
- VAD endpointing and hands-free turn detection.
- Barge-in / full-duplex (echo cancellation).
- Tool use, desktop control, or the CUA phase from ADR-0027.
- Cloud fallback chains beyond the existing `llm_provider_fallback` semantics.

## 16. Acceptance criteria

- A user selects an LLM provider, opens Chat, speaks a question, sees their text, sees the
  reply, and hears it — then asks a follow-up that correctly references the previous turn.
- Stopping speech works; cancelling a turn leaves no partial reply and no stuck state.
- With `tts_enabled` off, replies are text-only and never start a TTS runtime.
- Provider consent/auth failures produce plain-language copy and a recovery action.
- Full test batches for touched areas, `typecheck:ci`, `format:check`, and `lint` are green;
  both IPC allowlists stay in lockstep.

## References

- `docs/adr/0027-voice-only-loop-cua-deferred.md`
- `docs/plan-model-providers-local-and-hosted.md`
- `voice_typer/server/model_providers/contracts/llm.py`
- `voice_typer/server/model_providers/routing.py`
- `voice_typer/server/tts/manager.py`, `voice_typer/server/service/tts.py`
- `voice_typer/server/ipc/registry.py`, `src-tauri/src/commands/sidecar_cmds/allowlist.rs`
- AGENTS.md: `C-CONC-1`, `C-TRANS-1`, `C-DATA-1`, `C-BG-1`, `C-MIC-3`, `E9`, `E13`
