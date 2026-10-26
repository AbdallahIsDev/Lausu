"""A missing audio backend must say so once, at ERROR, with a repair hint.

Pre-fix both enumeration seams swallowed the import failure: the mic list
returned ``[]`` behind a DEBUG traceback and the UI simply showed no
microphones, so a broken install looked like an unplugged device.
"""

from __future__ import annotations

import logging
import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _reset_module_state():
    from voice_typer.server.server_platform import microphone_list as _ml

    _ml.invalidate_microphone_list_cache()
    _ml._AUDIO_BACKEND_FAULT_LOGGED = False
    yield
    _reset_lazy_sounddevice_proxies()
    _ml.invalidate_microphone_list_cache()
    _ml._AUDIO_BACKEND_FAULT_LOGGED = False


def _reset_lazy_sounddevice_proxies() -> None:
    """Clear cached ImportErrors on the module-level ``sd`` lazy proxies.

    ``sys.modules["sounddevice"] = None`` makes every proxy that touches it
    cache the ImportError for the rest of the process; without this the
    next test in the same worker sees a permanently broken backend.
    """
    from voice_typer.server._lazy_import import _LazyModule

    for name, module in list(sys.modules.items()):
        if not name.startswith("voice_typer.server"):
            continue
        for attr, value in list(vars(module).items()):
            if isinstance(value, _LazyModule) and attr == "sd":
                value.reset_cache()


@pytest.fixture
def missing_backend(monkeypatch):
    """Make ``import sounddevice`` fail without touching a real install."""
    monkeypatch.setitem(sys.modules, "sounddevice", None)


def _fake_sounddevice(default_input: int = 0) -> types.ModuleType:
    """Minimal stand-in module: one USB mic on the platform's canonical API."""
    from voice_typer.server.server_platform import microphone_list as _ml

    host_api = _ml._preferred_host_api_substring() or "Windows WASAPI"
    devices = [
        {
            "index": default_input,
            "name": "USB Mic",
            "hostapi": 0,
            "max_input_channels": 1,
            "default_samplerate": 44100.0,
        }
    ]
    module = types.ModuleType("sounddevice")
    module.query_devices = lambda *a, **k: devices[0] if k.get("kind") == "input" else [dict(d) for d in devices]
    module.query_hostapis = lambda: [{"name": host_api, "default_input_device": default_input}]
    return module


def _error_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_missing_backend_logs_one_actionable_error(caplog, missing_backend):
    from voice_typer.server.server_platform import microphone_list as ml

    with caplog.at_level(logging.ERROR):
        assert ml._list_microphones_uncached() == []
        # Second enumeration in the same fault episode stays quiet.
        assert ml._list_microphones_uncached() == []

    errors = _error_records(caplog)
    assert len(errors) == 1
    message = errors[0].getMessage()
    assert "Audio backend unavailable" in message
    assert "sounddevice" in message
    assert "reinstall the app" in message


def test_non_import_failure_stays_debug(monkeypatch, caplog):
    """A PortAudio fault is transient noise, not a broken install."""
    from voice_typer.server.server_platform import microphone_list as ml

    module = types.ModuleType("sounddevice")

    def _boom(*args, **kwargs):
        raise OSError("PortAudio unavailable")

    module.query_devices = _boom
    monkeypatch.setitem(sys.modules, "sounddevice", module)

    with caplog.at_level(logging.DEBUG):
        assert ml._list_microphones_uncached() == []

    assert not _error_records(caplog)
    assert any("Could not enumerate microphones" in r.getMessage() for r in caplog.records)
    assert ml._AUDIO_BACKEND_FAULT_LOGGED is False


def test_fault_report_rearms_after_a_clean_import(monkeypatch, caplog):
    from voice_typer.server.server_platform import microphone_list as ml

    monkeypatch.setitem(sys.modules, "sounddevice", None)
    with caplog.at_level(logging.ERROR):
        assert ml._list_microphones_uncached() == []
    assert ml._AUDIO_BACKEND_FAULT_LOGGED is True

    monkeypatch.setitem(sys.modules, "sounddevice", _fake_sounddevice())
    assert [m["name"] for m in ml._list_microphones_uncached()] == ["USB Mic"]
    assert ml._AUDIO_BACKEND_FAULT_LOGGED is False

    monkeypatch.setitem(sys.modules, "sounddevice", None)
    with caplog.at_level(logging.ERROR):
        assert ml._list_microphones_uncached() == []
    assert len(_error_records(caplog)) == 2


def test_happy_path_still_lists_devices(monkeypatch):
    from voice_typer.server.server_platform import microphone_list as ml

    monkeypatch.setitem(sys.modules, "sounddevice", _fake_sounddevice())
    mics = ml.list_microphones()

    assert [m["name"] for m in mics] == ["USB Mic"]
    assert mics[0]["default"] is True


def test_recording_device_walk_uses_the_same_report(caplog, missing_backend):
    from voice_typer.server.recording.device_manager import DeviceManager

    recorder = MagicMock()
    recorder.config = MagicMock(sample_rate=16000, microphone=None)
    manager = DeviceManager(recorder)
    cached = [{"index": 7, "name": "Previous Mic"}]
    manager._device_list_cache = cached
    manager._device_list_cache_time = 0.0

    with caplog.at_level(logging.ERROR):
        assert manager._refresh_device_list() is cached

    errors = _error_records(caplog)
    assert len(errors) == 1
    assert "Audio backend unavailable" in errors[0].getMessage()


def test_recording_device_walk_keeps_other_import_errors_quiet(monkeypatch, caplog):
    """A non-audio import fault is transient noise, not a broken install."""
    from voice_typer.server.recording.device_manager import DeviceManager
    from voice_typer.server.server_platform import microphone_list as ml

    def _boom(_devices):
        raise ImportError("No module named 'some_helper'")

    monkeypatch.setattr(ml, "iter_filtered_input_devices", _boom, raising=False)
    recorder = MagicMock()
    recorder.config = MagicMock(sample_rate=16000, microphone=None)
    manager = DeviceManager(recorder)
    ml._AUDIO_BACKEND_FAULT_LOGGED = False

    with caplog.at_level(logging.DEBUG):
        assert manager._refresh_device_list() == []

    assert not _error_records(caplog)
    assert ml._AUDIO_BACKEND_FAULT_LOGGED is False
