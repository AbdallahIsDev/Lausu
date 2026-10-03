"""C-LOG-4: app-starting banner format, order, and once-per-process."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from voice_typer.server import startup_banner
from voice_typer.server.branding import APP_NAME
from voice_typer.server.startup_banner import (
    emit_app_starting_banner,
    reset_app_starting_banner_for_tests,
)


def _config(**overrides):
    cfg = MagicMock()
    cfg.model_size = overrides.get("model_size", "tiny")
    cfg.asr_backend = overrides.get("asr_backend", "whisper")
    cfg.hotkey = overrides.get("hotkey", "<caps_lock>")
    cfg.microphone = overrides.get("microphone")
    cfg.sample_rate = overrides.get("sample_rate", 16000)
    return cfg


def test_banner_uses_pipe_separators_not_double_dash(monkeypatch, caplog):
    reset_app_starting_banner_for_tests()
    monkeypatch.setattr(
        "voice_typer.server.tray_models.is_active_model_downloaded",
        lambda config: True,
    )

    with caplog.at_level(logging.INFO, logger="voice_typer.server.app"):
        emit_app_starting_banner(_config())

    messages = [
        r.message
        for r in caplog.records
        if r.name == "voice_typer.server.app" and "starting" in r.message
    ]
    assert messages, "app-starting banner must be emitted"
    msg = messages[0]
    assert msg.startswith(f"{APP_NAME} starting | model="), msg
    assert "--" not in msg, f"C-LOG-4 forbids '--' in the starting banner: {msg!r}"
    assert msg.count("|") == 4, f"expected 4 pipe separators: {msg!r}"


def test_banner_emitted_only_once_per_process(monkeypatch, caplog):
    reset_app_starting_banner_for_tests()
    monkeypatch.setattr(
        "voice_typer.server.tray_models.is_active_model_downloaded",
        lambda config: True,
    )

    with caplog.at_level(logging.INFO, logger="voice_typer.server.app"):
        emit_app_starting_banner(_config())
        emit_app_starting_banner(_config())

    lines = [
        r.message
        for r in caplog.records
        if r.name == "voice_typer.server.app" and " starting | model=" in r.message
    ]
    assert len(lines) == 1, f"banner must be once-per-process, got {len(lines)}"


def test_banner_never_raises_on_bad_config(caplog):
    reset_app_starting_banner_for_tests()
    bad = object()  # no model_size / hotkey attrs

    with caplog.at_level(logging.DEBUG, logger="voice_typer.server.app"):
        emit_app_starting_banner(bad)  # must not raise

    # Either a banner line or a debug failure record; never a crash.
    assert startup_banner._emitted is False or any(
        "starting | model=" in r.message for r in caplog.records
    )
