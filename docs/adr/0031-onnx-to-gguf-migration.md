# ADR-0031: ONNX-to-GGUF migration — research only, no decision yet

## Status

Proposed (spike done, decision pending)

---

## SPIKE RESULTS (plain English, read this first)

This round measured, outside the repo, whether the owner's chosen GGUF direction is viable.  
**No application code changed.** All models, binaries, transcripts and logs live under `C:\Users\11\gguf-spike\`.

**What we learned, plainly:**

1. The "about 677 MB" GGUF is **not Parakeet Ultra**. It is `fluid-speech-pro-q8_0.gguf` (676,653,088 bytes) from `cstr/fluid-speech-pro-GGUF`, built on Ultra but with an extra residual block and targeting CrispASR, not transcribe.cpp. It is **not** the file to ship. (VERIFIED — Firecrawl scrape of the model card and Files tab; Hugging Face JSON API.)
2. Exactly one clear file meets all three owner criteria — fine-tuned Ultra, 8-bit/Q8_0, transcribe.cpp runtime: `handy-computer/parakeet-ultra-gguf/parakeet-ultra-Q8_0.gguf`, 740,363,168 bytes. It was downloaded and tested. (VERIFIED — Firecrawl scrape of model card and Files tab; exact byte size from the Hugging Face JSON API.)
3. On this machine, with the same 8:00.49 audio and 8 threads, CPU wall time was ~29 s for installed ONNX and ~27 s for GGUF; GGUF used more peak RAM (1.80 GB vs 1.02 GB). Vulkan GGUF was much faster on warm run (4.98 s vs 27 s CPU). These are speed/memory facts only — **no WER and no quality conclusion**, because the ONNX file is non-fine-tuned Ultra and the GGUF file is fine-tuned Ultra with different weights. (VERIFIED — measured runs in §11.)
4. ONNX GPU is **NOT RUN**. The app uses an ONNX Runtime CPU wheel with no CUDA provider. Installing the GPU wheel in a throwaway venv exposed the real dependency error: `onnxruntime_providers_cuda.dll` depends on `cublasLt64_13.dll`, which is missing; ORT docs require CUDA 13.0 + cuDNN 9.x. NuGet's GPU Windows package supplied `onnxruntime_providers_cuda.dll` but still not the CUDA/cuDNN runtime DLLs. No fix under the 500 MB-per-file rule was completed, so there is no ONNX GPU number. (VERIFIED — §12.)
5. The hallucination gate needs `no_speech_prob`, `avg_logprob`, `first_segment_start`, and `last_segment_end`; transcribe.cpp exposes segment `t0_ms`/`t1_ms`/`text` but **not** those confidence fields. This is the largest integration risk. (VERIFIED — §13.)
6. Installer sizes are partly measured and partly unknown: the shipped NSIS payload is 243.47 MiB, dominated by a 128.27 MiB ffmpeg and a 103.04 MiB one-file Python sidecar. We cannot measure how many bytes of that sidecar are onnxruntime/CTranslate2/PyAV because it is one compressed executable. Added transcribe.cpp binaries are measured: 53.63 MiB CPU+Vulkan, 237.38 MiB CUDA. (VERIFIED/UNVERIFIED mix — §14.)

**Still unknown:** exact sidecar bytes saved by removing ORT/CT2/PyAV; whether llama.cpp and transcribe.cpp can share ggml DLLs; whether a CUDA 13/cuDNN 9 runtime can be supplied with acceptable per-file sizes; quality parity on the same weights.

**Owner decisions still required:** (1) accept the confidence-field gap and change the gate, or require a runtime that emits those fields; (2) bundle transcribe.cpp, download on first use, or make it optional; (3) CPU/Vulkan/CUDA target; (4) whether to purge old GitHub history after junk removal; (5) whether to accept higher peak RAM on CPU. Facts and options are in §15.

---

## 0. Plain English (owner read this first)

**What this is.** You asked whether we can move our local speech-to-text away from the current
setup (`faster-whisper` + ONNX-based helpers) to the GGUF format that llama.cpp-style tools use.
This record is **research only**. It does not change code, does not pick a winner, and does not
commit us to a migration. Its job is to lay out the real facts so the decision is made on evidence
instead of assumptions. (VERIFIED — this file itself, `## Status`.)

**The big surprise, stated plainly.** The phrase "ONNX-to-GGUF" is only half accurate, and the
obvious target is not what people assume:

