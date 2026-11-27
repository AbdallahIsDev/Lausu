"""Policy data shape for every local model kind.

A policy is the small adapter a model kind supplies to the unified lifecycle:
three data fields plus the seven lifecycle verbs. Defaults are safe no-ops so a
kind can register with a handful of lines; real kinds subclass or supply
callables through :class:`CallablePolicy`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Hook = Callable[..., Any]


@dataclass
class ModelPolicy:
    name: str
    residency: str = "optional"
    estimate_private_bytes: int = 0
    # True when the kind already has its own dedicated post-ready prewarm
    # (TTS does). The unified startup gate must not start a second one.
    dedicated_startup: bool = False

    def applicable(self, config: Any) -> bool:
        return True

    def is_loaded(self, config: Any) -> bool:
        return False

    def is_busy(self) -> bool:
        return False

    def load(self, config: Any) -> bool:
        return False

    def unload(self) -> None:
        return None

    def wait(self, timeout_s: float) -> bool:
        return False

    def note_use(self) -> None:
        return None


@dataclass
class CallablePolicy(ModelPolicy):
    """A policy assembled from callables: the few-line registration path."""

    applicable_fn: Hook | None = None
    is_loaded_fn: Hook | None = None
    is_busy_fn: Hook | None = None
    load_fn: Hook | None = None
    unload_fn: Hook | None = None
    wait_fn: Hook | None = None
    note_use_fn: Hook | None = None

    def applicable(self, config: Any) -> bool:
        return bool(self.applicable_fn(config)) if self.applicable_fn else True

    def is_loaded(self, config: Any) -> bool:
        return bool(self.is_loaded_fn(config)) if self.is_loaded_fn else False

    def is_busy(self) -> bool:
        return bool(self.is_busy_fn()) if self.is_busy_fn else False

    def load(self, config: Any) -> bool:
        return bool(self.load_fn(config)) if self.load_fn else False

    def unload(self) -> None:
        if self.unload_fn:
            self.unload_fn()

    def wait(self, timeout_s: float) -> bool:
        return bool(self.wait_fn(timeout_s)) if self.wait_fn else False

    def note_use(self) -> None:
        if self.note_use_fn:
            self.note_use_fn()


__all__ = ["CallablePolicy", "ModelPolicy"]
