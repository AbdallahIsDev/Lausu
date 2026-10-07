

# ADR-0021: Split Transcription from Translation (Points 1 + 2)

Status: AGREED plan (Points 1 + 2 locked). Points 3/4/5 deferred to user direction.
Date: 2026-10-06

## 1. Locked decision: Transcription != Translation

Two separate jobs, two separate stages:

- **Stage A — Transcription (speech model):** "write down exactly what you hear." No translation, no rewording.
- **Stage B — Translation (small text model, NEW):** takes Stage A text, converts to user's chosen output language.

Rationale: one model doing both produces literal / inaccurate output. Each model does one job at peak quality.

Scope lock: **8 core languages only.** No every-language-in-the-world support locally — that needs datacenter-class checkpoints (~100 GB STT + ~50 GB MT). Users run on consumer hardware. Models stay lightweight. If a user speaks outside the 8, app does not target them. Accepted tradeoff.

## 2. Locked decision: default output = same as spoken

Speak Arabic -> get Arabic text. No silent English-ification.

This is Point 2 agreement. Detection / pinning mechanics below are NOT fully locked (see Sec. 5 conflict).

## 3. Translation model hunt — rules

Search Hugging Face + elsewhere for small multilingual MT models (NLLB-distilled, M2M100-small, Marian group, etc.).

Criteria:
- covers >= top-3 (ideally all 8)
- smallest size wins
- offline / consumer-PC friendly
- license must allow shipping (see warning on NLLB below)

> ### ⚠️ HARD RULE — NO AUTO-DOWNLOAD
> After search, agent MUST report candidate + **exact file size** then **STOP and ask for explicit approval**.
> NEVER auto-download a checkpoint in background (a 20 GB pull burns quota).
> Alternative allowed: record model ID / URL without downloading, download + test later only after approval.

First-look starting point (NOT approved, NOT downloaded):

- `facebook/nllb-200-distilled-600M` — translation-only, ~600M params (~1.2 GB FP16 / ~2.4 GB FP32 approx, verify exact bytes before any pull), 200 languages incl. all 8. License **CC-BY-NC-4.0** — research-only, likely NOT shippable. Flag for legal / replace with MIT/Apache alternative (M2M100, Marian, MADLAD-small, etc.).
- AR-EN codeswitch STT finetunes exist (e.g. `Mano200600/faster-whisper-large-v2-ar-codeswitching`, GPL-3.0, ~238 downloads) — niche, Egyptian-dialect, GPL viral. Reference only, not a base.

## 4. What the web says (researched 2026-10-06, not guessed)

- Whisper `--language` pin vs auto-detect (`openai/whisper#1456`): auto-detect samples first ~30 s and guesses. Paper p.11: tiny ~45% correct, large-v2 ~65% across 102 langs. EN/ES/DE near 100% in practice; Hindi↔Urdu, Tatar, low-quality audio misdetect often. Pinning when language is known is strictly more accurate — confirms user's "Speaking Language" instinct.
- Short clips: 1-second single-word detect fails near-100%, hallucination risk. Community consensus: never trust auto-detect on <2-3 s; pin or skip detect.
- Code-switching (theneuralbase whisper course + `faster-whisper#918`): stock Whisper already handles mixed speech "remarkably well out of the box" — training data includes code-switch. No pre-splitting needed. Output is one continuous transcription without language labels; per-segment confidence drops on heavy switching — flag low-confidence segments for review instead of upstream fixing.
- Pinning breaks switching: forcing `language=en` on AR+EN audio corrupts Stage A, Stage B then translates garbage → worse garbage. No local algorithmic fix without massive unified model (Gemini-class = datacenter only). This is the triangle: **decoupled stages + pinned Speaking Language + seamless code-switch cannot all hold locally.**

## 5. Open conflicts (Points 3/4/5 — NOT decided)

- "Speaking Language" pinned code + Auto-as-codeswitch-mode vs pinned-only.
- Mixed AR+EN through pinned STT: failure lives in Stage A, not Stage B.
- Whether Auto mode = current auto-detect (with above failure modes) or something smarter.

Awaiting user direction on Points 3/4/5.

## 6. Build order

1. Reorder 8-language dropdown (UI-only, resolve de-vs-pt first).
2. Search + report translation candidates with exact sizes + licenses (no download).
3. User approves → download + test → wire Stage B behind "Same as spoken" default.
