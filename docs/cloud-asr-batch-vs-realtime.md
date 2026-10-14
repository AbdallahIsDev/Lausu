# Cloud ASR: batch models vs realtime models

**Status: RESOLVED for OpenAI 2026-10-14 (WS burst-append transport shipped, rows selectable);
GUARD-ONLY for Gemini Live (disabled marker until its protocol lands).** Lausu's cloud catalogue serves
**batch** models plus the two streamed OpenAI models. Two OpenAI models the user asked for are **realtime-only** and are
therefore served over a WS session instead of the batch endpoint. This document records the evidence, the
reason, and the three ways to change it — so the remaining decision can be made later without
re-doing the research. The shipped guard and transport are recorded in
[`adr/0028-cloud-realtime-transcription.md`](adr/0028-cloud-realtime-transcription.md).

Read this before adding **any** cloud model to
[`lib/utils/cloudCatalog.ts`](../voice_typer/client/src/renderer/src/lib/utils/cloudCatalog.ts).

---

## The short version (updated 2026-10-14)

Lausu sends a **finished audio file** to a provider and gets text back — except the two
OpenAI realtime models, which go over a **WebSocket session carrying that same finished
recording** (burst-append at stop, then commit; see ADR-0028 §2). Every other cloud model
in the catalogue uses the one-shot call. A model that only exists inside a **live streaming
session** and has no transport here (Gemini Live) still gets a disabled marker, never a
Select button — a control that looks usable and is not would fail on the next dictation.

---

## What the app does today

Dictation is *record → stop → one request*. The audio is complete before it is uploaded:

