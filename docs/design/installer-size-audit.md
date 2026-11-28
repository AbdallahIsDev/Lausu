# Installer size and dependency audit — evidence map (read-only)

Read-only audit, 2026-11-28, Worker S4 Parts E+F. No installer was built, nothing was downloaded,
no process belonging to another session was touched, no workflow/test/config file was changed.
Only this document and the appended section in `docs/design/runtime-delivery-options.md` were written.

Evidence labels: **MEASURED** = read from this machine or read-only GitHub artifact/release metadata;
**VERIFIED** = proven from source, build config or a pinned manifest; **ESTIMATE** = arithmetic from
those inputs (no build made here); **UNVERIFIED** = no evidence available; do not promote to fact.
"Stale" means the artifact predates ADR-0031 Phase 1 and cannot describe the current code state.

---

## Plain English first

The 163.66 MiB installer in CI is not what a current build would produce — that number is from
2026-11-22, before Phase 1 removed the retired media-decode stack. The honest current size is
**UNVERIFIED** because no installer was built in this round. What *is* measured is the expensive
stuff: a 128.23 MiB `ffmpeg.exe`, ~65 MiB of scipy in the frozen sidecar, ~35 MiB of ONNX Runtime,
~26 MiB of numpy, and 53.63 MiB of speech DLLs staged as installer resources.

Three reviewer ideas do not survive contact with the code:

1. **"scipy is only the resampler, so it is easy to drop."** False. Resampling is the *smallest*
   part of scipy's job here. The same sidecar uses `sosfilt`/`lfilter` for the high-pass and notch
   filters, `butter`/`sos2zpk` for filter design, `firwin`/`upfirdn`/`resample_poly` for rate
   conversion, `iirnotch` for mains hum and `get_window` for GTCRN. The worker calls the *same*
   shared resampler, so dropping scipy means changing both frozen processes, not one.
2. **"RNNoise is an ONNX Runtime dependent."** False. RNNoise is a native `rnnoise.dll` loaded via
   ctypes; ORT stays for Silero VAD, DPDFNet (the default denoiser), GTCRN and the local ONNX
   polish provider. No GGUF backend exists for DPDFNet or GTCRN today, so removing ORT now is a
   functional downgrade, not a size win.
3. **"The ADR-0026 80 MB diet already shipped."** False. ADR-0026 set a *target*; the current
   sidecar freeze script still includes `yt_dlp`, `yt_dlp_ejs`, `Crypto`, and follows scipy and
   onnxruntime. The measured 11/22 extraction still holds 62.05 MiB of the retired media-decoding libraries libs (already removed
   from source — stale evidence, not a current byte count).

The cheapest real win is **not** a Python rewrite: it is shipping a smaller ffmpeg (45–75 MiB
ESTIMATE off the installer) or moving ffmpeg into the already-planned runtime pack (55–75 MiB
ESTIMATE). The retired media libraries are already gone from source (~25–35 MiB ESTIMATE still
waiting for a real build to confirm). scipy is a ~29–39 MiB ESTIMATE installer lever but the
highest-risk one: it needs numerical parity work across two frozen processes. A plausible
low-risk floor is **~55–95 MiB** for the slim installer; ~45 MB requires scipy *and* ORT to go,
which is not viable today.

---

## F1 — Top contributors to the frozen sidecar and the NSIS installer

### Measured inputs

