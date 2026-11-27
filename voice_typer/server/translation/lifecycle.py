"""Translator registration with the shared model lifecycle (ADR-0030).

The policy adapter owns no warm thread and no idle timer: the runtime stays the
single llama-server process held by ``translation.service``.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from voice_typer.server.translation import service as _service

log = logging.getLogger(__name__)

KIND = "translation"
# S5 E2: 15.5 s cold 1.31 GB file read, 13.8 s spawn-to-health, 33.9 s worst
# measured cold translation. 45 s is the single shared wait budget with headroom.
TRANSLATION_LOAD_WAIT_S = 45.0
_PRIVATE_BYTES = 1_800_000_000  # S5 E2: ~1.8 GB private after a GPU load

_loading = threading.Event()
_load_lock = threading.Lock()
_last_attempt_key: tuple[object, ...] | None = None


def is_applicable(config: Any) -> bool:
    """Enabled translator + installed GGUF + a Stage A source of text."""
    if config is None or not bool(getattr(config, "translation_enabled", False)):
        return False
    if not str(getattr(config, "model_size", "") or "") and str(getattr(config, "asr_backend", "") or "") != "cloud":
        return False
    return _service._model_is_installed(config)


def _is_loaded(config: Any) -> bool:
    return _service.is_loaded(config)


def _load(config: Any) -> bool:
    """Load the one runtime; concurrent callers wait for the first attempt."""
    global _last_attempt_key
    key = _service._service_key(config)
    if not _load_lock.acquire(blocking=False):
        _wait(TRANSLATION_LOAD_WAIT_S)
        return _service.is_loaded(config)
    try:
        _last_attempt_key = key
        _loading.set()
        try:
            _service.get_service(config)._ensure_runtime()
            return _service.is_loaded(config)
        except Exception:
            log.warning("[TRANSLATE] shared load failed; keeping original text", exc_info=True)
            return False
        finally:
            _loading.clear()
    finally:
        _load_lock.release()


def _unload() -> None:
    _service.stop_cached_service()


def _wait(timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while _loading.is_set() and time.monotonic() < deadline:
        time.sleep(0.02)
    return not _loading.is_set()


def _record_use() -> None:
    # A POST is a use even when the shared loader did not start this load.
    from voice_typer.server.model_lifecycle.idle import touch

    touch(KIND)


def _policy() -> Any:
    from voice_typer.server.model_lifecycle import CallablePolicy

    return CallablePolicy(
        name="translation",
        residency="optional",
        estimate_private_bytes=_PRIVATE_BYTES,
        applicable_fn=is_applicable,
        is_loaded_fn=_is_loaded,
        is_busy_fn=_service.service_is_busy,
        load_fn=_load,
        unload_fn=_unload,
        wait_fn=_wait,
        note_use_fn=_record_use,
    )


def register() -> None:
    """Register the one optional translator kind; safe to call repeatedly."""
    from voice_typer.server import model_lifecycle

    if KIND not in model_lifecycle.kinds():
        model_lifecycle.register(KIND, _policy())


def ensure_translation_loaded(config: Any, timeout_s: float = TRANSLATION_LOAD_WAIT_S) -> bool:
    """Shared wait first; a skipped kind loads once on demand (no retry)."""
    if not is_applicable(config):
        return False
    register()
    from voice_typer.server import model_lifecycle

    policy = model_lifecycle.get(KIND)
    if policy is None:
        return False
    if model_lifecycle.ensure_loaded(KIND, config, timeout_s):
        return True
    if _last_attempt_key == _service._service_key(config):
        # An in-flight load was attempted and did not make the kind ready.
        return False
    return bool(policy.load(config))


def note_use() -> None:
    """Tell the shared lifecycle a POST succeeded, when the kind is registered."""
    from voice_typer.server import model_lifecycle

    if KIND in model_lifecycle.kinds():
        policy = model_lifecycle.get(KIND)
        if policy is not None:
            policy.note_use()


register()
