"""Effective compute-device reporting for the loaded ASR engine.

``config.device`` is the persisted REQUEST; the loaded engine can run
elsewhere (CPU-only onnxruntime build, forced-CPU load, worker fallback).
The sidebar toggle reads ``active_device`` so it never claims a GPU that is
not serving (C-UI-15); these tests pin the translation and the push.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from voice_typer.server import active_device


class TestNormalizeDevice:
    @pytest.mark.parametrize(
        ("info", "expected"),
        [
            ("GPU", "cuda"),
            ("cuda", "cuda"),
            (" CUDA ", "cuda"),
            ("CPU", "cpu"),
            ("cpu", "cpu"),
            ("pack worker", None),
            ("cloud/openai", None),
            ("", None),
            (None, None),
        ],
    )
    def test_normalizes_engine_words(self, info, expected) -> None:
        assert active_device.normalize_device(info) is expected


class TestResolveActiveDevice:
    def test_reads_the_active_engine_device(self) -> None:
        app = SimpleNamespace(
            models=SimpleNamespace(active_transcriber=lambda: SimpleNamespace(device_info="CPU")),
        )
        assert active_device.resolve_active_device(app) == "cpu"

    def test_no_loaded_engine_is_unknown(self) -> None:
        app = SimpleNamespace(models=SimpleNamespace(active_transcriber=lambda: None))
        assert active_device.resolve_active_device(app) is None

    def test_app_without_models_is_unknown(self) -> None:
        assert active_device.resolve_active_device(SimpleNamespace()) is None

    def test_device_info_failure_is_unknown(self) -> None:
        class _Engine:
            @property
            def device_info(self) -> str:
                raise RuntimeError("boom")

        app = SimpleNamespace(
            models=SimpleNamespace(active_transcriber=lambda: _Engine()),
        )
        assert active_device.resolve_active_device(app) is None

    def test_active_transcriber_failure_is_unknown(self) -> None:
        def _boom():
            raise RuntimeError("boom")

        app = SimpleNamespace(models=SimpleNamespace(active_transcriber=_boom))
        assert active_device.resolve_active_device(app) is None


class TestPublishActiveDevice:
    def test_publishes_on_the_config_channel(self, monkeypatch) -> None:
        published: list[dict] = []
        monkeypatch.setattr("voice_typer.server.event_bus.publish", published.append)

        active_device.publish_active_device("cpu")

        assert published == [{"type": "config_changed", "data": {"active_device": "cpu"}}]

    def test_unknown_device_publishes_nothing(self, monkeypatch) -> None:
        published: list[dict] = []
        monkeypatch.setattr("voice_typer.server.event_bus.publish", published.append)

        active_device.publish_active_device(None)

        assert published == []

    def test_publish_failure_is_swallowed(self, monkeypatch) -> None:
        def _boom(event) -> None:
            raise RuntimeError("bus down")

        monkeypatch.setattr("voice_typer.server.event_bus.publish", _boom)

        active_device.publish_active_device("cuda")  # must not raise


class TestGetConfigReportsEffectiveDevice:
    def _service(self, device_info: str | None):
        from voice_typer.server.config import Config
        from voice_typer.server.service.config_service import ConfigMutationMixin

        class _Service(ConfigMutationMixin):
            def __init__(self, app) -> None:
                self._app = app

            def _keyring_status(self) -> dict:
                return {}

        engine = None if device_info is None else SimpleNamespace(device_info=device_info)
        app = SimpleNamespace(
            # The request says GPU: the snapshot's device stays that, while
            # active_device reports what the engine actually got.
            config=Config(device="cuda"),
            models=SimpleNamespace(active_transcriber=lambda: engine),
        )
        return _Service(app)

    def test_active_device_rides_the_config_snapshot(self, monkeypatch) -> None:
        monkeypatch.setattr("voice_typer.server.device_caps.gpu_available", lambda **_: True)

        data = self._service("CPU").get_config()

        assert data["device"] == "cuda"
        assert data["active_device"] == "cpu"

    def test_unknown_engine_reports_null(self, monkeypatch) -> None:
        monkeypatch.setattr("voice_typer.server.device_caps.gpu_available", lambda **_: True)

        data = self._service(None).get_config()

        assert data["active_device"] is None