| Input | Value | Label |
|---|---:|---|
| CI `Lausu-Windows-Installer` artifact zip (run 45024128135, head `9c099320`, 2026-11-22) | 171,607,767 B / 163.66 MiB | MEASURED, CI artifact metadata (`packaging-and-runtime-pack.md:58-64`) |
| CI `Lausu-Windows-MSI` artifact zip | 185,345,958 B / 176.76 MiB | MEASURED, same |
| CI `windows-sidecar-exe` artifact zip | 124,442,947 B / 118.68 MiB | MEASURED, same |
| CI `Lausu-Windows-Sidecar-Binaries` / `windows-worker-exe` artifact zips | 118.77 / 117.82 MiB | MEASURED, same |
| `ffmpeg-x86_64-pc-windows-msvc.exe` in `src-tauri/bin` | 134,459,904 B / 128.23 MiB | MEASURED local |
| Native speech bundle extracted (`scripts/transcribe-cpp-win64.json` pin) | 56,234,621 B / 53.63 MiB | MEASURED local spike dir |
| Sidecar onefile extraction `LausuSidecar/2026.11.22.1250/onefile-tmp` | 441,839,446 B / 421.37 MiB total, of which the sidecar exe itself is 156.78 MiB | MEASURED, **stale** (pre-Phase-1) |
| Payload inside that onefile (excluding the exe) | ~264.59 MiB | MEASURED, stale (`performance-measurements.md:437-446`) |
| `src-tauri/resources` locally | 0.07 MiB — stubs only; CI fetch replaces them | MEASURED |
| Current-code installer byte split | **UNVERIFIED** — one compressed Nuitka exe; no build made | — |

Raw-payload → installer compression ratio used below is **0.45–0.59**, derived from measured
payload and CI artifact sizes (`performance-measurements.md:461-463`). It is an ESTIMATE, not a
build measurement.

### Top 30 raw contributors (stale 11/22 sidecar extraction + installer resources)

All MiB values MEASURED but **stale** unless marked otherwise.

| # | File / group | MiB | Where | Current-code status |
|---:|---|---:|---|---|
| 1 | `python-sidecar-*.exe` (onefile container) | 156.78 | extraction dir | Stale exe; CI artifact zip 118.68 MiB MEASURED |
| 2 | ffmpeg.exe | 128.23 | `src-tauri/bin` | MEASURED, still in slim installer (`slim conf:50`) |
| 3 | `retired-media/avcodec-62-0f4d…dll` | 18.32 | the retired media-decoding libraries | **Retired** in source (ADR-0031 Phase 1); stale extraction only |
| 4 | `onnxruntime/capi/onnxruntime_pybind11_state.pyd` | 17.88 | ORT | VERIFIED still included (`build_worker_windows.sh:242`; sidecar follows ORT imports) |
| 5 | `onnxruntime/capi/onnxruntime.dll` | 17.26 | ORT | same |
| 6 | `rnnoise.dll` | 14.14 | native denoiser | VERIFIED shipped as sidecar data (`build_sidecar_windows.sh:167`) |
| 7 | `retired-media/libx265-7e74…dll` | 11.98 | the retired media-decoding libraries | **Retired** in source; GPL-named |
| 8 | `voice_typer/server/dpdfnet2.onnx` | 9.71 | default denoiser model | VERIFIED included via `--include-package-data=voice_typer.server` |
| 9 | `hf_xet/hf_xet.pyd` | 9.06 | HF hub transfer | Needed by model downloads |
| 10 | `retired-media/libSvtAv1Enc-5ee…dll` | 7.25 | the retired media-decoding libraries | **Retired** |
| 11 | `tokenizers/tokenizers.pyd` | 7.21 | HF tokenizers | Needed by model/provider paths — UNVERIFIED which callers remain |
| 12 | `python312.dll` | 6.61 | CPython runtime | Irremovable while Python remains |
| 13 | `scipy/optimize/_highspy/_core.pyd` | 6.40 | scipy | Not used by this app's code; follows from `import scipy.signal` package graph |
| 14 | `libcrypto-3-x64.dll` | 5.66 | OpenSSL/TLS | Needed for HTTPS |
| 15 | `retired-media/avfilter-11-780a…dll` | 5.49 | the retired media-decoding libraries | **Retired** |
| 16 | `scipy/sparse/_sparsetools.pyd` | 4.04 | scipy | Not used directly; package graph |
| 17 | `numpy/_core/_multiarray_umath.pyd` | 3.67 | numpy | Irremovable (mic/VAD math) |
| 18 | `retired-media/avformat-62-9c2d…dll` | 2.69 | the retired media-decoding libraries | **Retired** |
| 19 | `scipy/fft/_duccfft/pyduccfft.pyd` | 2.66 | scipy | Not used directly; package graph |
| 20 | `scipy/special/_ufuncs_cxx.pyd` | 2.55 | scipy | Not used directly; package graph |
| 21 | `PIL/_imaging.pyd` | 2.54 | Pillow | VERIFIED declared (`pyproject.toml:145`) |
| 22 | `_soundfile_data` (whole dir) | 2.25 | soundfile data | Stale; current freeze does not include soundfile |
| 23 | (native speech DLL group, 13 files) | 53.63 | installer resource | MEASURED in spike dir; CI stages pinned archive into installer |
| 24–30 | `numpy.libs/libscipy_openblas64…dll` 19.55; `scipy.libs/libscipy_openblas-197…dll` 19.32; `scipy.libs/libscipy_openblas-64ed…dll` 19.32; `numpy.libs/libopenblas64…dll` 36.40 (older extraction); `cryptography/hazmat/bindings/_rust.pyd` 9.48; `pydantic_core/_pydantic_core.pyd` 5.01; `dfpdfnet/other ONNX assets` ~2.85 | — | BLAS / crypto / validation | numpy+scipy BLAS duplication is real; pydantic_core needed for schema |

