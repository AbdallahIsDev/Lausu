# Research: translation models + general text models for local polish (no downloads)

> Status: **research only, 2026-11-01. Nothing downloaded, nothing integrated.**
> Companion to the measured benchmark (`D:\polish_eval\llm\reports\minicpm5-2b-onnx*.md`).

## 0. Why we are looking

Our own benchmark of MiniCPM5-2B (q4f16 ONNX, 1.7B) says, on the owner's real
dictations (250-1750 words, mixed Egyptian Arabic + English):

| capability | measured | note |
|---|---|---|
| translation AR/EN → EN | 25/100 | invents brands (`HubSpot`, `Mailchimp`), loops on long input |
| polish | 15/100 | copies the input back beyond ~150 words |
| tone | 45/100 | changes register but drops 50-80% of the content |
| grammar | 10/100 | no measurable edits |

With sentence-packed chunking (150-200 words/call) it reaches 77.7% overall, but the
translation step specifically *degrades* when chunked (86.7 → 71.7-83.3) because it
loses cross-sentence context.

Two consequences drive this research:

1. **Translation is the mandatory first stage.** Real usage is `dictation → translate
   → requested task (polish/tone/grammar)`. A single small model doing both is a
   harder job than the tests we ran, so a dedicated translation model is the sane
   split.
2. **Size ≠ quality, but quantization costs quality.** A 1.7B at q4 is a fraction of
   the same model at fp16; a 2B translation *specialist* can beat a 7B general model
   on MT, and we should pick on measured MT quality, not on parameter count.

## 1. Requirements the model must meet

| # | requirement | why |
|---|---|---|
| R1 | **Arabic ↔ English works, including code-switched/colloquial input** | the owner dictates Egyptian Arabic with English technical terms inline; formal-MSA-only MT models degrade here |
| R2 | **Runs in our runtime** | ONNX Runtime preferred (already in the app). GGUF is acceptable but means adding a llama.cpp/ggml backend — a real integration cost, not a free option |
| R3 | **≤ ~2 GB at the chosen quant** | must fit next to ASR/TTS models and download reasonably |
| R4 | **Commercial-safe license** | Lausu ships to users; `CC-BY-NC` models cannot be shipped |
| R5 | Fast | target: a 200-word segment in < 2 s on the RTX 5060, < 6 s CPU |
| R6 | No prompt-format trap | a plain "translate to X" call must work; we do not want to babysit a chat template |

## 2. How candidates were filtered (owner's rule)

1. Already **ONNX or GGUF** → highest priority.
2. Only **SafeTensors/PyTorch** → included **only** if convertible (llama/t5/gemma-2
   architectures with an existing `optimum` ONNX export or llama.cpp conversion path),
   flagged as "needs conversion".
3. **MLX / GPTQ / AWQ-only / exotic** → excluded (no ONNX/GGUF path).

Formats and sizes below were read from the Hugging Face API on 2026-11-01 (real file
sizes, not claims). Quality claims are the vendor's/paper's and are marked
**(unverified)** where we have not run them.

## 3. Translation-dedicated candidates

