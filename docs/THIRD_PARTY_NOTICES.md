# Third-Party Notices

This project distributes or downloads the following third-party components
as part of the media-ingest feature (ADR-0023). Their licenses are
acknowledged here.

## Lausu (this project)

- **License:** PolyForm Strict License 1.0.0 (`LicenseRef-PolyForm-Strict-1.0.0`),
  source-available. Full text and required notice are in the repository
  root `LICENSE`.
- **Required Notice:** Copyright 2026 Abdallah IsDev.

The sections below are third-party components and retain their own licenses;
this project's license does not replace or relicense any of them.

## yt-dlp

- **Homepage:** https://github.com/yt-dlp/yt-dlp
- **License:** Unlicense (public domain)
- **Use:** URL resolution and audio-only download fallback for remote media
  sources.

## yt-dlp-ejs

- **Homepage:** https://github.com/yt-dlp/ejs
- **License:** Unlicense
- **Bundled components in prebuilt wheels:** `meriyah` (ISC License),
  `astring` (MIT License)
- **Use:** External-JavaScript solver support for YouTube extraction.

## transcribe.cpp (ASR runner)

transcribe.cpp 0.4.2 is MIT-licensed and ships as a sibling executable beside the sidecar.
Source and licence: https://github.com/handy-computer/transcribe.cpp
Pinned asset/hash: `scripts/transcribe-cpp-win64.json`.

## GGUF ASR model weights

ASR weights are NOT bundled. They are downloaded on first use into the Hugging Face cache.
Licences per model: `voice_typer/server/gguf_model_registry.py` (Whisper MIT, Parakeet CC BY 4.0,
Qwen3-ASR Apache-2.0). No GPL-licensed codec library is introduced by these weights.

## FFmpeg (LGPL-only executable, Windows x64)

