# Third-Party Notices

This project distributes or downloads the following third-party components
as part of the media-ingest feature (ADR-0023). Their licenses are
acknowledged here.

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

- **Homepage:** https://github.com/PyAV-Org/PyAV
- **License:** BSD 3-Clause
- **Bundled components in binary wheels:** FFmpeg libraries, licensed under
  the GNU Lesser General Public License (LGPL) v2.1 or later. FFmpeg source
  code is available at https://ffmpeg.org/download.html
- **Use:** Container/codec decode of local files and remote audio streams
  to 16 kHz mono PCM.

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
