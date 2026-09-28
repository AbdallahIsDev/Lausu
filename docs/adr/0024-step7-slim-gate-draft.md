# ADR-0024 Step 7 - slim-build gate

> **PARTIALLY APPLIED 2026-09-26.** Step 6 is signed off (real host), so the
> "DO NOT APPLY" hold is lifted. What landed: the ownership decision below +
> the ML-import ratchet gate (`scripts/slim_core_ml_ratchet_check.py` +
> `slim-core-ml-baseline.json`, wired into `tauri-windows-build.yml`). What
> is still NOT applied: the `--nofollow-import-to` ASR exclusions, which
> remain gated on cutting the dictation engine off the in-process
> `TranscriptionEngine` onto the worker hop. The onnxruntime half of the
> original grep sketch is now **permanently out of scope** (VAD + GTCRN stay
> in the slim core); the ratchet counts only the ASR libs.

## Ownership decision (resolves the plan 5.3 vs 4.1 conflict)

VAD (`vad.py`) and the GTCRN noise filter (`audio_filters/gtcrn_backend.py`)
run on the real-time audio processing path in the slim core (`RT-SAFE-001`:
the PortAudio callback must not call them, but `audio_pipeline.py:343` runs
`compute_vad_prob` on the processing thread). Streaming them to the worker
would put a network round-trip on the audio path. **Decision: they stay
in-process; `onnxruntime` remains a declared slim-core dependency** (plan
5.3). Only the ASR libraries (`faster_whisper`, `ctranslate2`) are the
worker's and are counted by the ratchet.

## Grep gate - implemented as a ratchet

`scripts/slim_core_ml_ratchet_check.py` scans the slim-core closure
(`voice_typer/server`, worker excluded) for `faster_whisper` / `ctranslate2`
imports and refuses to let the count grow, mirroring the existing
`ruff`/`mypy` ratchet idiom. Baseline committed at
`slim-core-ml-baseline.json` (current total=4). The ratchet runs as an
additive fail-fast step in `tauri-windows-build.yml`, placed after the
config-drift pytest and before stub generation (C-CI-7 order preserved).
Covered by `tests/test_slim_core_ml_ratchet.py`.

## Size gate - already enforced (no change needed)

`tauri-windows-build.yml` already hard-fails the 185 MB sidecar and the
200 MB worker pack, and warns on the 45 MB NSIS informational gate. These
are plan 11.4; the original "insert these steps" instruction is obsolete.

## Still NOT applied (the real slimming work)

1. Cut the dictation engine off in-process `TranscriptionEngine`
   (`dictation_pipeline/transcribe_step.py:98` -> `active_transcriber()`)
   onto the worker hop.
2. Only then add `--nofollow-import-to=faster_whisper` and
   `--nofollow-import-to=ctranslate2` to the **sidecar** Nuitka invocation
   (`scripts/build/build_sidecar_*.sh` + the inline step in
   `tauri-windows-build.yml`). Keep `nuitka==2.8.10` (C-CI-6), the torch
   exclusions and `torch-disable-jit=no` (C-CI-8), and
   `--include-package-data` / `--windows-console-mode` /
   `--onefile-tempdir-spec` (C-CI-9) untouched.
3. `tests/tauri/test_config_script_drift.py::
   TestNuitkaSidecarBuildsDoNotExcludeTorchDistributed` currently HARD-FORBIDS
   the exclusions (plan 11.2); update it in the same commit that adds the
   ASR exclusions or CI fails by design.
4. `pyproject.toml` / `requirements-lock.txt` - move ASR deps to the worker
   dependency set (onnxruntime STAYS in slim core).
