"""App-facing TTS manager: status, pack preparation, speak, compare.

This module exists so the IPC/service layer never touches runtimes or paths:
it resolves the HF-folder layout into concrete engines, downloads a pack when
asked, and renders or compares the configured engine with playback.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from voice_typer.server.tts import packs, runtimes
from voice_typer.server.tts.engines import Audio8Engine, MagpieEngine
from voice_typer.server.tts.paths import (
    audio8_binary,
    bin_dir,
    magpie_binary,
    model_dir,
    tts_root,
    work_dir,
)
from voice_typer.server.tts.playback import play_wav
from voice_typer.server.tts.service import TtsService
from voice_typer.server.tts.types import TtsError, TtsRequest

log = logging.getLogger(__name__)

ENGINES = ("audio8", "magpie")
#: Language codes the Magpie runtime advertises (v2607 profile).
MAGPIE_LANGUAGES = ("en-US", "ar-MSA", "de-DE", "es-US", "fr-FR", "it-IT", "ja-JP", "ko-KR", "pt-BR", "vi-VN", "zh-CN")
AUDIO8_VOICES = ("default",)


def _first(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


@dataclass
class TtsManager:
    """Owns the TTS runtime lifecycle for the running app."""

    config: Any
    _service: TtsService | None = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------ paths

    def _audio8_engine(self) -> Audio8Engine | None:
        model = model_dir("audio8") / packs.AUDIO8_REALISTIC_BF16.filename
        binary = audio8_binary()
        if not (model.is_file() and binary.is_file()):
            return None
        backend = os.environ.get("VOICE_TYPER_AUDIO8_BACKEND", "vulkan")
        return Audio8Engine(binary=binary, model=model, backend=backend)

    def _magpie_engine(self) -> MagpieEngine | None:
        binary = magpie_binary()
        root = model_dir("magpie")
        magpie = _first(sorted(root.glob("**/magpie_tts_multilingual_357m*.gguf")))
        codec = _first(sorted(root.glob("**/*nano*codec*.gguf")))
        tokenizer = _first([p for p in root.glob("**/model_config.yaml")]) if root.is_dir() else None
        if not (binary.is_file() and magpie and codec and tokenizer):
            return None
        return MagpieEngine(binary=binary, magpie_model=magpie, codec_model=codec, tokenizer_dir=tokenizer.parent)

    def _tts_service(self) -> TtsService:
        audio8 = self._audio8_engine()
        magpie = self._magpie_engine()
        service = self._service
        if service is not None:
            # A pack can land (or vanish) while the app is running: tts_prepare
            # writes into the HF folder, and without this check a service built
            # on the first attempt would keep reporting the engine as absent
            # until the whole app restarted.
            changed = (service.audio8 is None) != (audio8 is None) or (
                service.magpie is None
            ) != (magpie is None)
            if changed:
                service.stop()
                self._service = service = None
        if service is None:
            service = TtsService(workdir=tts_root() / 'work', audio8=audio8, magpie=magpie)
            self._service = service
            atexit.register(service.stop)
        return service

    def _installed(self, engine: str) -> bool:
        """True when both the runtime binary and the model pack are on disk."""
        if engine == "audio8":
            return self._audio8_engine() is not None
        return self._magpie_engine() is not None

    def _runtime_for(self, engine: str) -> Path:
        """Return the engine runtime, installing it when the app may.

        An explicit ``VOICE_TYPER_AUDIO8_BIN`` / ``VOICE_TYPER_NEMO_SPEECH_BIN``
        override stays authoritative: installing over a path the user chose
        would be surprising, so a missing override is reported, not replaced.
        """
        override = os.environ.get(
            "VOICE_TYPER_AUDIO8_BIN" if engine == "audio8" else "VOICE_TYPER_NEMO_SPEECH_BIN"
        )
        if override:
            path = Path(override)
            if not path.is_file():
                raise TtsError(f"{engine} runtime missing at {path}")
            return path
        return runtimes.install(engine)

    # ----------------------------------------------------------------- status

    def status(self) -> dict[str, object]:
        """Everything the Models page needs to render the TTS toggle."""
        audio8 = self._audio8_engine()
        magpie = self._magpie_engine()
        return {
            "engine": getattr(self.config, "tts_engine", "off"),
            "voice": getattr(self.config, "tts_voice", "Aria"),
            "language": getattr(self.config, "tts_language", "en-US"),
            "root": str(tts_root()),
            "voices": list(AUDIO8_VOICES),
            "languages": list(MAGPIE_LANGUAGES),
            "engines": {
                "audio8": {
                    "available": audio8 is not None,
                    "label": "Audio8 TTS Realistic 0.6B",
                    "download_bytes": packs.total_bytes(packs.AUDIO8_ARTIFACTS),
                    "models_dir": str(model_dir("audio8")),
                    "binary": str(audio8_binary()),
                    "capabilities": ["tts", "clone"],
                },
                "magpie": {
                    "available": magpie is not None,
                    "label": "MagpieTTS Multilingual 357M",
                    "download_bytes": packs.total_bytes(packs.MAGPIE_ARTIFACTS),
                    "models_dir": str(model_dir("magpie")),
                    "binary": str(magpie_binary()),
                    "capabilities": ["tts", "arabic"],
                },
            },
        }

    # -------------------------------------------------------------- preparing

    def prepare(self, engine: str) -> dict[str, object]:
        """Download one engine's pack into the HF folder."""
        if engine == "audio8":
            self._runtime_for("audio8")
            target = model_dir("audio8")
            for artifact in packs.AUDIO8_ARTIFACTS:
                artifact.download(target)
            return {"engine": engine, "downloaded": [a.filename for a in packs.AUDIO8_ARTIFACTS]}
        if engine == "magpie":
            # Magpie's tokenizer lives inside its .nemo archive; the runtime's
            # own `pull` is the documented, verified way to fetch all three.
            binary = self._runtime_for("magpie")
            target = model_dir("magpie")
            target.mkdir(parents=True, exist_ok=True)
            env = {**os.environ, "NEMO_SPEECH_MODEL_DIR": str(target)}
            completed = subprocess.run(  # noqa: S603 - fixed argv
                [str(binary), "pull", "magpie"],
                capture_output=True,
                text=True,
                env=env,
                timeout=1800,
                check=False,
            )
            if completed.returncode != 0:
                raise TtsError(f"magpie pull failed: {(completed.stderr or completed.stdout)[-500:]}")
            return {"engine": engine, "models_dir": str(target)}
        raise TtsError(f"unknown tts engine: {engine}")

    # ---------------------------------------------------------------- speaking

    def _request(self, text: str) -> TtsRequest:
        return TtsRequest(
            text=text,
            voice=getattr(self.config, "tts_voice", None) or None,
            language=getattr(self.config, "tts_language", None) or None,
        )

    def speak(self, text: str, engine: str | None = None) -> dict[str, object]:
        """Render with ``engine`` (default: the configured one), play it, report timings."""
        if not text.strip():
            raise TtsError("tts: empty text")
        engine = engine or getattr(self.config, "tts_engine", "off")
        if engine not in ENGINES:
            raise TtsError("tts is turned off; pick Audio8 or Magpie first")
        if not self._installed(engine):
            raise TtsError(
                f"{engine} is not installed: no runtime in {bin_dir(engine)} "
                f"or no model pack in {model_dir(engine)}"
            )
        service = self._tts_service()
        out = work_dir(engine) / "speak.wav"
        result = service.synthesize(self._request(text), engine, out)
        played = play_wav(result.wav_path)
        return {
            "engine": engine,
            "wav_path": str(result.wav_path),
            "duration_s": round(result.duration_s, 3),
            "wall_s": round(result.wall_s, 3),
            "realtime_factor": round(result.realtime_factor, 2),
            "sample_rate": result.sample_rate,
            "played_s": round(played, 3),
        }

    def shutdown(self) -> None:
        """Stop every runtime (app shutdown)."""
        if self._service is not None:
            self._service.stop()
            self._service = None


def describe(manager: TtsManager) -> str:
    """Compact one-line status for logs and issue reports."""
    return json.dumps(manager.status(), sort_keys=True)
