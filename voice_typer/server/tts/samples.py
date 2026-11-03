"""Voice samples: render once, reuse forever.

A sample is the same sentence for every voice, so synthesizing it again on each
click is pure waste (a Magpie render can take seconds). The resolution order is:

1. a sample shipped with the app (``server/assets/tts_samples/<engine>/<voice>.wav``);
2. a previously rendered sample in the TTS cache;
3. render once and cache it.

Voice/language/sample-text are part of the cache key, so switching voices never
invalidates another voice's sample and editing the sentence does not serve a
stale clip. The key carries the runtime's WIRE selector, not just the display
id: a clip rendered before the selector was pinned (v1) is not the voice the
user picked, so bumping the version discards it instead of replaying it.
"""

from __future__ import annotations

import hashlib
import re
import threading
from pathlib import Path

from voice_typer.server.tts.paths import tts_root
from voice_typer.server.tts.voices import wire_voice

SAMPLE_TEXT = "This is what your dictated text sounds like when spoken back to you."

#: Bump when SAMPLE_TEXT, the render pipeline, or the voice selector changes
#: (invalidates every previously rendered clip).
#: v2: clips keyed by the verified wire voice instead of the display label.
#: v3: the wire voice is the model's speaker index; v2 clips were played by the
#:     runtime's scrambled name table, so every clip on disk is the wrong voice.
SAMPLE_CACHE_VERSION = 3

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_LOCK = threading.Lock()


def _asset_root() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "tts_samples"


def sample_key(engine: str, voice: str, language: str) -> str:
    """Stable cache key for one (engine, voice, language) sample."""
    digest = hashlib.sha256(SAMPLE_TEXT.encode("utf-8")).hexdigest()[:8]
    selector = wire_voice(engine, voice) or voice or "default"
    parts = [engine, selector, language or "default", f"v{SAMPLE_CACHE_VERSION}", digest]
    return "-".join(_SAFE.sub("_", part) for part in parts if part)


def bundled_sample_path(engine: str, voice: str) -> Path | None:
    """A sample shipped inside the app, when one exists for this voice."""
    path = _asset_root() / _SAFE.sub("_", engine) / f"{_SAFE.sub('_', voice or 'default')}.wav"
    if path.is_file() and path.stat().st_size > 0:
        return path
    return None


def sample_cache_path(engine: str, voice: str, language: str) -> Path:
    """Where a rendered sample is stored (and reused from)."""
    return tts_root() / "samples" / f"{sample_key(engine, voice, language)}.wav"


def sample_lock() -> threading.Lock:
    """Serializes first renders so two clicks cannot render the same clip twice."""
    return _LOCK


__all__ = [
    "SAMPLE_CACHE_VERSION",
    "SAMPLE_TEXT",
    "bundled_sample_path",
    "sample_cache_path",
    "sample_key",
    "sample_lock",
]
