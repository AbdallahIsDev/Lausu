# ADR-0030: One ASR model + one text translator, gated by real language capability

Status: **Accepted, locked 2026-11-17 (owner-confirmed in session)**.
Refines ADR-0021 §5.2 / §5.3 (which already reserved refusal for genuine
no-coverage) and closes the model-count question ADR-0021 left open.

## 1. Locked decision: exactly one speech model, never two

Dictation uses **one** speech-recognition (ASR) model at a time. Audio is
never split, routed or raced between two ASR models, and two ASR models are
never resident together.

- One dictation cycle = one ASR model = one transcript.
- Speaking two languages (Arabic + English) is handled by that one model's
  own multilingual decode, **not** by per-language engines.
- Adding a language means choosing or installing a **different model** and
  switching to it. The old model is unloaded first (the existing
  `ModelLeaseGate` / switch path already enforces one resident engine).

Why: ASR models are the app's dominant memory/GPU cost (0.6-3 GB each,
plus runtime), the target machines are consumer boxes (8 GB VRAM class), and
half an utterance through each of two engines yields two transcripts with
different tokenization and no shared context — a merge that cannot be made
correct. Owner decision, restated verbatim: "we cannot use two models
simultaneously and route the speech between them."

**Different model types are fine and expected**: one ASR model plus (once
built) one text translation model, or an ASR model plus a TTS model. The
constraint is per type, not per count.

## 2. Locked decision: transcription and translation stay two stages

Kept from ADR-0021 §1, unchanged: Stage A = speech model writes what it
hears (never translates); Stage B = a small **text** model translates Stage A
output to the requested output language. Stage B is a different model type
and is therefore allowed under §1.

Reasons this is not "one model doing both":
- Whisper's built-in translate task is **English-target only** (`task=translate`),
  so it cannot deliver Arabic/French/etc. targets at all.
- Without an explicit language pinned, Whisper **auto-translates** code-switched
  audio into English instead of transcribing it (ServiceNow-AI code-switching
  benchmark, 2026-06; it ranked last for exactly this reason) — an accidental
  translation the user never asked for.
- Separate stages keep the two error budgets measurable. A single model hides
  which stage failed.

## 3. Locked decision: no "language packs"

There is no such artefact as a downloadable pack that teaches an existing ASR
model a new language — that needs retraining. Wording to avoid in UI, docs and
code: "install the Arabic pack". The correct model is:

- each model declares the languages it was published with
  (`ModelMetadata.supported_languages`, `None` = every language the decode accepts);
- a language it does not declare is **refused before capture**, with the
  message `<model> does not support <language>.` in the app **and** in the OS
  notification area, whose click target is the Models page;
- the user resolves it by choosing a model that declares that language.

## 4. Locked decision: capability is per (model, language), not per app

The app has no language support of its own; the pair does. Implemented in
`model_language_support.py` (per-model published lists) and
`model_language_gate.py` (start-path refusal + surfaces). Spoken language
defaults to **Auto** (`config.language = ""`) because a pinned wrong language
is decoded as if it were right, while Auto asks the model to identify it.

Evidence for the gate (2026-11-17): Parakeet Ultra's base
(`nvidia/parakeet-tdt-0.6b-v3`) publishes **25 European languages, Arabic not
among them**, and this repo's Parakeet path runs an English-only junk filter
when `language == "en"`. Parakeet + default config + Arabic dictation therefore
returned an **empty transcript, silently**.

## 4a. Implementation notes (2026-11-17)

Auto (`config.language == ""`) is one value with one meaning — "the model
detects the spoken language" — and it must survive every boundary:

- Engines normalize it with `asr_utils.asr_language_param` (`"" -> None`):
  Whisper (which only detects on `None`), Parakeet (which arms its
  English-only junk filter from it, so Auto must not look pinned), and the
  worker proxies / worker loaders.
- Cloud request shaping omits the language instead of sending a forced
  `en`: OpenAI-compatible multipart drops the field (the API detects),
  Deepgram sends `detect_language=true` because its own default is `en`.
- Media jobs run the same capability check (`model_language_unsupported`)
  before any download or decode: the audio would come back as junk from a
  model that cannot speak the language, and the run is expensive.
