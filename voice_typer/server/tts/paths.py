"""Filesystem layout for TTS runtimes and model packs.

The TTS packs live in the SAME Hugging Face cache ``huggingface_hub`` resolves
for the ASR weights (``<HF root>/hub/models--*``), so the app has one model
folder on disk instead of an app-private duplicate beside it:

    <HF root>/tts/bin/{audio8,magpie}     native runtimes
    <HF root>/tts/models/{audio8,magpie}  GGUF packs
    <HF root>/tts/work/{engine}           runtime configs, logs, rendered WAVs

On Windows that root is ``C:\\Users\\<user>\\.cache\\huggingface``; ``HF_HOME``
moves it, and this module follows whatever ``huggingface_hub`` itself reports.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Subdirectory of the HF cache root that holds TTS models, binaries, and logs.
TTS_DIRNAME = "tts"


def hf_root() -> Path:
    """Hugging Face cache root shared with the ASR weights.

    ``shared_hub_dir()`` is ``huggingface_hub``'s ``HF_HUB_CACHE`` (honoring
    ``HF_HOME``); its parent is the root the ASR snapshots already sit under, so
    the TTS packs belong there rather than in a second app-private folder.
    Imported lazily: ``model_availability`` pulls in ``huggingface_hub``, and
    the TTS path helpers must stay import-cheap.
    """
    from voice_typer.server.model_availability import shared_hub_dir

    return shared_hub_dir().parent


def tts_root() -> Path:
    """Root of all TTS artifacts (models, runtimes, scratch)."""
    return hf_root() / TTS_DIRNAME


def model_dir(engine: str) -> Path:
    """Directory holding one engine's model packs."""
    return tts_root() / "models" / engine


def bin_dir(engine: str) -> Path:
    """Directory holding one engine's native runtime."""
    return tts_root() / "bin" / engine


def work_dir(engine: str) -> Path:
    """Scratch directory for runtime configs, logs, and rendered WAVs."""
    return tts_root() / "work" / engine


def _exe(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def audio8_binary() -> Path:
    """``audiocpp_server`` binary, overridable for a portable install."""
    override = os.environ.get("VOICE_TYPER_AUDIO8_BIN")
    if override:
        return Path(override)
    return bin_dir("audio8") / _exe("audiocpp_server")


def magpie_binary() -> Path:
    """``nemo-speech`` binary, overridable for a portable install."""
    override = os.environ.get("VOICE_TYPER_NEMO_SPEECH_BIN")
    if override:
        return Path(override)
    return bin_dir("magpie") / _exe("nemo-speech")