| model | params | ready-made format(s) & size | AR support | license | MT evidence | verdict |
|---|---|---|---|---|---|---|
| **tencent/Hy-MT2-1.8B** | 1.8B | **GGUF** Q8 = 1.78 GB, Q6 = 1.37 GB, Q4_K_M = 1.06 GB (official). **No ONNX**, and the export is *not* a plain-Llama job: `model_type = hunyuan_v1_dense`, `architectures = HunYuanDenseV1ForCausalLM`, `custom_code` → ONNX needs a traced custom module (possible, but a real task). GGUF/llama.cpp is the low-risk path | ✅ 33 languages + 5 dialect variants; family is tuned for **mixed-language** input | **Apache-2.0** | family pedigree: Hy-MT1.5-7B is the **WMT25 championship model**; vendor states 1.8B ≈ 7B quality; ships IFMTBench; supports **style / terminology / context / delimiter-preserving** instructions (report: arXiv 2605.22064) **(none of it measured by us)** | **top pick for translation on priors** — dialect variants + mixed-language tuning + style instructions (translate+tone in one call) are exactly our problem |
| **tencent/Hy-MT2-7B** | 7B | GGUF Q4_K_M = 4.31 GB, Q8 = 7.43 GB | ✅ | Apache-2.0 | same family, bigger **(unverified)** | only if 1.8B disappoints and the user has the RAM |
| **facebook/nllb-200-distilled-600M** | 600M | **ONNX exists** (`Xenova/nllb-200-distilled-600M`, transformers.js export) | ✅ 200 languages | **CC-BY-NC-4.0 → cannot ship** | canonical FLORES-200 baseline, widely reproduced | research-only baseline (license blocker) |
| **facebook/nllb-200-distilled-1.3B** | 1.3B | ONNX: community conversions (`forkjoin-ai/...`, `fine444666/...-int8`); no official export | ✅ | **CC-BY-NC-4.0 → cannot ship** | stronger than 600M | research-only baseline |
| **Helsinki-NLP/opus-mt-tc-big-ar-en** | ~230M | **ONNX** (`onnx-community/opus-mt-*` family; ar-en via `Xenova/opus-mt-ar-en`) | ✅ AR→EN only | **CC-BY-4.0 ✅ ship-able** | classic Marian; card carries FLORES BLEU | **cheap AR→EN specialist**; one model per direction (no EN→ES) — pair per language |
| **Helsinki-NLP/opus-mt-mul-en** | ~80M | ONNX via onnx-community (family) | ✅ multi→EN | CC-BY-4.0 ✅ | as above | tiny fallback / offline |
| **google/madlad400-3b-mt** | 3B | **GGUF official in-repo** (q4k = 1.54 GB); ONNX community (`Kutalia/...`, `CXDuncan/...quantized-onnx`) | ✅ 400+ languages | **Apache-2.0 ✅** | FLORES/WMT numbers in paper | strong multilingual coverage; 3B + T5 decoder → slower, needs `optimum` ONNX or llama.cpp |
| **ModelSpace/GemmaX2-28-2B-v0.1** | 2B | SafeTensors 6 GB; **GGUF** (community `mradermacher/...` Q8 = 2.59 GB, Q4_K_M = 1.59 GB); ONNX = convert (Gemma-2 arch) | ✅ 28 languages incl. Arabic | **Gemma Terms of Use** (shippable with restrictions) | paper: GemmaX2-28 family "outperforms TowerInstruct/XALMA, competitive with Google Translate & GPT-4-turbo" on 28 languages **(unverified for the 2B)** | best *small MT specialist* candidate; needs conversion to ONNX unless we accept GGUF |
| **BSC-LT/salamandraTA-2b / -7B** | 2B / 7B | GGUF (community for 2B: Q8 = 2.24 GB; official 7B q4_k_m = 4.52 GB) | ❓ European-focused (Arabic coverage **not confirmed**) | Apache-2.0 (verifying) | strong on WMT24++ EU pairs | **excluded for now**: the AR pair is unverified, and our first need is AR↔EN |
| **Unbabel/TowerInstruct-7B-v0.2** | 7B | SafeTensors (GGUF community) | ✅ | **CC-BY-NC-4.0 → cannot ship** | translation-tuned Mistral | research-only (license + size) |

## 4. General small models (polish / tone / grammar — the second stage)

| model | params | ready-made format & size | AR support | license | note |
|---|---|---|---|---|---|
| **LiquidAI/LFM3-1.7B** | 1.7B | **official ONNX**: q8 = **2.16 GB**, q8f16 = 1.89 GB, q4 = 1.51 GB, q4f16 = **1.29 GB**; official GGUF (Q8 = 1.72 GB, Q4_K_M = 1.02 GB) | ✅ 16 languages incl. Arabic | **LFM Open License v1.0** (commercial terms must be reviewed — it is *not* Apache) | the model the owner asked about: agent/tool oriented, 256K ctx, "9B-class agentic performance"; those benchmarks are **agentic, not MT/polish** — nothing suggests it polishes better than MiniCPM |
| **Qwen/Qwen3-1.7B** (+ ONNX: `onnx-community/Qwen2.5-1.5B-Instruct`) | 1.5-1.7B | SafeTensors; ONNX via onnx-community (Qwen2.5-1.5B is ONNX-ready today, Qwen3 needs export) | ✅ strong multilingual | Apache-2.0 ✅ | best-known instruction-following per parameter at this size; worth benchmarking as the polish model |
| **MiniCPM5-2B** (current) | 2B | ONNX q4f16 1.76 GB (already downloaded) | ✅ | Apache-2.0 | measured: 15/100 polish at real sizes, 85/100 chunked to ≤150 words |
| **SmolLM3-3B / Granite-4.0-micro** | 3B / 3B | GGUF ready; ONNX via export | ✅ | Apache-2.0 | alternatives if Qwen3-1.7B is not better |

