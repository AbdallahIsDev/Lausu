"""One dictation provider decision across startup, record start and notices.

The state-machine tests enter through the same production seams (the gate's
``decide_toggle``, the model-manager load methods, the tray reconciler and the
shared start entry). Fakes stop at the OS/process boundary; no real model,
browser profile or network provider is touched.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from voice_typer.server import dictation_gate, dictation_origin, hotkey_dispatch, internal_plugin_hook
from voice_typer.server.asr_errors import OfflinePackMissingError
from voice_typer.server.dictation_provider import for_app, for_config
from voice_typer.server.model_lifecycle import builtins as lifecycle_builtins, loading, registry
from voice_typer.server.model_manager._loading import LoadingMixin
from voice_typer.server.model_manager._notify import LastResortNotifyMixin, clear_load_refusal_notice
from voice_typer.server.recording_lifecycle_start import RecordingLifecycleStartMixin
from voice_typer.server.tray_types import AppState


@pytest.fixture(autouse=True)
def _worker_start_at_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider tests own no worker process; worker lifecycle has its own tests."""
    from voice_typer.server.model_lifecycle import worker_lifecycle

    monkeypatch.setattr(worker_lifecycle, "request_start", lambda *_a, **_k: True)


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch: pytest.MonkeyPatch) -> Any:
    saved = {kind: registry.get(kind) for kind in registry.kinds()}
    saved_app = registry.current_app()
    registry._reset_for_tests()
    loading._reset_for_tests()
    clear_load_refusal_notice()
    yield
    loading._reset_for_tests()
    registry._reset_for_tests()
    for kind, policy in saved.items():
        if policy is not None:
            registry.register(kind, policy)
    registry.bind_app(saved_app)
    clear_load_refusal_notice()


