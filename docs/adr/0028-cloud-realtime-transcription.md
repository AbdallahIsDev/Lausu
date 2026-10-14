# ADR-0028: Cloud realtime transcription (end-only delivery)

## Status

Proposed (2026-10-13). Living record — update in place as follow-up discussions land. Supplements `docs/cloud-asr-batch-vs-realtime.md` (open decision, 2026-10-12) and pins `C-TRANS-1`.

**Implementation status 2026-10-14:** SHIPPED for OpenAI (burst-append WS transport + selectable rows + hook/panel un-guard). `gemini-3.5-transcribe-live` stays guard-only (different protocol). Live mic feed deliberately not built (C-TRANS-1 makes it UX-neutral; see §2). Not yet live-verified against the real API (no key in this environment) — first real-key dictation should confirm handshake + turnaround, then this line can claim it.

## Context

The cloud catalogue serves **batch** models only. Dictation is record → stop → one request with a finished file:

- OpenAI / Groq `POST .../v1/audio/transcriptions` (multipart, whole file)
- Deepgram `POST .../v1/listen` (pre-recorded batch)
- Gemini `POST .../models/{model}:generateContent` (unary, base64 inline)

Two OpenAI models the user asked for are realtime-only and deliberately absent from selectable `CLOUD_PROVIDERS` rows (listed as disabled Realtime-only guard rows since 2026-10-13): `gpt-live-transcribe` (realtime transcription workflow) and `gpt-realtime-whisper` (Realtime API session model). Same rule already pins `gemini-3.5-transcribe-live` (Live API) and Deepgram Flux (streaming voice-agent) out. `models-cloud-catalogue.test.ts` pins these guards as deliberately brittle.

Listing a realtime id as a normal selectable row would save to config, render Active, then fail the next dictation at the batch endpoint with no transcript — a lying control.

Global UX rule since 2026-10-13 (`C-TRANS-1`, AGENTS.md): regardless of transport (one-shot POST, chunked upload, local hidden streaming, realtime WS), the transcript is delivered **once, at the end**, after the stop trigger. A realtime backend that already holds the text buffers it and releases at stop. Never live partials. Rationale: live text distracts while dictating; one delivery keeps backends interchangeable.

Recording modes (both must work): toggle (press to start, press again to stop; default) and hold-to-talk (hold down, release to stop; opt-in). Both define the same recording window; only the stop signal differs.

Verified 2026-10-13 against OpenAI docs (Firecrawl search, golden rule): transport chunking is **client-side**. The provider owns noise filtering, VAD, word segmentation and delta text; the client owns framing mic audio into WS messages:

- `Stream audio — Send audio chunks with input_audio_buffer.append { audio: base64Pcm16 }`, then `input_audio_buffer.commit` (`developers.openai.com/api/docs/guides/realtime-transcription`).
- `For best realtime behavior, append audio in 200 ms chunks. If a chunk is shorter, the server buffers it until it has enough audio for one frame.` WebSocket sessions accept base64 24 kHz PCM16 mono in 200 ms chunks (API reference).
- Community samples all loop `for i in range(0, len(audio), frames_per_packet): send append`, then `commit`.

There is no "send one raw file" call on the realtime path. An empty append loop means an empty session at stop. Double-chunking is not a risk: local `chunk_seconds` windowing is for local inference and is not reused here; short WS frames are server-buffered by contract.

Current code that is **not** the realtime path: `_StreamingMultipartBody` 64 KB HTTP body chunks and `_read_capped` (memory caps on one-shot POST), `microphone_test_read_audio` ≤256 KiB IPC slices (frame-cap workaround, C-MIC-17/21), `StreamingTranscriptionSession` / worker streaming (local-only live preview), `InputStream` level monitor (capture, not transcription). `CloudEngine.transcribe(audio: np.ndarray)` takes the full array and POSTs once (`cloud/_engine.py`).

## Decision

### 1. Catalogue guard (Option 1, cheapest honest step)

