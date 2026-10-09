"""Regression tests: mic-permission revocation must refuse cleanly."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_heavy_imports():
    yield


def test_probe_returns_denied_on_portaudio_error(monkeypatch):
    from voice_typer.server import permissions
    from voice_typer.server.permissions import mic as mic_mod

    class _PortAudioError(Exception):
        pass

    class _FakeStream:
        def start(self):
            raise _PortAudioError(
                "Error opening InputStream: Unanticipated host error "
                "[PaErrorCode -9999]: 'Undefined external error.' [MME error 1]"
            )

        def stop(self):
            pass

        def close(self):
            pass

    class _FakeSD:
        def InputStream(self, **kw):  # noqa: N802 - mirrors sounddevice API
            return _FakeStream()

    monkeypatch.setitem(__import__("sys").modules, "sounddevice", _FakeSD())
    monkeypatch.setattr(mic_mod, "_windows_microphone_consent_denied", lambda: True)
    state = mic_mod._check_windows_microphone()
    assert state == permissions.MicrophonePermissionState.DENIED


def test_probe_unknown_when_registry_unreadable(monkeypatch):
    """-9999 with unreadable consent store is UNKNOWN, not a false DENIED."""
    from voice_typer.server import permissions
    from voice_typer.server.permissions import mic as mic_mod

    class _PortAudioError(Exception):
        pass

    class _FakeStream:
        def start(self):
            raise _PortAudioError(
                "Error opening InputStream: Unanticipated host error "
                "[PaErrorCode -9999]: 'Undefined external error.' [MME error 1]"
            )

        def stop(self):
            pass

        def close(self):
            pass

    class _FakeSD:
        def InputStream(self, **kw):  # noqa: N802 - mirrors sounddevice API
            return _FakeStream()

    monkeypatch.setitem(__import__("sys").modules, "sounddevice", _FakeSD())
    monkeypatch.setattr(mic_mod, "_windows_microphone_consent_denied", lambda: None)
    state = mic_mod._check_windows_microphone()
    assert state == permissions.MicrophonePermissionState.UNKNOWN


def test_preflight_blocks_denied_start(monkeypatch):
    """End-to-end: probe DENIED (-9999 + registry Deny) blocks start."""
    import voice_typer.server.permissions as permissions_mod
    from voice_typer.server.asr_errors import MicrophonePermissionDeniedError
    from voice_typer.server.permissions import mic as mic_mod
    from voice_typer.server.recording import Recorder

    class _PortAudioError(Exception):
        pass

    class _FakeStream:
        def start(self):
            raise _PortAudioError(
                "Error opening InputStream: Unanticipated host error "
                "[PaErrorCode -9999]: 'Undefined external error.' [MME error 1]"
            )

        def stop(self):
            pass

        def close(self):
            pass

    class _FakeSD:
        def InputStream(self, **kw):  # noqa: N802 - mirrors sounddevice API
            return _FakeStream()

    monkeypatch.setitem(__import__("sys").modules, "sounddevice", _FakeSD())
    monkeypatch.setattr(mic_mod, "_windows_microphone_consent_denied", lambda: True)
    monkeypatch.setattr(permissions_mod, "is_macos", lambda: False)
    monkeypatch.setattr(permissions_mod, "is_windows", lambda: True)
    monkeypatch.setattr(permissions_mod, "is_linux", lambda: False)
    config = MagicMock(
        sample_rate=16000,
        microphone=None,
        max_recording_time_seconds=900,
        pre_roll_buffer_seconds=1.0,
        recording_channels=1,
    )
    rec = Recorder(config)
    rec._recording_event.clear()
    with pytest.raises(MicrophonePermissionDeniedError):
        rec.start()


def test_fallback_sweep_cannot_override_denial(monkeypatch):
    import voice_typer.server.permissions as permissions_mod
    from voice_typer.server.asr_errors import MicrophonePermissionDeniedError
    from voice_typer.server.recording.stream_lifecycle import StreamLifecycle

    def _raise_denied():
        raise MicrophonePermissionDeniedError("denied", state="denied")

    monkeypatch.setattr(permissions_mod, "verify_microphone_accessible", _raise_denied)
    lifecycle = StreamLifecycle(recorder=MagicMock())
    recorder = MagicMock()
    with pytest.raises(MicrophonePermissionDeniedError):
        lifecycle.open_stream_fallback(recorder, [], MagicMock(), 16000, None)
    recorder._devices._all_input_device_candidates.assert_not_called()


def test_denied_hotkey_press_kicks_no_model_load():
    import voice_typer.server.permissions as permissions_mod
    from voice_typer.server.asr_errors import MicrophonePermissionDeniedError
    from voice_typer.server.recording_lifecycle import RecordingLifecycle

    app = MagicMock(name="app")
    app.recorder = MagicMock(name="recorder")
    app.recorder.recording = False
    app._busy_event = threading.Event()
    app._busy_event.set()
    app._cycle_id = "#1"
    app._cycle_counter = 0
    app.config = MagicMock()
    app.config.voice_biometric_consent = True
    app.tray = MagicMock()
    app._waveform_bubble = MagicMock()
    app._cancel_pending_timers = MagicMock()
    app._schedule_timer = MagicMock()
    app.models = MagicMock()
    app.models.active_transcriber = MagicMock(return_value=None)
    app.models._model_load_thread = None

    def _raise_denied():
        raise MicrophonePermissionDeniedError("denied", state="denied")

    real_verify = permissions_mod.verify_microphone_accessible
    permissions_mod.verify_microphone_accessible = _raise_denied
    try:
        controller = MagicMock(name="controller")
        controller._app = app
        controller._toggle_lock = threading.RLock()
        lifecycle = RecordingLifecycle()
        lifecycle._toggle_impl(controller)
    finally:
        permissions_mod.verify_microphone_accessible = real_verify
    app.models.start_background_load.assert_not_called()
    app.recorder.start.assert_not_called()
    app._waveform_bubble.set_state.assert_called_once_with("permission_revoked")


def test_too_short_path_resets_bubble():
    import threading

    import numpy as np
    from voice_typer.server.recording_lifecycle import RecordingLifecycle

    app = MagicMock(name="app")
    app.recorder = MagicMock(name="recorder")
    app.recorder._dropped_ring_chunks = 0
    app.recorder.last_rms = 0.0
    app.config = MagicMock()
    app.config.sample_rate = 16000
    app.config.bubble_behavior = "show_on_record"
    app.tray = MagicMock()
    app._waveform_bubble = MagicMock()
    app._busyness = MagicMock()
    app._schedule_timer = MagicMock()
    app._restore_volume = MagicMock()
    app._finalize_audio_quality_report = MagicMock()
    app._cycle_id = "#2"
    controller = MagicMock(name="controller")
    controller._app = app
    controller._watchdog_lock = threading.Lock()
    controller._cancel_streaming_session = MagicMock()
    controller._maybe_restart_level_monitor_for_always_visible_bubble = MagicMock()
    lifecycle = RecordingLifecycle()
    lifecycle._run_stop_and_transcribe(controller, np.zeros(1600, dtype=np.float32), "#2")
    app._waveform_bubble.hide.assert_called_once_with()
