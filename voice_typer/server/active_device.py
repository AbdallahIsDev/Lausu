"""Effective compute device of the LOADED ASR engine.

``config.device`` is the user's request (persisted preference). The engine can
end up elsewhere: a CPU-only onnxruntime build, a forced-CPU load on a low-disk
machine, a worker that fell back to CPU. Every surface that prints "GPU"/"CPU"
(the sidebar toggle, the tray) must name what is actually serving, so this
module owns the one translation and the push that keeps the snapshot current.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def normalize_device(info: object) -> str | None:
    """Map an engine ``device_info`` string to ``"cpu"`` / ``"cuda"``.

    Engines speak the user-facing words (``"GPU"``/``"CPU"``) while config
    values stay ``"cuda"``/``"cpu"``; anything else (``"pack worker"``,
    ``"cloud/openai"``) says nothing about local compute and stays unknown.
    """
    text = str(info or "").strip().lower()
    if text.startswith("gpu") or text.startswith("cuda"):
        return "cuda"
    if text == "cpu":
        return "cpu"
    return None


def engine_active_device(engine: Any) -> str | None:
    """Return the device ``engine`` reports, or ``None`` when it is silent."""
    try:
        return normalize_device(getattr(engine, "device_info", None))
    except Exception:
        log.debug("[DEVICE] engine device_info unavailable", exc_info=True)
        return None


def resolve_active_device(app: Any) -> str | None:
    """Return the device the ACTIVE engine runs on (``None`` when unknown)."""
    try:
        models = getattr(app, "models", None)
        transcriber = getattr(models, "active_transcriber", None) if models is not None else None
        engine = transcriber() if callable(transcriber) else None
    except Exception:
        log.debug("[DEVICE] active transcriber probe failed", exc_info=True)
        return None
    return engine_active_device(engine)


def publish_active_device(device: str | None) -> None:
    """Push the effective device onto the shared config snapshot."""
    if device not in ("cpu", "cuda"):
        return
    try:
        from voice_typer.server import event_bus

        event_bus.publish({"type": "config_changed", "data": {"active_device": device}})
    except Exception:
        log.debug("[DEVICE] active_device publish failed", exc_info=True)


__all__ = [
    "engine_active_device",
    "normalize_device",
    "publish_active_device",
    "resolve_active_device",
]
