"""Config-directory patching and fake-config helpers shared across test files."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType
from typing import Any

__all__ = [
    "patch_config_dir_refs",
    "preimport_config_modules",
    "real_config_dir_impl",
    "heal_leaked_config_dir_patch",
    "FakeConfig",
]

_CONFIG_MODULE_NAMES = (
    "voice_typer.server.config",
    "voice_typer.server.app",
    "voice_typer.server._paths",
    "voice_typer.server.config_internals.paths",
    "voice_typer.server.logging_setup",
    "voice_typer.server.startup_sequence._phases_early",
)
_config_modules: dict[str, ModuleType] = {}


def preimport_config_modules() -> None:
    """Import every config-dir consumer once, at session start.

    CPython's ``_ModuleLock.acquire`` is not re-entrant safe when an
    import callback imports mid-acquire (bpo-43546 / cpython#87712):
    the outer acquire raises ``KeyError: <thread id>``. First imports
    must not happen inside per-test fixture setup, so pay them here.
    """
    for name in _CONFIG_MODULE_NAMES:
        if name not in _config_modules:
            _config_modules[name] = importlib.import_module(name)
    # Capture before any test can patch it: a leak in the very first test would
    # otherwise be mistaken for the production implementation and be "healed"
    # back to itself on every later test.
    real_config_dir_impl()


def _config_module(name: str) -> ModuleType:
    module = _config_modules.get(name)
    if module is None:
        module = importlib.import_module(name)
        _config_modules[name] = module
    return module


def patch_config_dir_refs(monkeypatch, path: Path) -> None:
    """Redirect every ``_config_dir`` binding to *path* for one test."""
    for name in _CONFIG_MODULE_NAMES:
        monkeypatch.setattr(_config_module(name), "_config_dir", lambda: path)


_REAL_CONFIG_DIR: Any = None


def real_config_dir_impl() -> Any:
    """Return the production ``_config_dir`` implementation (captured once)."""
    global _REAL_CONFIG_DIR
    if _REAL_CONFIG_DIR is None:
        _REAL_CONFIG_DIR = _config_module("voice_typer.server.config_internals.paths")._config_dir
    return _REAL_CONFIG_DIR


def heal_leaked_config_dir_patch() -> bool:
    """Reinstall the real ``_config_dir`` when a previous test leaked a patch.

    An aborted ``monkeypatch.undo()`` leaves this module's ``_config_dir`` as
    the per-test lambda; every later test then dies in ``cache_clear()``. Repair
    it so one broken teardown cannot poison the rest of the worker.
    """
    module = _config_module("voice_typer.server.config_internals.paths")
    real = real_config_dir_impl()
    if module._config_dir is real:
        return False
    module._config_dir = real
    return True


class FakeConfig:
    """Minimal config object for audio-filter-chain tests."""

    def __init__(self, **kwargs):
        # ADR 0007 defaults
        self.audio_preset = "custom"
        self.noise_filter_enabled = True
        self.noise_filter_highpass = True
        self.noise_filter_highpass_cutoff_hz = 80.0
        self.noise_filter_gate = True
        self.noise_filter_gate_threshold = 0.003
        self.noise_filter_gate_hold_ms = 200.0
        self.noise_filter_gate_open_threshold_db = -26.0
        self.noise_filter_gate_close_threshold_db = -32.0
        self.noise_filter_gate_attack_ms = 25.0
        self.noise_filter_gate_release_ms = 150.0
        self.noise_filter_rnnoise = True
        self.noise_filter_post_capture = False
        self.noise_suppression_method = "none"  # skip RNNoise in tests
        self.noise_filter_eq = True
        self.noise_filter_eq_low_db = -3.0
        self.noise_filter_eq_mid_db = 3.0
        self.noise_filter_eq_high_db = 2.0
        self.noise_filter_compressor = True
        self.noise_filter_compressor_threshold_db = -18.0
        self.noise_filter_compressor_ratio = 3.0
        self.noise_filter_compressor_attack_ms = 6.0
        self.noise_filter_compressor_release_ms = 60.0
        self.noise_filter_compressor_output_gain_db = 0.0
        self.noise_filter_limiter = True
        self.noise_filter_limiter_ceiling_db = -6.0
        self.noise_filter_limiter_release_ms = 60.0
        self.noise_filter_notch = False
        self.noise_filter_notch_frequency_hz = 0.0
        self.sample_rate = 16000
        for k, v in kwargs.items():
            setattr(self, k, v)