Package-level totals from that same stale extraction (MEASURED, stale):

`the retired media DLL folder` 62.05 · `scipy` 46.03 + `scipy.libs` 19.32 = **65.35** · `onnxruntime` **35.16** ·
`numpy.libs` 20.09 + `numpy` 5.97 = **26.06** · `voice_typer` 12.58 · `hf_xet` 9.06 ·
`tokenizers` 7.21 · `PIL` 5.08 · `Crypto` 1.90 · `zstandard` 1.14 · `certifi` 0.23 MiB.

Compressed vs uncompressed: CI ships zipped artifacts (163.66 MiB installer zip, 118.68 MiB
sidecar zip); the onefile extraction is the *unpacked* payload (421.37 MiB including the container
exe). A recent local llama.cpp archive gives a concrete ratio for native DLLs: 103.74 MiB
extracted → 37.13 MiB zip (36%) MEASURED. These ratios are not a substitute for a real installer build.

---

## F2 — scipy: every call site, and what a numpy-only replacement would require

**VERIFIED** from source (`voice_typer/` grep + file reads). No scipy import remains in
`voice_typer/worker/` directly: the worker calls the *shared* resampler
(`worker/_transcribe.py:51-63` → `server/recording/resampling.resample_audio`), and Nuitka follows
that import into the worker onefile because the build uses `--include-package=voice_typer`
(`build_worker_windows.sh:241`). So scipy is in **both** frozen processes today.

