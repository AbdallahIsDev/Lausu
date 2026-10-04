"""Tray tooltip segments: state word, friendly model name, hotkey.

``Lausu | <state> | <model> | <hotkey>`` — segments split on `` | ``
only (no nested parentheses); the state word must track the real state
(never a hardcoded "Ready"), the model segment must name the ASR model
(``Whisper Large V3``), never the engine (``Whisper ASR``) or the raw id
(``large-v3``), and the hotkey must render (``Caps Lock``).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from voice_typer.server.tray import TrayIcon
from voice_typer.server.tray_models import tooltip_model_label
from voice_typer.server.tray_types import AppState


def _cfg(**over):
    base = {"hotkey": "<caps_lock>", "asr_backend": "whisper", "model_size": "large-v3"}
    base.update(over)
    return SimpleNamespace(**base)


def _tray(config, downloaded: bool, monkeypatch) -> TrayIcon:
    import voice_typer.server.tray_models as tray_models_mod

    monkeypatch.setattr(tray_models_mod, "is_active_model_downloaded", lambda _c: downloaded)
    tray = TrayIcon(controller=MagicMock(), config=config)
    tray._cpu_fallback_active = False
    return tray


class TestTooltipModelLabel:
    def test_whisper_sizes_get_family_prefix(self):
        assert tooltip_model_label(_cfg(model_size="tiny")) == "Whisper Tiny"
        assert tooltip_model_label(_cfg(model_size="large-v3")) == "Whisper Large V3"
        assert tooltip_model_label(_cfg(model_size="large-v3-turbo")) == "Whisper Large V3 Turbo"

    def test_backends_use_registry_display_names(self):
        assert tooltip_model_label(_cfg(asr_backend="parakeet", model_size="")) == "Parakeet-TDT-0.6b-V3"
        assert tooltip_model_label(_cfg(asr_backend="qwen", model_size="")) == "Qwen-3"

    def test_no_model_or_cloud_has_no_label(self):
        assert tooltip_model_label(_cfg(model_size="")) == ""
        assert tooltip_model_label(_cfg(asr_backend="cloud", model_size="")) == ""


class TestTooltipSegments:
    def test_ready_state_names_friendly_model_and_hotkey(self, monkeypatch):
        tray = _tray(_cfg(), True, monkeypatch)
        tooltip = tray._compute_tooltip(AppState.IDLE, "")
        assert tooltip.startswith("Lausu | Ready")
        assert "Whisper Large V3" in tooltip
        assert "[large-v3]" not in tooltip
        assert "Whisper ASR" not in tooltip
        assert tooltip.endswith("Caps Lock")
        assert "(" not in tooltip and ")" not in tooltip

    def test_bare_idle_without_model_is_not_ready(self, monkeypatch):
        tray = _tray(_cfg(model_size=""), False, monkeypatch)
        tooltip = tray._compute_tooltip(AppState.IDLE, "")
        assert "| Ready" not in tooltip
        assert "No model selected" in tooltip
        assert "[" not in tooltip

    def test_bare_non_idle_shows_state_word(self, monkeypatch):
        tray = _tray(_cfg(), True, monkeypatch)
        assert "| recording" in tray._compute_tooltip(AppState.RECORDING, "")
        assert "| loading" in tray._compute_tooltip(AppState.LOADING, "")
        assert "| error" in tray._compute_tooltip(AppState.ERROR, "")

    def test_message_still_wins_over_state_word(self, monkeypatch):
        tray = _tray(_cfg(), True, monkeypatch)
        tooltip = tray._compute_tooltip(AppState.RECORDING, "Recording...")
        assert "| Recording..." in tooltip
        assert "Whisper Large V3" in tooltip

    def test_ready_gpu_tooltip_has_no_nesting(self, monkeypatch):
        from voice_typer.server.tray_models import describe_device

        assert describe_device("cuda") == "GPU"
        assert describe_device("cpu") == "CPU"
        assert describe_device("cuda:0") == "GPU"
        tray = _tray(_cfg(), True, monkeypatch)
        tooltip = tray._compute_tooltip(AppState.IDLE, "Ready | GPU")
        assert tooltip == "Lausu | Ready | GPU | Whisper Large V3 | Caps Lock"
        assert "cuda" not in tooltip
