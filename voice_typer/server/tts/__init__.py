"""Local text-to-speech subsystem (Audio8 + MagpieTTS).

This package exists so the app can speak through native GGML runtimes with no
torch dependency, comparing two engines that both expose the OpenAI-compatible
``/v1/audio/speech`` route.
"""

from voice_typer.server.tts.engines import Audio8Engine, MagpieEngine
from voice_typer.server.tts.service import TtsService
from voice_typer.server.tts.types import TtsBackend, TtsError, TtsRequest, TtsResult

__all__ = [
    "Audio8Engine",
    "MagpieEngine",
    "TtsBackend",
    "TtsError",
    "TtsRequest",
    "TtsResult",
    "TtsService",
]