- Our Whisper transcription does **not** run on ONNX today. It runs on `faster-whisper`, which
  uses CTranslate2 and stores weights in **CTranslate2 format**, not ONNX. ONNX Runtime is used
  elsewhere: voice detection, noise filters, and the two non-Whisper speech models. (VERIFIED —
  `voice_typer/worker/whisper/engine.py:76,201-243`; `voice_typer/server/model_registry.py:137,161,184`;
  https://github.com/SYSTRAN/faster-whisper/blob/master/README.md)
- **whisper.cpp does NOT use GGUF.** Its own docs say models are converted to a "custom `ggml`
  format" in `.bin` files, and the maintainer stated in 2024 that "whisper.cpp does not support
  the GGUF file format yet"; a 2026 comment on that same thread still asks whether GGUF support is
  planned, with no answer in the thread. (VERIFIED —
  https://github.com/ggml-org/whisper.cpp/blob/master/models/README.md ;
  https://github.com/ggml-org/whisper.cpp/discussions/2578)
- The runner that **does** use GGUF for speech is a newer project, **transcribe.cpp** (MIT), which
  is explicitly described as "llama.cpp for STT models". (VERIFIED —
  https://blog.mozilla.ai/announcing-transcribe-cpp ;
  https://github.com/handy-computer/transcribe.cpp)

**Why consider changing at all.** Today's Windows bundle still carries three things we would rather
not ship: PyAV (BSD-3-Clause Python wrapper) with its bundled FFmpeg DLLs that report
`LGPL version 3 or later`, `faster-whisper`/CTranslate2, and those DLLs. A CI gate exists to catch
the DLLs but is deliberately left soft (`ENFORCE_NO_GPL_DLLS` defaults to `0`), so the warning is
informational and the build passes. (VERIFIED — `docs/THIRD_PARTY_NOTICES.md:32-71`;
`scripts/verify_windows_bundle.py:23-26,389-398`; `tests/tauri/test_windows_build_workflow.py:104`)

**What research favors (not a decision).** If the owner ever wants a GGUF-based local ASR,
**transcribe.cpp shipped as a separate executable beside the worker** is the best fit on paper:
it genuinely uses GGUF, is MIT-licensed, runs on Windows/macOS/Linux with CPU + Metal/Vulkan/CUDA,
and can consume the `.bin` models whisper.cpp used so the change can be incremental. It does
**not** remove the need for ONNX Runtime, because VAD, the noise filters, Parakeet and Qwen3-ASR
still use it. (VERIFIED — https://github.com/handy-computer/transcribe.cpp ;
`voice_typer/server/vad.py:17,143`; `voice_typer/server/audio_filters/gtcrn_backend.py:64`;
`voice_typer/server/audio_filters/dpdfnet_backend.py:171`;
`voice_typer/server/parakeet_engine/_load.py:68`; `voice_typer/server/qwen_onnx_model.py:226`)

**What would need an explicit owner decision first:** whether a migration is worth doing at all,
which runner, whether to keep Parakeet/Qwen as separate registered models, and whether the size /
license win justifies the engineering cost. See §8. (VERIFIED — this is a list of unresolved
choices, not a claim of fact.)

---

## 1. Evidence rules and how to read this record

- **VERIFIED** = checked against primary source in this repo (`file:line`) or an upstream URL
  fetched during this research. A URL is given for every external claim. (VERIFIED — method used
  throughout this document.)
- **UNVERIFIED** = no primary source obtained; the reason is stated inline. Do not treat these as
  facts. (VERIFIED — method used throughout this document.)
- Code line numbers are from checkout `3b7352ba8`; they drift, so re-read before acting.
  (VERIFIED — `git rev-parse --short HEAD` returned `3b7352ba8`.)
- This ADR does not touch ADR-0021 (dirty from another session) or any code, workflow, test, or
  index other than the ADR index row. (VERIFIED — task scope given to this agent; no files other
  than this ADR and `docs/adr/README.md` were written.)

---

## 2. CURRENT STATE (verified in code)

### 2.1 Where transcription actually runs

- The slim-core sidecar does **no** Whisper inference. Its registry slot is
  `voice_typer/server/worker_backed_asr.py:1-16`, whose docstring says it "runs ZERO inference in
  this process" and forwards every call to the runtime-pack worker over the C2/C3 bridge.
  (VERIFIED — `voice_typer/server/worker_backed_asr.py:1-16,42-53`)
- The real Whisper model load and `transcribe()` live in the **worker**, in
  `voice_typer/worker/whisper/engine.py`: `load()` at line 160, actual `WhisperModel(...)`
  construction at lines 201-243, `transcribe()` at line 360, `transcribe_words()` at line 434.
  (VERIFIED — `voice_typer/worker/whisper/engine.py:160,201-243,360,434`)
- `faster_whisper` and `ctranslate2` are deliberately excluded from the sidecar freeze; the
  engine module's header says no such import remains under `voice_typer/server`. (VERIFIED —
  `voice_typer/worker/whisper/engine.py:1-9`; `voice_typer/server/worker_backed_asr.py:6-8`)
- Word-timestamps/streaming go through the worker session, not an in-process engine. (VERIFIED —
  `voice_typer/server/worker_backed_asr.py:13-16`)
- The worker decodes media to 16 kHz mono WAV itself (`_load_wav_float32`, `_resample_to_16k`),
  using the shared scipy resampler. (VERIFIED — `voice_typer/worker/_transcribe.py:19-21,24-63`)

### 2.2 Models shipped / used

- **No ASR model weights are bundled in the installer.** Every registered model is marked
  `network_behavior="downloads-on-first-use-consent-gated"`, and `load()` is documented
  "NEVER downloads" — weights live in a Hugging Face cache after an explicit Models-page
  download. (VERIFIED — `voice_typer/server/model_registry.py:65,87,110,138,162,185`;
  `voice_typer/worker/whisper/engine.py:161`; `voice_typer/server/transcription_download.py:125-180`)
- Whisper-family sizes/refs in the registry: `tiny` → `Systran/faster-whisper-tiny` (75 MB),
  `large-v3` → `Systran/faster-whisper-large-v3` (3000 MB), `large-v3-turbo` →
  `dropbox-dash/faster-whisper-large-v3-turbo` (1618 MB). The default is deliberately "no model
  selected" (`DEFAULT_MODEL_SIZE = ""`). (VERIFIED —
  `voice_typer/server/model_registry.py:47-50,52-119`)
- Non-Whisper ASR: `parakeet` (Parakeet TDT 0.6b Ultra, **ONNX int8**, 25 European languages,
  Arabic excluded) → `Masterx/parakeet-tdt-0.6b-ultra-onnx`; `qwen3-1.7b` and `qwen3-0.6b`
  (Qwen3-ASR, **ONNX int4**, 30 languages) → `andrewleech/qwen3-asr-*.onnx`. (VERIFIED —
  `voice_typer/server/model_registry.py:121-189`; `docs/adr/0030-one-asr-model-and-text-translator.md:69-73`)
- Noise suppression: **DPDFNet** (default, "DeepFilterNet2 + dual-path RNN, 16 kHz streaming
  ONNX"), **RNNoise** (lightweight; a C library, not ONNX), **GTCRN** (older neural denoiser,
  also ONNX), and None. (VERIFIED — `voice_typer/server/config/_schema.py:418-424`;
  `voice_typer/server/audio_filters/dpdfnet_backend.py:171`;
  `voice_typer/server/audio_filters/gtcrn_backend.py:64`;
  `voice_typer/server/audio_filters/noise_suppressor.py` via `voice_typer/server/media_ingest/selfcheck.py:98-105`)
- Silero VAD runs through `onnxruntime.InferenceSession`; the module docstring says this keeps the
  app fully local and the session stateless. (VERIFIED — `voice_typer/server/vad.py:17,25,108,143`)
- The already-shipped **text translator** uses a GGUF model (`IndexTeam/Index-Translate-2B-GGUF`
  Q4_K_M) via a separately shipped `llama-server` binary — proof that the app already has a
  "GGUF model + sibling executable" pattern to learn from. (VERIFIED —
  `docs/adr/0030-one-asr-model-and-text-translator.md:108-139`)

### 2.3 Libraries and their roles

| Library | Role | VERIFIED evidence |
|---|---|---|
| `faster-whisper` (>=1.0,<2.0) | Primary Whisper ASR; CTranslate2 backend | `pyproject.toml:72-77`; https://github.com/SYSTRAN/faster-whisper |
| CTranslate2 | The actual inference engine; weights in CT2 format, not ONNX/GGUF | https://github.com/SYSTRAN/faster-whisper/blob/master/README.md ; https://github.com/opennmt/ctranslate2 |
| `onnxruntime` | Silero VAD, DPDFNet, GTCRN, Parakeet, Qwen3-ASR, GPU memory probe | `voice_typer/server/vad.py:143`; `voice_typer/server/audio_filters/{dpdfnet,gtcrn}_backend.py`; `voice_typer/server/parakeet_engine/_load.py:68`; `voice_typer/server/qwen_onnx_model.py:226`; `voice_typer/server/resource_probe.py:52-66` |
| PyAV (`av>=17,<18`) | Was media decode; **no longer used for decode**, but `faster_whisper` imports `av` at module scope so the wheel and DLLs still ship | `pyproject.toml:105-112`; `docs/THIRD_PARTY_NOTICES.md:32-41` |
| scipy | Live mic resample + filter chain; not movable without VAD redesign | `pyproject.toml:98-104`; `docs/adr/0026-slim-core-installer-80mb-target.md:29-35` |
| numpy, sounddevice | Mic capture, levels, VAD math | `pyproject.toml:78-97`; `docs/adr/0026-slim-core-installer-80mb-target.md:33-35` |
| `yt-dlp`, `yt-dlp-ejs` | URL download / EJS solver for media ingest | `pyproject.toml:113-119`; `docs/THIRD_PARTY_NOTICES.md:17-31` |
| FFmpeg (separate LGPL build) | Media decode now uses a separately shipped executable, not PyAV | `scripts/ffmpeg-lgpl-win64.json:2-12`; `voice_typer/server/media_ingest/ffmpeg_binaries.py:157-163` |

### 2.4 Model load / download / cache / installer paths

- Download IPC command is `download_model`; models are verified with SHA-256 / size and stored in
  Hugging Face cache layout. (VERIFIED — `docs/adr/0030-one-asr-model-and-text-translator.md:124-128`;
  `voice_typer/server/transcription_download.py:65-75,216-269`)
- Runtime resolution passes the canonical `repo_id` and pinned `revision` so `WhisperModel`
  resolves **our** downloaded snapshot rather than faster-whisper's own alias map, with
  `local_files_only=True` (never auto-download at inference time). (VERIFIED —
  `voice_typer/worker/whisper/engine.py:228-243`; `voice_typer/server/transcription_download.py:65-75`)
- Device resolution: CUDA + int8/float16 attempted first, then CPU int8, then `tiny` fallbacks.
  (VERIFIED — `voice_typer/worker/whisper/engine.py:304-313`)
- The translator already resolves its sibling `llama-server` via `_shipped_dirs()`: exe-adjacent,
  `resources/`, parent chain, onefile extraction — with writable app-data last. (VERIFIED —
  `docs/adr/0030-one-asr-model-and-text-translator.md:131-134`;
  `voice_typer/server/media_ingest/ffmpeg_binaries.py:100-117`)

### 2.5 What changed in rounds 1–24 (and what did not)

- Media decoding moved off PyAV to a separately shipped **LGPL FFmpeg** build; the pinned manifest
  is `scripts/ffmpeg-lgpl-win64.json` with version `n9.0.2-61-gd59078794d-20261120`, SHA-256
  `814c62c3...`, `license: LGPL-3.0-or-later`, and forbidden config tokens `--enable-gpl`,
  `--enable-nonfree`, `--enable-libx264`, `--enable-libx265`. (VERIFIED —
  `scripts/ffmpeg-lgpl-win64.json:1-29`)
- `scripts/verify_windows_bundle.py` is a post-build gate over bundle contents, the frozen
  sidecar self-check, and a single soft switch. (VERIFIED —
  `scripts/verify_windows_bundle.py:20-26`; `review.md:563`)
- **BUT** PyAV, `faster-whisper` and the GPL-linked DLLs are still bundled. PyAV is retained only
  because `faster_whisper` imports it at module scope. (VERIFIED —
  `docs/THIRD_PARTY_NOTICES.md:32-41`; `pyproject.toml:72-77,105-112`)
- `ENFORCE_NO_GPL_DLLS` is still `0` by default; the workflow declares
  `"${{ vars.ENFORCE_NO_GPL_DLLS || '0' }}"`, and the gate prints a warning with exit 0 at `0`
  while `1` makes any sighting a hard failure. The round that removes PyAV must set it to `1`.
  (VERIFIED — `tests/tauri/test_windows_build_workflow.py:104`;
  `scripts/verify_windows_bundle.py:23-26,389-398`; `review.md:563`)
- The frozen-sidecar `--self-check` requires five grep-able markers — `frozen-build`,
  `no-path-fallback`, `bundled-ffmpeg`, `decode-samples=16000`, `rnnoise-active` — and fails closed
  on an empty/missing onefile extraction dir under `ENFORCE_NO_GPL_DLLS=1`. (VERIFIED —
  `voice_typer/server/media_ingest/selfcheck.py:13-19,107-117`; `review.md:579`)
- A real Nuitka 2.8.10 onefile probe (four launch modes) proved `sys.executable` points **inside**
  the cached extraction dir while `__compiled__.containing_dir` points at the original exe, so
  `bundled_bin_dir()` prefers the latter and frozen builds have **no PATH fallback**. (VERIFIED —
  `voice_typer/server/media_ingest/ffmpeg_binaries.py:71-97,142-154`; `review.md:577-579`)
- The freeze wrapper is `scripts/build/nuitka_freeze.sh`, dispatching to per-platform scripts;
  its header still documents `--include-package` for `faster_whisper`, `ctranslate2` and
  `--onefile-tempdir-spec`. (VERIFIED — `scripts/build/nuitka_freeze.sh:3-23,32-36,63-64`)
- Known latent issue carried forward: `voice_typer/server/autostart/tauri_spawn.py:196` still uses
  `Path(sys.executable).resolve().parent` for its manifest lookup — the same onefile mistake the
  ffmpeg resolver already fixed. (VERIFIED —
  `voice_typer/server/autostart/tauri_spawn.py:194-196`; `review.md:581`)

### 2.6 Other code depending on onnxruntime / faster-whisper

- onnxruntime is imported in: `voice_typer/server/vad.py:108,143`,
  `voice_typer/server/audio_filters/gtcrn_backend.py:64,143`,
  `voice_typer/server/audio_filters/dpdfnet_backend.py:171,275`,
  `voice_typer/server/parakeet_engine/_load.py:68,94`,
  `voice_typer/server/qwen_onnx_model.py:226`,
  `voice_typer/server/model_providers/local_onnx/client.py:117`,
  `voice_typer/server/resource_probe.py:52-66`,
  `voice_typer/server/asr_utils.py:43-45`,
  `voice_typer/server/cuda_install/{paths,activation}.py`. (VERIFIED — search of `voice_typer/`, cited lines)
- faster-whisper is confined to the worker path after the ADR-0025 C7 move; no
  `faster_whisper` import remains under `voice_typer/server`. (VERIFIED —
  `voice_typer/worker/whisper/engine.py:1-9`; `voice_typer/server/worker_backed_asr.py:6-8`)
- Consequence for the migration: **removing onnxruntime is a separate, larger project** from
  replacing the Whisper engine. (VERIFIED — derived from the import list above; this is an
  inference from code, not a claim about future feasibility.)

---

## 3. OPTIONS — GGUF-class Whisper runners

**Premise correction first (important).** "GGUF Whisper runner" describes only some projects.
The two most-linked names have different formats:

| Runner | Model format per upstream docs | License | Windows / macOS / Linux | GPU | Distribution | Last release |
|---|---|---|---|---|---|---|
| **whisper.cpp** (`ggml-org/whisper.cpp`) | **Custom `ggml` `.bin`, NOT GGUF** — docs: "converted to custom `ggml` format"; download script `download-ggml-model.sh`, converter `convert-pt-to-ggml.py`. Maintainer: "whisper.cpp does not support the GGUF file format yet." | MIT | Yes / Yes / Yes (+ iOS, Android, WASM, FreeBSD, Raspberry Pi) | Metal, Vulkan, CUDA, ROCm, OpenVINO, Ryzen AI NPU, others | Build from source (CMake); `whisper-server` = HTTP server with OAI-like API; bindings listed | v1.9.5, published 2026-10-06 |
| **transcribe.cpp** (`handy-computer/transcribe.cpp`) | **GGUF** — "Runs diverse STT model families via GGUF models on the ggml runtime"; pre-built GGUFs under `handy-computer` HF org; readme also documents whisper.cpp `.bin` compatibility | MIT (vendored ggml + miniz also MIT) | Yes / Yes / Yes | Metal (auto on Apple Silicon), Vulkan (Win/Linux), CUDA (Linux), ROCm/HIP (Linux), tinyBLAS CPU | Build from source (CMake); official Python / TypeScript / Rust / Swift bindings; `transcribe-cli`, `transcribe-quantize` | Announced 2026-06-30; v0.1.3 on 2026-07-12; v0.2.3 observed 2026-09-02. **Exact latest release date UNVERIFIED (GitHub releases API fetch failed during research).** |
| **llama.cpp** (`ggml-org/llama.cpp`) | **GGUF**, but for **LLM/VLM text**, not an ASR engine — README describes "LLM inference in C/C++" and its tools are `llama cli` / `llama serve` with GGUF models such as `ggml-org/Qwen3.5-0.8B-GGUF` | MIT | Yes / Yes / Yes | CUDA, HIP, Metal, Vulkan, SYCL, OpenCL, MUSA, others | Prebuilt binaries + source | v1.0.0, published 2026-11-13 |
| **PyAV / sherpa-onnx / other ONNX ASR** | ONNX, not GGUF — no migration to GGUF by definition | varies | varies | varies | varies | n/a |

Sources for the table (all VERIFIED):
- whisper.cpp README + models README: https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/README.md ;
  https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/models/README.md
- maintainer statement + 2026 follow-up: https://github.com/ggml-org/whisper.cpp/discussions/2578
- whisper.cpp release: https://api.github.com/repos/ggml-org/whisper.cpp/releases/latest
- transcribe.cpp README + repo metadata: https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/README.md ;
  https://github.com/handy-computer/transcribe.cpp
- transcribe.cpp announcement: https://blog.mozilla.ai/announcing-transcribe-cpp
- transcribe.cpp version observations (secondary, not primary): https://kompozy.io/reviews/transcribe-cpp ;
  https://github.com/jamditis/audiobud/issues/170
- llama.cpp README + release: https://raw.githubusercontent.com/ggml-org/llama.cpp/master/README.md ;
  https://api.github.com/repos/ggml-org/llama.cpp/releases/latest

**Notes on each runner:**

1. **whisper.cpp** — the mature reference. If the goal were merely "stop shipping PyAV/CT2", a
   whisper.cpp binary would work, but it would produce **`.bin` models, not GGUF**, so it would not
   satisfy a literal "GGUF" requirement. Its stated memory table is tiny 75 MiB / ~273 MB, base
   142 MiB / ~388 MB, small 466 MiB / ~852 MB, medium 1.5 GiB / ~2.1 GB, large 2.9 GiB / ~3.9 GB.
   (VERIFIED — https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/README.md)
2. **transcribe.cpp** — the only mainstream option that is actually **GGUF-first for speech** and
   supports our current model families (Whisper 12 variants, Parakeet including `parakeet-ultra`,
   Qwen3-ASR 0.6b/1.7b). Every published model is WER-validated against its reference; it reports
   segment timestamps and translate capability for Whisper. (VERIFIED —
   https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/README.md)
3. **llama.cpp** — relevant as the **already-shipped translator runtime** and as the origin of the
   GGUF format, but its own README does not present it as aWhisper/ASR runner. Using it for ASR
   would be a category error. (VERIFIED — https://raw.githubusercontent.com/ggml-org/llama.cpp/master/README.md)
4. **Other maintained options** — `pywhispercpp` / `whispercpp-kit` are Python bindings over
   whisper.cpp (MIT, PyPI 0.1.7 latest shown) and therefore inherit GGML `.bin`, not GGUF.
   (VERIFIED — https://pypi.org/project/whispercpp-kit). `moss-transcribe.cpp` is a narrow
   single-family MIT ggml/GGUF port (MOSS-Transcribe-Diarize), not a Whisper replacement.
   (VERIFIED — https://github.com/localai-org/moss-transcribe.cpp). A full survey of every
   GGUF ASR fork was **not** completed — **UNVERIFIED: time-boxed research; no claim of
   exhaustiveness is made.**

---

## 4. INTEGRATION SHAPES

Three shapes were considered. "Can we delete X?" refers to the shipped bundle, not the source
tree. All three assume the worker owns ASR (§2.1).

| | (a) Separate executable (ffmpeg / llama-server pattern) | (b) Python binding in the sidecar/worker | (c) Other: compile static library into the worker |
|---|---|---|---|
| **Freeze / installer changes** | Add binary to `externalBin` + manifest; no Nuitka `--include-package` for the engine. Reuse `_shipped_dirs()` resolution. (VERIFIED — `docs/adr/0030...:131-134`; `scripts/build/nuitka_freeze.sh:14-23`) | Add a binding wheel to the freeze (`--include-package`); more C-extension + Nuitka hidden-import risk. (VERIFIED — `scripts/build/nuitka_freeze.sh:19-21`; `pyproject.toml:109-112` shows the existing PyAV Cython shim workaround) | Native build step in the worker freeze; most invasive. (UNVERIFIED — no primary source for a working Nuitka + vendored ggml build in this repo.) |
| **Size impact** | Comparable to the 39 MB `llama-server` already shipped; GGUF Whisper base ~142 MiB, large-v3-turbo ~1.5 GiB per whisper.cpp's table. (VERIFIED — `docs/adr/0030...:119`; whisper.cpp README) | Binding is small but still pulls the ggml runtime; model size unchanged. (UNVERIFIED — no measured wheel size obtained.) | Same runtime, no duplicate wheel. (UNVERIFIED — no measurement.) |
| **Remove PyAV?** | Yes, once `faster_whisper` is gone — PyAV is retained only because `faster_whisper` imports it. (VERIFIED — `docs/THIRD_PARTY_NOTICES.md:32-36`) | Yes, same reason. (VERIFIED — same source) | Yes, same reason. (VERIFIED — same source) |
| **Remove faster-whisper / CT2?** | Yes for Whisper ASR; Parakeet/Qwen are separate engines and unaffected. (VERIFIED — `voice_typer/server/worker_backed_asr.py:10-13`) | Yes for Whisper ASR. (VERIFIED — same source) | Yes for Whisper ASR. (VERIFIED — same source) |
| **Remove onnxruntime?** | **No** — VAD, DPDFNet, GTCRN, Parakeet, Qwen3-ASR still import it. (VERIFIED — §2.6 line list) | No (same reason). (VERIFIED — same) | No (same reason). (VERIFIED — same) |
| **Effect on GPL-DLL gate** | Lets `ENFORCE_NO_GPL_DLLS=1` finally be set **once PyAV is actually removed**; the LGPL FFmpeg build stays (it is the compliant decoder). (VERIFIED — `scripts/verify_windows_bundle.py:23-26`; `review.md:563`) | Same. (VERIFIED — same) | Same. (VERIFIED — same) |
| **Frozen-path logic** | New sibling binary MUST resolve via `__compiled__.containing_dir`, never `sys.executable`; `_shipped_dirs()` already does this. `tauri_spawn.py:196` remains a latent bug to fix in the same change. (VERIFIED — `voice_typer/server/media_ingest/ffmpeg_binaries.py:71-97`; `review.md:577-581`) | No sibling binary, but binding data files still need the same onefile-aware base. (UNVERIFIED — no probe of a ggml binding under Nuitka.) | Same caveat. (UNVERIFIED — no probe.) |

**Shape (a) is the research favourite** because it mirrors two already-shipped patterns (LGPL
ffmpeg, `llama-server`), keeps C++ out of the Nuitka freeze, and preserves the worker boundary.
This is a **preference, not a decision** — see §8. (VERIFIED — the two shipped patterns cited
above; the preference is this document's reasoning.)

---

## 5. LICENSE COMPATIBILITY

- The app is `LicenseRef-PolyForm-Strict-1.0.0`, source-available, copyright 2026 Abdallah IsDev.
  (VERIFIED — `pyproject.toml:37-38`; `docs/THIRD_PARTY_NOTICES.md:7-15`)
- PolyForm Strict 1.0.0 is the most restrictive member of the suite: it removes permission to
  **distribute copies** and **make changes**, leaving only noncommercial use. (VERIFIED —
  https://polyformproject.org/licenses ; https://github.com/polyformproject/polyform-licenses/blob/1.0.0/README.md)
- MIT / BSD-3-Clause / Apache-2.0 components (whisper.cpp, transcribe.cpp, llama.cpp,
  CTranslate2, PyAV) can be bundled with a source-available app provided the copyright and
  permission notices are carried. (VERIFIED — https://github.com/handy-computer/transcribe.cpp ;
  https://github.com/opennmt/ctranslate2 ; `docs/THIRD_PARTY_NOTICES.md:32-41`. **UNVERIFIED:
  no legal opinion was obtained; this is a license-text reading, not legal advice.**)
- CTranslate2 is MIT, not Apache-2.0 — earlier guesses in conversation were wrong. (VERIFIED —
  https://github.com/opennmt/ctranslate2 "MIT license")
- ONNX Runtime: core is MIT, but some ONNX-adjacent components are Apache-2.0 and each wheel
  carries its own ThirdPartyNotices. (VERIFIED — https://github.com/microsoft/onnxruntime/issues/13892 ;
  https://github.com/MooreThreads/onnxruntime-musa/blob/master/LICENSE. **UNVERIFIED: the exact
  notice set of the specific pinned wheel was not inspected here.**)
- **LGPL FFmpeg** is already handled by an explicit notice + source-offer scheme: the manifest
  pins `source_offer_url`, `build_scripts_source_url` and `ffmpeg_source_url`, and forbids
  `--enable-gpl`/`--enable-nonfree`/x264/x265. (VERIFIED — `scripts/ffmpeg-lgpl-win64.json:13-25`;
  `docs/THIRD_PARTY_NOTICES.md:54-71`)
- **What goes in `THIRD_PARTY_NOTICES.md` for a migration:** add a section for the chosen runner
  (MIT text + copyright + URL), a section for its GGUF model weights with each model's own
  license (Whisper weights: OpenAI model card; Parakeet/Qwen: their cards), and keep the FFmpeg
  LGPL source offer intact. Remove the PyAV section only in the same round PyAV is actually
  removed. (VERIFIED — structure follows `docs/THIRD_PARTY_NOTICES.md:1-15,32-71`; the need for
  per-model license sections is a compliance inference, not legal advice.)
- **Source offers needed:** FFmpeg LGPL build scripts + exact source commit (already pinned);
  no source offer is required for MIT/BSD components beyond including their notices. (VERIFIED —
  `scripts/ffmpeg-lgpl-win64.json:20-25`. **UNVERIFIED: whether the owner's PolyForm Strict terms
  interact with LGPL "relinking" obligations for a closed distributable was not reviewed by
  counsel.**)

---

## 6. RISKS / UNKNOWNS

| Topic | Status | Detail |
|---|---|---|
| CPU quality / speed | **VERIFIED (upstream claim, not local benchmark)** | whisper.cpp publishes 2m05s small/CPU vs faster-whisper 2m37s (same audio, 8 threads); faster-whisper int8 1m42s. (https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/README.md) **UNVERIFIED: no local A/B on the owner's hardware or Arabic/English dictations was run for this ADR.** |
| Model conversion | **VERIFIED (docs)** | transcribe.cpp ships pre-built GGUFs and a `transcribe-quantize` tool (F16/Q8_0/Q6_K/Q5_K_M/Q4_K_M); Whisper GGUF conversion exists (e.g. `memoravox/whisper-large-gguf`). (https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/README.md ; https://huggingface.co/memoravox/whisper-large-gguf) **UNVERIFIED: numerical parity of any of these against our pinned CT2 snapshots was not measured.** |
| Language support | **VERIFIED** | Whisper GGUF variants include multilingual `whisper-large-v3` / `large-v3-turbo`; transcribe.cpp lists 12 Whisper variants plus Qwen3-ASR (30 languages incl. Arabic) and Parakeet. (same URLs; `docs/adr/0030...:69-73`) |
| Timestamp / segment compatibility | **VERIFIED (what the app consumes)** | The pipeline consumes `seg.text`, `seg.start`, `seg.end`, `seg.avg_logprob`, `seg.no_speech_prob`, `info.language`, `info.language_probability`, and for streaming `seg.words` with `word.word/start/end`. (VERIFIED — `voice_typer/server/transcription_result.py:217-239,265-283,360-399`; `voice_typer/server/streaming.WordTiming` via same file:349-398) **UNVERIFIED: whether transcribe.cpp's documented "segment timestamps" map 1:1 to these fields (especially per-segment logprobs / no_speech_prob used by the hallucination gate) — no header-level API inspection was completed.** This is the single biggest integration unknown. |
| Memory | **VERIFIED (upstream tables)** | whisper.cpp: base ~388 MB, small ~852 MB, large ~3.9 GB; our registry assigns 512–3072 MB VRAM per model. (whisper.cpp README ; `voice_typer/server/model_registry.py:56,77,101,124,151,174`) **UNVERIFIED: transcribe.cpp runtime overhead and GPU residency with our other engines were not measured.** |
| Project maturity | **VERIFIED** | transcribe.cpp announced 2026-06-30, v0.2.x, 2.2k stars / ~68 open issues at research time. (https://github.com/handy-computer/transcribe.cpp ; https://blog.mozilla.ai/announcing-transcribe-cpp) It is much younger than whisper.cpp (v1.9.5). **UNVERIFIED: long-term maintenance commitment.** |
| Windows CUDA build | **VERIFIED (docs)** | transcribe.cpp's CUDA build is documented for **Linux + NVIDIA**; Windows docs are for Vulkan SDK / Visual Studio. (https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/README.md) **UNVERIFIED: whether CUDA works on Windows for this library — must be probed, not assumed.** |

---

## 7. RECOMMENDED OPTION + PLAN OF ROUNDS

**Research recommendation (NOT a decision):** keep the worker boundary, pick **transcribe.cpp as a
separate executable (shape a)** for any future GGUF work, starting with the existing Whisper model
family, and **do not** attempt to remove onnxruntime in the same migration. Keep whisper.cpp as the
fallback reference (mature, but `.bin` not GGUF). Revisit after the small probes below produce
real numbers. (VERIFIED — reasoning grounded in §§3–6; this is a recommendation, not an accepted
decision, per `## Status`.)

Each round below is small, independently verifiable, and ends with evidence written to
`worklog.md`. No round changes the license, the GPL gate, or the model registry until its
predecessor is green.

| Round | Goal | Likely files | Tests | Verification |
|---|---|---|---|---|
| **25 — API/format spike (read-only)** | Pin transcribe.cpp's actual output struct against what `transcription_result.py` consumes; decide if a shim is needed. | none (research) | none | Header-level check of `include/transcribe.h` + `docs/models/whisper.md` upstream; write findings with VERIFIED/UNVERIFIED tags. |
| **26 — local build probe** | Build `transcribe-cli` on all three OSes in CI scratch; run one 16 kHz WAV through a Whisper GGUF. | scratch only | none | Real binary prints `seg.text/start/end`; record exact command + hashes. |
| **27 — quant + quality A/B** | Compare Q4_K_M / Q6_K / Q8_0 GGUF against our pinned CT2 `large-v3-turbo` on Arabic/English samples. | scratch only | none | WER + latency table with hardware named; no shipping change. |
| **28 — sibling binary wiring** | Add the runner as an `externalBin` sibling resolved by `_shipped_dirs()`; no engine cutover yet. | `tauri.conf.json`, `tauri-binaries.json`, `scripts/build/*`, `ffmpeg_binaries.py`-style resolver | `tests/tauri/*`, new resolver test | Frozen build finds the runner beside the exe; **PATH fallback refused**; fix `tauri_spawn.py:196` here using `__compiled__.containing_dir`. |
| **29 — worker adapter behind a flag** | New backend that calls the sibling runner, behind an opt-in config flag; registry keeps current engine as default. | `voice_typer/worker/whisper/`, `voice_typer/server/model_providers/`, `config/_schema.py` | focused adapter tests (mocked subprocess) | Existing dictation unchanged when flag off; flag on yields text via shim. |
| **30 — remove PyAV + CT2, flip the gate** | Only after round 29 is green: drop `faster-whisper`/`ctranslate2`/`av` deps and freeze includes, drop the PyAV notice, set `ENFORCE_NO_GPL_DLLS=1`. | `pyproject.toml`, `requirements-lock.txt`, `scripts/build/*`, `docs/THIRD_PARTY_NOTICES.md`, workflow vars | `tests/test_windows_bundle_gate.py`, freeze-drift tests | Gate hard-fails on any GPL DLL; self-check five markers still PASS; LGPL ffmpeg still works. |
| **31 — assess onnxruntime separately** | Decide VAD/filter/Parakeet/Qwen strategy; do **not** bundle this with the ASR cutover. | separate ADR | separate | Separate evidence; onnxruntime stays until then. |

**Note on the "final round" requirement in the task:** rounds 30–31 are where PyAV / faster-whisper
/CT2 are removed and `ENFORCE_NO_GPL_DLLS=1` is set. Removing **onnxruntime** is *not* applicable
to this migration as scoped — it has five independent consumers (§2.6) and would be a downgrade of
VAD/filter capability if done without replacements. (VERIFIED — imports listed in §2.6;
E12 of `AGENTS.md` forbids regressions.)

---

## 8. OWNER DECISIONS (plain English)

1. **Is a migration worth doing at all?** Facts: the current system works; the pain is bundle size
   and the GPL DLL warning, not broken transcription. (VERIFIED — gate is soft at `0`, app ships
   and works: `scripts/verify_windows_bundle.py:23-26`.) Research favors "only if the size/license
   win matters to you" — no evidence of user-visible transcription failure was found.
2. **Which runner?** Facts: whisper.cpp is mature but uses `.bin`, not GGUF; transcribe.cpp is
   GGUF-first and MIT but young. (VERIFIED — §3 sources.) Research favors **transcribe.cpp** *if*
   "GGUF" is a hard requirement; whisper.cpp if the real goal is simply "no PyAV/CT2".
3. **Separate exe or Python binding?** Facts: two sibling executables already ship successfully.
   (VERIFIED — LGPL ffmpeg; `llama-server` per ADR-0030.) Research favors **separate executable**.
4. **Do we remove onnxruntime too?** Facts: no — VAD, three denoisers and two other ASR models use
   it. (VERIFIED — §2.6.) Research favors **no**, handled in a separate ADR.
5. **When do we flip `ENFORCE_NO_GPL_DLLS=1`?** Facts: the gate is soft today by design and the
   round that removes PyAV is the one that must flip it. (VERIFIED — `review.md:563`.) Research
   favors flipping it **only** in the round that actually removes the DLLs.
6. **What about Parakeet / Qwen3-ASR?** Facts: they are separate registered models, one of them
   already GGUF-eligible in transcribe.cpp's catalogue, but ADR-0030 locks "one ASR model at a
   time, never two resident". (VERIFIED — `docs/adr/0030...:7-29`; transcribe.cpp model table.)
   Research favors **no registry change** in this migration.

**None of these are decided by this ADR.** (VERIFIED — `## Status`.)

---

## 9. HANDOFF FOR NEXT AGENT

**First 10 files to read, in order:**
1. `docs/adr/0031-onnx-to-gguf-migration.md` (this file)
2. `docs/adr/0030-one-asr-model-and-text-translator.md` (GGUF translator precedent)
3. `voice_typer/worker/whisper/engine.py` (real Whisper load/transcribe)
4. `voice_typer/server/worker_backed_asr.py` (worker boundary)
5. `voice_typer/server/transcription_result.py` (what the pipeline consumes)
6. `voice_typer/server/model_registry.py` (model list + repos)
7. `voice_typer/server/media_ingest/ffmpeg_binaries.py` (sibling-binary + frozen-path authority)
8. `scripts/verify_windows_bundle.py` (GPL gate + self-check)
9. `voice_typer/server/media_ingest/selfcheck.py` (five markers)
10. `scripts/build/nuitka_freeze.sh` (freeze includes)

**Commands to see current state:**
```bash
cd /c/Users/11/voice-typer
git status -sb                       # shared tree, main; 0021 is dirty — DO NOT TOUCH
git rev-parse --short HEAD
grep -rn "faster_whisper\|onnxruntime\|import av" voice_typer/server voice_typer/worker | head -50
grep -rn "ENFORCE_NO_GPL_DLLS" scripts tests/tauri review.md
cat scripts/ffmpeg-lgpl-win64.json
grep -n "containing_dir\|sys.executable" voice_typer/server/media_ingest/ffmpeg_binaries.py voice_typer/server/autostart/tauri_spawn.py
grep -n "seg\.\|info\.language\|word\." voice_typer/server/transcription_result.py | head -40
```

**Binding rules (from `AGENTS.md`, binding):**
- Git: work on `main` in the shared checkout; never branch/merge/rebase/stash/clean; before
  committing `git fetch` + `git status -sb`, stop if behind/diverged; `git add -- <paths>` only;
  no commits unless the prompt says so. (VERIFIED — `AGENTS.md` "Git workflow for all agents".)
- No PATH fallback for ffmpeg in frozen builds; a dev-only concession, never shipped. (VERIFIED —
  `voice_typer/server/media_ingest/ffmpeg_binaries.py:142-154`.)
- Nuitka probe rule: **facts about frozen behavior come from running a compiled binary**, not
  from docs or reasoning. A 2026-11-21 correction in `review.md:575-581` shows a doc-based claim
  about `sys.executable` was wrong and only a real onefile probe settled it. (VERIFIED — same.)
- Any new sibling binary must use `__compiled__.containing_dir`, never `sys.executable`; fix
  `tauri_spawn.py:196` in the same change. (VERIFIED — `review.md:577-581`.)
- W0: web-search first before implementing; E10: investigation before implementation; E12: no
  downgrades; E1: verify with `cargo check` / typecheck / `pytest --collect-only`. (VERIFIED —
  `AGENTS.md` "Golden Rule", W0, E1, E10, E12.)
- Online research: use the Firecrawl CLI, not the harness's internal search tools. (VERIFIED —
  owner correction, round 27.)
- No task IDs in code; tag conventions `SEC-*`, `RACE-*`, `PERF-*` only. (VERIFIED — `AGENTS.md`.)
- After using xerj for reference coding, submit the field report; index peer corpora under their
  own prefixes. (VERIFIED — `AGENTS.md` "XERJ (code search)".)

---

## 11. ROUND-27 MODEL INVENTORY (Part A)

Counts: **15 local models/artifacts — 12 READY, 1 UNCERTAIN, 2 NO BACKEND.** "GGUF exists?" means the family/variant has a GGUF artifact, not that this app ships it. This table was assembled from repo code plus upstream research; external URLs outside the Hugging Face candidate tables were collected before the Firecrawl-only correction and should be re-verified with Firecrawl before implementation. (VERIFIED — local `file:line` evidence; PARTIAL — upstream URLs.)

| model | today | GGUF exists? | runtime | license | status | evidence URL |
|---|---|---|---|---|---|---|
| Whisper tiny | CTranslate2, `Systran/faster-whisper-tiny`, 75 MB | YES | transcribe.cpp v0.4.2 | MIT | READY | https://github.com/handy-computer/transcribe.cpp |
| Whisper large-v3 | CTranslate2, `Systran/faster-whisper-large-v3`, 3000 MB | YES | transcribe.cpp v0.4.2 | MIT | READY | https://github.com/handy-computer/transcribe.cpp |
| Whisper large-v3-turbo | CTranslate2, `dropbox-dash/...turbo`, 1618 MB | YES | transcribe.cpp v0.4.2 | MIT | READY | https://github.com/handy-computer/transcribe.cpp |
| Parakeet Ultra (`parakeet`) | ONNX int8, `Masterx/parakeet-tdt-0.6b-ultra-onnx`, rev `99b09f03`, ~670 MB | YES | transcribe.cpp v0.4.2 | CC-BY-4.0 | READY | https://huggingface.co/handy-computer/parakeet-ultra-gguf |
| Qwen3-ASR 1.7B | ONNX int4, `andrewleech/qwen3-asr-1.7b-onnx`, 3943 MB | YES | transcribe.cpp v0.4.2 | Apache-2.0 | READY | https://github.com/handy-computer/transcribe.cpp |
| Qwen3-ASR 0.6B | ONNX int4, `andrewleech/qwen3-asr-0.6b-onnx`, 1940 MB | YES | transcribe.cpp v0.4.2 | Apache-2.0 | READY | https://github.com/handy-computer/transcribe.cpp |
| Silero VAD | `silero_vad.onnx`, 2,327,524 B, onnxruntime CPU-only | YES (`silero-vad-v6.2`, `silero-vad-F32.gguf`) | transcribe.cpp / s2s.cpp | model MIT (upstream), runtimes MIT | READY (caveat: older local export; internal to STT runtime, not drop-in ORT swap) | https://github.com/handy-computer/transcribe.cpp |
| DPDFNet | `dpdfnet2.onnx`, 10,178,747 B, onnxruntime | NOT FOUND | none found | Apache-2.0 | NO BACKEND (exhaustiveness UNVERIFIED) | https://github.com/ceva-ip/DPDFNet |
| RNNoise | native C library via ctypes; no ORT/CT2 | N/A | native C | BSD | NO BACKEND (GGUF not applicable; no backend needed) | https://jmvalin.ca/demo/rnnoise |
| GTCRN | `gtcrn_simple.onnx`, 535,190 B, onnxruntime | PARTIAL — LocalVQE GGUF is a different GTCRN-AEC architecture | LocalVQE GGML engine v1.3 | Apache-2.0 | UNCERTAIN (different architecture; Windows unverified) | https://github.com/localai-org/LocalVQE |
| Translation `index-translate-2b-q4-k-m` | already GGUF, 1,312,164,352 B | YES — shipped today | llama.cpp `llama-server` | Apache-2.0 / MIT | READY | in-repo `voice_typer/server/translation/catalogue.py:17-25` |
| Local ONNX polish model | user-supplied `*.onnx` + `.onnx_data`, onnxruntime | YES — any GGUF LLM | llama.cpp `llama-server` | user model UNVERIFIED | READY (runtime) | in-repo `voice_typer/server/model_providers/local_onnx/models.py:27-32,195-224` |
| Audio8 TTS Realistic 0.6B | already GGUF, 1,890,480,128 B | YES | `audio8` native | weights UNVERIFIED | READY | in-repo `voice_typer/server/tts/packs.py:105-113` |
| MagpieTTS Multilingual 357M | already GGUF, 568,663,328 B | YES | `nemo-speech` native | weights UNVERIFIED | READY | in-repo `voice_typer/server/tts/packs.py:115-127` |
| Magpie NanoCodec decoder | already GGUF, 78,823,104 B | YES | `nemo-speech` native | weights UNVERIFIED | READY | in-repo `voice_typer/server/tts/packs.py:129-140` |

Cloud providers and rule-based "AI enhancement" are not local weights and are not counted.

### 11.1 Parakeet Ultra candidate comparison (Firecrawl-verified)

| repo | file | quantization | exact bytes | runtime target | model identity | license |
|---|---|---|---:|---|---|---|
| `moondream/parakeet-ultra` | `model.safetensors` | full precision | 1,255,353,386 | Photon/transformers layout, not a shipped GGUF | fine-tuned Ultra | CC-BY-4.0 |
| `cstr/fluid-speech-pro-GGUF` | `fluid-speech-pro-q8_0.gguf` | Q8_0 | 676,653,088 | CrispASR (`-m fluid-speech-pro`) | built on Ultra but with an extra residual block — **not exact Ultra** | CC-BY-4.0 |
| `dawsonvosburg/parakeet-ultra-gguf` | `parakeet-ultra.q8_0.gguf` | Q8_0 | 714,456,704 | NeMo-Speech.cpp | fine-tuned Ultra | CC-BY-4.0 |
| `handy-computer/parakeet-ultra-gguf` | `parakeet-ultra-Q8_0.gguf` | Q8_0 | 740,363,168 | **transcribe.cpp** | fine-tuned Ultra | CC-BY-4.0 |

Choice: `handy-computer/parakeet-ultra-gguf/parakeet-ultra-Q8_0.gguf`. It is the only file satisfying all three owner criteria, and its card documents transcribe.cpp compatibility and pins upstream commit `73175eb`. (VERIFIED — Firecrawl scrape of model card and Files tab; Hugging Face JSON API via Firecrawl.)

---

## 12. ROUND-27 MEASUREMENTS (Part B)

Audio: extracted once from `C:\Users\11\Downloads\How To Build a Clean Gaming Laptop Setup_(240P).mp4` with the shipped `src-tauri/bin/ffmpeg-x86_64-pc-windows-msvc.exe` to 16 kHz mono s16 WAV, 480.4905625 s, 15,375,776 bytes. (VERIFIED — command output.) No PATH ffmpeg was used. All runs used 8 threads; ONNX used `OMP_NUM_THREADS=8`/`ORT_NUM_THREADS=8`, GGUF used `session(n_threads=8)`.

| Test | Model | Backend | Run | Load s | Wall s | RTF (audio s / wall s) | Peak RSS bytes | Threads | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | installed ONNX int8 non-fine-tuned Ultra | CPU | 1 | 3.04 | 29.35 | 16.37 | 1,022,423,040 | 8 | app `ParakeetEngine(device="cpu")` |
| 1 | installed ONNX int8 non-fine-tuned Ultra | CPU | 2 | — | 28.82 | 16.67 | 1,023,045,632 | 8 | warm |
| 2 | fine-tuned Ultra GGUF Q8_0 | CPU | 1 | 1.05 | 27.23 | 17.65 | 1,787,817,984 | 8 | standalone transcribe.cpp binding, no app integration |
| 2 | fine-tuned Ultra GGUF Q8_0 | CPU | 2 | — | 27.58 | 17.42 | 1,804,812,288 | 8 | warm |
| 3 | installed ONNX int8 | GPU | 1/2 | — | — | — | — | 8 | **NOT RUN** — see §13 |
| 4 | fine-tuned Ultra GGUF Q8_0 | Vulkan0 (RTX 5060) | 1 | 8.46 | 15.68 | 30.65 | 736,219,136 | 8 | first run includes Vulkan pipeline/load |
| 4 | fine-tuned Ultra GGUF Q8_0 | Vulkan0 (RTX 5060) | 2 | — | 4.98 | 96.55 | 573,440,000 | 8 | warm |

GGUF segment output: 18 segments, fields `t0_ms`, `t1_ms`, `text`, `first_token`, `n_tokens`, `first_word`, `n_words`, `speaker_id`. `timestamp_kind = segment`; no confidence fields. ONNX text word count 2,161, GGUF 1,924; word-level diff ratio 0.0903. Both transcripts are single-line text, so "first 30 lines" means the line itself; excerpts are in the spike folder, not in the repo. **No WER and no quality conclusion** — the weights differ. (VERIFIED — measured outputs under `C:\Users\11\gguf-spike\`.)

---

## 13. GPU DIAGNOSIS

- GPU: NVIDIA GeForce RTX 5060, driver 610.88, 8151 MiB. Two Vulkan devices found (RTX 5060 and AMD Radeon). (VERIFIED — `nvidia-smi` and ggml Vulkan init.)
- Project venv: `onnxruntime 1.29.0`, providers `['AzureExecutionProvider','CPUExecutionProvider']`. App requests `CUDAExecutionProvider` when available (`voice_typer/server/parakeet_engine/_load.py:100-116`); it falls back to CPU because the provider is absent. (VERIFIED — code + probe.)
- Missing DLLs probed: `cudart64_12.dll`, `cublas64_12.dll`, `cublasLt64_12.dll`, `cudnn64_9.dll`, `cudnn_engines_precompiled64_9.dll`, `onnxruntime_providers_cuda.dll`. Only `onnxruntime_providers_shared.dll` was present. (VERIFIED — ctypes probe.)
- Throwaway venv with `onnxruntime-gpu==1.29.0` (148,181,781-byte wheel from PyPI, under 500 MB) gave providers including CUDA, but loading the model failed: `onnxruntime_providers_cuda.dll` depends on `cublasLt64_13.dll`, missing (Error 126). ORT docs require CUDA 13.0 + cuDNN 9.x for ORT 1.29.x. (VERIFIED — Firecrawl scrape of ORT CUDA docs and PyPI JSON; run output.)
- NuGet `Microsoft.ML.OnnxRuntime.Gpu.Windows` 1.32.0 (148.02 MB, under 500 MB) supplied `onnxruntime_providers_cuda.dll` (195,548,512 B) but not the CUDA/cuDNN runtime DLLs. `nvidia-cudnn-cu13` PyPI win_amd64 wheel is 407,065,099 B (under 500 MB), but a CUDA 13 `cublasLt` package with Windows binaries was not identified within this round. (VERIFIED — Firecrawl scrapes; extracted NuGet package.) Therefore **TEST 3 is NOT RUN**, not zero.

---

## 14. INSTALLER SIZE (Part C)

Most recent local installer: `C:/Users/11/ci-run-2/Lausu-Windows-Installer/Lausu_1.0.0_x64-setup.exe`, extracted read-only with `C:/Program Files/7-Zip/7z.exe` to `C:\Users\11\gguf-spike\installer\setup`. Payload total 255,297,922 bytes (243.47 MiB), 16 files. Largest contained items:

| bytes | component | item |
|---:|---|---|
| 134,459,904 | ffmpeg (LGPL build) | `ffmpeg.exe` |
| 108,075,008 | Python sidecar (blended runtime + packages) | `python-sidecar.exe` |
| 12,387,328 | Rust host | `lausu-tauri.exe` |
| 168,448 | native key listener | `resources/native/windows-key-listener.exe` |
| 97,862 | notices | `_up_/docs/THIRD_PARTY_NOTICES.md` |
| 34,304 | NSIS | `$PLUGINSDIR/nsis_tauri_utils.dll` |
| 26,494 | NSIS | `$PLUGINSDIR/modern-wizard.bmp` |
| 15,360 | NSIS | `$PLUGINSDIR/NSISdl.dll` |
| 12,288 | NSIS | `$PLUGINSDIR/System.dll` |
| 9,728 | NSIS | `$PLUGINSDIR/nsDialogs.dll` |
| 7,680 | NSIS | `$PLUGINSDIR/StartMenu.dll` |
| 760–681 | tray icons | four PNGs |

Measured transcribe.cpp release v0.4.2 binaries (Firecrawl release page; real downloads):

| build | archive bytes | extracted bytes | largest DLLs |
|---|---:|---:|---|
| Windows x86_64 CPU+Vulkan | 18,052,817 | 56,239,103 | `ggml-vulkan.dll` 43,652,608; `transcribe.dll` 2,052,608; CPU kernels ~1.2 MB each |
| Windows x86_64 CUDA | 202,569,132 | 248,914,431 | `ggml-cuda.dll` 201,624,576; `ggml-vulkan.dll` 43,652,608; `transcribe.dll` 2,052,608 |

`transcribe.dll`, `ggml.dll`, `ggml-base.dll` and `ggml-vulkan.dll` are **different** between CPU+Vulkan and CUDA builds (SHA-256 differs), so they cannot simply be shared. No `llama-server` binary was present in this installer artifact; its size and duplicate-ggml comparison with transcribe.cpp are **UNVERIFIED**.

Scenarios (`R` = bytes actually removed from the one-file sidecar; **UNVERIFIED** because package contents are not separately visible in the installer):

| scenario | arithmetic | measured vs assumed |
|---|---|---|
| CPU-only GGUF | 255,297,922 + 56,239,103 − R | added measured; R assumed |
| GGUF + Vulkan | 255,297,922 + 56,239,103 − R | same release build as CPU+Vulkan; added measured; R assumed |
| GGUF + CUDA | 255,297,922 + 248,914,431 − R | added measured; R assumed |

Model files are not bundled: registry rows use `network_behavior="downloads-on-first-use-consent-gated"` and `load()` never downloads (`voice_typer/server/model_registry.py:65,87,110,138,162,185`; `voice_typer/worker/whisper/engine.py:161`). They do not affect installer size. Other expected shrink/grow: Python packages `onnxruntime`, `ctranslate2`, `faster-whisper`, `av` drop with the old stack; `numpy` may remain for other code; THIRD_PARTY_NOTICES needs GGUF model and transcribe.cpp entries. Exact byte deltas are **UNVERIFIED** until a frozen build is measured.

Distribution options (facts only, no decision):

| option | installer size | update flow | antivirus/SmartScreen | offline use | license/source offer | consistent with app today |
|---|---|---|---|---|---|---|
| bundled next to sidecar | +53.63 MiB CPU/Vulkan or +237.38 MiB CUDA | updated with app release | signed installer helps; new unsigned DLLs may trigger detection | works offline | MIT source offer for transcribe.cpp + ggml | YES — ffmpeg and llama-server already ship as sibling binaries |
| downloaded on first use | no installer growth, model-like download flow | separate update path needed | downloaded executable has higher SmartScreen risk | needs prior download | same notices, plus download integrity | partially — matches model downloads, not current binary pattern |
| separate optional download | no installer growth | user-managed | highest user-facing risk | user must opt in before offline use | same | NO — no current optional-binary flow |

---

## 15. RISKS, REVISED PLAN, OWNER DECISIONS

**Hallucination gate:** app consumes `seg.avg_logprob`, `seg.no_speech_prob`, `first_segment_start`, `last_segment_end` (`voice_typer/server/transcription_result.py:227-305`; `voice_typer/server/hallucination.py:90-102,134-186`). transcribe.cpp segment rows expose `t0_ms`, `t1_ms`, `text`, `first_token`, `n_tokens`, `first_word`, `n_words`, `speaker_id` — timestamps yes, confidence/no-speech **no**. Options: (a) change the gate to accept missing confidence as a conservative fallback, (b) ask upstream for per-segment logprob/no-speech, (c) keep a small ONNX confidence model — which would defeat full ONNX removal. (VERIFIED — binding source and measured output.)

**Revised plan (owner decision already made: remove onnxruntime entirely; one round per model family, safest first):**

1. Spike the gate-field adapter and decide the fallback; files: `transcription_result.py`, `hallucination.py`; tests: hallucination gate unit tests; verify with targeted pytest.
2. Wire the transcribe.cpp sibling binary via `__compiled__.containing_dir`; files: freeze scripts, binary locator, `tauri_spawn.py:196`; verify: compiled onefile probe.
3. Migrate Whisper/faster-whisper to transcribe.cpp GGUF; remove CT2/faster-whisper in a later milestone; verify: dictation + media decode parity.
4. Migrate Parakeet Ultra (fine-tuned GGUF chosen above); verify: speed/memory and transcript excerpt checks.
5. Migrate Qwen3-ASR 0.6B/1.7B; verify: multilingual smoke, timestamps.
6. Replace Silero VAD with the STT runtime's VAD; verify: silence gate and short-audio tests.
7. Replace GTCRN/DPDFNet — **NO BACKEND/UNCERTAIN**; owner must choose LocalVQE or another runtime before this round.
8. Final GGUF milestone: remove PyAV, faster-whisper, CTranslate2 and onnxruntime, then set `ENFORCE_NO_GPL_DLLS=1`; verify full suite + installer artifact.

**Owner decisions still open:**

1. Gate confidence fields — options (a)/(b)/(c) above; research favors (a) with a conservative fallback plus upstream request.
2. transcribe.cpp distribution — bundled is most consistent with current app; first-use download lowers installer size but adds SmartScreen/update risk.
3. Target backend — Vulkan measured 4.98 s warm on RTX 5060; CPU 27 s; CUDA measured only as binary size, not speed. Research does not decide.
4. Accept CPU peak RAM increase (1.80 GB GGUF vs 1.02 GB ONNX) — facts measured.
5. GTCRN/DPDFNet backend — no exact GGUF backend found; needs owner choice.
6. History purge for old junk files — separate irreversible decision; not done.

**Handoff rule added:** Online research: use the Firecrawl CLI, not the harness's internal search tools.

---

## 10. Sources

**Upstream (fetched during this research):**
- https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/README.md
- https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/models/README.md
- https://github.com/ggml-org/whisper.cpp/discussions/2578
- https://api.github.com/repos/ggml-org/whisper.cpp/releases/latest
- https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/README.md
- https://github.com/handy-computer/transcribe.cpp
- https://blog.mozilla.ai/announcing-transcribe-cpp
- https://raw.githubusercontent.com/ggml-org/llama.cpp/master/README.md
- https://api.github.com/repos/ggml-org/llama.cpp/releases/latest
- https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/README.md
- https://github.com/opennmt/ctranslate2
- https://github.com/microsoft/onnxruntime/issues/13892
- https://polyformproject.org/licenses
- https://github.com/polyformproject/polyform-licenses/blob/1.0.0/README.md
- https://pypi.org/project/whispercpp-kit
- https://github.com/localai-org/moss-transcribe.cpp

**Secondary (labelled as such in §3):**
- https://kompozy.io/reviews/transcribe-cpp
- https://github.com/jamditis/audiobud/issues/170

**In-repo primary evidence:** every `file:line` cited in §§0–9.

**Explicitly UNVERIFIED:** transcribe.cpp latest-release date; local CPU/WER/memory A/B;
one-to-one field mapping of transcribe.cpp segment output to our hallucination gate; Windows CUDA
support in transcribe.cpp; legal opinion on PolyForm Strict + LGPL interaction; completeness of
the GGUF ASR survey.
