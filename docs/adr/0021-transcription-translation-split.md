

# ADR-0021: Split Transcription from Translation (Points 1 + 2)

Status: LOCKED (2026-10-07, user-confirmed Sec. 5 + Sec. 6).
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

## 5. Locked design (2026-10-07, user-confirmed)

### 5.1 Two settings, not one
- **Speaking Language:** `Auto` (default, mixed-language) + 8 pinned codes. Auto preserves mixed speech. Pinned = single-language accuracy boost; mixed input under a pin may degrade (documented, not a bug).
- **Output Target:** `Same as spoken` (default) + 8 languages. This is the only thing Stage B acts on.

### 5.2 Stage A → B contract (locked)
- Stage A writes what it hears, each part in its own script. AR stays AR, mixed stays mixed. `language=` is a transcription instruction, never a translation instruction.
- Stage A output = `{text, segments[], detected_lang + confidence}`.
- Skip Stage B when: target is `Same as spoken`; or text already confidently matches target. Rule: when in doubt (very short text, low confidence, single words / proper nouns), SKIP translation. A mistranslation of correct text is worse than passthrough.
- Mixed input + matching target: sentence-level routing. Only translate non-target segments (script guess AR-vs-Latin is free, no model call), splice the rest back verbatim. Never run whole mixed text through the translator.
- Transcription is NEVER blocked on language grounds when the model is multilingual (Whisper covers all 8). Refusal is reserved for genuine no-coverage (e.g. Parakeet + Arabic).

### 5.3 Fallback chain without a translation model (locked)
1. Translator present → use it (best quality, all pairs).
2. No translator + Whisper + target EN → Whisper built-in translate mode acceptable temporarily (weaker, English-only by model fact).
3. No translator + Whisper + target non-EN → transcribe fully in spoken language, return original text + one honest line: target output needs the translation model. Nothing blocked, nothing faked.
4. No translator + English-only model (Parakeet) → transcribe only. Non-English output request → one-line "not supported" message.
- Capability check = intersect spoken/detected language with model's supported list. Notify on capability gap only, never on setting mismatch. Whisper + Auto never warns; Parakeet + Arabic warns once.

## 6. Translation model choice — license lock (2026-10-07)
- `facebook/nllb-200-distilled-600M` stays Plan B only. Reason: CC-BY-NC-4.0, and NC covers adapted material — finetune, quant, or format convert (ONNX/INT8) does NOT clean the license; the restriction travels with the weights. Distilled checkpoints re-shared under CC-BY-NC are restricted regardless of how they were made. Free + open-source today = low risk; any future closed-source/company distribution = violation + forced rip-out.
- Plan A = permissive license base (M2M100 / Marian / MADLAD-small or equivalent Apache/MIT). Verify exact license + exact file bytes before any pull. HARD RULE in Sec. 3 still binds: report candidate + size, STOP, ask approval, never auto-download.
- Engineering note, not legal advice.

## 8. Candidate measurements (2026-10-08, verified, NOT downloaded)

8 langs = en zh hi es ar fr ru de. Sizes are Xet "Size of remote file" on the weight blob. Nothing pulled.

| # | Model ID | Weight file | Exact size | License (HF hub API) | Covers 8 | Format | Verdict |
|---|----------|-------------|------------|----------------------|----------|--------|---------|
| 1 | `Helsinki-NLP/opus-mt-en-mul` + `Helsinki-NLP/opus-mt-mul-en` | `pytorch_model.bin` each | 310 MB + 310 MB = ~620 MB + tokenizer | Apache-2.0 + Apache-2.0 | yes via EN pivot | pickle | Smallest shippable. 2-hop on non-EN pairs. CT2-native (Marian, Sec. 8.2). |
| 2 | `alirezamsh/small100` (SMaLL-100, 332M, M2M100 distill) | `model.safetensors` (use this; `model.onnx` = 1.86 GB, `pytorch_model.bin` dup) | 1.33 GB | MIT | yes direct | safetensors | Single direct model. CT2 via M2M path + prefix tweak (Sec. 8.2). Community mirror, needs trust check. |
| 3 | `facebook/m2m100_418M` (418M, official) | `pytorch_model.bin` | 1.94 GB | MIT | yes direct | pickle | Official direct. CT2 official example (Sec. 8.2). |
| R | `facebook/nllb-200-distilled-600M` | `pytorch_model.bin` | 2.46 GB | CC-BY-NC-4.0 | yes direct | pickle | REJECT per Sec. 6 (NC travels with weights). Plan B only. |
| R | `google/madlad400-3b-mt` (2.94B) | repo 63.8 GB total (`model.safetensors` ~11-12 GB + 3 GGUF) | ~11 GB+ single | Apache-2.0 | yes | safetensors+GGUF | REJECT on size, not consumer-PC. |
| R | `facebook/mbart-large-50-many-to-many-mmt` (611M) | repo 21.2 GB total | ~2.4 GB single | none declared | yes | safetensors | REJECT, no license. |

