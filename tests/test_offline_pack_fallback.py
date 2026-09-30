"""Offline-pack-missing UX + system-library fallback.

Weights on disk but no runtime pack must NOT report "no model
selected": the tray/homepage message names the offline pack, and a
dev checkout with system ML libraries serves the model in-process.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest
from voice_typer.server.asr_errors import ModelNotDownloadedError, OfflinePackMissingError


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
        assert issubclass(OfflinePackMissingError, ModelNotDownloadedError)

    def test_worker_raises_pack_error_when_pack_absent(self, monkeypatch):
        from voice_typer.server import worker_backed_asr
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
        exc = OfflinePackMissingError(
            "The offline pack is not installed.",
            model_size="large-v3",
            backend="whisper",
        )
        reason = mgr._notify_model_load_refused(exc, backend="whisper")
        assert "Offline pack" in reason, f"pack message must name the pack, got: {reason!r}"
        assert "No speech model is selected" not in reason
        assert messages and "Offline pack" in messages[0]


def _fake_faster_whisper(calls: list):
    mod = types.ModuleType("faster_whisper")

    class _FakeModel:
        def __init__(self, path, **kwargs):
            calls.append((path, kwargs))

        def transcribe(self, audio, **kwargs):
            class _Seg:
                def __init__(self, text):
                    self.text = text

            return ([_Seg("hello"), _Seg("world")], None)

    mod.WhisperModel = _FakeModel
    return mod


class TestSystemWhisperFallback:
    def test_serves_model_from_system_libraries(self, tmp_path, monkeypatch):
        from voice_typer.server import system_whisper

        weights = tmp_path / "snap"
        weights.mkdir()
        (weights / "model.bin").write_bytes(b"\x00")
        calls: list = []
        monkeypatch.setitem(sys.modules, "faster_whisper", _fake_faster_whisper(calls))
        monkeypatch.setattr(system_whisper, "_resolve_weights_dir", lambda *a, **k: weights)
        cfg = SimpleNamespace(model_size="large-v3", device="cpu", language="en", beam_size=5)
        engine = system_whisper.try_load_system_whisper(cfg)
        assert engine is not None
        assert engine.is_loaded is True
        assert engine.loaded_via == "system/large-v3"
        assert engine.transcribe_with_fallback([0.0, 0.1]) == "hello world"
        assert calls and calls[0][1].get("local_files_only") is True

    def test_missing_libraries_returns_none(self, monkeypatch):
        from voice_typer.server import system_whisper

        monkeypatch.setitem(sys.modules, "faster_whisper", None)
        monkeypatch.setattr(system_whisper, "_resolve_weights_dir", lambda *a, **k: None)
        cfg = SimpleNamespace(model_size="large-v3", device="cpu", language="en", beam_size=5)
        assert system_whisper.try_load_system_whisper(cfg) is None

    def test_missing_weights_returns_none(self, monkeypatch):
        from voice_typer.server import system_whisper

        monkeypatch.setitem(sys.modules, "faster_whisper", _fake_faster_whisper([]))
        monkeypatch.setattr(system_whisper, "_resolve_weights_dir", lambda *a, **k: None)
        cfg = SimpleNamespace(model_size="large-v3", device="cpu", language="en", beam_size=5)
        assert system_whisper.try_load_system_whisper(cfg) is None


class TestRegistrySystemFallback:
    def _registry(self):
        from voice_typer.server.asr_registry import AsrBackendRegistry

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
        return AsrBackendRegistry(cfg)

    def test_pack_missing_falls_back_to_system(self, tmp_path, monkeypatch):
        from voice_typer.server import system_whisper
        from voice_typer.server.service import update_check
        from voice_typer.server.worker_backed_asr import WorkerBackedAsr

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda: None)
        weights = tmp_path / "snap"
        weights.mkdir()
        (weights / "model.bin").write_bytes(b"\x00")
        monkeypatch.setitem(sys.modules, "faster_whisper", _fake_faster_whisper([]))
        monkeypatch.setattr(system_whisper, "_resolve_weights_dir", lambda *a, **k: weights)

        registry = self._registry()
        registry.register("whisper", WorkerBackedAsr(model_size="large-v3", config=registry._config))
        backend = registry.load_with_fallback()
        assert backend is not None
        assert backend.loaded_via == "system/large-v3"
        assert registry.get("whisper") is backend

    def test_pack_missing_without_system_libs_reraises(self, monkeypatch):
        from voice_typer.server.asr_errors import OfflinePackMissingError
        from voice_typer.server.service import update_check
        from voice_typer.server.worker_backed_asr import WorkerBackedAsr

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda: None)
        monkeypatch.setitem(sys.modules, "faster_whisper", None)

        registry = self._registry()
        registry.register("whisper", WorkerBackedAsr(model_size="large-v3", config=registry._config))
        with pytest.raises(OfflinePackMissingError):
            registry.load_with_fallback()
