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

## PyAV

- **Status:** still bundled until faster-whisper and `av` are removed. Media
  decoding no longer uses PyAV; faster-whisper still imports `av` at module
  scope, so the wheel and its DLLs remain in the shipped app for now.
- **Homepage:** https://github.com/PyAV-Org/PyAV
- **License:** BSD 3-Clause
- **Locked version (binary verified):** `av==17.1.0` (`requirements-lock.txt:11`);
  installed version `av.__version__ = 17.1.0`; wheel tag `cp311-abi3-win_amd64`
  (`av-17.1.0.dist-info/WHEEL`). PyAV's own licence is BSD-3-Clause.
- **Bundled FFmpeg libraries (binary facts, Windows wheel):** all six DLLs
  report the SAME answer from their own C exports — `avutil_license()`,
  `avcodec_license()`, `avformat_license()`, `swresample_license()`,
  `swscale_license()` and `avfilter_license()` each return verbatim:
  `LGPL version 3 or later`. PyAV's `av.library_versions` reports
  `libavutil (60, 26, 101)`, `libavcodec (62, 28, 101)`,
  `libavformat (62, 12, 101)`, `libavdevice (62, 3, 101)`,
  `libavfilter (11, 14, 101)`, `libswscale (9, 5, 101)` and
  `libswresample (6, 3, 101)`. The wheel's `av.libs` folder holds **25 DLL
  files** (counted with `find av.libs -maxdepth 1 -name '*.dll' | wc -l`).
  Individual byte sizes are deliberately not recorded here — they go stale;
  file names are listed in the table below.
