# Research: Nemotron 3.5 Transcribe 30B-A4B + Audio8-TTS-Realistic-0.6B

Date: 2026-10-31. Scope: can either model ship inside lausu, on the owner's machine, without
introducing torch and without leaving ONNX Runtime as the inference base.

Every number below is either **verified** (quoted from a primary source, linked at the end) or
marked **suspected**. Nothing here was implemented; no code was touched.

---

## 0. TL;DR

| Question | Answer |
|---|---|
| Is the 30B-A4B transcribe model real? | Yes. Released 2026-10-28, OpenMDW-1.1, 40 languages, Arabic included but in the **lowest** quality tier. |
| Does it fit the owner's machine (RTX 5060 8 GB / 15.2 GB RAM)? | **No.** Smallest published quant is 13.57 GB decoder + 1.67 GB encoder = **15.24 GB of weights**, against 15.20 GB of *total system RAM*. Not tight — impossible. |
| Is there an ONNX build? | **No**, and it is not a packaging gap. Mamba-2 + MoE + parallel expert encoder + CTC head + MTP head; the sanctioned runtimes are vLLM, SGLang-Omni, Transformers and GGML. |
| Can quantization rescue it? | Not on this box. 4-bit is 19.68 GB, 2-bit is 13.57 GB. The floor is above the ceiling. |
| Is TurboQuant the lever he thinks it is? | **No.** TurboQuant is **KV-cache** compression (PolarQuant + QJL, ~3 bit, ~6x), not weight compression. It shrinks the cache, never the 34 B of weights. |
| Is there a model that *does* fit and speaks Arabic? | **Yes** — `nvidia/nemotron-3.5-asr-streaming-0.6b` (600 M, Arabic in the top tier, native punctuation, ONNX + GGUF community builds, OpenMDW-1.1) plus an **Egyptian-Arabic (`arz`) adapter** fine-tune that already exists. |
| Audio8 TTS viable? | Architecture and licence are good (Apache-2.0, 23 langs incl. Arabic, 601 M). But: torch-only, 2.5 GB of files, no ONNX, 10-codebook autoregressive decode. It breaks three of the project's standing constraints. |

The short version: the interesting model is the wrong size, the right-sized model already exists
and is less exciting, and the TTS model is architecturally the hardest thing in this document.

---

## 1. Model A — NVIDIA-Nemotron-3.5-Transcribe-30B-A4B

### 1.1 What it actually is (verified, model card)

- Speech-augmented language model: a **hybrid Mamba-2 / Transformer MoE** backbone
  (`nemotron_h_moe`), plus a ~600 M Transformer ASR encoder, a ~99 M Sortformer speaker encoder,
  and a CTC timestamp head.
- **34 B total / ~4.3 B active** parameters. The name says 30B-A4B; the card says 34B total.
- 65,536-token context, up to **1 hour of audio** per request, 16 kHz mono PCM in, **text out only**.
- 40 languages. Arabic is in the **"Supported"** tier — the *lowest* of three tiers
  (Leading / Production-ready / Supported). Code-switching and multispeaker ASR are ticked for it.
- **The caveat that matters most:** audio understanding, reasoning and *spoken-instruction
  following* were evaluated **only in English**. Text instruction-following was trained, but at a
  small share.
- Licence: OpenMDW-1.1, commercial use allowed.
- Published: English mean WER 4.71, multilingual 4.62, long-form 10.98, LibriSpeech clean 1.09.
  Arabic FLEURS language-ID 99.77 (that is *language ID*, not transcription accuracy — do not read
  it as an Arabic WER).

### 1.2 The capability he actually wants

The card does support prompt-driven output shaping: verbatim vs clean-written, punctuation and
capitalisation control, `<spk:N>` speaker tags, contextual biasing, translation, PII tagging, and
`enable_thinking` for audio QA. So "transcribe and also obey instructions about the transcript" is
real — it is the same decoder doing both jobs.

What is **not** demonstrated anywhere in the card: expanding a short dictation into a longer one,
restructuring, or Arabic-language instruction following. Those are plausible, untested, and — on
the evidence available — English-shaped.

