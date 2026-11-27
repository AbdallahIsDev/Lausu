"""Unified lifecycle for local model kinds (ASR, translation, TTS).

One registry, one record-start hook, one startup gate, one idle duration and
one shutdown path. A new kind registers a :class:`ModelPolicy` and inherits all
of them; nothing in the orchestration needs a new branch.
"""

from __future__ import annotations

from . import builtins as _builtins
from .idle import apply_idle_setting
from .loading import ensure_loaded, load_in_background, on_dictation_start
from .memory import memory_fits
from .policy import CallablePolicy, ModelPolicy
from .registry import get, kinds, register
from .shutdown import shutdown_all
from .startup import prewarm_optional_at_startup

_builtins.register_builtins()

__all__ = [
    "CallablePolicy",
    "ModelPolicy",
    "apply_idle_setting",
    "ensure_loaded",
    "get",
    "kinds",
    "load_in_background",
    "memory_fits",
    "on_dictation_start",
    "prewarm_optional_at_startup",
    "register",
    "shutdown_all",
]
