# ADR-0026: Slim-core installer target is 80 MB, not 45 MB

## Status

Accepted (owner decision).

## Context

The Windows installer is ~226 MB: sidecar onefile ~97 MB + worker onefile
~124 MB + Rust host, all bundled via `externalBin`. The runtime-pack split
plan (`docs/plan-runtime-pack-split.md` §11.4) set a 45 MB slim-core target,
enforced as an informational CI gate in all three Tauri release workflows.

Reaching 45 MB requires moving scipy (~32 MB) out of the sidecar freeze.
But scipy does live microphone work: resampling mic audio to 16 kHz plus the
notch/highpass/noise-suppressor filter chain, which the Silero VAD needs
instantly every few milliseconds (`voice_typer/server/recording/`,
`voice_typer/server/audio_filters/`). Moving it means relocating live mic
processing behind the worker socket (VAD latency redesign) — a large,
risky change for diminishing user-visible returns: users do not distinguish
45 MB from 80 MB on a one-time download.

## Decision

1. The slim-core installer target is **80 MB**. The three informational
   size gates (`tauri-windows-build.yml`, `tauri-macos-build.yml`,
   `tauri-linux-build.yml`) assert ≤ 80 MB.
2. The sidecar diet moves ONLY libraries with no live-mic role:
   - **PyAV + FFmpeg** (~21 MB): sole user is `media_ingest/decoder.py`
     (transcribe-audio-file). Live dictation never touches it.
   - **yt_dlp + media/subtitle download helpers**: download/subtitle
     features only, nothing on the recording hot path.
3. These STAY in the installer: **scipy** (live resample + filters),
   **numpy** (mic capture, levels, VAD math — irremovable), **onnxruntime**
   (Silero VAD + GTCRN filter on the real-time path), **sounddevice**.
4. Expected result: ~97 − 21 − yt_dlp ≈ ~70 MB sidecar; minus the bundled
   worker (separate Phase 2c step) the installer lands under 80 MB.

## Consequences

- File-transcription and media-download features require the runtime pack;
  before its first download they must degrade with a clear message, never
  a dead button. The first-run pack gate is a prerequisite of the move.
- The scipy relocation (true 45 MB) stays possible later if ever wanted;
  it is a VAD-architecture decision, not a packaging tweak.
- The §11.4 "45 MB" references in the plan doc are superseded by this ADR
  for the gate value; the plan's Phase 2c mechanics are unchanged.