SHIPPED 2026-10-13 (all three ids), then narrowed 2026-10-14: the two OpenAI rows are selectable now that §2 ships; `gemini-3.5-transcribe-live` keeps the disabled marker until its protocol lands. Mechanics unchanged: `realtimeOnly?: true` on `CloudModel`, non-interactive state in `CloudModelRow`, hook refusal as defence in depth, strings in all 8 locales. New `realtimeWs?: true` distinguishes app-streamable rows (`isRealtimeWsSupported`); parity test pins both sets cross-language against `REALTIME_MODELS` / `WS_REALTIME_MODELS`.

### 2. Realtime transport (Option 2, backend-only per C-TRANS-1)

SHIPPED 2026-10-14 for OpenAI (`gpt-live-transcribe`, `gpt-realtime-whisper`) as **burst-append at stop** — no live mic feed, no live UI. Rationale: under C-TRANS-1 the transcript releases at stop either way, so streaming during the window buys nothing and costs recorder/pipeline surgery. The WS session carries the finished recording: open at stop, append all ~200 ms frames back-to-back (the documented file-loop pattern), commit, await completed.

- As-built: `cloud/_realtime.py` (capability sets, official envelopes, PCM16/24 kHz framing, delta assembler) + `cloud/_realtime_ws.py` (WS IO only, `websockets` dep already hard-pinned). `CloudEngine._send_request` routes per model; batch paths untouched.
- Official protocol (developers.openai.com realtime-transcription, verified 2026-10-14): `wss://api.openai.com/v1/realtime?intent=transcription` + `Bearer`/`OpenAI-Beta` headers; `session.update` with `audio/pcm` 24 kHz + `turn_detection: null` (no `server_vad` on this model); deltas buffered, first `transcription.completed` wins.
- Deliberate omissions: `prompt`/`keywords`/`languages`/`delay` unset (server defaults; avoids rejecting locale codes) — product may add `delay` + vocabulary hints later.
- Guards: official-host-only (custom `api_url` hosts refused — no SSRF surface); 15 MB PCM input cap (~9 min, client-side; server buffer limit unverified) with local fallback; 120 s overall deadline + 15 s handshake timeout + bounded join (abort-latency contract kept); 1 MiB inbound cap; typed errors (auth/network/empty) feeding the existing cloud→local fallback; no per-frame logs (C-LOG-3).

### 3. Non-option

Option 3 (selectable rows without the transport) stays rejected — it reproduces the lying control.

## Consequences

Positive: catalogue stays honest; realtime becomes a bounded backend feature with no UX fork (C-TRANS-1); toggle and hold modes share one window abstraction.

Negative: new WS transport + lifecycle + resample + abort/retry/fallback surface; new tests (framing, commit-at-stop both modes, delta buffering, no-partial-render pin); provider per-minute WS cost vs one POST.

Neutral: batch POST path unchanged; local hidden streaming unchanged; `defaultModel` parity (`models.ts` ↔ `_defaults.py`), exclusion-guard tests, and stale-`cloud_model` no-migration behaviour (see `cloud-asr-batch-vs-realtime.md` "must not break") all still hold.

## Open questions (fill as decided)

- ~~Which provider first?~~ Decided 2026-10-14: OpenAI. Gemini Live / Deepgram streaming later (separate protocols).
- ~~`delay` default?~~ Deferred: field omitted (server default) until a product decision funds tuning + eval.
- ~~WS timeout budget?~~ Shipped: 120 s overall + 15 s handshake + bounded join (abort-latency contract kept).
- ~~Fallback on WS drop?~~ Decided: typed error → existing cloud→local fallback (no silent batch re-POST; the batch endpoint rejects these ids anyway).
- Server input-buffer limit (the 15 MB client cap is a stand-in) — verify against real API behavior on a long recording.
- `prompt`/`keywords`/`languages` hints (vocabulary context) — add when a real-key eval shows the need.
- Live mic feed during the window — only if burst turnaround ever proves too slow (C-TRANS-1 keeps it UX-neutral).

## Competitor evidence (2026-10-13, 8 projects, Firecrawl primary)

Convergence: **end-only delivery with optional live preview, realtime gated on model capability, client frames PCM16, same prefs both paths.** Validates C-TRANS-1 and the §2 backend-only scope.

