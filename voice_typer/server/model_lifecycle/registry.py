"""Global policy registry and the single app reference.

One authority for "which local model kinds exist". ``register`` is the only
write path; every other module reads through ``get``/``kinds`` so a new kind
needs no changes to the orchestration code.
"""

from __future__ import annotations

import threading
from typing import Any

from .policy import ModelPolicy

_lock = threading.RLock()
_policies: dict[str, ModelPolicy] = {}
_app: Any = None


def register(kind: str, policy: ModelPolicy) -> None:
    with _lock:
        _policies[kind] = policy


def get(kind: str) -> ModelPolicy | None:
    with _lock:
        return _policies.get(kind)


def kinds() -> tuple[str, ...]:
    with _lock:
        return tuple(_policies)


def bind_app(app: Any) -> None:
    """Record the app once; policies with no app parameter read it from here."""
    global _app
    with _lock:
        _app = app


def current_app() -> Any:
    with _lock:
        return _app


def ordered_kinds() -> tuple[str, ...]:
    """Core first, then optional in NEED ORDER; TTS always last."""
    snapshot = kinds()

    def rank(kind: str) -> tuple[int, int, str]:
        policy = get(kind)
        core = 0 if policy is not None and policy.residency == "core" else 1
        need = {"asr": 0, "translation": 1, "tts": 9}.get(kind, 5)
        return core, need, kind

    return tuple(sorted(snapshot, key=rank))


def _reset_for_tests() -> None:
    global _app
    with _lock:
        _policies.clear()
        _app = None


__all__ = ["bind_app", "current_app", "get", "kinds", "ordered_kinds", "register"]
