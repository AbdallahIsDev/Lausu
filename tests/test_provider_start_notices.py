"""Real-entry proof for provider refusals, notice cadence and start origins.

Entry points are the production ones (app.toggle_dictation, the IPC handler,
the tray dispatcher, the hotkey callback, the plugin session, the startup
phase). Fakes stop at the OS boundary: no mic, browser, network or model load.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from voice_typer.server import (
    dictation_gate,
    dictation_notices,
    dictation_origin,
    hotkey_dispatch,
    internal_plugin_hook,
    plugin_dev_driver,
)
from voice_typer.server.app_dictation import AppDictation
from voice_typer.server.asr_errors import OfflinePackMissingError
from voice_typer.server.dictation_provider import for_config
from voice_typer.server.handlers.dictation_handlers import DictationHandlersMixin
from voice_typer.server.i18n import t
from voice_typer.server.model_manager._notify import LastResortNotifyMixin, clear_load_refusal_notice
from voice_typer.server.recording_lifecycle import RecordingLifecycle
from voice_typer.server.startup_sequence._phases_late import LatePhases
from voice_typer.server.tray_menu import dispatch_tray_action


@pytest.fixture(autouse=True)
def notice_capture(monkeypatch: pytest.MonkeyPatch) -> Any:
    published: list[dict[str, Any]] = []
    monkeypatch.setattr("voice_typer.server.event_bus.publish", lambda p: published.append(p) or True)
    clear_load_refusal_notice()
    yield published
    clear_load_refusal_notice()


def _config(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "active_plugin": "",
        "asr_backend": "parakeet",
        "asr_provider": "",
        "cloud_provider": "",
        "cloud_model": "gpt-4o-transcribe",
        "model_size": "parakeet",
        "developer_mode": False,
        "model_idle_unload_minutes": 0,
        "hotkey": "<caps_lock>",
        "recording_mode": "toggle",
        "tts_enabled": False,
        "translation_enabled": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _start_app(config: Any | None = None) -> tuple[Any, Any]:
    """App + controller wired to the real AppDictation -> gate -> lifecycle."""
    app = SimpleNamespace(
        config=config or _config(),
        tray=MagicMock(),
        _shutting_down=False,
        _cycle_counter=0,
        _cycle_id="",
        models=MagicMock(),
        recorder=MagicMock(),
        _busy_event=SimpleNamespace(is_set=lambda: True),
    )
    app.recorder.recording = False
    app.models.active_transcriber.return_value = None
    app.models._model_load_thread = None
    lifecycle = RecordingLifecycle()
    controller = SimpleNamespace(_app=app, _toggle_lock=threading.RLock())
    app.recording = SimpleNamespace(toggle=lambda: lifecycle.toggle(controller))
    app.toggle_dictation = AppDictation.toggle_dictation.__get__(app, type(app))
    app._start_dictation = MagicMock()  # mic boundary; must stay untouched on refusal
    return app, controller


def _notices(published: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [p for p in published if p.get("type") == "notification"]


class TestPluginRefusalIsNotSilent:
    def test_selected_plugin_without_session_notifies_and_never_starts_local(
        self, monkeypatch: pytest.MonkeyPatch, notice_capture: list[dict[str, Any]]
    ) -> None:
        monkeypatch.setattr(internal_plugin_hook, "plugin_display_name", lambda app=None: "ChatGPT STT")
        app, _controller = _start_app()

        with dictation_origin.user_action("hotkey"):
            app.toggle_dictation()

        notes = _notices(notice_capture)
        assert len(notes) == 1
        message = notes[0]["data"]["message"]
        assert "ChatGPT STT" in message
        assert "Plugins" in message
        assert message == t("notify.dictation_provider.plugin_unavailable", name="ChatGPT STT")
        app.tray.notify.assert_called_once()
        app._start_dictation.assert_not_called()
        app.models.start_background_load.assert_not_called()
        assert app._cycle_counter == 0

    def test_plugin_start_timeout_reports_itself(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tools.internal_plugins._common.bridge import session as bridge

        copy_mod = SimpleNamespace(
            DISPLAY_NAME="Claude STT",
            notify_enabled=lambda: True,
            START_HINTS={"page-not-ready": "The Claude tab is still loading. Wait a moment."},
            START_FAILURE_FALLBACK="Claude STT could not start.",
            BRIDGE_UNAVAILABLE="Claude STT bridge unavailable.",
            duration=lambda _seconds: "",
        )
        entry = SimpleNamespace(ensure_daemon=lambda: True)
        app = SimpleNamespace(tray=MagicMock())
        session = bridge.PluginSession(app, entry=entry, copy_mod=copy_mod)
        monkeypatch.setattr(bridge, "ensure_target_ready", lambda **_kw: (False, "page-not-ready"))

        with dictation_origin.user_action("hotkey"):
            session.start()

        assert session.active is False
        app.tray.notify.assert_called_once()
        assert "still loading" in app.tray.notify.call_args.args[1]

    def test_plugin_daemon_failure_reports_itself(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tools.internal_plugins._common.bridge import session as bridge

        copy_mod = SimpleNamespace(
            DISPLAY_NAME="Claude STT",
            notify_enabled=lambda: True,
            START_HINTS={},
            START_FAILURE_FALLBACK="fallback",
            BRIDGE_UNAVAILABLE="Claude STT bridge unavailable.",
            duration=lambda _seconds: "",
        )
        entry = SimpleNamespace(ensure_daemon=lambda: False)
        app = SimpleNamespace(tray=MagicMock())
        session = bridge.PluginSession(app, entry=entry, copy_mod=copy_mod)

        with dictation_origin.user_action("hotkey"):
            session.start()

        assert session.active is False
        app.tray.notify.assert_called_once_with("Claude STT (internal)", copy_mod.BRIDGE_UNAVAILABLE)


class TestNoticeCadence:
    def _refusal_stub(self, app: Any) -> LastResortNotifyMixin:
        class _Stub(LastResortNotifyMixin):
            def __init__(self, app_: Any) -> None:
                self._app = app_

        return _Stub(app)

    def test_automatic_attempts_dedupe_per_episode(self, notice_capture: list[dict[str, Any]]) -> None:
        app, _ = _start_app()
        stub = self._refusal_stub(app)
        exc = OfflinePackMissingError("The offline pack is not installed.")

        stub._notify_model_load_refused(exc, "parakeet")
        stub._notify_model_load_refused(exc, "parakeet")

        assert len(_notices(notice_capture)) == 1
        app.tray.notify.assert_called_once()

    def test_every_user_press_notifies_at_most_once_per_second(
        self, monkeypatch: pytest.MonkeyPatch, notice_capture: list[dict[str, Any]]
    ) -> None:
        clock = [1000.0]
        monkeypatch.setattr(dictation_notices, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        app, _ = _start_app()
        app._dictation_gate = dictation_gate.DictationGate(clock=SimpleNamespace(monotonic=lambda: clock[0]))
        stub = self._refusal_stub(app)
        exc = OfflinePackMissingError("The offline pack is not installed.")

        for _ in range(3):
            clock[0] += 1.0
            with dictation_origin.user_action("hotkey"):
                assert dictation_gate.decide_toggle(app) == "start"
                stub._notify_model_load_refused(exc, "parakeet")

        assert len(_notices(notice_capture)) == 3
        assert app.tray.notify.call_count == 3

        # A burst inside the same second is rate-limited, not silently dropped
        # for the rest of the episode.
        stub._notify_model_load_refused(exc, "parakeet")
        assert len(_notices(notice_capture)) == 3
        clock[0] += 1.0
        stub._notify_model_load_refused(exc, "parakeet")
        assert len(_notices(notice_capture)) == 4

    def test_missing_pack_press_never_opens_the_mic_with_the_real_probe(
        self, monkeypatch: pytest.MonkeyPatch, notice_capture: list[dict[str, Any]]
    ) -> None:
        from voice_typer.server import local_asr_readiness
        from voice_typer.server.config import Config as RealConfig

        # The production probe must still be installed here: this test drives
        # the real readiness function through the shared start entry.
        assert local_asr_readiness.readiness_probe is local_asr_readiness.local_asr_problem
        config = RealConfig()
        config.asr_backend = "parakeet"
        config.model_size = "parakeet"
        config.voice_biometric_consent = True
        monkeypatch.setattr("voice_typer.server.tray_models.is_active_model_downloaded", lambda _config: True)
        monkeypatch.setattr(
            "voice_typer.server.service.update_check._local_offline_pack_version", lambda root=None: None
        )
        app, _ = _start_app(config)

        with dictation_origin.user_action("button"):
            app.toggle_dictation()

        assert len(_notices(notice_capture)) == 1
        assert "Offline pack" in _notices(notice_capture)[0]["data"]["message"]
        app._start_dictation.assert_not_called()
        app.models.start_background_load.assert_not_called()

    def test_readiness_probe_seam_is_explicit(
        self, monkeypatch: pytest.MonkeyPatch, notice_capture: list[dict[str, Any]]
    ) -> None:
        from voice_typer.server import local_asr_readiness as readiness

        monkeypatch.setattr(readiness, "readiness_probe", lambda _config: "model_not_downloaded")
        app, _ = _start_app()

        with dictation_origin.user_action("button"):
            app.toggle_dictation()

        assert len(_notices(notice_capture)) == 1
        assert "No speech model" in _notices(notice_capture)[0]["data"]["message"]
        app._start_dictation.assert_not_called()

    @pytest.mark.parametrize(
        "config",
        [
            _config(asr_backend="cloud", cloud_provider="openai", model_size=""),
            _config(asr_provider="openrouter", model_size=""),
            _config(active_plugin="chatgpt_stt"),
        ],
    )
    def test_non_local_providers_never_emit_a_local_model_notice(
        self,
        monkeypatch: pytest.MonkeyPatch,
        notice_capture: list[dict[str, Any]],
        config: Any,
    ) -> None:
        monkeypatch.setattr(internal_plugin_hook, "internal_surface_enabled", lambda _cfg: True)
        monkeypatch.setattr(internal_plugin_hook, "plugin_display_name", lambda app=None: "ChatGPT STT")
        app, _ = _start_app(config)
        stub = self._refusal_stub(app)

        stub._notify_model_load_refused(OfflinePackMissingError("offline pack"), "parakeet")

        assert _notices(notice_capture) == []
        app.tray.notify.assert_not_called()
        app.tray.set_state.assert_not_called()


class TestCloudProviderDoesNotTouchLocalWeights:
    def test_startup_phase_skips_the_local_load_for_cloud(self, monkeypatch: pytest.MonkeyPatch) -> None:
        app, _ = _start_app(_config(asr_backend="cloud", cloud_provider="openai", model_size=""))
        phases = LatePhases()
        phases._app = app
        phases._t0 = 0.0
        monkeypatch.setattr(phases, "_prewarm_recorder_subsystem", lambda _app: None)
        monkeypatch.setattr("voice_typer.server.startup_tasks.reconcile_configured_device", lambda _app: None)
        monkeypatch.setattr("voice_typer.server.startup_tasks.reconcile_configured_model", lambda _app: None)
        monkeypatch.setattr("voice_typer.server.cuda_install.apply_pending_activation", lambda: None)

        result = phases._phase_7_hotkey_and_model_load()

        assert result.success is True
        app.models.start_background_load.assert_not_called()
        app.models.load_background.assert_not_called()

    def test_cloud_does_not_reconcile_a_stale_local_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from voice_typer.server.startup_tasks import reconcile_configured_model

        config = _config(asr_backend="cloud", cloud_provider="openai", model_size="parakeet")
        saved: list[bool] = []
        config.save = lambda: saved.append(True) or True
        app = SimpleNamespace(config=config)
        monkeypatch.setattr("voice_typer.server.tray_models.is_active_model_downloaded", lambda _cfg: False)

        assert reconcile_configured_model(app) is False
        assert config.model_size == "parakeet"
        assert saved == []

    def test_tray_names_cloud_not_the_unused_local_model(self) -> None:
        from voice_typer.server.tray_models import tooltip_model_label

        assert tooltip_model_label(_config(asr_backend="cloud", cloud_provider="openai")) == "OpenAI Gpt 4o Transcribe"


class TestStartOrigins:
    def test_button_handler_carries_button_origin(self) -> None:
        seen: list[str] = []
        handler = DictationHandlersMixin()
        handler.service = SimpleNamespace(toggle_dictation=lambda: seen.append(dictation_origin.current()))
        resp: dict[str, Any] = {}

        handler._handle_toggle_dictation(None, resp)

        assert resp["type"] == "ack"
        assert seen == ["button"]

    def test_tray_dispatch_carries_tray_origin(self) -> None:
        seen: list[str] = []
        tray = SimpleNamespace(_tray_id_map={"toggle_dictation": lambda: seen.append(dictation_origin.current())})

        assert dispatch_tray_action(tray, "toggle_dictation") is True
        assert seen == ["tray"]

    def test_hotkey_callback_carries_hotkey_origin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: list[str] = []
        app = _start_app()[0]
        app.toggle_dictation = lambda: seen.append(dictation_origin.current())
        app.config.recording_mode = "toggle"
        monkeypatch.setattr(hotkey_dispatch.keyboard_ownership(), "is_hotkey_capture_active", lambda: False)
        monkeypatch.setattr(hotkey_dispatch, "no_active_engine", lambda _app: False)
        monkeypatch.setattr("voice_typer.server.hotkey_dispatcher.permissions", MagicMock(), raising=False)
        dispatcher = hotkey_dispatch.HotkeyDispatchMixin()
        dispatcher._app = app
        monkeypatch.setattr(dispatcher, "_force_caps_lock_off_before_dictation", lambda: None)

        dispatcher._make_dictation_callback()()

        assert seen == ["hotkey"]

    def test_no_origin_is_refused_at_the_app_entry(self) -> None:
        calls: list[str] = []
        app, _ = _start_app()
        app.recording.toggle = lambda: calls.append("toggled")

        app.toggle_dictation()

        assert calls == []

    def test_no_origin_is_refused_at_the_plugin_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []
        app, _ = _start_app()
        original = app.toggle_dictation
        app.recording.toggle = lambda: calls.append("toggled")
        app._stop_dictation = MagicMock()
        app._cancel_dictation = MagicMock()
        monkeypatch.setattr(internal_plugin_hook, "_developer_mode_on", lambda _cfg: True)
        monkeypatch.setattr(internal_plugin_hook, "internal_surface_enabled", lambda _cfg: True)
        monkeypatch.setattr(internal_plugin_hook, "_selected_session", lambda _app: None)
        monkeypatch.setattr("voice_typer.server.plugins.workspace.ensure_developer_workspace", lambda: None)
        monkeypatch.setattr("voice_typer.server.plugins.shared_settings.sync_all", lambda _cfg: None)
        monkeypatch.setattr("voice_typer.server.plugin_dev_driver.start_watcher", lambda _app: None)
        monkeypatch.setattr(internal_plugin_hook, "sync_selection", lambda _app: None)

        assert internal_plugin_hook.install(app) is True
        app.toggle_dictation()

        assert calls == []
        assert app.toggle_dictation is not original

    def test_stale_dev_driver_command_is_not_claimed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
        import json
        import os

        directory = tmp_path / "commands"
        directory.mkdir()
        stale = directory / "command.json"
        stale.write_text(json.dumps({"cmd": "toggle", "seq": 1}), encoding="utf-8")
        os.utime(stale, (0.0, 0.0))
        monkeypatch.setattr(plugin_dev_driver, "command_dir", lambda _app: directory)

        assert plugin_dev_driver._claim(directory, 100.0, 0) is None
        assert not stale.exists()

        stale.write_text(json.dumps({"cmd": "toggle", "seq": 2}), encoding="utf-8")
        claimed = plugin_dev_driver._claim(directory, 0.0, 0)
        assert claimed is not None


class TestProviderClassification:
    @pytest.mark.parametrize(
        ("model_size", "expected"),
        [
            ("", "none"),
            ("parakeet", "local"),
            ("unknown-model-id", "local"),
            ("qwen", "local"),
            ("qwen3-1.7b", "local"),
        ],
    )
    def test_every_model_size_value_has_one_owner(self, model_size: str, expected: str) -> None:
        assert for_config(_config(model_size=model_size)).kind == expected

    def test_cloud_and_remote_win_over_a_stale_local_model(self) -> None:
        assert for_config(_config(asr_backend="cloud", cloud_provider="openai")).kind == "cloud"
        assert for_config(_config(asr_provider="openrouter")).kind == "remote"