| Provider | Endpoint the catalogue points at | Shape |
|----------|----------------------------------|-------|
| OpenAI | `POST https://api.openai.com/v1/audio/transcriptions` | multipart, whole file |
| Groq | `POST https://api.groq.com/openai/v1/audio/transcriptions` | multipart, whole file |
| Deepgram | `POST https://api.deepgram.com/v1/listen` | pre-recorded (batch) |
| Google Gemini | `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | unary, base64 audio inline |

All four are "here is my finished recording, give me the transcript" calls, and the two
OpenAI realtime rows reuse the same finished recording through the WS burst-append path. See
[cloud-transcription-setup.md](cloud-transcription-setup.md) for the provider/key detail and
the request shaping (`voice_typer/server/cloud/_providers/`), and ADR-0028 §2 for the WS path.

**A realtime model without a transport here cannot be reached from any of these** (today:
Gemini Live only). It needs a persistent session that stays open while audio streams out,
and the text arrives in pieces as you speak.

---

## The two excluded OpenAI models

| Model id | OpenAI's display name | What OpenAI says it is for | Reachable from `/v1/audio/transcriptions`? |
|----------|----------------------|----------------------------|-------------------------------------------|
| `gpt-live-transcribe` | GPT-Live-Transcribe | "Low-latency speech-to-text model for realtime transcription" | **No** — Realtime transcription workflow |
| `gpt-realtime-whisper` | GPT-Realtime-Whisper | "Streaming speech-to-text model for realtime transcription" | **No** — Realtime API session model |

Both need a Realtime API session: `v1/realtime/transcription_sessions` over WebSocket (server
audio pipelines) or WebRTC (browser audio).

### The decisive evidence

OpenAI's own **Transcription workflow** guide splits transcription into two workflows and
assigns each model to one of them:

> **File transcription** — you have a complete recording or a bounded audio request → recommended
> model **`gpt-transcribe`**
>
> **Realtime transcription** — you have a microphone, a call, or another live audio stream and need
> text as the speech arrives → recommended model **`gpt-live-transcribe`**

and then, explicitly:

> "Streaming output and live audio are two separate decisions. You can stream the transcript of a
> completed file **without** starting a Realtime session. Only use Realtime when your audio is
> arriving live or you need a persistent connection."

That last sentence is the whole rule: our audio is already complete when we send it, so we must
**not** use Realtime — and the two realtime models are not offered on the batch path.

Corroborating, from the Realtime transcription guide:

> "For the lowest-latency streaming transcription path, use `gpt-realtime-whisper`. For offline
> files or workflows that don't need streaming deltas, use the standard speech-to-text models in
> the Audio API."

The session shape is nothing like ours — there is no file upload and no single response:

```json
{
  "type": "session.update",
  "session": {
    "type": "transcription",
    "audio": { "input": { "transcription": { "model": "gpt-live-transcribe" } } }
  }
}
```

Audio then goes out in chunks (`input_audio_buffer.append` + `input_audio_buffer.commit`) and
text comes back as `conversation.item.input_audio_transcription.delta` events, with
`...completed` carrying the final transcript per committed item.

### Why a normal Select row would break dictation

1. The user clicks **Select** on the row → `activateCloudModel` writes
   `asr_backend: "cloud"`, `cloud_provider: "openai"`, `cloud_model: "gpt-live-transcribe"`.
   That write succeeds, because it is just config.
2. The row renders as **Active**. Everything looks correct.
3. The next dictation POSTs the finished WAV to `/v1/audio/transcriptions` with
   `model=gpt-live-transcribe`.
4. OpenAI rejects the request — the batch endpoint only accepts the models it serves. The user
   gets an error and **no transcript**, and has to work out that the model they picked cannot
   work here.

Step 4 is the problem: it is a control that looks usable and is not. The exact error body was
**not** verified (no API key available while writing this), so treat the wording as unverified —
but the model is not in the batch workflow, so a rejection is the expected outcome.

---

## The same rule elsewhere in the catalogue

This is not an OpenAI quirk. The rule is: **a catalogue lists only what that provider's own
endpoint serves.** Two precedents are already encoded:

| Provider | Excluded model | Why |
|----------|----------------|-----|
| OpenAI | `gpt-live-transcribe`, `gpt-realtime-whisper` | Realtime API sessions (WebSocket/WebRTC) |
| Google Gemini | `gemini-3.5-transcribe-live` | Live API (WebSocket) sibling of the unary model |
| Deepgram | Flux | Streaming voice-agent model with native turn detection, not a batch dictation engine |

`models-cloud-catalogue.test.ts` pins all of these exclusions. Those tests are **deliberately
brittle**: if a provider starts serving one of these ids on its batch endpoint, the test fails
and forces a re-check rather than letting the omission rot silently.

---

## What the catalogue serves today (verified 2026-10-12)

### OpenAI

| Model id | Display name | WER | Speed | Performance |
|----------|--------------|-----|-------|-------------|
| `whisper-1` | Whisper 1 | 5.5 (derived, no published pooled row) | medium | Average |
| `gpt-transcribe` | GPT-Transcribe | — (no pooled figure) | medium | Highest |
| `gpt-4o-transcribe` | GPT-4o Transcribe | — (no pooled figure) | medium | Higher |
| `gpt-4o-mini-transcribe` | GPT-4o mini Transcribe | — (no pooled figure) | fast | High |

`defaultModel` is `whisper-1` — the only model here with a pooled real-world figure, so it is the
only one the Cloud tab's WER column can compare against the Local tab.

### Speed labels mirror the vendor

`speed_rating` is **not** a judgement call — it copies the provider's published **Speed** value:

| OpenAI's published Speed | catalogue `speed_rating` |
|--------------------------|--------------------------|
| "Very fast" | `fast` |
| "Fast" | `fast` |
| "Medium" | `medium` |
| "Slow" | `slow` |

Two rows were corrected on 2026-10-12 to follow this:

* `gpt-transcribe` was `fast` — an **inference** ("same GPT-4o-class generation"), which was
  wrong. OpenAI publishes **Medium**.
* `gpt-4o-transcribe` had said `fast` since before this work; OpenAI publishes **Medium**.
  (`gpt-4o-mini-transcribe` is genuinely published as **Fast**, so the two tiers really do
  differ — do not "harmonise" them.)

### WER is never a guess

`wer: null` means *no pooled benchmark covers this model*, and the cell renders an em dash. The
column exists so Local and Cloud are comparable, so inventing a number would break the
comparison. Several OpenAI rows share the same tier now, so tests must **count** chips and em
dashes off the catalogue — never use a single-element query like `getByRole` for something that
can legitimately appear more than once. (A `getByRole("button", { name: "Medium Speed" })` call
threw once `gpt-transcribe` became `medium` alongside `whisper-1`.)

---

## How to resolve this — three options

### Option 1 — show them, but not selectable *(SHIPPED 2026-10-13; narrowed 2026-10-14:
OpenAI rows became selectable with §2, Gemini Live keeps the marker)*

Both names appear in the OpenAI list exactly as on OpenAI's site, but the action area renders a
**disabled "Realtime only"** marker instead of a Select button, with the reason in a tooltip.
Activation is also refused at the hook level, so no code path can write a realtime model id.

* Add an optional flag to `CloudModel` (e.g. `realtimeOnly?: true`).
* Render a non-interactive state in `CloudModelRow` (`components/models/CloudProvidersPanel.tsx`).
* Refuse in `activateCloudModel` (`hooks/models/useCloudProviders.ts`) as defence in depth.
* Needs new strings in all **8** `i18n/translations/*.json` — and `scripts/translate-i18n.js`
  must be updated in lockstep, because it only writes entries that are `undefined` or still
  English.
* Extend the existing `describe("OpenAI catalogue — batch endpoint only")` block in
  `models-cloud-catalogue.test.ts`.

Nothing lies, nothing can break dictation, and the list matches OpenAI's page. This is the
cheapest honest option.

### Option 2 — build the live-streaming path so they really work *(SHIPPED 2026-10-14
for OpenAI as burst-append at stop — no live mic feed, per C-TRANS-1; see ADR-0028 §2
for the as-built design and its deliberate omissions)*

The option where these two models actually transcribe. It was a real feature, not a list
entry. **As built:** `voice_typer/server/cloud/_realtime.py` holds the capability sets
(`REALTIME_MODELS`, `WS_REALTIME_MODELS`), the official session/append/commit envelopes,
PCM16 conversion + 16→24 kHz resampling, 200 ms framing, the delta assembler and the guards;
`voice_typer/server/cloud/_realtime_ws.py` holds the WS session (open → session.update →
burst appends → commit → first `transcription.completed`); `CloudEngine` routes per model.
Superseded design notes (kept for history — the shipped path differs where struck):

* ~~New transport streaming the mic live during the window~~ — shipped as burst-append of
  the finished recording at stop instead (same wire protocol, no recorder surgery).
* Session lifecycle: `session.update` with `type: "transcription"`, then
  `input_audio_buffer.append` per frame, `input_audio_buffer.commit` at stop.
* Delta assembly: merge `...transcription.delta` events into the final
  `...transcription.completed` transcript, buffered and released once (never rendered live).
* ~~Wire the mic stream live~~ — not built; revisit only if burst turnaround proves too slow.
* A per-model capability flag so batch vs realtime routing is explicit (`realtimeOnly` +
  `realtimeWs`, pinned cross-language by the parity test).
* `gpt-live-transcribe` tunable `delay` — deferred (field omitted, server default).

### Option 3 — add them as normal selectable rows *(rejected; OpenAI rows are selectable
now only because Option 2 ships beneath them)*

They appear and are selectable like everything else. Consequence without a transport
beneath: selecting one saves to config, the row shows Active, and the next dictation fails
with an OpenAI API error. Listed only for completeness — it produces exactly the lying
control the project's own UX doctrine rules out. (The OpenAI rows are selectable today
only because Option 2 ships beneath them; a transport-less selectable row is still banned.)

---

## Things a future agent must not break

* **`tests/test_cloud_provider_catalogue_parity.py`** — parses `cloudCatalog.ts` for the contiguous
  `key:`/`url:`/`defaultModel:` triplet and compares it to `_PROVIDER_DEFAULTS`
  (`voice_typer/server/cloud/_defaults.py`), plus the `realtimeOnly` set against
  `REALTIME_MODELS` and the `realtimeWs` set against `WS_REALTIME_MODELS`.
  Changing a `defaultModel` means changing **both**.
  Drift is silent: with an empty `cloud_model` (what onboarding leaves) the backend serves the
  Python default while the Cloud tab marks the TS one active.
* **`defaultModel` must be one of that provider's own models** — `isCloudModelActive` falls back
  to it, so a default outside the list leaves the tab showing no active row.
* **`models-cloud-catalogue.test.ts`** — catalogue invariants, the OpenAI/Gemini exclusion
  guards, and the label tests. Count-based, never single-element.
* **C-DATA-1** — credentials never go in a URL. OpenAI uses a `Bearer` header; Gemini uses
  `X-goog-api-key` (`_providers/gemini.py`), never `?key=`.
* **The consent gate** — activating a provider's model requires a stored key and routes through
  the shared consent dialog (`lib/consentGate.ts`). A new provider's consent name must be added
  to `CONSENT_FIELD_NAMES`, which also joins it to the derived `DICTATION_RETRY_CONSENT_FIELDS`
  list that `hooks/__tests__/useConsentRequiredEvent.test.ts` pins verbatim.
* **A stale stored `cloud_model` is not migrated.** `isCloudModelActive` only falls back to
  `defaultModel` when `cloud_model` is *empty*, so a user holding a model id that was removed
  from the catalogue keeps transcribing with it (if the provider still serves it) while the tab
  shows **no** active row. Known, deliberate, unresolved.

---

## Sources

All fetched 2026-10-12.

* OpenAI — Transcription workflow overview (`developers.openai.com/api/docs/guides/transcription`):
  the file-vs-realtime workflow split and the "streaming output and live audio are two separate
  decisions" paragraph.
* OpenAI — Realtime transcription guide (`.../guides/realtime-transcription`): session shape,
  delta events, and the `gpt-realtime-whisper` guidance.
* OpenAI — model pages for `gpt-live-transcribe`, `gpt-transcribe`, `gpt-4o-transcribe`,
  `gpt-4o-mini-transcribe`, `whisper-1`: Performance, Speed, pricing, snapshots.
* Google — `gemini-3.5-transcribe` model page (`ai.google.dev/gemini-api/docs/models/gemini-3.5-transcribe`):
  Unary vs Live API versions, 1-hour unary limit, supported languages.
* Deepgram — Models & Languages overview: Nova-3/Nova-2 batch vs Flux streaming.

**Confidence.** The endpoint verdicts for `gpt-live-transcribe` and `gpt-realtime-whisper` rest on
OpenAI's own workflow guide, which is explicit. The Performance/Speed values are quoted from
OpenAI's model pages. The only unverified item is the exact error body OpenAI returns if a
realtime model is sent to the batch endpoint — stated as such above.
