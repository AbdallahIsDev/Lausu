"""Runtime launch specs for the two local TTS engines.

This module exists so engine-specific argv and config files live in one place,
while process supervision, HTTP transport, and comparison stay engine-agnostic.
Both engines are driven through the OpenAI-compatible ``/v1/audio/speech`` route
their upstream projects already ship.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from voice_typer.server.tts.packs import (
    AUDIO8_REALISTIC_BF16,
    MAGPIE_V2607_F16,
    NANO_CODEC_F16,
    Artifact,
)
from voice_typer.server.tts.runtime_server import RuntimeSpec

#: OpenAI-compatible model id the client sends. Each runtime serves exactly one
#: TTS model per process, but the field is required by the request schema.
AUDIO8_MODEL_ID = "audio8"
MAGPIE_MODEL_ID = "magpie"


@dataclass(frozen=True)
class Audio8Engine:
    """Audio8-TTS-Realistic-0.6B served by ``audiocpp_server``."""

    binary: Path
    model: Path
    backend: str = "vulkan"

    def pinned_artifacts(self) -> list[tuple[Path, Artifact | None]]:
        """Model file + the pinned artifact that defines its exact size."""
        return [(self.model, AUDIO8_REALISTIC_BF16)]

    def spec(self, workdir: Path) -> RuntimeSpec:
        """Write the server config and return the argv that consumes it."""
        workdir.mkdir(parents=True, exist_ok=True)
        config_path = workdir / "audio8-server.json"
        config_path.write_text(
            json.dumps(
                {
                    "host": "127.0.0.1",
                    "port": "{port}",
                    "backend": self.backend,
                    "lazy_load": True,
                    "max_loaded_models": 1,
                    "models": [
                        {
                            "id": AUDIO8_MODEL_ID,
                            "family": "audio8_tts",
                            "path": str(self.model).replace("\\", "/"),
                            "task": "tts",
                            "mode": "offline",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return RuntimeSpec(
            name="audio8",
            argv=[
                str(self.binary),
                "--config",
                str(config_path),
                "--no-ui",
                "--port",
                "{port}",
                "--log",
                "--log-file",
                str(workdir / "audio8-runtime.log"),
            ],
            log_path=workdir / "audio8-stdout.log",
        )


@dataclass(frozen=True)
class MagpieEngine:
    """MagpieTTS multilingual 357M served by ``nemo-speech serve``."""

    binary: Path
    magpie_model: Path
    codec_model: Path
    tokenizer_dir: Path

    def pinned_artifacts(self) -> list[tuple[Path, Artifact | None]]:
        """Both GGUFs, each with the artifact that pins its size."""
        return [(self.magpie_model, MAGPIE_V2607_F16), (self.codec_model, NANO_CODEC_F16)]

    def spec(self, workdir: Path) -> RuntimeSpec:
        """Return the argv for a TTS-only server (same binary also hosts ASR)."""
        workdir.mkdir(parents=True, exist_ok=True)
        return RuntimeSpec(
            name="magpie",
            argv=[
                str(self.binary),
                "serve",
                "--tts-model",
                str(self.magpie_model),
                "--codec-model",
                str(self.codec_model),
                "--tokenizer-dir",
                str(self.tokenizer_dir),
                "--no-ui",
                "--host",
                "127.0.0.1",
                "--port",
                "{port}",
            ],
            log_path=workdir / "magpie-stdout.log",
        )
