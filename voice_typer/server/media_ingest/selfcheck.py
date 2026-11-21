"""Frozen-sidecar self-check entry point (CI bundle verification, Part B).

Invoked ONLY by ``scripts/verify_windows_bundle.py`` as::

    python-sidecar.exe --self-check <path-to-16k-wav>

It is deliberately inert during normal sidecar startup: ``main()`` calls
``maybe_run_self_check()`` right after argument parsing and returns early
(via ``SystemExit``) only when the flag is present. ``parse_ipc_args()`` uses
``parse_known_args``, so the flag needs no argparse change and cannot alter
the existing ``(port, ws_mode)`` contract.

Five assertions, printed as grep-able markers:
  * frozen-build      -- a Nuitka/PyInstaller build, not a dev interpreter;
  * no-path-fallback  -- ffmpeg came from the exe-adjacent install, not PATH;
  * bundled-ffmpeg    -- resolved next to the running exe, never from PATH;
  * decode-samples    -- decodes the 1 s / 16 kHz fixture to exactly 16000;
  * rnnoise-active    -- the effective noise-suppression method is RNNoise,
                        not the GTCRN substitute.
"""

from __future__ import annotations

import shutil
from pathlib import Path

_MARKER = "SELFCHECK"
_EXPECTED_SAMPLES = 16_000


def maybe_run_self_check(argv: list[str]) -> bool:
    """Exit the process with a self-check result when the flag is present.

    Returns ``False`` (no side effects) on every normal startup path.
    """
    if "--self-check" not in argv:
        return False
    idx = argv.index("--self-check")
    wav = (
        argv[idx + 1]
        if idx + 1 < len(argv) and not argv[idx + 1].startswith("--")
        else ""
    )
    raise SystemExit(run(wav))


def run(wav_path: str) -> int:
    """Execute the three checks; always print markers, return a process code."""
    if not wav_path:
        print(f"{_MARKER}: FAIL no-wav-path", flush=True)
        return 2
    wav = Path(wav_path)
    if not wav.is_file():
        print(f"{_MARKER}: FAIL wav-not-found {wav}", flush=True)
        return 2

    try:
        from voice_typer.server.media_ingest import ffmpeg_binaries
        from voice_typer.server.media_ingest.decoder import decode_chunks
    except Exception as exc:  # import failure is a hard self-check failure
        print(f"{_MARKER}: FAIL import-decode-stack {exc!r}", flush=True)
        return 2

    try:
        if not ffmpeg_binaries.is_frozen_build():
            raise AssertionError("self-check must run from a frozen sidecar build")
        print(f"{_MARKER}: PASS frozen-build", flush=True)

        pair = ffmpeg_binaries.resolve_binaries()
        if pair is None or not pair.ffmpeg:
            raise AssertionError("resolve_binaries() returned no ffmpeg")
        exe_dir = ffmpeg_binaries.bundled_bin_dir()
        resolved = Path(pair.ffmpeg).resolve()
        from_path = shutil.which("ffmpeg")
        if from_path and Path(from_path).resolve() == resolved:
            raise AssertionError(f"ffmpeg resolved from PATH: {from_path}")
        if resolved.parent != exe_dir:
            raise AssertionError(
                f"ffmpeg resolved to {resolved}, not exe-adjacent {exe_dir} "
                "(PATH fallback or missing bundled externalBin)"
            )
        print(f"{_MARKER}: PASS no-path-fallback", flush=True)
        print(
            f"{_MARKER}: PASS bundled-ffmpeg {resolved}",
            flush=True,
        )

        total = 0
        for chunk in decode_chunks(str(wav), remote=False):
            total += len(chunk)
        if total != _EXPECTED_SAMPLES:
            raise AssertionError(
                f"expected {_EXPECTED_SAMPLES} decoded samples, got {total}"
            )
        print(f"{_MARKER}: PASS decode-samples={total}", flush=True)

        from voice_typer.server.audio_filters.noise_suppressor import NoiseSuppressor

        suppressor = NoiseSuppressor(method="rnnoise", quiet=True)
        effective = suppressor.effective_method
        degraded = suppressor.is_degraded
        if effective != "rnnoise" or degraded:
            raise AssertionError(
                f"RNNoise not active (effective method={effective!r}, degraded={degraded})"
            )
        print(f"{_MARKER}: PASS rnnoise-active", flush=True)
    except Exception as exc:
        print(f"{_MARKER}: FAIL {type(exc).__name__}: {exc}", flush=True)
        return 1

    print(f"{_MARKER}: ALL PASS", flush=True)
    return 0