### 1.3 The hardware wall (his numbers, measured on this machine)

```
nvidia-smi  ->  NVIDIA GeForce RTX 5060, 8151 MiB
Win32_ComputerSystem.TotalPhysicalMemory -> 15.20 GB
```

Weight sizes (verified, AtomicChat GGUF repo, decoder + mandatory F16 encoder):

| Build | Decoder | + encoder 1.67 GB | Smallest documented host |
|---|---:|---:|---|
| Q8_0 | 35.00 GB | 36.67 GB | 48 GB GPU |
| AD-Q5_0_XL | 29.26 GB | 30.93 GB | — |
| AD-IQ4_NL_L | 22.55 GB | 24.22 GB | 32 GB |
| AD-IQ4_NL / AD-NVFP4 | 19.68 GB | 21.35 GB | 24 GB GPU |
| AD-Q2_0_L | 15.55 GB | 17.22 GB | 24 GB Mac |
| **AD-Q2_0_M** | **13.57 GB** | **15.24 GB** | **16 GB GPU** ("it is tight") |
| BF16 reference | 65.85 GB | 67.52 GB | H100 80 GB |

NVIDIA's own SALM configuration guide starts its GPU table at **24 GB**. There is no 8 GB or 12 GB
row, and 16 GB only appears in a community note that calls it tight.

The killer is not VRAM, it is **system RAM**. MoE offloading (`-ngl` / expert-offload) works by
keeping attention and shared weights on the GPU and paging experts from system memory. That needs
the weights to *exist* in RAM: 15.24 GB of weights against 15.20 GB of total RAM, of which Windows
takes several GB. There is no configuration — no quant, no offload split, no `mmap` trick — that
puts 15.24 GB into a machine with ~11 GB of usable RAM.

Consequence: **model A cannot run locally on this machine at any precision.** The only local
options are a bigger box (24 GB GPU for the 4-bit build, 16 GB GPU *and* 32 GB RAM for the 2-bit
build) or a hosted endpoint.

### 1.4 ONNX status (verified negative)

- The model card lists vLLM 0.32, SGLang-Omni, HF Transformers, and GGML. **No TensorRT, no ONNX.**
- `NeMo-Speech.cpp` conversion (`convert_model.py --architecture salm`) writes **GGUF only**.
- There is no community ONNX port, and unlike the 0.6B sibling there is no plausible one: the graph
  is a Mamba-2 SSM state space + routed MoE + a second (encoder) graph + CTC + an MTP draft head.
  ONNX Runtime can express that on paper; nobody has, and it would not fit the box anyway.

Runtime reality check for a future Windows build: `NeMo-Speech.cpp` **does** publish a prebuilt
`nemo-speech-0.3.0-windows-x86_64-cuda.zip` (508.6 MB, 2026-10-30). That matters because this repo
has no MSVC toolchain (C-TDEV-1), so "build it from source" was never an option — but it is moot
here since the model does not fit.

---

## 2. Quantization — what is real, and the TurboQuant correction

He asked specifically about TurboQuant and about "10x smaller at 90% quality". Splitting the two:

### 2.1 TurboQuant is not weight quantization

Verified from five independent write-ups of the same paper: **TurboQuant** (Google Research,
ICLR 2026) is a **KV-cache** method — PolarQuant (polar-coordinate rotation + scalar quantization)
plus QJL (1-bit residual correction) — compressing cached K/V vectors to ~3 bits, ~6x cache
reduction, near-lossless. There is an `mlx-lm` issue tracking a port.

It does **not** touch the 34 B of weights. For this decision it buys nothing: our wall is weight
residency, not cache size. (For a *long-context* local LLM it would be genuinely interesting —
worth remembering for the polish-model track, not for the transcribe model.)

### 2.2 What actually exists for shrinking weights

