"""huggingface_hub flags must land on the already-imported module.

The sidecar imports ``huggingface_hub`` long before any download, so writing
the env vars alone never reached ``huggingface_hub.constants`` and the symlink
warning, the WinError 1314 retry, and the tqdm bars all survived.
"""

from __future__ import annotations

import importlib
import inspect

import pytest


class _GateHitError(Exception):
    """Sentinel raised by the patched gate."""


def _hf_constants():
    pytest.importorskip("huggingface_hub")
    from huggingface_hub import constants

    return constants


@pytest.fixture(autouse=True)
def _isolate_hf_global_state(monkeypatch: pytest.MonkeyPatch):
    """``disable_progress_bars()`` is process-global: restore it afterwards."""
    pytest.importorskip("huggingface_hub")
    tqdm_module = importlib.import_module("huggingface_hub.utils.tqdm")
    snapshot = dict(tqdm_module.progress_bar_states)
    for var in (
        "HF_HUB_DISABLE_PROGRESS_BARS",
        "HF_HUB_DISABLE_SYMLINKS",
        "HF_HUB_DISABLE_SYMLINKS_WARNING",
        "HF_HUB_DISABLE_TELEMETRY",
        "HF_HUB_DISABLE_XET",
    ):
        monkeypatch.delenv(var, raising=False)
    yield
    tqdm_module.progress_bar_states.clear()
    tqdm_module.progress_bar_states.update(snapshot)


class TestConstantsMirroredAfterImport:
    def test_flags_set_on_imported_module(self, monkeypatch: pytest.MonkeyPatch):
        constants = _hf_constants()
        from voice_typer.server import asr_setup

        monkeypatch.setattr(constants, "HF_HUB_DISABLE_SYMLINKS_WARNING", False)
        monkeypatch.setattr(constants, "HF_HUB_DISABLE_PROGRESS_BARS", None)

        asr_setup.ensure_hf_env()

        assert constants.HF_HUB_DISABLE_SYMLINKS_WARNING is True
        assert constants.HF_HUB_DISABLE_PROGRESS_BARS is True

    def test_progress_bars_silenced_for_new_bars(self):
        from voice_typer.server import asr_setup

        asr_setup.ensure_hf_env()
        bar = asr_setup.get_download_tqdm_class()(total=3, disable=False)
        try:
            assert bar.disable is True, "tqdm bars still render into the sidecar log"
        finally:
            bar.close()


class TestSymlinkFlagIsPlatformGated:
    def test_windows_disables_symlinks(self, monkeypatch: pytest.MonkeyPatch):
        constants = _hf_constants()
        from voice_typer.server import asr_setup

        monkeypatch.setattr(constants, "HF_HUB_DISABLE_SYMLINKS", False)
        monkeypatch.setattr(asr_setup.os, "name", "nt")

        asr_setup.ensure_hf_env()

        assert constants.HF_HUB_DISABLE_SYMLINKS is True

    def test_posix_leaves_symlinks_untouched(self, monkeypatch: pytest.MonkeyPatch):
        constants = _hf_constants()
        from voice_typer.server import asr_setup

        monkeypatch.setattr(constants, "HF_HUB_DISABLE_SYMLINKS", False)
        monkeypatch.setattr(asr_setup.os, "name", "posix")

        asr_setup.ensure_hf_env()

        assert constants.HF_HUB_DISABLE_SYMLINKS is False


class TestGateSurvivesDisabledProgressBars:
    def test_update_still_calls_gate(self, monkeypatch: pytest.MonkeyPatch):
        from voice_typer.server import asr_setup

        asr_setup.ensure_hf_env()
        asr_setup.reset_download_pause_state()
        try:

            def _boom() -> None:
                raise _GateHitError("gate reached")

            monkeypatch.setattr(asr_setup, "check_download_gate", _boom)
            gate = asr_setup.get_download_tqdm_class()(total=5, disable=False)
            assert gate.disable is True, "progress bars must stay off"
            with pytest.raises(_GateHitError):
                gate.update(1)
        finally:
            asr_setup.clear_download_pause_state()


class TestWhisperBranchAppliesFlagsBeforeTransfer:
    def test_ensure_hf_env_runs_before_force_http(self, tmp_config_dir, monkeypatch: pytest.MonkeyPatch):
        from unittest.mock import MagicMock

        import voice_typer.server.asr_setup as asr
        from voice_typer.server import service as svc_mod

        calls: list[str] = []

        class _StopTransferError(Exception):
            pass

        monkeypatch.setattr(asr, "ensure_hf_env", lambda: calls.append("ensure_hf_env"))

        def _force_http() -> None:
            calls.append("force_http_download_path")
            raise _StopTransferError

        monkeypatch.setattr(asr, "force_http_download_path", _force_http)

        class FakeApp:
            config = type("FakeConfig", (), {})()
            _microphones: list = []
            tray = MagicMock()

        service = svc_mod.LausuService(FakeApp())
        monkeypatch.setattr(service, "_require_huggingface_consent", lambda name: None)
        meta = MagicMock()
        meta.repo_id = "org/target"
        meta.backend = "whisper"
        meta.download_size_mb = 1

        asr.clear_download_pause_state()
        try:
            with pytest.raises(_StopTransferError):
                service._download_whisper_family("tiny", meta)
        finally:
            asr.clear_download_pause_state()

        assert calls == ["ensure_hf_env", "force_http_download_path"]


class TestDeprecatedArgsRemoved:
    def test_no_resume_download_in_asr_setup(self):
        from voice_typer.server import asr_setup

        assert "resume_download" not in inspect.getsource(asr_setup)