- Schema v8 resets a config that carries the legacy `language="en"` default
  to Auto. `"en"` was the app's own default, so it was never a user's
  decision, and as a decode instruction it armed Parakeet's English-only
  junk guard — the exact reason an existing install still dropped Arabic
  with no message even after the default changed. A user who wants one
  language picks it again in Settings.

## 5. Consequences

- Model cards/UI must show the declared language list; "multilingual" alone is
  not a capability claim.
- A future translation model is a second, separately versioned model of a
  different type; it never participates in the ASR decode.
- The refusal is a start-time gate, not a post-decode filter: no audio is
  captured for a pair that cannot be decoded.
- Mixed-language speech remains a *one-model* concern (Auto + a model that
  declares both languages), per §1.

## 6. Resolved 2026-11-19: shipped translator candidate

**Decision (owner-approved Q4 build): `IndexTeam/Index-Translate-2B-GGUF`
`Q4_K_M`, exact weight file 1,312,164,352 bytes (~1.31 GB), SHA-256
`044b313d29342bd3b2c77cbb64023ca0d209bd9b3247763f9d162767ef2d746a`,
Apache-2.0.** It replaces Hy-MT2 Q6 as the Stage B candidate: local
head-to-head on the owner's Arabic/English technical dictations gave chrF++
72.4 (Q4) vs 68.3 (Hy-MT2 Q6), with fewer invented product names and no
mandatory glossary. Q6_K (1,606,323,712 bytes) remains the higher-fidelity
option but is not the shipped default.

Runtime: the 39 MB Vulkan-capable `llama-server`, **not** the 1.5 GB CUDA
bundle. Failures are non-fatal: the dictation pipeline returns the Stage A
text unchanged. Storage follows the app's existing architecture (owner
decision 2026-11-22):

- The GGUF lives in the **shared HuggingFace hub cache**
  (`~/.cache/huggingface/hub`), addressed by repo id + exact filename. It is
  installed through the existing `download_model` IPC command with SHA-256 /
  size verification; the Settings → Post-Processing row is the UI. The two
  env vars (`LAUSU_TRANSLATION_MODEL` / `LAUSU_TRANSLATION_RUNTIME`) and the
  two config path fields are dev escape hatches, never the default location.
  The model is NOT stored in an Ollama blob directory.
- `llama-server` resolves from the installer-bundled binary search
  (`_shipped_dirs()`: exe-adjacent, `resources/`, parent chain, onefile
  extraction), with the writable app-data dir as the last fallback. No
  Ollama installation and no D: dev path are required.
- Translation runs for **every** dictation provider. Local + cloud ASR go
  through `TranslationStage` in `DictationPipeline`; the Chrome-profile STT
  plugins (which bypass that pipeline) translate in
  `tools/internal_plugins/_common/delivery.py` before paste, so the final
  translated text is what gets copied, pasted, stored and shown in History.
- History keeps **both** versions: schema v7 adds nullable `original_text`
  for the raw Stage A transcript. `text` stays the canonical final text, so
  search/FTS/preview/paste are untouched; the full original is returned only
  by `get_transcription_text` and revealed on demand in the transcript modal.
  Original text is encrypted at rest under the same row flag as `text`.

The seven `translation_*` config keys ride on the existing `set_config` IPC
command and the model download reuses `download_model`, so the command-count
allowlists are unchanged.

Still open: the shared pronoun-direction flaw (both models fail
`اللي بعتهولي`), the exact GGUF runner-CUDA vs GGUF-Vulkan ASR speed A/B,
and a larger real-dictation validation set. EN→AR remains weak.

## 7. Sources

- `nvidia/parakeet-tdt-0.6b-v3` model card — "Supported Languages" (25 EU languages).
- `Qwen/Qwen3-ASR-1.7B` model card — 30-language list (Arabic included).
- `https://huggingface.co/blog/ServiceNow-AI/code-switching` — Whisper
  auto-translates code-switched audio; English-target-only translate task.
- In-repo: `docs/adr/0021-transcription-translation-split.md`,
  `docs/research-translation-and-text-models.md`,
  `voice_typer/server/worker_backed_asr.py`,
  `voice_typer/server/config/_schema.py` (`language`).
- Local reports (2026-11-19): `D:\polish_eval\llm\reports\hy-mt2-vs-index-translate-headtohead.md`,
  `D:\polish_eval\llm\reports\cuda-vs-vulkan-translation-ab-2026-11-19.md`.