| Technique | What it compresses | Status here |
|---|---|---|
| NVFP4 (Blackwell-native 4-bit float, block-32) | weights | Shipped by NVIDIA for model A; RTX 5060 is Blackwell so the *format* is supported. 19.68 GB — still 4x too big. |
| MXFP4 (OCP open 4-bit float) | weights | Same class, same size class. |
| IQ4_NL / Q5_0_XL / Q2_0 + importance matrix | weights | AtomicChat's builds. **The imatrix is text-only** — `llama-imatrix` cannot feed audio, so audio-position activations are not represented. Below 4 bits the quantizer choice dominates: stock Q2_0 cost +3.5 WER English and +14…25 on German/French/Spanish; their imatrix-weighted Q2_0 recovered it. |
| AWQ / GPTQ | weights | Activation-aware 4-bit; needs calibration data and a torch pipeline. No released build for model A. |
| Rotation-based (QuaRot / SpinQuant) | weights + activations | Strong at 4-bit, but research-grade tooling, torch-bound. |
| QAT (quantization-aware training) | weights | The only path that genuinely holds quality at ≤3 bits. Needs NVIDIA to do it, not us. |

### 2.3 The "10x at 90% quality" claim

Directionally true for **LLMs at 4-bit** (~4x), and roughly true for 8-bit (~2x). 10x is 3.2-bit
average, which is where quality falls off a cliff *unless* QAT or a rotation method is used, and
even then it is per-model. For an encoder+MoE+SSM speech model, the measured curve is the table in
§1.3: 4-bit is within noise, 2-bit costs real WER on non-English.

**The honest conclusion:** quantization is a *memory* lever, not a *fit* lever. It moved model A
from 65.85 GB to 13.57 GB — a 4.8x win that still lands 4 GB above this machine's total RAM.

---

## 3. The model that actually fits — and it already speaks Egyptian Arabic

This is the finding worth the session. Buried one level down from the model he linked:

### 3.1 `nvidia/nemotron-3.5-asr-streaming-0.6b`

- 600 M params, Cache-Aware FastConformer-24 + RNNT + language-ID prompt conditioning.
- Released 2026-06-04; **691,234 downloads, 1,249 likes** — i.e. the community already settled on it.
- **Arabic (ar-AR) is in the top "Transcription-ready" tier** (19 locales out of 40), not the bottom.
  FLEURS Arabic WER 12.03 at the 1.12 s setting.
- **Native punctuation and capitalisation** — this alone beats the current regex pass in
  `ai_enhancement.py`.
- Chunk sizes 80 / 160 / 320 / 560 / 1120 ms (`att_context_size = [56, N]`).
- Licence OpenMDW-1.1.
- **No instruction following.** It is an ASR model with a language prompt, not a chat model. Polish /
  expand / shorten stays a *second* model — the two-model plan is correct.

Sizes: 600 M → ~1.2 GB FP16, ~600 MB INT8. Fits an 8 GB card with room to spare.

### 3.2 ONNX builds already exist

Community ports, verified present on the Hub:

- `onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4` (2,093 downloads) — `encoder.onnx` +
  `decoder.onnx` + `joint.onnx`, i.e. the RNNT triad split the way ORT wants it.
- `soniqo/…-ONNX-FP16`, `soniqo/…-ONNX-INT8`
- `pantinor/…-onnx`, `pantinor/…-int8-sherpa` (sherpa-onnx packaging)
- `smcleod/…-int8`

That is the same shape as the existing Parakeet backend: encoder / decoder / joiner ONNX + ORT.
No new runtime, no new dependency class.

### 3.3 The Egyptian-Arabic adapter

`Abdelkareem/Ara-nemotron-3.5-asr-streaming-0.6b` — **an `arz` (Egyptian Arabic) LinearAdapter
fine-tune of exactly that 0.6B base**, CC-BY-4.0, tags `arabic` + `egyptian-arabic` +
`streaming-asr`, 600 M base frozen, adapter dim 64, 16 kHz, Arabic-script output with common
punctuation.

This is the closest existing artefact to his actual dictation style. Caveats, stated plainly:
it is an *adapter* (NeMo format), so it needs merging into the encoder before an ONNX export; it
was not trained for Arabic↔English code-switching specifically; and 61 downloads means nobody has
stress-tested it. It is a lead, not a solution.

