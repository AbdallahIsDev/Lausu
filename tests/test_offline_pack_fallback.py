"""Offline-pack-missing UX: no in-process ASR fallback remains.

Weights on disk but no runtime pack must NOT report "no model selected":
the tray/homepage message names the offline pack. The old system-library
fallback is gone with the Python ASR stack; the worker loader stays.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _manager():
    from voice_typer.server.model_manager._notify import LastResortNotifyMixin

    class _M(LastResortNotifyMixin):
        def __init__(self):
            self._app = SimpleNamespace(
                config=SimpleNamespace(asr_backend="whisper"),
                tray=SimpleNamespace(
                    set_state=lambda *a, **k: None,
                    notify=lambda *a, **k: None,
                ),
            )

    return _M()


class TestOfflinePackMissingError:
    def test_is_model_not_downloaded_subclass(self):
        from voice_typer.server.asr_errors import ModelNotDownloadedError, OfflinePackMissingError

        assert issubclass(OfflinePackMissingError, ModelNotDownloadedError)

    def test_worker_raises_pack_error_when_pack_absent(self, monkeypatch):
        from voice_typer.server import worker_backed_asr
        from voice_typer.server.asr_errors import OfflinePackMissingError
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda: None)
        shim = worker_backed_asr.WorkerBackedAsr(model_size="large-v3")
        try:
            shim.load()
        except OfflinePackMissingError as exc:
            assert exc.model_size == "large-v3"
        else:
            raise AssertionError("expected OfflinePackMissingError")

    def test_worker_loads_when_pack_present(self, monkeypatch):
        from voice_typer.server import worker_backed_asr
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda: "1.0.0")
        shim = worker_backed_asr.WorkerBackedAsr(model_size="large-v3")
        assert shim.load() is True
        assert shim.is_loaded is True

    def test_notify_names_pack_not_model_selection(self):
        mgr = _manager()
        messages: list[str] = []
        mgr._app.tray.set_state = lambda *a, **k: messages.append(a[1] if len(a) > 1 else "")
        from voice_typer.server.asr_errors import OfflinePackMissingError

        exc = OfflinePackMissingError(
            "The offline pack is not installed.",
            model_size="large-v3",
            backend="whisper",
        )
        reason = mgr._notify_model_load_refused(exc, backend="whisper")
        assert "Offline pack" in reason, f"pack message must name the pack, got: {reason!r}"
        assert "No speech model is selected" not in reason
        assert messages and "Offline pack" in messages[0]


class TestNoInProcessFallback:
    def test_system_fallback_always_refuses(self):
        from voice_typer.server import system_whisper

        cfg = SimpleNamespace(model_size="large-v3", device="cpu", language="en", beam_size=5)
        assert system_whisper.try_load_system_whisper(cfg) is None

    def test_worker_fallback_refuses_when_worker_down(self, monkeypatch):
        from voice_typer.server import system_whisper, worker_client

        client = SimpleNamespace(port=None)
        monkeypatch.setattr(worker_client, "get_shared_client", lambda: client)
        cfg = SimpleNamespace(model_size="large-v3", device="cpu", language="en")
        assert system_whisper.try_load_worker_whisper(cfg) is None

    def test_pack_missing_reraises_without_worker(self, monkeypatch):
        from voice_typer.server.asr_errors import OfflinePackMissingError
        from voice_typer.server.asr_registry import AsrBackendRegistry
        from voice_typer.server.service import update_check
        from voice_typer.server.worker_backed_asr import WorkerBackedAsr

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda: None)
        cfg = SimpleNamespace(
            asr_backend="whisper",
            model_size="large-v3",
            device="cpu",
            language="en",
            beam_size=5,
            best_of=5,
            condition_on_previous_text=False,
            disabled_backends=[],
        )
        registry = AsrBackendRegistry(cfg)
        registry.register("whisper", WorkerBackedAsr(model_size="large-v3", config=cfg))
        with pytest.raises(OfflinePackMissingError):
            registry.load_with_fallback()
