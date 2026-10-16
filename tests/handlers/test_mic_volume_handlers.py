"""Unit tests for ``MicVolumeHandlersMixin`` (S1/S5 IPC surface).

Three commands:

* ``get_microphone_volume`` — the guard read (pure read, lock-bypassing).
* ``set_microphone_volume`` — the ``[Back to 100%]`` write.
* ``set_output_volume``   — the S1 ``[Lower to 75%]`` offer.
"""

from __future__ import annotations


class TestGetMicrophoneVolume:
    def test_returns_the_guard_snapshot(self, ipc_server, fake_service):
        fake_service.get_microphone_volume.return_value = {
            "available": True,
            "level": 0.92,
            "supports_set": True,
            "name": "pycaw (WASAPI capture)",
        }
        resp = ipc_server._handle_get_microphone_volume(None, {})
        assert resp["type"] == "microphone_volume"
        assert resp["data"]["level"] == 0.92
        assert resp["data"]["supports_set"] is True

    def test_service_failure_returns_generic_envelope(self, ipc_server, fake_service):
        fake_service.get_microphone_volume.side_effect = RuntimeError("COM exploded")
        resp = ipc_server._handle_get_microphone_volume(None, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.internal_error"
        # The exception text must never reach the renderer.
        assert "COM exploded" not in resp["data"]["message"]

    def test_macos_no_gain_shape_is_passed_through_verbatim(self, ipc_server, fake_service):
        """``supports_set: false`` is what makes the renderer drop the button."""
        fake_service.get_microphone_volume.return_value = {
            "available": True,
            "level": 0.6,
            "supports_set": False,
            "name": "coreaudio (input, read-only)",
        }
        resp = ipc_server._handle_get_microphone_volume(None, {})
        assert resp["data"]["supports_set"] is False


class TestSetMicrophoneVolume:
    def test_happy_path_delegates_the_level(self, ipc_server, fake_service):
        fake_service.set_microphone_volume.return_value = {"ok": True, "level": 1.0}
        resp = ipc_server._handle_set_microphone_volume({"level": 1.0}, {})
        assert resp["type"] == "microphone_volume"
        assert resp["data"] == {"ok": True, "level": 1.0}
        fake_service.set_microphone_volume.assert_called_once_with(1.0)

    def test_missing_level_is_a_missing_field_error(self, ipc_server, fake_service):
        resp = ipc_server._handle_set_microphone_volume({}, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "client.missing_field"
        fake_service.set_microphone_volume.assert_not_called()

    def test_non_numeric_level_is_rejected(self, ipc_server, fake_service):
        resp = ipc_server._handle_set_microphone_volume({"level": "loud"}, {})
        assert resp["type"] == "error"
        fake_service.set_microphone_volume.assert_not_called()

    def test_out_of_range_level_is_clamped_not_rejected(self, ipc_server, fake_service):
        """A slider landing on 1.0000002 must still write, not error."""
        fake_service.set_microphone_volume.return_value = {"ok": True, "level": 1.0}
        resp = ipc_server._handle_set_microphone_volume({"level": 1.0000002}, {})
        assert resp["type"] == "microphone_volume"
        fake_service.set_microphone_volume.assert_called_once_with(1.0)

    def test_device_without_settable_gain_reports_not_ok(self, ipc_server, fake_service):
        fake_service.set_microphone_volume.return_value = {"ok": False, "level": 1.0}
        resp = ipc_server._handle_set_microphone_volume({"level": 1.0}, {})
        assert resp["type"] == "microphone_volume"
        assert resp["data"]["ok"] is False

    def test_non_dict_payload_is_a_missing_field_error(self, ipc_server, fake_service):
        resp = ipc_server._handle_set_microphone_volume(None, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "client.missing_field"

    def test_service_failure_returns_generic_envelope(self, ipc_server, fake_service):
        fake_service.set_microphone_volume.side_effect = OSError("device handle lost")
        resp = ipc_server._handle_set_microphone_volume({"level": 1.0}, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.internal_error"
        assert "device handle lost" not in resp["data"]["message"]


class TestSetOutputVolume:
    def test_happy_path_delegates_the_level(self, ipc_server, fake_service):
        fake_service.set_output_volume.return_value = {"ok": True, "level": 0.75}
        resp = ipc_server._handle_set_output_volume({"level": 0.75}, {})
        assert resp["type"] == "output_volume"
        assert resp["data"] == {"ok": True, "level": 0.75}
        fake_service.set_output_volume.assert_called_once_with(0.75)

    def test_missing_level_is_a_missing_field_error(self, ipc_server, fake_service):
        resp = ipc_server._handle_set_output_volume({}, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "client.missing_field"
        fake_service.set_output_volume.assert_not_called()

    def test_unavailable_backend_reports_not_ok(self, ipc_server, fake_service):
        fake_service.set_output_volume.return_value = {"ok": False, "level": None}
        resp = ipc_server._handle_set_output_volume({"level": 0.75}, {})
        assert resp["data"]["ok"] is False

    def test_service_failure_returns_generic_envelope(self, ipc_server, fake_service):
        fake_service.set_output_volume.side_effect = RuntimeError("no backend")
        resp = ipc_server._handle_set_output_volume({"level": 0.75}, {})
        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.internal_error"