### 3.4 What this means for the architecture

| Need | Model | Fits 8 GB | ONNX | Arabic |
|---|---|---|---|---|
| Transcribe mixed AR/EN, keep the mixture | nemotron-3.5-asr-streaming-0.6b (+arz adapter) | yes | yes (community) | ar-AR tier 1 |
| Polish / expand / shorten / grammar | small local chat LLM (GGUF via llama.cpp-style binary, per ADR-0027) | yes | n/a (native GGML) | weak at 1–3 B; honest limit |
| Speak the reply | see §4 | — | — | — |

The 30B dream — one model, transcription *and* instruction-shaped post-processing — is real but
lives on an H100. The 0.6B + small-LLM split lives on his desk. ADR-0027 already picked that shape
for the *voice loop*; this is the same shape applied to dictation polish.

---

## 4. Model B — Edge0/Audio8-TTS-Realistic-0.6b

### 4.1 Verified facts

- **601,159,424** main-model params (codec excluded). DualAR, inspired by Fish Audio S2 Pro:
  slow AR predicts one semantic token per frame, fast AR predicts that frame's 10 codebooks.
- Codec: 44.1 kHz, 2048 samples/frame, ~21.5 frames/s. Bundled as `codec.pth` (1,349.9 MB);
  `model.safetensors` 1,202.3 MB. **~2.55 GB on disk.**
- **23 languages**, Arabic added in this release. Zero-shot voice cloning from reference audio +
  transcript. Apache-2.0. arXiv 2610.14776.
- Quality, Arabic: **CV3 WER 21.098 %**, SIM 0.612; **MiniMax CER 2.403 %**, SIM 0.704. The two
  suites disagree by an order of magnitude — treat Arabic as "supported, uneven". The card itself
  says "the support list is not a claim of equal quality across languages".
- Loading requires `trust_remote_code=True`, `torch>=2.5`, `torchaudio`, `transformers 4.57.x`.
  The card's own install line is a torch install.

### 4.2 The three blockers, in order of cost

1. **Torch.** ADR-0027 is explicit: the project is torch-free (Phase 1c), and a local model "MUST
   NOT reintroduce torch/transformers into the sidecar". Audio8 as shipped is a torch checkpoint
   with custom remote code. That is not a preference, it is a standing decision.
2. **No ONNX.** Nothing on the card, nothing on the Hub. And this is the hard one: a 10-codebook
   autoregressive decode with a fast-AR KV cache per frame is the least ONNX-friendly shape a
   speech model can have. It is exportable in principle (fixed-length unroll, cache as graph
   inputs) — the way Whisper's decoder is — but it is a genuine engineering project, not a
   `torch.onnx.export` call. The one community write-up I found on exporting Audio8 to ONNX covers
   the **0.1B preview**, not this model, and it is a low-authority blog post — treat as *suspected*.
3. **Budget.** ADR-0027 sets TTS ≤ 1 GB. Audio8 is 2.55 GB, and the codec alone is 1.35 GB. The
   decision was Piper (~61 MB) / Kokoro (~341 MB). Audio8 is 2.5x over the ceiling before the
   runtime is counted.

### 4.3 The alternative already inside the runtime we would add anyway

`NeMo-Speech.cpp` ships a **TTS component** (MagpieTTS + NanoCodec) and even a `cuda-s2s` VoiceChat
preset with a realtime WebSocket server. If the 0.6B ASR goes in via that runtime, speech output
arrives as the same binary, same licence family, no torch, no ONNX export of an AR codec loop.

Unverified: **whether MagpieTTS covers Arabic.** I did not find a language list, and its known
tuning work is English-centric. Do not assume it does. If it does not, the honest options are
(a) Kokoro/Piper for the languages they cover and no Arabic voice, or (b) accept a torch pack for
Audio8 as an *isolated optional* dependency — which contradicts ADR-0027 and needs his explicit
reversal, not my judgement call.

---

## 5. Integration cost against this codebase

