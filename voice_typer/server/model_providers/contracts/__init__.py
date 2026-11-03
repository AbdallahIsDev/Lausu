"""The three domain contracts (ASR, TTS, LLM).

Each contract is a runtime-checkable Protocol: a provider client is validated
against exactly one of them, so a client that only speaks text can never be
handed audio.
"""

from __future__ import annotations

from voice_typer.server.model_providers.contracts.asr import AsrClient
from voice_typer.server.model_providers.contracts.llm import ChatMessage, LlmClient
from voice_typer.server.model_providers.contracts.tts import TtsAudio, TtsClient, TtsRequest

__all__ = [
    "AsrClient",
    "ChatMessage",
    "LlmClient",
    "TtsAudio",
    "TtsClient",
    "TtsRequest",
]
