"""ASR domain contract: one finished recording in, one transcript out.

Streaming partials stay out of this contract on purpose (C-TRANS-1): every ASR
provider is called once, after stop, and returns the final transcript.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class AsrClient(Protocol):
    """A batch transcription client for exactly one provider + model."""

    provider_id: str
    model_id: str

    def transcribe(self, audio: np.ndarray, *, abort_event: Any = None) -> str:
        """Transcribe 16 kHz mono float32 ``audio`` and return the text."""
        ...


__all__ = ["AsrClient"]