## 5. The two things that actually block shipping

1. **NLLB-200 and TowerInstruct are CC-BY-NC** → they can be benchmarked, never
   shipped. Do not build the product path on them.
2. **GGUF is not ONNX.** Our runtime is onnxruntime. Choosing Hy-MT2 (GGUF) or
   SalamandraTA (GGUF) means shipping a second inference backend (llama.cpp), i.e.
   a new dependency, a new binary per platform, plus its own KV/cache handling —
   this is the same class of work as WP6 in
   `docs/plan-model-providers-local-and-hosted.md`, not a download.

   Cheapest path that keeps one runtime: **LFM3-1.7B-ONNX** (already official) or
   **Opus-MT ONNX** (already converted) now; **convert Hy-MT2-1.8B with `optimum`**
   (Llama architecture, same export path Microsoft used for their Llama ONNX models)
   if the benchmark says it wins. **Correction:** Hy-MT2 is `hunyuan_v1_dense` with custom code, not
   a plain Llama, so its ONNX export is a small project of its own — plan for GGUF or budget the
   export properly.

## 6. Recommended shortlist to benchmark next (in this order)

| # | model | format to test first | why this one |
|---|---|---|---|
| 1 | **Hy-MT2-1.8B** | GGUF Q8 (llama.cpp) *and* ONNX export | purpose-built MT, 33 languages incl. Arabic, Apache-2.0, style/terminology instructions (translate + tone in one call) |
| 2 | **LFM3-1.7B** | official ONNX q4f16 / q8 | zero conversion work, 16 languages incl. Arabic, 256K context; owner's suggestion; unknown for MT/polish |
| 3 | **GemmaX2-28-2B** | GGUF Q4_K_M / Q8 | small *MT specialist* with a published 28-language claim; needs ONNX conversion |
| 4 | **Opus-MT tc-big-ar-en (+ per-language pair)** | ONNX (ready) | 230M, CC-BY-4.0, dirt cheap AR→EN baseline — if it beats a 2B LLM on our dictations, that is a huge win for size and speed |
| 5 | **Qwen3-1.7B** | ONNX (Qwen2.5-1.5B is ready today) | the *polish/tone* candidate (stage 2), Apache-2.0 |
| — | MADLAD-400-3B | GGUF q4k | only if language coverage (400+) becomes a requirement |

## 7. How we will measure (harness is already built)

`D:\polish_eval\llm` already does levels, chunking and deterministic scoring. Add
only these:

1. **`translation` task stays as-is** (mixed AR/EN dictation → English) — it is the
   make-or-break test, and it caught MiniCPM's invented brands.
2. **Direction matrix**: AR→EN, EN→AR, EN→ES, EN→FR at the three sizes, so we see
   whether quality is symmetric.
3. **Two-stage replay** (the real product flow): `translate → polish` as (a) two
   separate calls, (b) one combined instruction — the owner's concern is that one
   model doing both degrades; measure it instead of assuming.
4. **Code-switch stress set**: sentences that mix Egyptian Arabic + English terms,
   which is exactly the owner's dictation style and is out-of-distribution for every
   model in this list.
5. Metrics: our existing rubric (language purity, entity retention, no invented
   names, loops, length ratio) + a **hallucination count** and a **COMET-style
   reference score** once we have one human-corrected reference per level (the only
   way to score fidelity properly).

## 8. Explicit non-goals

- No downloads yet (owner's instruction).
- No product/integration work until a winner is measured.
- No PyTorch-only models in the product path.
- No model that needs an unreviewed commercial license.

## 9. Open questions for the owner

1. If Hy-MT2-1.8B wins, do we accept **adding llama.cpp** or spend a day on an
   `optimum` ONNX export (keeps one runtime)?
2. Is **EN→AR** (English dictation → Arabic output) a real use case, or only AR→EN
   and EN→{ES,FR,DE}?
3. Target languages beyond English/Arabic — the 33-language Hy-MT2 vs the
   28-language GemmaX2 vs 400+ with MADLAD changes which model is "enough".
4. Budget for the polish stage: 1.7B-class (fast, weak) or 4-8B (slower, actually
   edits at paragraph scale)?