| scipy symbol | Call site | Hot? | NumPy-only replacement | Risk / tests |
|---|---|---|---|---|
| `signal.resample_poly`, `signal.upfirdn`, `signal.firwin` | `recording/resampling.py:120-230,327,410`; `audio_processor.py:26-40,241`; `recording/audio_pipeline.py:42-50,367` | **Yes** — VAD resample per chunk | Code already caches FIR taps and has a 31-tap Hamming window interp fallback (`resampling.py:66-117`). Make Kaiser taps numpy-only with `np.i0` (numpy has the Bessel function) and polyphase up/down with `np.convolve`/strided gather; delete the scipy import path. | **High**: golden parity already exists (6,661 float32 values; 3,726 bit-identical; worst abs 7.45e-9 after Round 6 vectorization — `performance-measurements.md:122-132`). Re-run state byte-identity over 10k chunks at 13/1, 1/3, 160/147 and the 44.1 kHz shapes. |
| `signal.sosfilt`, `signal.sosfilt_zi` | `audio_filters/base.py:190-221`; `highpass.py:73+` (order-4 Butterworth high-pass) | **Yes** — live mic chain | Hand-rolled transposed direct-form-II biquad cascade with float32 `zi`, preserving anti-denormal epsilon. Fixed design (80 Hz @ 16 kHz) could also ship precomputed SOS constants. | **High**: need impulse-response and streaming-state parity tests for the exact 16 kHz and 44.1 kHz chains; a wrong `zi` update is a silent audio artifact. |
| `signal.lfilter`, `signal.iirnotch` | `base.py:224-238`; `notch.py:48-85` (50/60 Hz, Q=30) | **Yes** | Closed-form biquad coefficients for a fixed notch (or precomputed constants) + the same numpy direct-form-II engine as above. | **High**: notch coefficient parity + state parity; existing suppressor/noise-gate tests must stay green. |
| `signal.butter`, `signal.sos2zpk` | `highpass.py:33-49` (design-time stability gate) | Design-only | Precompute SOS for the fixed cutoff/sample rate; replace `sos2zpk` pole check with a numpy roots/gain check. | **Low-medium**: design-time only; assert max pole < 1 in a test. |
| `signal.get_window` | `audio_filters/gtcrn_backend.py:173` (`sqrt(get_window("hann", N_FFT, fftbins=True))`) | Model init, once | `np.hanning` is the periodic Hann window; assert bit-equality against the current scipy result for the exact `N_FFT` before swapping. | **Low**: one-time, deterministic. |
| `signal` module probe / error type | `recording/audio_pipeline.py:42-50`; `handlers/_base.py:305`; `recording/exceptions.py:32` | Fallback paths | Delete only after all above are replaced; keep the user-facing error code mapping until then. | **Low**: dead-code removal (E15), update pinned tests that assert scipy-unavailable copy. |

**Savings**: raw scipy payload in the stale sidecar extraction is **65.35 MiB MEASURED**; applying
the 0.45–0.59 ratio gives **~29–39 MiB installer ESTIMATE**. The worker artifact would also shrink
by roughly the same raw amount (~25–35 MiB compressed ESTIMATE), reducing the pack download but
not the installer. **Order: last.** It is the largest Python-side lever and the one most likely to
introduce a subtle audio regression; do it only with full numerical-parity evidence and a real
frozen smoke test. ADR-0026 explicitly classifies scipy relocation as a VAD-architecture decision,
not a packaging tweak.

---

## F3 — ONNX Runtime dependents and the GGUF exit path

**Current ORT dependents (VERIFIED — grep of `voice_typer/`, current checkout):**

| Dependent | Import site | Role | GGUF/native exit? |
|---|---|---|---|
| Silero VAD | `server/vad.py:108,143,173` | `InferenceSession` per current segment | `transcribe.cpp` owns VAD only if the runner takes it; no shipped GGUF VAD path here. Blocked. |
| DPDFNet (default denoiser) | `server/audio_filters/dpdfnet_backend.py:171,182,275` | streaming `InferenceSession` | No GGUF backend found (partA-inventory §4). Blocked. |
| GTCRN (fallback denoiser) | `server/audio_filters/gtcrn_backend.py:64,75,143` | streaming `InferenceSession` | LocalVQE's GGUF is a GTCRN-derived **AEC** model, not our weights — parity UNVERIFIED. Blocked. |
| Local ONNX polish provider | `server/model_providers/local_onnx/client.py:117,123` | user-supplied ONNX LLM | llama-server already serves GGUF LLMs (partA-inventory §3.2); needs model conversion + UI/config work. Possible later. |
| GPU capability probes / classification | `server/resource_probe.py:52-66`, `server/asr_utils.py:36-38`, `server/cuda_install/paths.py:41-43`, `cuda_install/activation.py:143` | `get_device()` / exception class | Replaceable with separate probes; **not** an inference dependency. |
| Freeze flags | `build_worker_windows.sh:242` (`--include-package=onnxruntime`) | forces ORT into worker even without direct worker imports | Remove together with the last inference dependent. |

