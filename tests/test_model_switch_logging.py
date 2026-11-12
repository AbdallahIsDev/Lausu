"""Model-switch + Parakeet load + tray truth (no real weights)."""

from __future__ import annotations

from voice_typer.server.model_manager._change import _friendly_model_label


class TestFriendlyModelLabel:
    def test_whisper_sizes_get_whisper_prefix(self):
        assert _friendly_model_label("large-v3-turbo", "whisper") == "Whisper Large V3 Turbo"
        assert _friendly_model_label("large-v3", "whisper") == "Whisper Large V3"
        assert _friendly_model_label("tiny", "whisper") == "Whisper Tiny"

    def test_parakeet_uses_registry_display_name(self):
        assert _friendly_model_label("parakeet", "parakeet") == "Parakeet Ultra"

    def test_qwen_sizes_use_display_names(self):
        assert _friendly_model_label("qwen3-1.7b", "qwen") == "qwen3 1.7B"
        assert _friendly_model_label("qwen3-0.6b", "qwen") == "qwen3 0.6B"

    def test_no_model_is_plain(self):
        assert _friendly_model_label("", "whisper") == "no model"


class TestOrtProviderRedaction:
    def test_provider_names_survive_redaction(self):
        from voice_typer.server.security.secret_redaction import redact_secret

        for name in ("CUDAExecutionProvider", "CPUExecutionProvider"):
            assert redact_secret(name) == name
        line = redact_secret("CUDAExecutionProvider not available (have: CPUExecutionProvider), using CPU only")
        assert "CUDAExecutionProvider" in line
        assert "CPUExecutionProvider" in line
        assert "***" not in line
        # Azure is filtered from the have list but the name itself is
        # still public vocabulary if it ever appears.
        assert redact_secret("AzureExecutionProvider") == "AzureExecutionProvider"


class TestParakeetDeviceTruth:
    def test_device_info_uses_effective_providers(self, tmp_path, monkeypatch):
        import sys
        from unittest.mock import MagicMock, patch

        from voice_typer.server.parakeet_engine import ParakeetEngine

        snap = tmp_path / "models--Masterx--parakeet-tdt-0.6b-ultra-onnx" / "snapshots" / "test123"
        snap.mkdir(parents=True)
        (snap / "model.onnx").write_bytes(b"fake-onnx")
        monkeypatch.setattr(
            "voice_typer.server.model_availability.snapshot_search_dirs",
            lambda config_dir, repo_id: [snap.parent.parent],
        )
        monkeypatch.setattr(
            "voice_typer.server.security.verify_model_integrity",
            lambda snapshot, repo_id: True,
        )
        mock_asr = MagicMock(name="mock_onnx_asr")
        mock_asr.__version__ = "0.12.0-test"
        mock_asr.load_model.side_effect = lambda *a, **k: MagicMock(name="m")
        mock_ort = MagicMock(name="mock_onnxruntime")
        mock_ort.__version__ = "1.20.0-test"
        mock_ort.get_available_providers.return_value = ["CPUExecutionProvider"]
        mock_ort.SessionOptions.return_value = MagicMock(name="opts")
        saved = (ParakeetEngine._imports_loaded, ParakeetEngine._onnx_asr, ParakeetEngine._ort)
        ParakeetEngine._imports_loaded = False
        ParakeetEngine._onnx_asr = None
        ParakeetEngine._ort = None
        try:
            with patch.dict(sys.modules, {"onnx_asr": mock_asr, "onnxruntime": mock_ort}):
                engine = ParakeetEngine(device="cuda", language="en")
                ParakeetEngine._ensure_imports()
                with patch.object(type(engine), "_is_cached", return_value=True):
                    assert engine.load() is True
            # Requested cuda but runtime only has CPU: truth is CPU.
            assert engine.device_info == "CPU"
            assert "parakeet/cpu/" in engine.loaded_via
        finally:
            (
                ParakeetEngine._imports_loaded,
                ParakeetEngine._onnx_asr,
                ParakeetEngine._ort,
            ) = saved

    def test_device_info_gpu_when_cuda_available(self):
        from voice_typer.server.parakeet_engine import ParakeetEngine

        engine = ParakeetEngine(device="cuda", language="en")
        engine._effective_providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        assert engine.device_info == "GPU"
        engine._effective_providers = ["CPUExecutionProvider"]
        assert engine.device_info == "CPU"


class TestGetActiveProbeLogIsDebug:
    def test_probe_fallback_is_debug_not_info(self):
        import inspect

        from voice_typer.server.asr.registry import RegistryCore

        src = inspect.getsource(RegistryCore.get_active)
        assert "probe during load" in src
        # The confusing permanent-sounding line must be gone.
        assert "falling back to whisper" not in src


class TestRestartLogTruth:
    def test_idle_unload_tray_message_keeps_device(self):
        """Idle unload must keep the last device in the tray message."""
        import inspect

        from voice_typer.server.model_manager._lifecycle import LifecycleMixin

        src = inspect.getsource(LifecycleMixin._do_idle_unload)
        assert "device_info" in src
        assert ' - {device_info}' in src or '" - " + device_info' in src or "- {device_info}" in src

    def test_ack_clear_before_publish(self):
        import inspect

        from voice_typer.server.app_lifecycle import LifecycleController

        src = inspect.getsource(LifecycleController.restart_app)
        assert "_relaunch_ack_event.clear()" in src
        assert 'publish({"type": "relaunch_app"})' in src
        assert src.index("_relaunch_ack_event.clear()") < src.index('publish({"type": "relaunch_app"})')

    def test_first_mic_load_does_not_log_device_added(self):
        import inspect

        from voice_typer.server import startup_tasks

        src = inspect.getsource(startup_tasks.load_microphones)
        # First load is already covered by the Found line; the
        # Device set changed event is only for later changes.
        assert "if old_ids and old_ids != new_ids:" in src

    def test_env_var_and_error_codes_survive_redaction(self):
        from voice_typer.server.security.secret_redaction import redact_secret

        assert redact_secret("VOICE_TYPER_SIDECAR_DEV=1") == "VOICE_TYPER_SIDECAR_DEV=1"
        assert redact_secret("sidecar_disconnected") == "sidecar_disconnected"
        assert redact_secret("VOICE_TYPER_BOOT_EPOCH_MS") == "VOICE_TYPER_BOOT_EPOCH_MS"

    def test_respawn_suppresses_host_boot(self, monkeypatch, caplog):
        import logging
        import time

        from voice_typer.server import startup_timeline as st

        now_ms = int(time.time() * 1000)
        monkeypatch.setenv(st.BOOT_EPOCH_ENV, str(now_ms - 78 * 60 * 1000))
        monkeypatch.setenv(st.SPAWN_EPOCH_ENV, str(now_ms - 2200))
        with caplog.at_level(logging.INFO, logger="test.respawn"):
            st.log_launch_timeline(logging.getLogger("test.respawn"))
        msgs = [r.getMessage() for r in caplog.records if "Launch timeline" in r.getMessage()]
        assert len(msgs) == 1
        assert "host boot" not in msgs[0]
        assert "backend init" in msgs[0]