- **Configuration (verbatim, identical from all six libraries):**
  ```
  --disable-static --enable-shared --libdir=/c/cibw/vendor/lib --prefix=/c/cibw/vendor --disable-programs --disable-doc --disable-libxml2 --disable-lzma --disable-libtheora --disable-libfreetype --disable-libfontconfig --disable-libbluray --disable-libopenjpeg --enable-mediafoundation --enable-version3 --disable-alsa --disable-gnutls --enable-libdav1d --enable-libmp3lame --enable-libopencore-amrnb --enable-libopencore-amrwb --enable-libopus --enable-libsvtav1 --enable-libvpx --enable-libwebp --disable-libxcb --enable-zlib --enable-libx264 --enable-libx265 --enable-nvenc --enable-nvdec --enable-amf --enable-libvpl --disable-encoder='avui,dca,mlp,opus,s302m,sonic,sonic_ls,truehd' --disable-decoder=sonic --disable-libjack --disable-indev=jack --disable-filter=gfxcapture
  ```
  The string contains neither `--enable-gpl` nor `--enable-nonfree`, but the
  x264/x265 encoders are present and are load-time imports of `avcodec-62`.
  The authoritative answer from the shipped libraries is the `*_license()`
  output above: **LGPL version 3 or later**. *Upstream documentation*
  (https://raw.githubusercontent.com/PyAV-Org/pyav-ffmpeg/8.1.1-2/patches/ffmpeg.patch)
  explains the contradiction: the recipe patches FFmpeg 8.1.1 `configure` to
  move `libx264`/`libx265` out of `EXTERNAL_LIBRARY_GPL_LIST` into
  `EXTERNAL_LIBRARY_VERSION3_LIST`, so `--enable-version3` selects
  `LGPL version 3 or later` even though both GPL libraries are linked.
  Patches are not echoed into `FFMPEG_CONFIGURATION`, which is built from the
  command-line arguments only (upstream documentation:
  https://raw.githubusercontent.com/FFmpeg/FFmpeg/n8.1.1/configure). This
  upstream explanation is NOT binary evidence and does not override the
  `*_license()` strings.

### Bundled third-party DLLs (binary/wheel facts and upstream documentation)

The wheel's `av-17.1.0.dist-info/METADATA` states `License-Expression: BSD-3-Clause`,
`License-File: LICENSE.txt`, `License-File: AUTHORS.py`, `License-File: AUTHORS.rst` —
these are PyAV's own Python-binding terms. No per-DLL licence field exists in
`METADATA`, `RECORD`, `WHEEL` or `DELVEWHEEL`, and `av.libs/` plus `av/` contain
no LICENSE/NOTICE/COPYING/README text. "Wheel" below therefore means the
DLL's own embedded version-resource / printable strings where present.
"Upstream" below is documentation, not a fact read from the shipped binary.

| File | From the wheel (verbatim or "not stated") | Upstream licence (documentation) | URL |
|---|---|---|---|
| `avcodec-62-0f4d449c1bbaaa5eeb9f8a10b4cc7e85.dll` | `FileDescription: FFmpeg codec library`; `LegalCopyright: Copyright (C) 2000-2026 FFmpeg Project`; `ProductVersion: 8.1.1`; embedded `libavcodec license: LGPL version 3 or later` | FFmpeg core LGPL v2.1+; this build LGPL v3+ per binary; upstream lists libx264/libx265 as GPLv2 | https://github.com/FFmpeg/FFmpeg/blob/n8.1.1/LICENSE.md |
| `avdevice-62-e71ffbe296e3d34589fb064328316bfc.dll` | `FileDescription: FFmpeg device handling library`; `ProductVersion: 8.1.1`; embedded `libavdevice license: LGPL version 3 or later` | FFmpeg core LGPL v2.1+; this build LGPL v3+ per binary | https://github.com/FFmpeg/FFmpeg/blob/n8.1.1/LICENSE.md |
| `avfilter-11-780a5681e7b21881ef585cd5ce000321.dll` | `FileDescription: FFmpeg audio/video filtering library`; embedded `libavfilter license: LGPL version 3 or later` | FFmpeg core LGPL v2.1+; this build LGPL v3+ per binary | https://github.com/FFmpeg/FFmpeg/blob/n8.1.1/LICENSE.md |
| `avformat-62-9c2d3ee2527a13ca0fdcb82b33ed040a.dll` | `FileDescription: FFmpeg container format library`; embedded `libavformat license: LGPL version 3 or later` | FFmpeg core LGPL v2.1+; this build LGPL v3+ per binary | https://github.com/FFmpeg/FFmpeg/blob/n8.1.1/LICENSE.md |
| `avutil-60-21bd72d722406bd9f4b24262cf4b35f3.dll` | `FileDescription: FFmpeg utility library`; embedded `libavutil license: LGPL version 3 or later` | FFmpeg core LGPL v2.1+; this build LGPL v3+ per binary | https://github.com/FFmpeg/FFmpeg/blob/n8.1.1/LICENSE.md |
| `swresample-6-2f06f0ee7dafc4af6aa424f40df61d57.dll` | `FileDescription: FFmpeg audio resampling library`; embedded `libswresample license: LGPL version 3 or later` | FFmpeg core LGPL v2.1+; this build LGPL v3+ per binary | https://github.com/FFmpeg/FFmpeg/blob/n8.1.1/LICENSE.md |
| `swscale-9-23c45a0fb3712fe0e8e3dafd8d2fd7d1.dll` | `FileDescription: FFmpeg image rescaling library`; embedded `libswscale license: LGPL version 3 or later` | FFmpeg core LGPL v2.1+; this build LGPL v3+ per binary | https://github.com/FFmpeg/FFmpeg/blob/n8.1.1/LICENSE.md |
| `libdav1d-d92ea30c3d9c9934f860c34d1ba70766.dll` | `FileDescription: dav1d 1.5.3 - AV1 decoder`; `CompanyName: VideoLAN`; licence word not stated | BSD 2-Clause (permissive) | https://github.com/videolan/dav1d/blob/master/COPYING |
| `libgcc_s_seh-1-eb70c1c038eb1106448e1bc7e15ae24a.dll` | not stated | GPLv3 with GCC Runtime Library Exception 3.1 (copyleft-with-exception) | https://www.gnu.org/licenses/gcc-exception-3.1.html |
| `libiconv-2-52797ea4538a440d60943a017fb87a4f.dll` | `FileDescription: LGPLed libiconv for Windows`; `FileVersion: 1.19`; `Comments: This library is free software; ... under the terms of the GNU Lesser General Public License.` | LGPL v2.1 or later (weak copyleft) | https://www.gnu.org/software/libiconv/ |
| `libmp3lame-0-7a64829d195e8823e9b581d29ebd8775.dll` | not stated | LGPL v2 (weak copyleft) | https://lame.sourceforge.io/ |
| `libopencore-amrnb-0-39f66c13099c652115aad3e3dbebfd3a.dll` | not stated | Apache-2.0 (permissive) | https://www.apache.org/licenses/LICENSE-2.0 |
| `libopencore-amrwb-0-715bb0ad19b03fa41dd3753676655d28.dll` | not stated | Apache-2.0 (permissive) | https://www.apache.org/licenses/LICENSE-2.0 |
| `libopus-0-b7c59d64d75a04d4907fe3036e46c927.dll` | not stated | BSD 3-Clause (permissive) | https://github.com/xiph/opus/blob/master/COPYING |
| `libsharpyuv-25eb0c4836aeeccd9b98aeb9ee77a148.dll` | not stated | BSD 3-Clause, part of libwebp (permissive) | https://github.com/webmproject/libwebp/blob/main/COPYING |
| `libstdc++-6-6cc2d0c6172bc373353f289ef20782fe.dll` | not stated | GPLv3 with GCC Runtime Library Exception 3.1 (copyleft-with-exception) | https://gcc.gnu.org/onlinedocs/libstdc++/manual/license.html |
| `libSvtAv1Enc-5eeef79489c86980df49968253b5be77.dll` | not stated | BSD 3-Clause Clear (permissive) | https://github.com/AOMediaCodec/SVT-AV1/blob/v4.1.0/LICENSE.md |
| `libvpl-7122e3918b8fda828a5af6af73ca944b.dll` | `FileDescription: Intelr VPL Dispatcher`; `FileVersion: 2.16.0.0`; licence word not stated | MIT (permissive) | https://github.com/intel/libvpl/blob/v2.16.0/LICENSE |
| `libvpx-1-c0f634e6ca42adeec806716d1a9e5c3e.dll` | not stated | BSD 3-Clause (permissive) | https://github.com/webmproject/libvpx/blob/main/LICENSE |
| `libwebp-e5d4f9543eae6d381f6212f006b75bdc.dll` | not stated | BSD 3-Clause (permissive) | https://github.com/webmproject/libwebp/blob/main/COPYING |
| `libwebpmux-c7c66c64054d42d6a25d9c92afeb2d3f.dll` | not stated | BSD 3-Clause (permissive) | https://github.com/webmproject/libwebp/blob/main/COPYING |
| `libwinpthread-1-26b1e143f68b103d25cd0ba0a146f5b4.dll` | `FileDescription: POSIX WinThreads for Windows`; `LegalCopyright: Copyright (C) MinGW-W64 Project Members 2010-2023`; licence word not stated | mingw-w64 winpthreads MIT-style + Lockless BSD-style (permissive), NOT GPL | https://github.com/mingw-w64/mingw-w64/blob/master/mingw-w64-libraries/winpthreads/COPYING |
| `libx264-165-71900781b680e0e06a1b966b46fee000.dll` | `FileDescription: H.264 (MPEG-4 AVC) encoder library`; `ProductName: x264`; `ProductVersion: 0.165.x`; licence word not stated | GPL v2 (strong copyleft) | https://github.com/mirror/x264/blob/master/COPYING |
| `libx265-7e74dd5103fd9dad5114dffeefd474ce.dll` | `FileDescription: HEVC video encoder`; `LegalCopyright: Multicoreware: GPLv2 or commercial`; `ProductVersion: 4.2+1-e444744` | GPL v2 or commercial (strong copyleft, dual) | https://github.com/videolan/x265/blob/master/COPYING |
| `zlib1-df406c365e4a532adb993bd06f95ca24.dll` | not stated (embedded `zlibVersion`, not a licence) | zlib licence (permissive) | https://zlib.net/zlib_license.html |

Facts, not conclusions: the table marks GPL v2 for libx264, GPL v2-or-commercial for libx265, LGPL for the FFmpeg libraries, libiconv and libmp3lame, GPLv3 with the GCC Runtime Library Exception 3.1 for the two GCC runtimes, and permissive terms for the remaining libraries. The two GPL DLLs are load-time imports of `avcodec-62`, so Windows loads them whenever avcodec loads. Source-offer and replaceability remain **pending owner decision**; no compliance claim is made.
- **Codecs verified with this wheel:** present — libx264, libx265, libx264rgb,
  libmp3lame, libopus, aac, libvpx, libvpx-vp9, libdav1d (decode only);
  absent — libxvid, libvorbis, libfdk_aac, libaom-av1. All 14 names containing
  "lib" in `av.codecs_available`: libdav1d, libmp3lame, libopencore_amrnb,
  libopencore_amrwb, libopus, libsvtav1, libvpx, libvpx-vp9, libwebp,
  libwebp_anim, libx264, libx264rgb, libx265, zlib.
- **Use:** Container/codec decode of local files and remote audio streams
  to 16 kHz mono PCM.
- **Redistribution note:** Nuitka onefile bundles these shared libraries inside
  a self-extracting executable; users cannot replace them as separate files.
  A corresponding-source offer for these exact library versions and the
  replaceability question are **pending owner decision**. No compliance claim
  is made.

## FFmpeg (LGPL-only executable, Windows x64)

- **Source (upstream documentation):** FFmpeg-Builds LGPL autobuild, immutable tag
  `autobuild-2026-11-20-12-40` —
  https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/tag/autobuild-2026-11-20-12-40
  (build scripts: https://github.com/FFmpeg-Builds/FFmpeg-Builds/tree/autobuild-2026-11-20-12-40 ;
  FFmpeg source commit: https://github.com/FFmpeg/FFmpeg/tree/7ddf7bc8a4).
- **Version (verbatim `ffmpeg -version` first line):** `ffmpeg version
  N-129150-g7ddf7bc8a4-20261120 Copyright (c) 2000-2026 the FFmpeg developers`.
  Archive: `ffmpeg-N-129150-g7ddf7bc8a4-win64-lgpl.zip`, 178,978,135 bytes,
  SHA-256 `0322fe632c4f6e1fb92c3a3648e100fec702bf86792c4440b4dfda22f7b95b82`.
  Pinned in `scripts/ffmpeg-lgpl-win64.json`; fetched and verified by
  `scripts/build/fetch_ffmpeg_lgpl_win64.sh`. The executables are gitignored and
  are not committed to this repository.
- **Licence (verbatim from `ffmpeg -L`):** "GNU Lesser General Public License
  ... version 3 of the License, or (at your option) any later version."
  The build's configuration explicitly contains `--disable-libx264`,
  `--disable-libx265`, `--disable-libxavs2`, `--disable-libxvid` and does NOT
  contain `--enable-gpl`, `--enable-nonfree`, `--enable-libx264` or
  `--enable-libx265`. The full stored configuration string is in the manifest.
- **Use:** `ffmpeg` and `ffprobe` are bundled on Windows x64 as Tauri external
  binaries and called as subprocesses by `media_ingest/decoder.py` to decode
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