**RNNoise is not an ORT dependent** — `rnnoise.dll` is loaded by ctypes, and the freeze excludes
`pyrnnoise`/`audiolab` (`build_worker_windows.sh:236-239`, `build_sidecar_windows.sh:165-167`).

**Savings**: ORT payload **35.16 MiB MEASURED** (stale extraction) → **16–21 MiB installer
ESTIMATE**, plus a similar reduction in the worker/pack artifact. Owner's ADR-0031 decision #1
keeps ORT in Phase 1 precisely because DPDFNet/GTCRN have no GGUF backend; Phase 2 is a separate
ADR. **Verdict: NOT NOW** — do not trade the default denoiser for 16–21 MiB. Revisit when a GGUF
denoiser and a GGUF VAD path both exist and are measured.

---

## F4 — Other heavy items

| Item | Evidence / size | Verdict |
|---|---|---|
| yt-dlp + EJS solver | VERIFIED included in sidecar (`build_sidecar_windows.sh:161-163`); extractors shipped as bytecode (`:138`). Stale extraction shows only 0.01 MiB of loose files because the bulk is compiled into the exe — true split **UNVERIFIED**. ADR-0026 says move it out of the slim core; that target has not shipped. | Medium lever, UNVERIFIED MB. Media URLs need it; if moved, the media feature must degrade with a clear message until the pack lands. |
| `Crypto` (pycryptodome) | VERIFIED declared (`pyproject.toml:301`), used by history at-rest encryption (`server/_text_crypto.py:18`); 1.90 MiB stale extraction. Sidecar includes it (`:157`), worker explicitly excludes it (`:240`). | Keep — real security function, small. |
| `cryptography` | 9.48 MiB stale extraction (`hazmat/bindings/_rust.pyd`); no direct `import cryptography` in `voice_typer/` — transitive (HF/HTTP stack). Removing it needs a dependency-graph change, not a freeze flag. | UNVERIFIED saving; not worth a supply-chain change for 9.48 MiB raw. |
| certifi | 0.23 MiB stale extraction; TLS trust store. | Keep. No meaningful saving. |
| `hf_xet` / `tokenizers` / `PIL` / `zstandard` | 9.06 / 7.21 / 5.08 / 1.14 MiB stale extraction; declared or transitive for HF cache, template export, schema. | Keep unless a caller audit proves otherwise; UNVERIFIED per-package necessity beyond `PIL` (declared) and `hf_xet` (HF transfer). |
| `_soundfile_data` | 2.25 MiB stale; current freeze does not include soundfile. | Already gone from current source; stale evidence only. |
| Unused stdlib/tests | Anti-bloat plugin + `--nofollow-import-to` for non-Windows psutil, scipy subpackages, sympy/mpmath/pytest/torch already applied (`build_sidecar_windows.sh:128-153`). | **<~2 MiB ESTIMATE** left, with frozen-import risk (`performance-measurements.md:457`). Not worth it. |
| Data files | ONNX assets 12.58 MiB in `voice_typer` dir; `rnnoise.dll` 14.14; `THIRD_PARTY_NOTICES.md`, tray icons, internal-plugin source (staged at build time). | Keep; ORT/GGUF migration, not packaging, is what can shrink these. |
| NSIS compression knobs | Tauri v2 `NsisCompression` default is `lzma`; alternatives zlib/bzip2/none; WiX has no key (Firecrawl scrape cited in `runtime-delivery-options.md:151`). | **~0 MB**. Do not touch workflows for this. |

---

## F5 — ffmpeg 128.23 MiB: facts and update consequences

**VERIFIED facts (no download, no build here):**