def _config(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "active_plugin": "",
        "asr_backend": "whisper",
        "asr_provider": "",
        "cloud_provider": "",
        "model_size": "parakeet-ultra",
        "developer_mode": False,
        "model_idle_unload_minutes": 0,
        "hotkey": "<caps_lock>",
        "recording_mode": "toggle",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _app(**config: Any) -> SimpleNamespace:
    return SimpleNamespace(config=_config(**config), tray=MagicMock(), _shutting_down=False)


def _plugin_owner(monkeypatch: pytest.MonkeyPatch, name: str = "ChatGPT STT") -> None:
    monkeypatch.setattr(internal_plugin_hook, "plugin_display_name", lambda app=None: name)


class TestSingleProviderDecision:
    def test_local_model_is_the_only_local_asr_provider(self) -> None:
        assert for_config(_config()).kind == "local"
        assert for_config(_config(model_size="")).kind == "none"

    def test_cloud_engine_and_remote_provider_do_not_need_local_weights(self) -> None:
        cloud = for_config(_config(asr_backend="cloud", cloud_provider="openai", model_size=""))
        assert (cloud.kind, cloud.name) == ("cloud", "openai")
        remote = for_config(_config(asr_provider="openrouter", model_size=""))
        assert (remote.kind, remote.name) == ("remote", "openrouter")
        # cloud_direct keeps the legacy engine path, whatever backend it uses.
        assert for_config(_config(asr_provider="cloud_direct")).kind == "local"

    @pytest.mark.parametrize("plugin_id", ["chatgpt_stt", "anthropic_stt", "google_stt"])
    def test_each_plugin_owns_dictation_when_the_surface_is_visible(
        self, monkeypatch: pytest.MonkeyPatch, plugin_id: str
    ) -> None:
        monkeypatch.setattr(internal_plugin_hook, "internal_surface_enabled", lambda cfg: True)
        monkeypatch.setattr(
            internal_plugin_hook,
            "plugin_display_name_for",
            lambda cfg: "ChatGPT STT" if plugin_id == "chatgpt_stt" else plugin_id,
        )
        provider = for_config(_config(active_plugin=plugin_id, developer_mode=True))
        assert provider.kind == "plugin"
        assert provider.id == plugin_id

    def test_hidden_plugin_surface_does_not_take_over_the_hotkey(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(internal_plugin_hook, "internal_surface_enabled", lambda cfg: False)
        assert for_config(_config(active_plugin="chatgpt_stt")).kind == "local"

    def test_app_probe_is_authoritative(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _plugin_owner(monkeypatch)
        assert for_app(_app()).kind == "plugin"

    def test_tray_label_names_the_remote_provider_not_an_unused_model(self) -> None:
        from voice_typer.server.tray_models import tooltip_model_label

        assert tooltip_model_label(_config(asr_provider="openrouter")) == "openrouter"


class TestLifecycleApplicability:
    @pytest.mark.parametrize(
        ("config", "expected"),
        [
            ({}, True),
            ({"asr_backend": "cloud", "model_size": ""}, False),
            ({"asr_provider": "openrouter"}, False),
        ],
    )
    def test_asr_kind_is_applicable_only_for_the_local_provider(
        self, monkeypatch: pytest.MonkeyPatch, config: dict[str, Any], expected: bool
    ) -> None:
        app = _app(**config)
        monkeypatch.setattr(lifecycle_builtins, "current_app", lambda: app)
        policy = lifecycle_builtins._AsrPolicy(name="asr", residency="core")
        assert policy.applicable(app.config) is expected

    def test_record_start_does_not_create_a_local_backend_for_a_plugin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _plugin_owner(monkeypatch)
        app = _app()
        calls: list[str] = []
        app.models = MagicMock()
        app.models.ensure_active_engine_loaded.side_effect = lambda: calls.append("load")
        app.models.active_transcriber.return_value = None
        policy = lifecycle_builtins._AsrPolicy(name="asr", residency="core")
        monkeypatch.setattr(lifecycle_builtins, "current_app", lambda: app)
        registry.register("asr", policy)

        with dictation_origin.user_action("hotkey"):
            assert dictation_gate.decide_toggle(app) == "start"
        loading.join_loaders(timeout_s=3.0)

        assert calls == []
        app.models.ensure_active_engine_loaded.assert_not_called()

    def test_record_start_still_loads_the_local_backend_on_a_press(self, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _app()
        ready = threading.Event()
        engine = SimpleNamespace(is_loaded=False)

        def _load() -> None:
            engine.is_loaded = True
            ready.set()

        app.models = MagicMock()
        app.models.ensure_active_engine_loaded.side_effect = _load
        app.models.active_transcriber.return_value = engine
        policy = lifecycle_builtins._AsrPolicy(name="asr", residency="core")
        monkeypatch.setattr(lifecycle_builtins, "current_app", lambda: app)
        registry.register("asr", policy)

        with dictation_origin.user_action("hotkey"):
            assert dictation_gate.decide_toggle(app) == "start"
        loading.join_loaders(timeout_s=3.0)

        assert ready.wait(0.5), "the local backend was never loaded"
        app.models.ensure_active_engine_loaded.assert_called_once()

    def test_on_demand_local_load_is_still_available_for_media(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _plugin_owner(monkeypatch)
        app = _app()
        app.models = MagicMock()
        app.models.active_transcriber.return_value = SimpleNamespace(is_loaded=True)
        policy = lifecycle_builtins._AsrPolicy(name="asr", residency="core")
        monkeypatch.setattr(lifecycle_builtins, "current_app", lambda: app)
        assert policy.applicable(app.config) is False
        assert policy.load(app.config) is True
        app.models.ensure_active_engine_loaded.assert_called_once()

    def test_provider_switch_is_read_fresh_on_the_next_press(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _plugin_owner(monkeypatch)
        app = _app()
        now = [100.0]
        app._dictation_gate = dictation_gate.DictationGate(clock=SimpleNamespace(monotonic=lambda: now[0]))
        calls: list[str] = []
        engine = SimpleNamespace(is_loaded=False)
        app.models = MagicMock()
        app.models.ensure_active_engine_loaded.side_effect = lambda: (
            calls.append("load"),
            setattr(engine, "is_loaded", True),
        )
        app.models.active_transcriber.return_value = engine
        policy = lifecycle_builtins._AsrPolicy(name="asr", residency="core")
        monkeypatch.setattr(lifecycle_builtins, "current_app", lambda: app)
        registry.register("asr", policy)

        with dictation_origin.user_action("hotkey"):
            assert dictation_gate.decide_toggle(app) == "start"
        loading.join_loaders(timeout_s=3.0)
        assert calls == []

        now[0] += 1.0
        monkeypatch.setattr(internal_plugin_hook, "plugin_display_name", lambda app=None: "")
        with dictation_origin.user_action("hotkey"):
            assert dictation_gate.decide_toggle(app) == "start"
        loading.join_loaders(timeout_s=3.0)
        assert calls == ["load"]

    def test_translation_keeps_its_own_applicability_rule(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from voice_typer.server.translation import lifecycle as translation_lifecycle

        monkeypatch.setattr(translation_lifecycle._service, "_model_is_installed", lambda cfg: True)
        app = _app(translation_enabled=True)
        assert translation_lifecycle.is_applicable(app.config) is True
        _plugin_owner(monkeypatch)
        assert translation_lifecycle.is_applicable(app.config) is True
        app.config.asr_backend = "cloud"
        assert translation_lifecycle.is_applicable(app.config) is True


class TestWarmAndNoticePaths:
    def test_model_manager_skips_warm_paths_for_plugin_and_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _plugin_owner(monkeypatch)

        background_mock = MagicMock()

        class _Stub(LoadingMixin):
            _model_load_thread: threading.Thread | None = None

            def __init__(self, app: Any) -> None:
                self._app = app
                self._model_load_spawn_lock = threading.Lock()
                self._thread_registry = MagicMock()

            def load_background(self) -> None:
                background_mock()

        stub = _Stub(_app())
        LoadingMixin.start_background_load(stub)
        assert stub._model_load_thread is None
        background_mock.assert_not_called()

        class _LoadStub(LoadingMixin):
            _shutting_down = False

            def __init__(self, app: Any) -> None:
                self._app = app

        app = _app()
        loader = _LoadStub(app)
        LoadingMixin.load_background(loader)
        app.tray.set_state.assert_not_called()

    def test_no_active_engine_does_not_refuse_plugin_cloud_or_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        published: list[dict[str, Any]] = []
        monkeypatch.setattr("voice_typer.server.event_bus.publish", lambda payload: published.append(payload) or True)
        assert hotkey_dispatch.no_active_engine(_app(model_size="", asr_backend="cloud")) is False
        assert hotkey_dispatch.no_active_engine(_app(model_size="", asr_provider="openrouter")) is False
        _plugin_owner(monkeypatch)
        app = _app(model_size="", asr_backend="parakeet")
        dispatcher = hotkey_dispatch.HotkeyDispatchMixin()
        dispatcher._app = app
        assert dispatcher._no_active_engine() is False
        assert published == []
        app.tray.notify.assert_not_called()

    def test_no_active_engine_still_refuses_the_no_model_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(internal_plugin_hook, "plugin_display_name", lambda app=None: "")
        assert hotkey_dispatch.no_active_engine(_app(model_size="")) is True

    def test_cloud_tray_status_is_ready_not_no_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        app = _app(asr_backend="cloud", cloud_provider="openai", model_size="")
        assert internal_plugin_hook.reconcile_status(app) is True
        state, message = app.tray.set_state.call_args.args
        assert state is AppState.IDLE
        assert message == "Ready"

    def test_load_refusal_notice_is_once_per_episode(self) -> None:
        class _NotifyStub(LastResortNotifyMixin):
            def __init__(self, app: Any) -> None:
                self._app = app

        app = _app(asr_backend="parakeet")
        stub = _NotifyStub(app)
        exc = OfflinePackMissingError("The offline pack is not installed.")
        reason = LastResortNotifyMixin._notify_model_load_refused(stub, exc, "parakeet")
        assert "Offline pack" in reason
        app.tray.notify.assert_called_once()

        LastResortNotifyMixin._notify_model_load_refused(stub, exc, "parakeet")
        app.tray.notify.assert_called_once()

        clear_load_refusal_notice()
        LastResortNotifyMixin._notify_model_load_refused(stub, exc, "parakeet")
        assert app.tray.notify.call_count == 2

    def test_plugin_provider_suppresses_local_load_refusal_notice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _plugin_owner(monkeypatch)

        class _NotifyStub(LastResortNotifyMixin):
            def __init__(self, app: Any) -> None:
                self._app = app

        app = _app()
        stub = _NotifyStub(app)
        LastResortNotifyMixin._notify_model_load_refused(
            stub, OfflinePackMissingError("The offline pack is not installed."), "parakeet"
        )
        app.tray.notify.assert_not_called()
        app.tray.set_state.assert_not_called()


class TestLocalFallbackRefusal:
    def test_selected_plugin_never_falls_through_to_the_local_recorder(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _plugin_owner(monkeypatch)
        app = _app()
        app.models = MagicMock()
        app.models.active_transcriber.return_value = None
        app._busy_event = SimpleNamespace(is_set=lambda: True)
        app.recorder = MagicMock()
        app.recorder.recording = False
        app._cycle_counter = 0
        app._cycle_id = ""
        controller = SimpleNamespace(_app=app)

        RecordingLifecycleStartMixin()._toggle_impl(controller)

        app.recorder.start.assert_not_called()
        assert app._cycle_counter == 0