- **Freestyle** (`freestyle-voice/freestyle`, MIT) — direct template. Cloud v2 has both: batch `POST /v2/transcribe` (multipart) + streaming WS `/v2/stream` (PR #387 `supportsStreaming()`). Client proxies binary PCM16 16 kHz mono frames live; `start` carries prefs, `commit` carries context + `audioDurationMs`; partials stream back but UX is hold/release → paste at end (`Hold a hotkey, speak, and release to paste`). Same prefs schema both paths, no server-side pref storage, `skipPostProcess` per request. Copy: dual-path one API version, PCM16 frame contract, start/commit envelope. Avoid: Durable-Object statefulness, cloud LLM cleanup bundled into transcription, usage-limit UX.
- **Superwhisper** (closed) — batch default (`Stop: ends recording and starts processing`); realtime opt-in per-mode, Pro-gated, only streaming-capable models (Nova 3/2/Medical, Scribe, Parakeet local; Cohere/Whisper toggle grayed out). With realtime on, window shows words as spoken; delivery still once at end. Toggle + push-to-talk both (`quick tap acts as toggle`). Transport undisclosed (suspected WS/POST split). Copy: per-mode realtime toggle gated on capability with graceful degrade to end-only. Avoid: paywalled realtime, model-matrix complexity.
- **Dictate** (`siddhantparadox/dictate`, Electrobun + Python sidecar) — batch everywhere, end-only, closest structural analog. `MicrophoneCaptureSession` buffers callback frames, `transcribe_without_streaming` at release; cloud is 4× one-shot POST (Groq multipart, Deepgram prerecorded `/v1/listen`, AssemblyAI upload→poll 750 ms/90 s, OpenRouter base64 chat). Live signal is RMS meter only. Copy: per-provider modules with shared `{text, latencyMs}` return, file-ref WAV handoff (cf. C-MIC-17), poll-with-deadline for async providers. Avoid: chat-completion transcription (paraphrase risk), 90 s poll as default, 45 s cap.
- **Handy** (`cjpais/Handy`, Tauri+Rust, offline) — end-only batch: hold/tap-toggle → full buffer → Silero VAD trim → whisper.cpp/Parakeet → paste once. No cloud, no partials (live streaming is a proposal only, discussion #1012). Best hold/toggle arbitration: `PendingRelease` 50 ms grace vs X11 auto-repeat, `PendingPress` busy queue, `hold_threshold`, hold-only/toggle-only modes. Copy: state machine + release grace + mic-state-only feedback. Avoid: clipboard-restore paste race (#502).
- **OpenASR** (`openasr.org`) — local-first, no cloud. `transcribe` (batch, end-only) vs `live` (final-per-utterance default, streaming-partial only for packs that declare it) vs `serve` (local POST). One Zipformer2 checkpoint serves streaming + offline. Hold-to-talk. Copy: final-per-utterance default with capability-declared partials — maps to C-TRANS-1.
- **MacParakeet** (`moona3k/macparakeet`, local) — live preview default (dictation tail-window preview, meeting preview, web tool `Show interim words` toggle, interim→final confirm). Batch-only Cohere is the exception (no preview, no word timestamps). Hold + tap-toggle both. Tension with C-TRANS-1 (they chose live); the toggle-OFF state (finals preserved for export) is the C-TRANS-1 shape. Do not copy live-default or engine-dependent UX split.
- **FluidVoice** (`altic-dev/FluidVoice`, local) — live overlay optional/minimal (pill→large, all optional), streaming-capable vs offline model table, hold-Space-to-mute inside toggle session. No cloud lessons.
- **Graphify-Labs/graphify** — out of scope (knowledge-graph CLI/skill, no audio/ASR).

## References

- `docs/cloud-asr-batch-vs-realtime.md` — batch vs realtime evidence, catalogue tables, three options.
- OpenAI Transcription workflow guide + Realtime transcription guide (fetched 2026-10-12/13): file-vs-realtime split, session shape, delta events.
- OpenAI API reference: 200 ms base64 PCM16 guidance.
- `C-TRANS-1` (AGENTS.md), `C-DATA-1`, `C-MIC-17/21`, `C-HOME-2` (no preview surface).
- `voice_typer/server/cloud/_engine.py`, `_transport.py`, `_sendpaths.py`; `streaming_session_coordinator.py`; `worker_streaming.py`.