- ASR backends implement the `AsrBackend` protocol in `voice_typer/server/asr/registry.py`
  (`is_loaded`, `device_info`, load/unload, `transcribe`), registered through
  `voice_typer/server/asr_registry.py`. Parakeet and Qwen3-ASR already prove the ONNX shape.
- New engines must ship as **on-demand packs** (ADR-0026 / `docs/plan-runtime-pack-split.md`), never
  in the base installer. A 600 MB INT8 encoder pack is in budget; a 15 GB one is not shippable at
  all, which is a second, independent reason model A is out.
- Post-processing seam already exists: `ai_enhancement.py` (regex rules, 231 lines),
  `dictation_pipeline/enhancement_steps.py`, and `llm_polish.py` (cloud, consent-gated, OpenAI-
  compatible, `MAX_INPUT_CHARS = 8000`). A local polish model is a new backend behind the same
  seam — not a new pipeline.
- `C-TRANS-1` means live partials are forbidden, so streaming ASR buys nothing for dictation. It
  does help media transcription latency, where chunking already exists.

---

## 6. Recommendation

1. **Drop model A for local use.** Not "revisit with a better quant" — the floor (15.24 GB) exceeds
   the machine (15.20 GB RAM). If it is ever wanted, it is a cloud/NIM endpoint or a 24 GB GPU.
2. **Prototype `nemotron-3.5-asr-streaming-0.6b` (INT8 or FP16 ONNX) as a third ASR backend.**
   It is the only candidate that is simultaneously: Arabic tier-1, ONNX-native in shape, ~600 MB,
   punctuating, and OpenMDW-licensed. Benchmark it against the current Whisper/Parakeet pair on his
   own `dictations-examples.md` recordings — Arabic-heavy, English technical terms inline.
3. **Treat the `arz` adapter as a separate experiment**, not a dependency. Merge → export → measure.
   If it moves Egyptian-dialect WER meaningfully, it justifies the merge tooling.
4. **Keep polish as a second model.** One model doing both jobs at 600 M does not exist; the 30B
   that does is out of reach. The realistic local polish model is 1–3 B GGUF, and Arabic quality
   there will be mediocre — say so up front rather than discovering it in QA.
5. **Audio8 TTS: no, not as specified.** It is 2.5 GB, torch-only, no ONNX, over the ADR-0027
   budget, and its Arabic scores are uneven. If spoken replies are wanted now, the NeMo-Speech.cpp
   TTS path is the one that costs no new dependency — *after* confirming its Arabic coverage.
6. **Do not spend time on TurboQuant** for this problem. It compresses KV cache. Our wall is
   weights. (It is worth a look later for long-context local polish.)

---

## 7. What I did not verify

- Whether MagpieTTS supports Arabic (no language list found).
- Whether the `arz` adapter's reported quality is real (61 downloads, no independent eval).
- Whether Audio8 0.6B's DualAR decodes under ONNX in practice (only the 0.1B preview has a
  community write-up, and it is low authority).
- Arabic instruction-following quality of model A — untested by anyone, evaluated in English only.
- Whether the 0.6B streaming model handles Arabic↔English code-switching as well as it handles
  monolingual Arabic. The 30B card ticks "code-switching" for Arabic; the 0.6B card does not say.

---

## 8. Sources

- https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B
- https://huggingface.co/AtomicChat/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B-GGUF
- https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/salm/configuration.md
- https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/salm/models.md
- https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/build.md
- https://github.com/NVIDIA/NeMo-Speech.cpp/releases/tag/v0.3.0
- https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b
- https://huggingface.co/Abdelkareem/Ara-nemotron-3.5-asr-streaming-0.6b
- https://huggingface.co/onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4
- https://huggingface.co/Edge0/Audio8-TTS-Realistic-0.6b
- https://turbo-quant.com/ (TurboQuant = KV cache, PolarQuant + QJL, ICLR 2026)
- https://github.com/ml-explore/mlx-lm/issues/1060 (port tracking)
- Local: `docs/adr/0027-voice-only-loop-cua-deferred.md`, `voice_typer/server/llm_polish.py`,
  `voice_typer/server/ai_enhancement.py`, `dictations-examples.md`