Notes:
- `used_storage_bytes` (whole repo, all frameworks) misleads; table uses per-file bytes.
- Opus bilingual singles (e.g. `opus-mt-en-de`, `opus-mt-en-ar`) are Apache-2.0 but one pair each; full 8-lang EN-pivot group = ~14 files, est. 3-4 GB. Pair in row 1 replaces them at ~620 MB.
- `facebook/m2m100_126M` does not exist (404); 418M is smallest official M2M100.
- Hunt open (remaining): opus-mt safetensors re-shares; community MADLAD-small distills.

### 8.1 Hunt round 2 (2026-10-08, verified, NOT downloaded)

| Model ID | Weight files | Exact size | License (HF hub API) | Verdict |
|----------|--------------|------------|----------------------|---------|
| `venddair/m2m100-418M-onnx-int8` (M2M100 418M, ONNX INT8) | `encoder_model.onnx` + `decoder_model.onnx` | 287 MB + 470 MB = ~757 MB | none declared | Smallest direct-M2M footprint, but NO license + 182 downloads. Needs owner/license proof before ship. |
| `entai2965/m2m100-418M-ctranslate2` (CT2, base `facebook/m2m100_418M`) | `model.bin` | 1.94 GB | MIT | Same size as base, no saving, 1340 downloads. Only useful if CT2 runtime chosen. |
| MADLAD-small | — | — | — | No official small MT below 3B; no trusted community small found. Dropped. |

### 8.2 Backend compat (2026-10-08, CT2 docs + forums, no torch at runtime)

Rule: shipped runtime is CT2 (`model.bin` + tokenizer) or ORT (`.onnx`). Torch+transformers exist ONLY at offline convert time. Checkpoint format (pickle/safetensors) is irrelevant to shipping. Nothing is ignored on backend grounds; rejects stay license/size only.
Sources: `opennmt.net/CTranslate2/guides/transformers.html` (v4.8.2: MarianMT/M2M-100/NLLB/T5 sections), `OpenNMT/CTranslate2#1560` (MADLAD=T5 works out-of-box), `forum.opennmt.net/t/convert-small100-with-ctranslate2/5134` + LibreTranslate thread (small100 converts via M2M path, target-prefix tweak needed), `BlackVarmir/m2m100-1.2B-ct2-int8` card ("inference without PyTorch"), `discuss.hf.co/t/export-m2m100-model-to-onnx/17694` + `optimum#16695` (M2M100/T5→ONNX has trace gaps; CT2 is the path, ORT not recommended here).

| Model | CT2 | ORT | Note |
|-------|-----|-----|------|
| opus-mt pair (Marian) | YES, first-class (`--model Helsinki-NLP/opus-mt-en-de` is the doc example) | possible | Keep. |
| m2m100_418M | YES (`--model facebook/m2m100_418M` is the doc example) | weak (trace issues) | Keep, via CT2. |
| small100 (m2m_100 arch) | YES with prefix tweak, test after approval | n/a | Keep, via CT2. |
| nllb-200-distilled-600M | YES (doc example) | n/a | Still REJECT (license Sec. 6). |
| madlad400-3b-mt (T5) | YES (T5 section + #1560) | n/a | Still REJECT (size). |
| mbart-50 (mBART arch listed in CT2 model types) | YES arch-wise | n/a | Still REJECT (no license). |
| venddair ONNX-INT8 | n/a (already ONNX) | YES files exist | Still BLOCKED (no license). |
| entai2965 CT2 model.bin | n/a (already CT2) | n/a | Usable only if CT2 runtime chosen; no size win. |

Status: reported, STOPPED, no download. Approval pending per Sec. 3 HARD RULE.

## 9. Build order