- `scripts/ffmpeg-lgpl-win64.json:5-12`: pinned `n9.0.2-61-gd59078794d-20261120`, release tag
  `autobuild-2026-11-20-12-40`, archive 171,850,189 B, SHA-256 `814c62c3…`, LGPL-3.0-or-later.
  The pin is mirrored byte-identically under the app's own GitHub release (same SHA).
- `:13` enables nearly every LGPL codec/filter (aom, dav1d, vpx, svtav1, openh264, jpeg-xl,
  webp,Ass/etc.); `--disable-libx264`, `--disable-libx265`, no `--enable-gpl`/`--enable-nonfree`.
- The app only asks ffmpeg for: `-vn -map 0:a:0 -ac 1 -ar 16000 -c:a pcm_f32le -f f32le -`
  (`media_ingest/decoder.py:87-115`), protocols `file,http,https,tcp,tls,crypto` (`:31-32,69-70`),
  and input-only duration probing (no ffprobe). yt-dlp is called with `format: bestaudio/best`,
  `fixup: never` (`downloader.py:94-108`), so no ffmpeg postprocessing.
- Upstream FFmpeg-Builds has **no audio-only flavor**; issue #5 was closed declining it, and the
  maintainer's workaround is `--disable-everything` plus explicit `--enable-*` items (ADR-0031:259-264,
  Firecrawl-verified 2026-11-22). The owner accepts a **pinned-source CI recipe** (fixed commit +
  configure line) but will not maintain a fork.
- Upstream LGPL **shared** build metadata (ADR-0031:262, Firecrawl-verified): 82,977,660 B latest,
  77,738,123 B `n9.0` — smaller archive but adds several loose libav DLLs; the bundle gate's
  `avcodec*.dll` name pattern must be checked before choosing it. **UNVERIFIED** in our staged layout.
- Rebuild size **ESTIMATE 10–30 MB static**, 20–60 CI minutes — no build was made.

**Does moving ffmpeg into a first-launch pack change update frequency?** Yes, in one specific way:
the ffmpeg *pin* then moves under the pack manifest. Today a code-only app update repays 128.23 MiB
of ffmpeg in every installer. In a pack, a code-only update keeps the old pack (and its ffmpeg)
untouched; ffmpeg bytes are paid once, and only a deliberate pin bump publishes a new pack version
and re-download. The trade is that media transcription is blocked until the pack lands — already
true for local ASR today (`runtime-delivery-options.md` §"First-launch UX today"). Pack budget is
180 MB compressed / 450 MB unpacked (`offline_pack/core.py:36-39`); a worker-only pack is 117.82 MiB
compressed MEASURED, so ffmpeg's ~45–60 MiB compressed ESTIMATE fits, but the budget must be
checked with a real build. Do not claim the pack carries ffmpeg today: it contains exactly one file
(`runtime-pack-publish.yml:309-327`).

---

## F6 — Realistic floor, ranked levers, recommendation

Baseline: **163.66 MiB CI artifact MEASURED, pre-Phase-1**; current-code size **UNVERIFIED**.
Installer savings below use the measured 0.45–0.59 payload→installer ratio and are ESTIMATEs.

| Order | Lever | Installer MB saved | Risk | Effort | Evidence / note |
|---:|---|---:|---|---|---|
| 1 | Confirm retired media stack gone in a real build | 25–35 | Low | Low (build + gate only) | Code already changed (ADR-0031 Phase 1); stale extraction still shows 62.05 MiB `the retired media DLL folder`. Verify, do not redesign. |
| 2 | Publish the worker pack (delivery fix) | 0 | Low | Low | No installer change; unblocks local ASR. Prerequisite for levers 3 and 5. |
| 3 | Move ffmpeg into the first-launch pack | 55–75 | Medium | Medium | `performance-measurements.md:453`; needs pack contents + gate + media-missing copy; media blocked before pack. |
| 4 | Audio-only pinned-source ffmpeg build | 45–75 | Medium | High (first build + toolchain pin) | 128.23 MiB MEASURED → 10–30 MB static ESTIMATE; owner's acceptable path in ADR-0031 §5. Alternative to 3, not additive with it. |
| 5 | Drop scipy via numpy-only audio | 29–39 | **High** | High | 65.35 MiB raw MEASURED in both freezes; needs numerical parity + two frozen builds. Last Python lever. |
| 6 | Remove ORT after GGUF denoiser/VAD exists | 16–21 | High today | High | 35.16 MiB raw MEASURED; blocked by DPDFNet/GTCRN, so **not now**. |
| 7 | Consent-gated llama-server download | 0 | Medium | Medium | Adds ~25–35 MiB compressed to a pack or its own download; installer unchanged. See appended E2 section. |
| 8 | Trim unused stdlib/tests / misc data | <2 | Medium (frozen imports) | Low | Anti-bloat already applied; no measurable win. |
| 9 | NSIS compression tuning | ~0 | Low | Low | LZMA already default; WiX has no key. |

