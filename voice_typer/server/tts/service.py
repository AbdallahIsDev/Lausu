"""TTS orchestration: start runtimes once, render, compare engines.

This module exists so callers never manage processes or URLs: it owns the
runtime lifecycle per engine, renders through the shared client, and produces
the side-by-side comparison the owner asked for.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from pathlib import Path

from voice_typer.server.tts.engines import AUDIO8_MODEL_ID, MAGPIE_MODEL_ID, Audio8Engine, MagpieEngine
from voice_typer.server.tts.local_client import LocalSpeechClient
from voice_typer.server.tts.packs import verify_model
from voice_typer.server.tts.runtime_server import RuntimeServer
from voice_typer.server.tts.types import TtsError, TtsRequest, TtsResult

log = logging.getLogger(__name__)

#: Per-engine default voice. Audio8 clones only when a reference is supplied,
#: otherwise it uses the checkpoint's built-in voice; Magpie needs a named one.
MAGPIE_DEFAULT_VOICE = "Aria"


@dataclass
class TtsService:
    """Owns the local runtimes and renders speech through them."""

    workdir: Path
    audio8: Audio8Engine | None = None
    magpie: MagpieEngine | None = None
    _servers: dict[str, RuntimeServer] = field(default_factory=dict, init=False, repr=False)
    _clients: dict[str, LocalSpeechClient] = field(default_factory=dict, init=False, repr=False)

    def _engine_spec(self, name: str):
        if name == "audio8" and self.audio8 is not None:
            return self.audio8.spec(self.workdir)
        if name == "magpie" and self.magpie is not None:
            return self.magpie.spec(self.workdir)
        raise TtsError(f"engine not configured: {name}")

    def _verify_pack(self, name: str) -> None:
        """Refuse to spawn a runtime on a pack that is not fully on disk.

        Ordering matters: a truncated GGUF passes the magic check and then fails
        inside a tensor read with an opaque 500, so the size check must run
        before the process starts.
        """
        engine = self.audio8 if name == "audio8" else self.magpie
        if engine is None:
            raise TtsError(f"engine not configured: {name}")
        for path, artifact in engine.pinned_artifacts():
            verify_model(path, artifact)

    def ensure_started(self, name: str) -> LocalSpeechClient:
        """Start the runtime for ``name`` if needed and return its client."""
        self._verify_pack(name)
        if name in self._clients:
            server = self._servers[name]
            if server.running:
                return self._clients[name]
            log.warning("[TTS] %s runtime died, restarting", name)
            self._servers.pop(name, None)
            self._clients.pop(name, None)
        server = RuntimeServer.start(self._engine_spec(name))
        self._servers[name] = server
        self._clients[name] = LocalSpeechClient(server.base_url, name)
        return self._clients[name]

    def configured_engines(self) -> list[str]:
        """Engines with a complete local pack, in stable comparison order."""
        names: list[str] = []
        if self.audio8 is not None:
            names.append("audio8")
        if self.magpie is not None:
            names.append("magpie")
        return names

    def synthesize(self, request: TtsRequest, engine: str, output_wav: Path) -> TtsResult:
        """Render with one engine, starting its runtime on first use."""
        if not request.text.strip():
            raise TtsError("tts: empty text")
        client = self.ensure_started(engine)
        if engine == "audio8":
            # Audio8 clones only from a reference WAV; forwarding a Magpie
            # voice name makes the runtime look for a cached clone reference
            # it does not have (HTTP 500), and the model is English-only, so
            # both the voice and the language hint are dropped for this engine.
            return client.speech(
                replace(request, voice=None, language=None), output_wav, model=AUDIO8_MODEL_ID
            )
        return client.speech(
            request,
            output_wav,
            model=MAGPIE_MODEL_ID,
            voice=request.voice or MAGPIE_DEFAULT_VOICE,
        )

    def stop(self) -> None:
        """Stop every runtime this service started."""
        for name, server in list(self._servers.items()):
            try:
                server.stop()
            except Exception:
                log.exception("[TTS] failed to stop %s runtime", name)
        self._servers.clear()
        self._clients.clear()

    def __enter__(self) -> TtsService:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()
