"""Unit tests for ``_handle_open_data_folder`` + ``get_model_status`` ``_storage``."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestOpenMicSettings:
    """``_handle_open_mic_settings`` opens the OS mic privacy page."""

    def test_windows_opens_ms_settings(self, ipc_server, monkeypatch):
        import voice_typer.server.platform_utils as plat

        monkeypatch.setattr(plat, "is_windows", lambda: True)
        monkeypatch.setattr(plat, "is_macos", lambda: False)
        monkeypatch.setattr(plat, "is_linux", lambda: False)
        opened = []
        monkeypatch.setattr("os.startfile", lambda path, *a, **k: opened.append(path), raising=False)

        resp = ipc_server._handle_open_mic_settings({}, {})
        assert resp["type"] == "mic_settings"
        assert resp["data"]["opened"] is True
        assert opened == ["ms-settings:privacy-microphone"]

    def test_unsupported_platform_returns_error(self, ipc_server, monkeypatch):
        import voice_typer.server.platform_utils as plat

        monkeypatch.setattr(plat, "is_windows", lambda: False)
        monkeypatch.setattr(plat, "is_macos", lambda: False)
        monkeypatch.setattr(plat, "is_linux", lambda: False)

        resp = ipc_server._handle_open_mic_settings({}, {})
        assert resp["type"] == "error"


class TestOpenDataFolder:
    """``_handle_open_data_folder`` opens the config dir in the OS file manager."""

    def test_happy_path_opens_folder_and_returns_opened_true(self, ipc_server, monkeypatch, tmp_path):
        monkeypatch.setattr("voice_typer.server._paths._config_dir", lambda: tmp_path)
        monkeypatch.setattr("subprocess.Popen", lambda cmd, **kw: MagicMock())
        monkeypatch.setattr("os.startfile", lambda path, *args, **kwargs: None, raising=False)

        resp = ipc_server._handle_open_data_folder({}, {})
        assert resp["type"] == "data_folder"
        assert resp["data"]["opened"] is True
        assert resp["data"]["path"] == str(tmp_path)

    def test_missing_folder_returns_opened_false_with_reason(self, ipc_server, monkeypatch, tmp_path):
        monkeypatch.setattr("voice_typer.server._paths._config_dir", lambda: tmp_path / "no_such_dir")

        resp = ipc_server._handle_open_data_folder({}, {})
        assert resp["type"] == "data_folder"
        assert resp["data"]["opened"] is False
        assert resp["data"]["reason"] == "not_found"
        assert "path" in resp["data"]


class TestModelStorageSummary:
    """``_handle_get_model_status`` attaches the ``_storage`` summary."""

    def test_storage_summary_counts_hub_bytes(self, ipc_server, fake_service, monkeypatch, tmp_path):
        hub = tmp_path / "huggingface" / "hub"
        hub.mkdir(parents=True)
        payload = b"x" * 1024
        (hub / "weights.bin").write_bytes(payload)
        (hub / "nested").mkdir()
        (hub / "nested" / "more.bin").write_bytes(payload)
        monkeypatch.setattr("voice_typer.server._paths._config_dir", lambda: tmp_path)

        fake_service.get_model_status.return_value = {"tiny": {"downloaded": True}}
        resp = ipc_server._handle_get_model_status({}, {})

        assert resp["type"] == "model_status"
        assert resp["data"]["tiny"] == {"downloaded": True}
        storage = resp["data"]["_storage"]
        assert storage["used_bytes"] == 2 * 1024
        assert storage["hub_path"] == str(hub)
        assert storage["config_dir"] == str(tmp_path)

    def test_missing_hub_reports_zero_bytes(self, ipc_server, fake_service, monkeypatch, tmp_path):
        monkeypatch.setattr("voice_typer.server._paths._config_dir", lambda: tmp_path)

        fake_service.get_model_status.return_value = {}
        resp = ipc_server._handle_get_model_status({}, {})

        assert resp["type"] == "model_status"
        assert resp["data"]["_storage"]["used_bytes"] == 0