**Floor:** with only low/medium-risk levers (1 + 3 *or* 4) the slim installer lands around
**55–95 MiB ESTIMATE** from the pre-Phase-1 baseline. Reaching ADR-0026's 80 MB target is plausible
with an audio-only ffmpeg; the older 45 MB target needs scipy and ORT removal, which breaks the
default denoiser and the live mic filter chain today. No number in this table is a measured
current-code installer size.

**Recommendation:** land lever 1's verification and lever 2 first (no new risk), then choose
*either* lever 3 (pack owns ffmpeg) *or* lever 4 (audio-only build) after measuring one real build.
Levers 5 and 6 stay as separately scoped ADRs with their own parity evidence.

---

## Hypotheses checked and rejected

| Hypothesis | Verdict | Evidence |
|---|---|---|
| "scipy is only the resampler; dropping it is a packaging tweak." | **False** | `highpass.py:33,42`; `notch.py:50,61`; `gtcrn_backend.py:173`; `audio_filters/base.py:198,215,232`; worker shares the resampler (`worker/_transcribe.py:61`). |
| "RNNoise depends on ONNX Runtime." | **False** | Native `rnnoise.dll` via ctypes; `pyrnnoise`/`audiolab` excluded at freeze (`build_worker_windows.sh:236-239`). |
| "The ADR-0026 80 MB diet shipped." | **False** | It was a target; current sidecar script still includes yt_dlp/Crypto and follows scipy/ORT (`build_sidecar_windows.sh:138,154-164`). |
| "the retired media-decoding libraries's 62.05 MiB is still in the installer." | **Stale / false for current source** | ADR-0031 Phase 1 removed it; the 11/22 extraction predates that change. Current-code size UNVERIFIED. |
| "The 163.66 MiB CI size describes HEAD." | **False** | CI run 45024128135 is 2026-11-22, head `9c099320`; HEAD here is `2efdf2e70` (2026-11-28). |
| "NSIS compression options unlock big savings." | **False** | LZMA default; alternatives zlib/bzip2/none; MSI/WiX no key (`runtime-delivery-options.md:151`). |
| "ORT can go now for 16–21 MiB." | **False / downgrade** | ADR-0031 decision #1 keeps ORT for DPDFNet/GTCRN; no GGUF backend for either (`partA-inventory.md:94-98,112`). |
| "The local llama-server dir proves a shipping delivery path." | **False** | Files are manually placed in `%APPDATA%\lausu\translation`; no workflow/Tauri config stages them (`packaging-and-runtime-pack.md:50,152`). |

## What the owner must do by hand

1. Approve which ffmpeg lever (3 or 4) to fund, and approve a real build to replace all ESTIMATEs.
2. Decide scipy/ORT removal as separate ADRs after the parity work exists; do not bundle them into a
   packaging change.
3. For llama-server delivery, see the appended section in `runtime-delivery-options.md`.
4. Run or delegate the full pytest suite on the final state (orchestrator only); this worker ran no
   suite, built nothing, and downloaded nothing.
