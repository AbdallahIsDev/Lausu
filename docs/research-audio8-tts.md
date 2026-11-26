# Research: Audio8-TTS-Realistic-0.6B

Date: 2026-10-31.

## 1. Model B — Edge0/Audio8-TTS-Realistic-0.6b

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

## 2. Integration cost against this codebase

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

## 3. Recommendation

1. **Treat the `arz` adapter as a separate experiment**, not a dependency. Merge → export → measure.
   If it moves Egyptian-dialect WER meaningfully, it justifies the merge tooling.
2. **Keep polish as a second model.** One model doing both jobs at 600 M does not exist; the 30B
   that does is out of reach. The realistic local polish model is 1–3 B GGUF, and Arabic quality
   there will be mediocre — say so up front rather than discovering it in QA.
3. **Audio8 TTS: no, not as specified.** It is 2.5 GB, torch-only, no ONNX, over the ADR-0027
   budget, and its Arabic scores are uneven. If spoken replies are wanted now, the NeMo-Speech.cpp
   TTS path is the one that costs no new dependency — *after* confirming its Arabic coverage.

---

## 4. What I did not verify

- Whether MagpieTTS supports Arabic (no language list found).
- Whether the `arz` adapter's reported quality is real (61 downloads, no independent eval).
- Whether Audio8 0.6B's DualAR decodes under ONNX in practice (only the 0.1B preview has a
  community write-up, and it is low authority).
- Arabic instruction-following quality of model A — untested by anyone, evaluated in English only.
- Whether the 0.6B streaming model handles Arabic↔English code-switching as well as it handles
  monolingual Arabic. The 30B card ticks "code-switching" for Arabic; the 0.6B card does not say.

---

## 5. Sources

- https://huggingface.co/Edge0/Audio8-TTS-Realistic-0.6b
- https://github.com/ml-explore/mlx-lm/issues/1060 (port tracking)
- Local: `docs/adr/0027-voice-only-loop-cua-deferred.md`, `voice_typer/server/llm_polish.py`,
  `voice_typer/server/ai_enhancement.py`, `dictations-examples.md`