- **Source (upstream documentation):** FFmpeg-Builds LGPL autobuild, immutable tag
  `autobuild-2026-11-20-12-40` —
  https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/tag/autobuild-2026-11-20-12-40
  (build scripts: https://github.com/FFmpeg-Builds/FFmpeg-Builds/tree/autobuild-2026-11-20-12-40 ;
  FFmpeg source commit: https://github.com/FFmpeg/FFmpeg/tree/d59078794d).
- **Version (verbatim `ffmpeg -version` first line):** `ffmpeg version
  n9.0.2-61-gd59078794d-20261120 Copyright (c) 2000-2026 the FFmpeg developers`.
  Archive: `ffmpeg-n9.0.2-61-gd59078794d-win64-lgpl-9.0.zip`, 171,850,189 bytes,
  SHA-256 `814c62c35ca7e2b15d85b0a2a5b79bbf21783176520154f26a6df1e9df72761e`.
  Pinned in `scripts/ffmpeg-lgpl-win64.json`; fetched and verified by
  `scripts/build/fetch_ffmpeg_lgpl_win64.sh`. This is a release-branch (9.0)
  build, not a master snapshot; dated tags are retained 14 days (daily) / 2
  years (month-end), so the manifest pins the owner-hosted mirror
  (`https://github.com/AbdallahIsDev/Lausu/releases/download/ffmpeg-lgpl-n9.0.2-20261120/`
  plus the asset name below) and carries the BtbN dated-tag URL as fallback.
  Both sources must produce the same SHA-256. The executable is
  gitignored and is not committed to this repository.
- **Licence (verbatim from `ffmpeg -L`):** "GNU Lesser General Public License
  ... version 3 of the License, or (at your option) any later version."
  The build's configuration explicitly contains `--disable-libx264`,
  `--disable-libx265`, `--disable-libxavs2`, `--disable-libxvid` and does NOT
  contain `--enable-gpl`, `--enable-nonfree`, `--enable-libx264` or
  `--enable-libx265`. The full stored configuration string is in the manifest.
- **Use:** `ffmpeg` is bundled on Windows x64 as a Tauri external binary and
  called as a subprocess by `media_ingest/decoder.py` to decode
  local files and remote audio to 16 kHz mono float32 PCM. No video encoding
  is performed.
- **Source offer:** the builder publishes the exact source and build scripts at
  the immutable tag above. The corresponding-source offer text for the shipped
  build, and the replaceability question for these executables, remain
  **pending owner decision**. No compliance claim is made.

## RNNoise (native library)

- **Upstream:** https://github.com/xiph/rnnoise — native library
  (`rnnoise.dll` / `librnnoise.dylib` / `librnnoise.so`) shipped inside the
  `pyrnnoise` package directory and included in the frozen sidecar as data.
- **Licence (upstream documentation, BSD-3-Clause):** the native RNNoise code is
  distributed under the BSD-3-Clause licence; `pyrnnoise` itself is Apache-2.0
  (`pyrnnoise-0.4.3.dist-info/METADATA` contains `License-File: LICENSE`). Our
  `audio_filters/rnnoise_ctypes.py` is an original minimal ctypes binding to the
  public C API; it does not copy or import pyrnnoise's Python code.
- **Use:** optional microphone noise suppression (`noise_suppression_method =
  "rnnoise"`); 480-sample frames at 48 kHz, with our own framing/resampling.
  Attribution and source-offer wording remain **pending owner decision**; no
  compliance claim is made.

## pystray

- **Homepage:** https://github.com/moses-palmer/pystray (PyPI: https://pypi.org/project/pystray/)
- **Version:** 0.19.5 (pinned as `pystray>=0.19,<0.20` in `pyproject.toml`)
- **License:** GNU Lesser General Public License v3 (LGPLv3), LGPL-3.0-or-later
- **Use:** Cross-platform system-tray icon for the frozen sidecar.
- **Redistribution note:** pystray is compiled into the Nuitka `--onefile`
  sidecar/worker binaries rather than shipped as a system shared library.
  The LGPL-3.0 §4d (relink) obligation for this Combined Work is under
  analysis and the owner/legal decision is **PENDING** — no compliance
  claim is made. Full verified facts, the concrete §4d analysis, and the
  decision options are recorded in
  [`migration/signing-guide.md` §"Third-party license obligations"](migration/signing-guide.md#third-party-license-obligations).
  Update both files together when a decision is made.

## Deno

- **Homepage:** https://github.com/denoland/deno
- **License:** MIT
- **Use:** Optional external JavaScript runtime shipped with the offline
  runtime pack; executes yt-dlp's JavaScript solver scripts for YouTube
  extraction.

## DPDFNet2 (bundled noise-suppression model)

- **Homepage:** https://github.com/ceva-ip/DPDFNet (weights:
  https://huggingface.co/Ceva-IP/DPDFNet)
- **License:** Apache-2.0
- **Bundled file:** `voice_typer/server/dpdfnet2.onnx` (official 16 kHz
  streaming ONNX export, `onnx/dpdfnet2.onnx`, revision `dd6818d0`)
- **Use:** Neural microphone denoising in the audio filter chain. The adapter
  in `voice_typer/server/audio_filters/dpdfnet_backend.py` reimplements the
  Apache-2.0 `dpdfnet` package's session/state bootstrap so the app can ship
  the weights without that package's librosa/numba dependency tree.

<!-- BEGIN GENERATED THIRD-PARTY NOTICES -->
## Consolidated Windows-installer inventory (generated)

Regenerate with `python scripts/generate_third_party_notices.py` (`--check` verifies
the committed artifact). Deterministic, offline, stdlib-only; no legal conclusions.
The hand-written Lausu / yt-dlp / transcribe.cpp / GGUF weights / FFmpeg / RNNoise / pystray / Deno / DPDFNet2
sections outside these markers are preserved verbatim by regeneration.

### Evidence and scope

- Shipping is established from the Windows bundle config and the extracted
  onefile/installed folders, NEVER from a lockfile alone.
- `requirements-lock.txt`: 79 pinned distributions (read-only).
- `package-lock.json`: production closure of 138 packages (licenses: 0BSD × 1, Apache-2.0 × 2, ISC × 14, MIT × 119, MIT and ISC × 1, Unlicense × 1).
- `Cargo.lock`: 524 package entries across all targets (Windows graph audited as 310 crates).
- Installed dist-info metadata is a local cross-check only; its count depends on the machine and is deliberately omitted so this artifact is byte-identical on every OS.
- Build drift is real: shipped python312.dll is 3.12.10 while dev .venv is 3.13.7;
  shipped onnxruntime.dll is 1.28.0 while dist-info says 1.29.0. Local metadata never
  overrides shipped-file evidence. UNVERIFIED means no local licence file was found.

### Components grouped by license identifier

#### Apache-2.0

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| cryptography | 50.0.0 | Apache-2.0 OR BSD-3-Clause | — | VERIFIED |
| dpdfnet2.onnx | revision dd6818d0 | Apache-2.0 | — | VERIFIED |
| hf-xet | 1.6.0 | Apache-2.0 | — | VERIFIED |
| huggingface_hub | 1.28.0 | Apache-2.0 | — | VERIFIED |
| OpenSSL (libcrypto-3.dll, libssl-3.dll) | 3.0.16 | Apache-2.0 | The OpenSSL Toolkit | UNVERIFIED |
| regex | 2026.7.19 | Apache-2.0 AND CNRI-Python | — | VERIFIED |
| requests | 2.34.2 | Apache-2.0 | — | VERIFIED |
| tokenizers | 0.23.1 | Apache-2.0 | — | VERIFIED |

- cryptography: Dual licensed; both identifiers quoted verbatim.
- dpdfnet2.onnx: Bundled 16 kHz streaming ONNX noise-suppression model.
- OpenSSL (libcrypto-3.dll, libssl-3.dll): PRESENT; Apache-2.0 NOTICE text not shipped. Upstream https://www.openssl.org/source/license.html

#### BSD-2-Clause

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| wrapt | 2.3.0 | BSD-2-Clause | — | VERIFIED |

#### BSD-3-Clause

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| MarkupSafe | 3.0.3 | BSD-3-Clause | — | VERIFIED |
| numpy | 2.5.2 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Copyright (c) 2005-2025, NumPy Developers. | VERIFIED |
| psutil | 7.2.2 | BSD-3-Clause | — | VERIFIED |
| scipy | 1.18.0 | BSD-3-Clause | Copyright (c) 2001-2002 Enthought, Inc. 2003, SciPy Developers. | VERIFIED |
| soundfile | 0.14.0 | BSD 3-Clause License | Copyright (c) 2013, Bastian Bechtold | VERIFIED |
| websockets | 13.1 | BSD-3-Clause | Copyright (c) Aymeric Augustin and contributors | VERIFIED |
| zstandard _cffi.pyd / backend_c.pyd | unknown | BSD-3-Clause (upstream only) | — | UNVERIFIED |

- numpy: OpenBLAS DLLs carry 'GPL-3.0-or-later WITH GCC-exception-3.1'; text not shipped.
- zstandard _cffi.pyd / backend_c.pyd: PRESENT; no dist-info or licence text. Upstream https://github.com/facebook/zstd

#### CC-BY-4.0

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| parakeet-tdt-0.6b-v3 / parakeet-tdt-0.6b-ultra-onnx | unknown | CC-BY-4.0 | — | NOT-IN-INSTALLER |

- parakeet-tdt-0.6b-v3 / parakeet-tdt-0.6b-ultra-onnx: Runtime download from Hugging Face, not in the Windows installer; listed for completeness.

#### GCC-exception-3.1

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| OpenBLAS DLLs (numpy.libs, scipy.libs) | unknown | GPL-3.0-or-later WITH GCC-exception-3.1 | Copyright (C) 2002-2017 Free Software Foundation, Inc. | UNVERIFIED |

- OpenBLAS DLLs (numpy.libs, scipy.libs): PRESENT; exception text not shipped; hash suffixes differ from .venv RECORD, provenance UNVERIFIED.

#### LGPL-2.1-or-later

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| FFmpeg (Windows x64, LGPL-only build) | n9.0.2-61-gd59078794d-20261120 | LGPL-2.1-or-later (LGPL-only build configuration) | Copyright (c) 2000-2026 the FFmpeg developers | VERIFIED |
| libsndfile_x64.dll | unknown | LGPL-2.1-or-later | — | UNVERIFIED |

- FFmpeg (Windows x64, LGPL-only build): See dedicated FFmpeg section; manifest scripts/ffmpeg-lgpl-win64.json. No legal conclusion.
- libsndfile_x64.dll: PRESENT in onefile cache; no licence file shipped. Local .venv COPYING: 'GNU LESSER GENERAL PUBLIC LICENSE Version 2.1, February 1999'.

#### MIT

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| charset-normalizer | 3.5.1 | MIT | Copyright (c) 2025 TAHRI Ahmed R. | VERIFIED |
| ggml (vendored in transcribe.cpp) | 0.4.2 runtime | MIT | Copyright (c) 2023-2024 ggml authors | VERIFIED |
| GGUF ASR model weights | Q8_0 | MIT / CC-BY-4.0 / Apache-2.0 | Copyright retained by each model author. | VERIFIED |
| gtcrn_simple.onnx | unknown | MIT | — | VERIFIED |
| miniz (vendored in transcribe.cpp) | 3.0.2 | MIT | Copyright 2013-2014 RAD Game Tools and Valve Software; Copyright 2010-2014 Rich Geldreich and Tenacious Software LLC | VERIFIED |
| onnxruntime | 1.29.0 (installed metadata); shipped DLL 1.28.0 | MIT License | Copyright (c) Microsoft Corporation | VERIFIED |
| pillow | 13.0.0 | MIT-CMU | — | VERIFIED |
| PyYAML | 6.0.3 | MIT | Copyright (c) 2017-2021 Ingy döt Net | VERIFIED |
| silero_vad.onnx | unknown | MIT (upstream only) | — | UNVERIFIED |
| sounddevice | 0.5.6 | MIT | Copyright (c) 2015-2025 Matthias Geier | VERIFIED |
| Tauri host crate graph | per Cargo.lock | mixed (MIT, Apache-2.0, Unicode-3.0, MPL-2.0, CC0-1.0, Zlib, BSL-1.0, ISC) | — | VERIFIED |
| transcribe.cpp | 0.4.2 | MIT | Copyright (c) 2026 transcribe.cpp contributors | VERIFIED |

- ggml (vendored in transcribe.cpp): MIT text from the ggml project LICENSE; vendored runtime DLLs (ggml.dll, ggml-base.dll, ggml-vulkan.dll, ggml-cuda.dll) ship beside transcribe.dll. Upstream https://github.com/ggml-org/ggml
- GGUF ASR model weights: Downloaded on first use; licences per model in voice_typer/server/gguf_model_registry.py. No weights are bundled.
- gtcrn_simple.onnx: Bundled noise-suppression model with local MIT evidence.
- miniz (vendored in transcribe.cpp): Full MIT text from the vendored miniz-3.0.2/LICENSE in the local PyTorch third-party licence bundle; upstream https://github.com/richgel999/miniz
- onnxruntime: Build drift: shipped onnxruntime.dll PE version 1.28.0; dist-info 1.29.0. ThirdPartyNotices not shipped.
- silero_vad.onnx: PRESENT; no licence file beside the model. Upstream https://github.com/snakers4/silero-vad/blob/master/LICENSE
- Tauri host crate graph: Root crate license-file = ../LICENSE (PolyForm Strict 1.0.0). Representative: unicode-ident '(MIT OR Apache-2.0) AND Unicode-3.0'; icu_* 2.2.0 'Unicode-3.0'; cssparser/selectors/option-ext/dtoa-short 'MPL-2.0'; ryu 'Apache-2.0 OR BSL-1.0'; dunce 'CC0-1.0 OR MIT-0 OR Apache-2.0'; foldhash 'Zlib'.
- transcribe.cpp: Sibling ASR runner. Pinned in scripts/transcribe-cpp-win64.json; upstream https://github.com/handy-computer/transcribe.cpp

#### MPL-2.0

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| certifi | 2026.10.19 | MPL-2.0 | — | UNVERIFIED |

- certifi: Shipped; MPL notice text not present in the installed output. Upstream https://github.com/certifi/python-certifi

#### MSVC-Redistrib

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| MSVC runtime (vcruntime140.dll, vcruntime140_1.dll) | unknown | Microsoft Software License Terms | — | UNVERIFIED |

- MSVC runtime (vcruntime140.dll, vcruntime140_1.dll): PRESENT; no licence file shipped. Upstream https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170

#### OFL-1.1

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| InterVariable.woff2 / InterVariable-Italic.woff2 | unknown | OFL-1.1 | Copyright (c) 2016 The Inter Project Authors (https://github.com/rsms/inter) | UNVERIFIED |

- InterVariable.woff2 / InterVariable-Italic.woff2: Found in stale dist/; no local OFL.txt. Upstream https://scripts.sil.org/OFL

#### PSF-2.0

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| CPython runtime (python312.dll, python3.dll, stdlib .pyd) | 3.12.10 | PSF-2.0 | Python Software Foundation | UNVERIFIED |
| pywin32 binaries | unknown (312 build tag) | PSF-2.0 (upstream only) | — | UNVERIFIED |

- CPython runtime (python312.dll, python3.dll, stdlib .pyd): PRESENT; PE 3.12.10 differs from dev .venv 3.13.7; no licence file shipped. Upstream https://docs.python.org/3/license.html
- pywin32 binaries: PRESENT; no dist-info in dev venv. Upstream https://github.com/mhammond/pywin32

#### PolyForm-Strict-1.0.0

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| Lausu (this project) | 1.0.0 | PolyForm Strict License 1.0.0 | Copyright 2026 Abdallah IsDev | VERIFIED |
| windows-key-listener.exe | source build | PolyForm Strict License 1.0.0 | Copyright 2026 Abdallah IsDev | VERIFIED |

- Lausu (this project): Own project; root LICENSE is authoritative. METADATA says MIT but the LICENSE file says PolyForm Strict 1.0.0 — contradiction quoted verbatim, no conclusion.
- windows-key-listener.exe: Compiled from voice_typer/server/native/windows-key-listener.c in this repository.

#### PortAudio-MIT

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| PortAudio (libportaudio64bit.dll, libportaudio64bit-asio.dll) | unknown | PortAudio MIT-style | Copyright (c) 1999-2011 Ross Bencina and Phil Burk | UNVERIFIED |

- PortAudio (libportaudio64bit.dll, libportaudio64bit-asio.dll): PRESENT; no licence file shipped. Upstream https://portaudio.com/license.html

#### Unlicense

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| yt-dlp | 2026.8.19 | Unlicense | — | VERIFIED |
| yt-dlp-ejs | unknown | Unlicense AND MIT AND ISC | — | VERIFIED |

- yt-dlp-ejs: Bundles meriyah (ISC) and astring (MIT).

#### UNVERIFIED

| Component | Version | License identifier (verbatim) | Copyright | Status |
|---|---|---|---|---|
| _pydantic_core.pyd | unknown | MIT (upstream only) | — | UNVERIFIED |
| libffi-8.dll | unknown | MIT (upstream only) | — | UNVERIFIED |
| pydantic-core | unknown | UNVERIFIED | — | UNVERIFIED |
| tzdata | unknown | UNVERIFIED | — | UNVERIFIED |
| uninstall.exe (NSIS) | unknown | Common Public License version 1.0 + LZMA exception | — | UNVERIFIED |
| zstandard | unknown | UNVERIFIED | — | UNVERIFIED |

- _pydantic_core.pyd: PRESENT; no dist-info or licence text. Upstream https://github.com/pydantic/pydantic-core
- libffi-8.dll: PRESENT; no version resource. Upstream https://github.com/libffi/libffi/blob/master/LICENSE
- pydantic-core: No installed dist-info; upstream hint only https://github.com/pydantic/pydantic-core
- tzdata: No local version evidence in the installed output.
- uninstall.exe (NSIS): PRESENT; linked modules unverified.
- zstandard: Upstream hint only https://github.com/facebook/zstd

### npm production closure (from package-lock.json, read-only)

All packages below are in the shipped renderer bundle. License identifiers are the
verbatim `license` strings in `package-lock.json`; no GPL/LGPL/MPL/CC-BY appears in
this closure.

| Package | Version | License identifier (verbatim) |
|---|---|---|
| @floating-ui/core | 1.7.5 | MIT |
| @floating-ui/dom | 1.7.6 | MIT |
| @floating-ui/react-dom | 2.1.8 | MIT |
| @floating-ui/utils | 0.2.11 | MIT |
| @hugeicons/core-free-icons | 4.2.3 | MIT |
| @hugeicons/react | 1.1.9 | MIT |
| @number-flow/react | 0.6.2 | MIT |
| @radix-ui/number | 1.1.2 | MIT |
| @radix-ui/primitive | 1.1.5 | MIT |
| @radix-ui/react-accessible-icon | 1.1.11 | MIT |
| @radix-ui/react-accordion | 1.2.16 | MIT |
| @radix-ui/react-alert-dialog | 1.1.19 | MIT |
| @radix-ui/react-arrow | 1.1.11 | MIT |
| @radix-ui/react-aspect-ratio | 1.1.11 | MIT |
| @radix-ui/react-avatar | 1.2.2 | MIT |
| @radix-ui/react-checkbox | 1.3.7 | MIT |
| @radix-ui/react-collapsible | 1.1.16 | MIT |
| @radix-ui/react-collection | 1.1.12 | MIT |
| @radix-ui/react-compose-refs | 1.1.3 | MIT |
| @radix-ui/react-context | 1.2.0 | MIT |
| @radix-ui/react-context-menu | 2.3.3 | MIT |
| @radix-ui/react-dialog | 1.1.19 | MIT |
| @radix-ui/react-direction | 1.1.2 | MIT |
| @radix-ui/react-dismissable-layer | 1.1.15 | MIT |
| @radix-ui/react-dropdown-menu | 2.1.20 | MIT |
| @radix-ui/react-focus-guards | 1.1.4 | MIT |
| @radix-ui/react-focus-scope | 1.1.12 | MIT |
| @radix-ui/react-form | 0.1.12 | MIT |
| @radix-ui/react-hover-card | 1.1.19 | MIT |
| @radix-ui/react-id | 1.1.2 | MIT |
| @radix-ui/react-label | 2.1.11 | MIT |
| @radix-ui/react-menu | 2.1.20 | MIT |
| @radix-ui/react-menubar | 1.1.20 | MIT |
| @radix-ui/react-navigation-menu | 1.2.18 | MIT |
| @radix-ui/react-one-time-password-field | 0.1.12 | MIT |
| @radix-ui/react-password-toggle-field | 0.1.7 | MIT |
| @radix-ui/react-popover | 1.1.19 | MIT |
| @radix-ui/react-popper | 1.3.3 | MIT |
| @radix-ui/react-portal | 1.1.13 | MIT |
| @radix-ui/react-presence | 1.1.7 | MIT |
| @radix-ui/react-primitive | 2.1.7 | MIT |
| @radix-ui/react-progress | 1.1.12 | MIT |
| @radix-ui/react-radio-group | 1.4.3 | MIT |
| @radix-ui/react-roving-focus | 1.1.15 | MIT |
| @radix-ui/react-scroll-area | 1.2.14 | MIT |
| @radix-ui/react-select | 2.3.3 | MIT |
| @radix-ui/react-separator | 1.1.11 | MIT |
| @radix-ui/react-slider | 1.4.3 | MIT |
| @radix-ui/react-slot | 1.3.0 | MIT |
| @radix-ui/react-switch | 1.3.3 | MIT |
| @radix-ui/react-tabs | 1.1.17 | MIT |
| @radix-ui/react-toast | 1.2.19 | MIT |
| @radix-ui/react-toggle | 1.1.14 | MIT |
| @radix-ui/react-toggle-group | 1.1.15 | MIT |
| @radix-ui/react-toolbar | 1.1.15 | MIT |
| @radix-ui/react-tooltip | 1.2.12 | MIT |
| @radix-ui/react-use-callback-ref | 1.1.2 | MIT |
| @radix-ui/react-use-controllable-state | 1.2.3 | MIT |
| @radix-ui/react-use-effect-event | 0.0.3 | MIT |
| @radix-ui/react-use-escape-keydown | 1.1.3 | MIT |
| @radix-ui/react-use-is-hydrated | 0.1.1 | MIT |
| @radix-ui/react-use-layout-effect | 1.1.2 | MIT |
| @radix-ui/react-use-previous | 1.1.2 | MIT |
| @radix-ui/react-use-rect | 1.1.2 | MIT |
| @radix-ui/react-use-size | 1.1.2 | MIT |
| @radix-ui/react-visually-hidden | 1.2.7 | MIT |
| @radix-ui/rect | 1.1.2 | MIT |
| @types/d3-array | 3.0.3 | MIT |
| @types/d3-color | 3.1.0 | MIT |
| @types/d3-delaunay | 6.0.1 | MIT |
| @types/d3-format | 3.0.1 | MIT |
| @types/d3-geo | 3.1.0 | MIT |
| @types/d3-interpolate | 3.0.1 | MIT |
| @types/d3-path | 3.1.1 | MIT |
| @types/d3-scale | 4.0.2 | MIT |
| @types/d3-shape | 3.1.7 | MIT |
| @types/d3-time | 3.0.0 | MIT |
| @types/d3-time-format | 2.1.0 | MIT |
| @types/geojson | 7946.0.16 | MIT |
| @types/lodash | 4.17.25 | MIT |
| @types/react | 19.2.17 | MIT |
| @types/react-dom | 19.2.3 | MIT |
| @visx/event | 4.0.1-alpha.0 | MIT |
| @visx/group | 4.0.1-alpha.0 | MIT |
| @visx/heatmap | 4.0.1-alpha.0 | MIT |
| @visx/pattern | 4.0.1-alpha.0 | MIT |
| @visx/point | 4.0.1-alpha.0 | MIT |
| @visx/responsive | 4.0.1-alpha.0 | MIT |
| @visx/scale | 4.0.1-alpha.0 | MIT |
| @visx/vendor | 4.0.0-alpha.0 | MIT and ISC |
| d3-array | 3.2.1 | ISC |
| aria-hidden | 1.2.6 | MIT |
| class-variance-authority | 0.7.1 | Apache-2.0 |
| classnames | 2.5.1 | MIT |
| clsx | 2.1.1 | MIT |
| csstype | 3.2.3 | MIT |
| d3-array | 3.2.4 | ISC |
| d3-color | 3.1.0 | ISC |
| d3-delaunay | 6.0.2 | ISC |
| d3-format | 3.1.0 | ISC |
| d3-geo | 3.1.0 | ISC |
| d3-interpolate | 3.0.1 | ISC |
| d3-path | 3.1.0 | ISC |
| d3-scale | 4.0.2 | ISC |
| d3-shape | 3.2.0 | ISC |
| d3-time | 3.1.0 | ISC |
| d3-time-format | 4.1.0 | ISC |
| date-fns | 4.4.0 | MIT |
| delaunator | 5.1.0 | ISC |
| detect-node-es | 1.1.0 | MIT |
| esm-env | 1.2.2 | MIT |
| framer-motion | 14.0.0 | MIT |
| fuse.js | 7.5.0 | Apache-2.0 |
| get-nonce | 1.0.1 | MIT |
| html-to-image | 1.11.13 | MIT |
| internmap | 2.0.3 | ISC |
| lodash | 4.18.1 | MIT |
| motion | 14.0.0 | MIT |
| motion-dom | 14.0.0 | MIT |
| motion-utils | 14.0.0 | MIT |
| number-flow | 0.6.2 | MIT |
| papaparse | 5.7.0 | MIT |
| radix-ui | 1.6.2 | MIT |
| react | 19.2.7 | MIT |
| react-dom | 19.2.7 | MIT |
| react-remove-scroll | 2.7.2 | MIT |
| react-remove-scroll-bar | 2.3.8 | MIT |
| react-style-singleton | 2.2.3 | MIT |
| robust-predicates | 3.0.3 | Unlicense |
| scheduler | 0.27.0 | MIT |
| skullet | 0.0.3 | MIT |
| sonner | 2.0.7 | MIT |
| tailwind-merge | 3.6.0 | MIT |
| tslib | 2.8.1 | 0BSD |
| tw-animate-css | 1.4.0 | MIT |
| use-callback-ref | 1.3.3 | MIT |
| use-sidecar | 1.1.3 | MIT |
| zustand | 5.0.14 | MIT |

### License texts (one copy per distinct text)

Each text below is emitted exactly once. Components reference it by the identifier
heading above. For an identifier with no local full-text file, the entry is an explicit
UNVERIFIED pointer with an upstream URL — never an invented legal body.

#### 0BSD

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://opensource.org/license/0bsd.

#### Apache-2.0

Full text source: hf-xet 1.6.0 LICENSE (full Apache License 2.0). Component-specific copyrights are listed above.

```text
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```

#### BSD-2-Clause

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://opensource.org/license/bsd-2-clause.

#### BSD-3-Clause

Full text source: av 17.1.0 LICENSE.txt (canonical BSD-3-Clause body). Component-specific copyrights are listed above.

```text
Copyright retained by original committers. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of the project nor the names of its contributors may be
      used to endorse or promote products derived from this software without
      specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

#### CC-BY-4.0

Full text source: caniuse-lite LICENSE (Attribution 4.0 International). Component-specific copyrights are listed above.

```text
Attribution 4.0 International

=======================================================================

Creative Commons Corporation ("Creative Commons") is not a law firm and
does not provide legal services or legal advice. Distribution of
Creative Commons public licenses does not create a lawyer-client or
other relationship. Creative Commons makes its licenses and related
information available on an "as-is" basis. Creative Commons gives no
warranties regarding its licenses, any material licensed under their
terms and conditions, or any related information. Creative Commons
disclaims all liability for damages resulting from their use to the
fullest extent possible.

Using Creative Commons Public Licenses

Creative Commons public licenses provide a standard set of terms and
conditions that creators and other rights holders may use to share
original works of authorship and other material subject to copyright
and certain other rights specified in the public license below. The
following considerations are for informational purposes only, are not
exhaustive, and do not form part of our licenses.

     Considerations for licensors: Our public licenses are
     intended for use by those authorized to give the public
     permission to use material in ways otherwise restricted by
     copyright and certain other rights. Our licenses are
     irrevocable. Licensors should read and understand the terms
     and conditions of the license they choose before applying it.
     Licensors should also secure all rights necessary before
     applying our licenses so that the public can reuse the
     material as expected. Licensors should clearly mark any
     material not subject to the license. This includes other CC-
     licensed material, or material used under an exception or
     limitation to copyright. More considerations for licensors:
	wiki.creativecommons.org/Considerations_for_licensors

     Considerations for the public: By using one of our public
     licenses, a licensor grants the public permission to use the
     licensed material under specified terms and conditions. If
     the licensor's permission is not necessary for any reason--for
     example, because of any applicable exception or limitation to
     copyright--then that use is not regulated by the license. Our
     licenses grant only permissions under copyright and certain
     other rights that a licensor has authority to grant. Use of
     the licensed material may still be restricted for other
     reasons, including because others have copyright or other
     rights in the material. A licensor may make special requests,
     such as asking that all changes be marked or described.
     Although not required by our licenses, you are encouraged to
     respect those requests where reasonable. More_considerations
     for the public:
	wiki.creativecommons.org/Considerations_for_licensees

=======================================================================

Creative Commons Attribution 4.0 International Public License

By exercising the Licensed Rights (defined below), You accept and agree
to be bound by the terms and conditions of this Creative Commons
Attribution 4.0 International Public License ("Public License"). To the
extent this Public License may be interpreted as a contract, You are
granted the Licensed Rights in consideration of Your acceptance of
these terms and conditions, and the Licensor grants You such rights in
consideration of benefits the Licensor receives from making the
Licensed Material available under these terms and conditions.


Section 1 -- Definitions.

  a. Adapted Material means material subject to Copyright and Similar
     Rights that is derived from or based upon the Licensed Material
     and in which the Licensed Material is translated, altered,
     arranged, transformed, or otherwise modified in a manner requiring
     permission under the Copyright and Similar Rights held by the
     Licensor. For purposes of this Public License, where the Licensed
     Material is a musical work, performance, or sound recording,
     Adapted Material is always produced where the Licensed Material is
     synched in timed relation with a moving image.

  b. Adapter's License means the license You apply to Your Copyright
     and Similar Rights in Your contributions to Adapted Material in
     accordance with the terms and conditions of this Public License.

  c. Copyright and Similar Rights means copyright and/or similar rights
     closely related to copyright including, without limitation,
     performance, broadcast, sound recording, and Sui Generis Database
     Rights, without regard to how the rights are labeled or
     categorized. For purposes of this Public License, the rights
     specified in Section 2(b)(1)-(2) are not Copyright and Similar
     Rights.

  d. Effective Technological Measures means those measures that, in the
     absence of proper authority, may not be circumvented under laws
     fulfilling obligations under Article 11 of the WIPO Copyright
     Treaty adopted on December 20, 1996, and/or similar international
     agreements.

  e. Exceptions and Limitations means fair use, fair dealing, and/or
     any other exception or limitation to Copyright and Similar Rights
     that applies to Your use of the Licensed Material.

  f. Licensed Material means the artistic or literary work, database,
     or other material to which the Licensor applied this Public
     License.

  g. Licensed Rights means the rights granted to You subject to the
     terms and conditions of this Public License, which are limited to
     all Copyright and Similar Rights that apply to Your use of the
     Licensed Material and that the Licensor has authority to license.

  h. Licensor means the individual(s) or entity(ies) granting rights
     under this Public License.

  i. Share means to provide material to the public by any means or
     process that requires permission under the Licensed Rights, such
     as reproduction, public display, public performance, distribution,
     dissemination, communication, or importation, and to make material
     available to the public including in ways that members of the
     public may access the material from a place and at a time
     individually chosen by them.

  j. Sui Generis Database Rights means rights other than copyright
     resulting from Directive 96/9/EC of the European Parliament and of
     the Council of 11 March 1996 on the legal protection of databases,
     as amended and/or succeeded, as well as other essentially
     equivalent rights anywhere in the world.

  k. You means the individual or entity exercising the Licensed Rights
     under this Public License. Your has a corresponding meaning.


Section 2 -- Scope.

  a. License grant.

       1. Subject to the terms and conditions of this Public License,
          the Licensor hereby grants You a worldwide, royalty-free,
          non-sublicensable, non-exclusive, irrevocable license to
          exercise the Licensed Rights in the Licensed Material to:

            a. reproduce and Share the Licensed Material, in whole or
               in part; and

            b. produce, reproduce, and Share Adapted Material.

       2. Exceptions and Limitations. For the avoidance of doubt, where
          Exceptions and Limitations apply to Your use, this Public
          License does not apply, and You do not need to comply with
          its terms and conditions.

       3. Term. The term of this Public License is specified in Section
          6(a).

       4. Media and formats; technical modifications allowed. The
          Licensor authorizes You to exercise the Licensed Rights in
          all media and formats whether now known or hereafter created,
          and to make technical modifications necessary to do so. The
          Licensor waives and/or agrees not to assert any right or
          authority to forbid You from making technical modifications
          necessary to exercise the Licensed Rights, including
          technical modifications necessary to circumvent Effective
          Technological Measures. For purposes of this Public License,
          simply making modifications authorized by this Section 2(a)
          (4) never produces Adapted Material.

       5. Downstream recipients.

            a. Offer from the Licensor -- Licensed Material. Every
               recipient of the Licensed Material automatically
               receives an offer from the Licensor to exercise the
               Licensed Rights under the terms and conditions of this
               Public License.

            b. No downstream restrictions. You may not offer or impose
               any additional or different terms or conditions on, or
               apply any Effective Technological Measures to, the
               Licensed Material if doing so restricts exercise of the
               Licensed Rights by any recipient of the Licensed
               Material.

       6. No endorsement. Nothing in this Public License constitutes or
          may be construed as permission to assert or imply that You
          are, or that Your use of the Licensed Material is, connected
          with, or sponsored, endorsed, or granted official status by,
          the Licensor or others designated to receive attribution as
          provided in Section 3(a)(1)(A)(i).

  b. Other rights.

       1. Moral rights, such as the right of integrity, are not
          licensed under this Public License, nor are publicity,
          privacy, and/or other similar personality rights; however, to
          the extent possible, the Licensor waives and/or agrees not to
          assert any such rights held by the Licensor to the limited
          extent necessary to allow You to exercise the Licensed
          Rights, but not otherwise.

       2. Patent and trademark rights are not licensed under this
          Public License.

       3. To the extent possible, the Licensor waives any right to
          collect royalties from You for the exercise of the Licensed
          Rights, whether directly or through a collecting society
          under any voluntary or waivable statutory or compulsory
          licensing scheme. In all other cases the Licensor expressly
          reserves any right to collect such royalties.


Section 3 -- License Conditions.

Your exercise of the Licensed Rights is expressly made subject to the
following conditions.

  a. Attribution.

       1. If You Share the Licensed Material (including in modified
          form), You must:

            a. retain the following if it is supplied by the Licensor
               with the Licensed Material:

                 i. identification of the creator(s) of the Licensed
                    Material and any others designated to receive
                    attribution, in any reasonable manner requested by
                    the Licensor (including by pseudonym if
                    designated);

                ii. a copyright notice;

               iii. a notice that refers to this Public License;

                iv. a notice that refers to the disclaimer of
                    warranties;

                 v. a URI or hyperlink to the Licensed Material to the
                    extent reasonably practicable;

            b. indicate if You modified the Licensed Material and
               retain an indication of any previous modifications; and

            c. indicate the Licensed Material is licensed under this
               Public License, and include the text of, or the URI or
               hyperlink to, this Public License.

       2. You may satisfy the conditions in Section 3(a)(1) in any
          reasonable manner based on the medium, means, and context in
          which You Share the Licensed Material. For example, it may be
          reasonable to satisfy the conditions by providing a URI or
          hyperlink to a resource that includes the required
          information.

       3. If requested by the Licensor, You must remove any of the
          information required by Section 3(a)(1)(A) to the extent
          reasonably practicable.

       4. If You Share Adapted Material You produce, the Adapter's
          License You apply must not prevent recipients of the Adapted
          Material from complying with this Public License.


Section 4 -- Sui Generis Database Rights.

Where the Licensed Rights include Sui Generis Database Rights that
apply to Your use of the Licensed Material:

  a. for the avoidance of doubt, Section 2(a)(1) grants You the right
     to extract, reuse, reproduce, and Share all or a substantial
     portion of the contents of the database;

  b. if You include all or a substantial portion of the database
     contents in a database in which You have Sui Generis Database
     Rights, then the database in which You have Sui Generis Database
     Rights (but not its individual contents) is Adapted Material; and

  c. You must comply with the conditions in Section 3(a) if You Share
     all or a substantial portion of the contents of the database.

For the avoidance of doubt, this Section 4 supplements and does not
replace Your obligations under this Public License where the Licensed
Rights include other Copyright and Similar Rights.


Section 5 -- Disclaimer of Warranties and Limitation of Liability.

  a. UNLESS OTHERWISE SEPARATELY UNDERTAKEN BY THE LICENSOR, TO THE
     EXTENT POSSIBLE, THE LICENSOR OFFERS THE LICENSED MATERIAL AS-IS
     AND AS-AVAILABLE, AND MAKES NO REPRESENTATIONS OR WARRANTIES OF
     ANY KIND CONCERNING THE LICENSED MATERIAL, WHETHER EXPRESS,
     IMPLIED, STATUTORY, OR OTHER. THIS INCLUDES, WITHOUT LIMITATION,
     WARRANTIES OF TITLE, MERCHANTABILITY, FITNESS FOR A PARTICULAR
     PURPOSE, NON-INFRINGEMENT, ABSENCE OF LATENT OR OTHER DEFECTS,
     ACCURACY, OR THE PRESENCE OR ABSENCE OF ERRORS, WHETHER OR NOT
     KNOWN OR DISCOVERABLE. WHERE DISCLAIMERS OF WARRANTIES ARE NOT
     ALLOWED IN FULL OR IN PART, THIS DISCLAIMER MAY NOT APPLY TO YOU.

  b. TO THE EXTENT POSSIBLE, IN NO EVENT WILL THE LICENSOR BE LIABLE
     TO YOU ON ANY LEGAL THEORY (INCLUDING, WITHOUT LIMITATION,
     NEGLIGENCE) OR OTHERWISE FOR ANY DIRECT, SPECIAL, INDIRECT,
     INCIDENTAL, CONSEQUENTIAL, PUNITIVE, EXEMPLARY, OR OTHER LOSSES,
     COSTS, EXPENSES, OR DAMAGES ARISING OUT OF THIS PUBLIC LICENSE OR
     USE OF THE LICENSED MATERIAL, EVEN IF THE LICENSOR HAS BEEN
     ADVISED OF THE POSSIBILITY OF SUCH LOSSES, COSTS, EXPENSES, OR
     DAMAGES. WHERE A LIMITATION OF LIABILITY IS NOT ALLOWED IN FULL OR
     IN PART, THIS LIMITATION MAY NOT APPLY TO YOU.

  c. The disclaimer of warranties and limitation of liability provided
     above shall be interpreted in a manner that, to the extent
     possible, most closely approximates an absolute disclaimer and
     waiver of all liability.


Section 6 -- Term and Termination.

  a. This Public License applies for the term of the Copyright and
     Similar Rights licensed here. However, if You fail to comply with
     this Public License, then Your rights under this Public License
     terminate automatically.

  b. Where Your right to use the Licensed Material has terminated under
     Section 6(a), it reinstates:

       1. automatically as of the date the violation is cured, provided
          it is cured within 30 days of Your discovery of the
          violation; or

       2. upon express reinstatement by the Licensor.

     For the avoidance of doubt, this Section 6(b) does not affect any
     right the Licensor may have to seek remedies for Your violations
     of this Public License.

  c. For the avoidance of doubt, the Licensor may also offer the
     Licensed Material under separate terms or conditions or stop
     distributing the Licensed Material at any time; however, doing so
     will not terminate this Public License.

  d. Sections 1, 5, 6, 7, and 8 survive termination of this Public
     License.


Section 7 -- Other Terms and Conditions.

  a. The Licensor shall not be bound by any additional or different
     terms or conditions communicated by You unless expressly agreed.

  b. Any arrangements, understandings, or agreements regarding the
     Licensed Material not stated herein are separate from and
     independent of the terms and conditions of this Public License.


Section 8 -- Interpretation.

  a. For the avoidance of doubt, this Public License does not, and
     shall not be interpreted to, reduce, limit, restrict, or impose
     conditions on any use of the Licensed Material that could lawfully
     be made without permission under this Public License.

  b. To the extent possible, if any provision of this Public License is
     deemed unenforceable, it shall be automatically reformed to the
     minimum extent necessary to make it enforceable. If the provision
     cannot be reformed, it shall be severed from this Public License
     without affecting the enforceability of the remaining terms and
     conditions.

  c. No term or condition of this Public License will be waived and no
     failure to comply consented to unless expressly agreed to by the
     Licensor.

  d. Nothing in this Public License constitutes or may be interpreted
     as a limitation upon, or waiver of, any privileges and immunities
     that apply to the Licensor or You, including from the legal
     processes of any jurisdiction or authority.


=======================================================================

Creative Commons is not a party to its public
licenses. Notwithstanding, Creative Commons may elect to apply one of
its public licenses to material it publishes and in those instances
will be considered the “Licensor.” The text of the Creative Commons
public licenses is dedicated to the public domain under the CC0 Public
Domain Dedication. Except for the limited purpose of indicating that
material is shared under a Creative Commons public license or as
otherwise permitted by the Creative Commons policies published at
creativecommons.org/policies, Creative Commons does not authorize the
use of the trademark "Creative Commons" or any other trademark or logo
of Creative Commons without its prior written consent including,
without limitation, in connection with any unauthorized modifications
to any of its public licenses or any other arrangements,
understandings, or agreements concerning use of licensed material. For
the avoidance of doubt, this paragraph does not form part of the
public licenses.

Creative Commons may be contacted at creativecommons.org.
```

#### CC0-1.0

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://creativecommons.org/publicdomain/zero/1.0/.

#### CNRI-Python

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://opensource.org/license/cnri-python.

#### GCC-exception-3.1

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://www.gnu.org/licenses/gcc-exception-3.1.html.

#### ISC

Full text source: d3-array 3.2.4 LICENSE (canonical ISC body). Component-specific copyrights are listed above.

```text
Copyright 2010-2023 Mike Bostock

Permission to use, copy, modify, and/or distribute this software for any purpose
with or without fee is hereby granted, provided that the above copyright notice
and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF
THIS SOFTWARE.
```

#### LGPL-2.1-or-later

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.

#### LGPL-3.0-or-later

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://www.gnu.org/licenses/lgpl-3.0.html.

#### MIT

Full text source: react 19.2.7 LICENSE (canonical MIT body). Component-specific copyrights are listed above.

```text
MIT License

Copyright (c) Meta Platforms, Inc. and affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

#### MIT-0

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://opensource.org/license/mit-0.

#### MPL-2.0

Full text source: cssparser 0.37.0 LICENSE (full MPL 2.0). Component-specific copyrights are listed above.

```text
Mozilla Public License Version 2.0
==================================

1. Definitions
--------------

1.1. "Contributor"
    means each individual or legal entity that creates, contributes to
    the creation of, or owns Covered Software.

1.2. "Contributor Version"
    means the combination of the Contributions of others (if any) used
    by a Contributor and that particular Contributor's Contribution.

1.3. "Contribution"
    means Covered Software of a particular Contributor.

1.4. "Covered Software"
    means Source Code Form to which the initial Contributor has attached
    the notice in Exhibit A, the Executable Form of such Source Code
    Form, and Modifications of such Source Code Form, in each case
    including portions thereof.

1.5. "Incompatible With Secondary Licenses"
    means

    (a) that the initial Contributor has attached the notice described
        in Exhibit B to the Covered Software; or

    (b) that the Covered Software was made available under the terms of
        version 1.1 or earlier of the License, but not also under the
        terms of a Secondary License.

1.6. "Executable Form"
    means any form of the work other than Source Code Form.

1.7. "Larger Work"
    means a work that combines Covered Software with other material, in
    a separate file or files, that is not Covered Software.

1.8. "License"
    means this document.

1.9. "Licensable"
    means having the right to grant, to the maximum extent possible,
    whether at the time of the initial grant or subsequently, any and
    all of the rights conveyed by this License.

1.10. "Modifications"
    means any of the following:

    (a) any file in Source Code Form that results from an addition to,
        deletion from, or modification of the contents of Covered
        Software; or

    (b) any new file in Source Code Form that contains any Covered
        Software.

1.11. "Patent Claims" of a Contributor
    means any patent claim(s), including without limitation, method,
    process, and apparatus claims, in any patent Licensable by such
    Contributor that would be infringed, but for the grant of the
    License, by the making, using, selling, offering for sale, having
    made, import, or transfer of either its Contributions or its
    Contributor Version.

1.12. "Secondary License"
    means either the GNU General Public License, Version 2.0, the GNU
    Lesser General Public License, Version 2.1, the GNU Affero General
    Public License, Version 3.0, or any later versions of those
    licenses.

1.13. "Source Code Form"
    means the form of the work preferred for making modifications.

1.14. "You" (or "Your")
    means an individual or a legal entity exercising rights under this
    License. For legal entities, "You" includes any entity that
    controls, is controlled by, or is under common control with You. For
    purposes of this definition, "control" means (a) the power, direct
    or indirect, to cause the direction or management of such entity,
    whether by contract or otherwise, or (b) ownership of more than
    fifty percent (50%) of the outstanding shares or beneficial
    ownership of such entity.

2. License Grants and Conditions
--------------------------------

2.1. Grants

Each Contributor hereby grants You a world-wide, royalty-free,
non-exclusive license:

(a) under intellectual property rights (other than patent or trademark)
    Licensable by such Contributor to use, reproduce, make available,
    modify, display, perform, distribute, and otherwise exploit its
    Contributions, either on an unmodified basis, with Modifications, or
    as part of a Larger Work; and

(b) under Patent Claims of such Contributor to make, use, sell, offer
    for sale, have made, import, and otherwise transfer either its
    Contributions or its Contributor Version.

2.2. Effective Date

The licenses granted in Section 2.1 with respect to any Contribution
become effective for each Contribution on the date the Contributor first
distributes such Contribution.

2.3. Limitations on Grant Scope

The licenses granted in this Section 2 are the only rights granted under
this License. No additional rights or licenses will be implied from the
distribution or licensing of Covered Software under this License.
Notwithstanding Section 2.1(b) above, no patent license is granted by a
Contributor:

(a) for any code that a Contributor has removed from Covered Software;
    or

(b) for infringements caused by: (i) Your and any other third party's
    modifications of Covered Software, or (ii) the combination of its
    Contributions with other software (except as part of its Contributor
    Version); or

(c) under Patent Claims infringed by Covered Software in the absence of
    its Contributions.

This License does not grant any rights in the trademarks, service marks,
or logos of any Contributor (except as may be necessary to comply with
the notice requirements in Section 3.4).

2.4. Subsequent Licenses

No Contributor makes additional grants as a result of Your choice to
distribute the Covered Software under a subsequent version of this
License (see Section 10.2) or under the terms of a Secondary License (if
permitted under the terms of Section 3.3).

2.5. Representation

Each Contributor represents that the Contributor believes its
Contributions are its original creation(s) or it has sufficient rights
to grant the rights to its Contributions conveyed by this License.

2.6. Fair Use

This License is not intended to limit any rights You have under
applicable copyright doctrines of fair use, fair dealing, or other
equivalents.

2.7. Conditions

Sections 3.1, 3.2, 3.3, and 3.4 are conditions of the licenses granted
in Section 2.1.

3. Responsibilities
-------------------

3.1. Distribution of Source Form

All distribution of Covered Software in Source Code Form, including any
Modifications that You create or to which You contribute, must be under
the terms of this License. You must inform recipients that the Source
Code Form of the Covered Software is governed by the terms of this
License, and how they can obtain a copy of this License. You may not
attempt to alter or restrict the recipients' rights in the Source Code
Form.

3.2. Distribution of Executable Form

If You distribute Covered Software in Executable Form then:

(a) such Covered Software must also be made available in Source Code
    Form, as described in Section 3.1, and You must inform recipients of
    the Executable Form how they can obtain a copy of such Source Code
    Form by reasonable means in a timely manner, at a charge no more
    than the cost of distribution to the recipient; and

(b) You may distribute such Executable Form under the terms of this
    License, or sublicense it under different terms, provided that the
    license for the Executable Form does not attempt to limit or alter
    the recipients' rights in the Source Code Form under this License.

3.3. Distribution of a Larger Work

You may create and distribute a Larger Work under terms of Your choice,
provided that You also comply with the requirements of this License for
the Covered Software. If the Larger Work is a combination of Covered
Software with a work governed by one or more Secondary Licenses, and the
Covered Software is not Incompatible With Secondary Licenses, this
License permits You to additionally distribute such Covered Software
under the terms of such Secondary License(s), so that the recipient of
the Larger Work may, at their option, further distribute the Covered
Software under the terms of either this License or such Secondary
License(s).

3.4. Notices

You may not remove or alter the substance of any license notices
(including copyright notices, patent notices, disclaimers of warranty,
or limitations of liability) contained within the Source Code Form of
the Covered Software, except that You may alter any license notices to
the extent required to remedy known factual inaccuracies.

3.5. Application of Additional Terms

You may choose to offer, and to charge a fee for, warranty, support,
indemnity or liability obligations to one or more recipients of Covered
Software. However, You may do so only on Your own behalf, and not on
behalf of any Contributor. You must make it absolutely clear that any
such warranty, support, indemnity, or liability obligation is offered by
You alone, and You hereby agree to indemnify every Contributor for any
liability incurred by such Contributor as a result of warranty, support,
indemnity or liability terms You offer. You may include additional
disclaimers of warranty and limitations of liability specific to any
jurisdiction.

4. Inability to Comply Due to Statute or Regulation
---------------------------------------------------

If it is impossible for You to comply with any of the terms of this
License with respect to some or all of the Covered Software due to
statute, judicial order, or regulation then You must: (a) comply with
the terms of this License to the maximum extent possible; and (b)
describe the limitations and the code they affect. Such description must
be placed in a text file included with all distributions of the Covered
Software under this License. Except to the extent prohibited by statute
or regulation, such description must be sufficiently detailed for a
recipient of ordinary skill to be able to understand it.

5. Termination
--------------

5.1. The rights granted under this License will terminate automatically
if You fail to comply with any of its terms. However, if You become
compliant, then the rights granted under this License from a particular
Contributor are reinstated (a) provisionally, unless and until such
Contributor explicitly and finally terminates Your grants, and (b) on an
ongoing basis, if such Contributor fails to notify You of the
non-compliance by some reasonable means prior to 60 days after You have
come back into compliance. Moreover, Your grants from a particular
Contributor are reinstated on an ongoing basis if such Contributor
notifies You of the non-compliance by some reasonable means, this is the
first time You have received notice of non-compliance with this License
from such Contributor, and You become compliant prior to 30 days after
Your receipt of the notice.

5.2. If You initiate litigation against any entity by asserting a patent
infringement claim (excluding declaratory judgment actions,
counter-claims, and cross-claims) alleging that a Contributor Version
directly or indirectly infringes any patent, then the rights granted to
You by any and all Contributors for the Covered Software under Section
2.1 of this License shall terminate.

5.3. In the event of termination under Sections 5.1 or 5.2 above, all
end user license agreements (excluding distributors and resellers) which
have been validly granted by You or Your distributors under this License
prior to termination shall survive termination.

************************************************************************
*                                                                      *
*  6. Disclaimer of Warranty                                           *
*  -------------------------                                           *
*                                                                      *
*  Covered Software is provided under this License on an "as is"       *
*  basis, without warranty of any kind, either expressed, implied, or  *
*  statutory, including, without limitation, warranties that the       *
*  Covered Software is free of defects, merchantable, fit for a        *
*  particular purpose or non-infringing. The entire risk as to the     *
*  quality and performance of the Covered Software is with You.        *
*  Should any Covered Software prove defective in any respect, You     *
*  (not any Contributor) assume the cost of any necessary servicing,   *
*  repair, or correction. This disclaimer of warranty constitutes an   *
*  essential part of this License. No use of any Covered Software is   *
*  authorized under this License except under this disclaimer.         *
*                                                                      *
************************************************************************

************************************************************************
*                                                                      *
*  7. Limitation of Liability                                          *
*  --------------------------                                          *
*                                                                      *
*  Under no circumstances and under no legal theory, whether tort      *
*  (including negligence), contract, or otherwise, shall any           *
*  Contributor, or anyone who distributes Covered Software as          *
*  permitted above, be liable to You for any direct, indirect,         *
*  special, incidental, or consequential damages of any character      *
*  including, without limitation, damages for lost profits, loss of    *
*  goodwill, work stoppage, computer failure or malfunction, or any    *
*  and all other commercial damages or losses, even if such party      *
*  shall have been informed of the possibility of such damages. This   *
*  limitation of liability shall not apply to liability for death or   *
*  personal injury resulting from such party's negligence to the       *
*  extent applicable law prohibits such limitation. Some               *
*  jurisdictions do not allow the exclusion or limitation of           *
*  incidental or consequential damages, so this exclusion and          *
*  limitation may not apply to You.                                    *
*                                                                      *
************************************************************************

8. Litigation
-------------

Any litigation relating to this License may be brought only in the
courts of a jurisdiction where the defendant maintains its principal
place of business and such litigation shall be governed by laws of that
jurisdiction, without reference to its conflict-of-law provisions.
Nothing in this Section shall prevent a party's ability to bring
cross-claims or counter-claims.

9. Miscellaneous
----------------

This License represents the complete agreement concerning the subject
matter hereof. If any provision of this License is held to be
unenforceable, such provision shall be reformed only to the extent
necessary to make it enforceable. Any law or regulation which provides
that the language of a contract shall be construed against the drafter
shall not be used to construe this License against a Contributor.

10. Versions of the License
---------------------------

10.1. New Versions

Mozilla Foundation is the license steward. Except as provided in Section
10.3, no one other than the license steward has the right to modify or
publish new versions of this License. Each version will be given a
distinguishing version number.

10.2. Effect of New Versions

You may distribute the Covered Software under the terms of the version
of the License under which You originally received the Covered Software,
or under the terms of any subsequent version published by the license
steward.

10.3. Modified Versions

If you create software not governed by this License, and you want to
create a new license for such software, you may create and use a
modified version of this License if you rename the license and remove
any references to the name of the license steward (except to note that
such modified license differs from this License).

10.4. Distributing Source Code Form that is Incompatible With Secondary
Licenses

If You choose to distribute Source Code Form that is Incompatible With
Secondary Licenses under the terms of this version of the License, the
notice described in Exhibit B of this License must be attached.

Exhibit A - Source Code Form License Notice
-------------------------------------------

  This Source Code Form is subject to the terms of the Mozilla Public
  License, v. 2.0. If a copy of the MPL was not distributed with this
  file, You can obtain one at http://mozilla.org/MPL/2.0/.

If it is not possible or desirable to put the notice in a particular
file, then You may include the notice in a location (such as a LICENSE
file in a relevant directory) where a recipient would be likely to look
for such a notice.

You may add additional accurate notices of copyright ownership.

Exhibit B - "Incompatible With Secondary Licenses" Notice
---------------------------------------------------------

  This Source Code Form is "Incompatible With Secondary Licenses", as
  defined by the Mozilla Public License, v. 2.0.
```

#### MSVC-Redistrib

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170.

#### NVIDIA-Proprietary

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://docs.nvidia.com/cuda/eula/index.html.

#### OFL-1.1

Full text source: LICENSES.chromium.html SIL Open Font License 1.1 section. Component-specific copyrights are listed above.

```text
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded,
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.
```

#### PSF-2.0

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://docs.python.org/3/license.html.

#### PolyForm-Strict-1.0.0

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://polyformproject.org/licenses/strict/1.0.0/.

#### PortAudio-MIT

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://portaudio.com/license.html.

#### UNVERIFIED

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion.

#### Unicode-3.0

Full text source: icu_collections 2.2.0 LICENSE (Unicode License V3). Component-specific copyrights are listed above.

```text
UNICODE LICENSE V3

COPYRIGHT AND PERMISSION NOTICE

Copyright © 2020-2024 Unicode, Inc.

NOTICE TO USER: Carefully read the following legal agreement. BY
DOWNLOADING, INSTALLING, COPYING OR OTHERWISE USING DATA FILES, AND/OR
SOFTWARE, YOU UNEQUIVOCALLY ACCEPT, AND AGREE TO BE BOUND BY, ALL OF THE
TERMS AND CONDITIONS OF THIS AGREEMENT. IF YOU DO NOT AGREE, DO NOT
DOWNLOAD, INSTALL, COPY, DISTRIBUTE OR USE THE DATA FILES OR SOFTWARE.

Permission is hereby granted, free of charge, to any person obtaining a
copy of data files and any associated documentation (the "Data Files") or
software and any associated documentation (the "Software") to deal in the
Data Files or Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, and/or sell
copies of the Data Files or Software, and to permit persons to whom the
Data Files or Software are furnished to do so, provided that either (a)
this copyright and permission notice appear with all copies of the Data
Files or Software, or (b) this copyright and permission notice appear in
associated Documentation.

THE DATA FILES AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF
THIRD PARTY RIGHTS.

IN NO EVENT SHALL THE COPYRIGHT HOLDER OR HOLDERS INCLUDED IN THIS NOTICE
BE LIABLE FOR ANY CLAIM, OR ANY SPECIAL INDIRECT OR CONSEQUENTIAL DAMAGES,
OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THE DATA
FILES OR SOFTWARE.

Except as contained in this notice, the name of a copyright holder shall
not be used in advertising or otherwise to promote the sale, use or other
dealings in these Data Files or Software without prior written
authorization of the copyright holder.

SPDX-License-Identifier: Unicode-3.0

—

Portions of ICU4X may have been adapted from ICU4C and/or ICU4J.
ICU 1.8.1 to ICU 57.1 © 1995-2016 International Business Machines Corporation and others.
```

#### Unlicense

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://unlicense.org/.

#### Zlib

No full license-text file was found in the installed Windows output for this identifier. Marked UNVERIFIED where local evidence is absent; no legal conclusion. Upstream documentation: https://opensource.org/license/zlib.

### UNVERIFIED items (local evidence absent)

Shipped-file statements come first; upstream facts are URL-labelled documentation and
never override shipped-file evidence. No legal conclusion is made.

| Component | Shipped | Reason / upstream documentation |
|---|---|---|
| _pydantic_core.pyd | PRESENT | PRESENT; no dist-info or licence text. Upstream https://github.com/pydantic/pydantic-core |
| certifi | see above | Shipped; MPL notice text not present in the installed output. Upstream https://github.com/certifi/python-certifi |
| CPython runtime (python312.dll, python3.dll, stdlib .pyd) | PRESENT | PRESENT; PE 3.12.10 differs from dev .venv 3.13.7; no licence file shipped. Upstream https://docs.python.org/3/license.html |
| InterVariable.woff2 / InterVariable-Italic.woff2 | see above | Found in stale dist/; no local OFL.txt. Upstream https://scripts.sil.org/OFL |
| libffi-8.dll | PRESENT | PRESENT; no version resource. Upstream https://github.com/libffi/libffi/blob/master/LICENSE |
| libsndfile_x64.dll | PRESENT | PRESENT in onefile cache; no licence file shipped. Local .venv COPYING: 'GNU LESSER GENERAL PUBLIC LICENSE Version 2.1, February 1999'. |
| MSVC runtime (vcruntime140.dll, vcruntime140_1.dll) | PRESENT | PRESENT; no licence file shipped. Upstream https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170 |
| OpenBLAS DLLs (numpy.libs, scipy.libs) | PRESENT | PRESENT; exception text not shipped; hash suffixes differ from .venv RECORD, provenance UNVERIFIED. |
| OpenSSL (libcrypto-3.dll, libssl-3.dll) | PRESENT | PRESENT; Apache-2.0 NOTICE text not shipped. Upstream https://www.openssl.org/source/license.html |
| PortAudio (libportaudio64bit.dll, libportaudio64bit-asio.dll) | PRESENT | PRESENT; no licence file shipped. Upstream https://portaudio.com/license.html |
| pydantic-core | see above | No installed dist-info; upstream hint only https://github.com/pydantic/pydantic-core |
| pywin32 binaries | PRESENT | PRESENT; no dist-info in dev venv. Upstream https://github.com/mhammond/pywin32 |
| silero_vad.onnx | PRESENT | PRESENT; no licence file beside the model. Upstream https://github.com/snakers4/silero-vad/blob/master/LICENSE |
| tzdata | see above | No local version evidence in the installed output. |
| uninstall.exe (NSIS) | PRESENT | PRESENT; linked modules unverified. |
| zstandard | see above | Upstream hint only https://github.com/facebook/zstd |
| zstandard _cffi.pyd / backend_c.pyd | PRESENT | PRESENT; no dist-info or licence text. Upstream https://github.com/facebook/zstd |

<!-- END GENERATED THIRD-PARTY NOTICES -->
