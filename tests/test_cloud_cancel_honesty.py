"""ESC during a cloud cycle: honest best-effort cancel feedback (§5/§6).

The cloud abort token is checked only BETWEEN attempts, so an in-flight
provider request may still complete; the pipeline drops the late result.
The ESC path must never claim the remote stopped: it surfaces "cancel
requested / provider may still finish / result will be discarded" (tray
status + bubble label + notification) instead of the local timeout
wording. Local engines keep the existing recovery surface unchanged.

Mic/model/network are mocked; the engine is a name-matched test double.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import patch

from voice_typer.server import i18n
from voice_typer.server.cloud_backend import active_engine_is_cloud, is_cloud_backend
from voice_typer.server.cycle_guard import is_cycle_live
from voice_typer.server.tray_types import AppState

from tests.test_recording_controller_lifecycle_fixes import _make_controller

TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent / "voice_typer/client/src/renderer/src/i18n/translations"
ALL_LOCALES = ["en", "ar", "de", "es", "fr", "hi", "ru", "zh"]


class CloudEngine:  # name-matched double, mirrors the real class-name check
    """Test double sharing the class NAME with the real CloudEngine."""

    is_loaded = True


class _BlockingPipeline:
    """Keeps the transcription worker alive so ESC hits the cancel window."""

    def __init__(self, entered: threading.Event, release: threading.Event) -> None:
        self._entered = entered
        self._release = release

    def __call__(self, app):
        return self

    def run(self, **kwargs) -> None:
        self._entered.set()
        self._release.wait(timeout=10)


def _arrange_post_stop_window(ctrl, app, cycle_id: str = "#7") -> None:
    app._cycle_id = cycle_id
    app.recording = ctrl
    app.recorder.recording = True

    def _stop():
        app.recorder.recording = False
        return b"\x00" * 16000

    app.recorder.stop.side_effect = _stop
    app._busyness.set_busy.side_effect = app._busy_event.clear
    app._busyness.set_idle.side_effect = app._busy_event.set


def _esc_during_transcription(ctrl, app, engine) -> None:
    app.models.active_transcriber.return_value = engine
    entered, release = threading.Event(), threading.Event()
    with patch("voice_typer.server.dictation_pipeline.DictationPipeline", _BlockingPipeline(entered, release)):
        ctrl.stop()
        assert entered.wait(timeout=5), "pipeline never reached run()"
        try:
            ctrl.cancel()  # the real ESC route
            assert is_cycle_live(app, "#7") is False, "the cancelled cycle must stop being live"
        finally:
            release.set()
            if ctrl._transcription_thread is not None:
                ctrl._transcription_thread.join(timeout=5)


class TestCloudCancelSurface:
    def test_esc_during_cloud_cycle_shows_honest_text_and_never_claims_remote_stopped(self):
        ctrl, app = _make_controller()
        _arrange_post_stop_window(ctrl, app)

        _esc_during_transcription(ctrl, app, CloudEngine())

        tray_calls = [(c.args[0], c.args[1] if len(c.args) > 1 else "") for c in app.tray.set_state.call_args_list]
        assert (AppState.CANCELLING, i18n.t("state.recording_controller.cloud_cancel_requested")) in tray_calls, (
            f"the cloud ESC path must surface the honest cancel text; got {tray_calls}"
        )
        notify_bodies = [c.args[1] for c in app.tray.notify.call_args_list]
        assert i18n.t("notify.recording_controller.cloud_cancel_requested") in notify_bodies
        assert all("took too long" not in body for body in notify_bodies), (
            "the cloud ESC path must not claim a local timeout recovery"
        )
        assert not any(state == AppState.IDLE and "Recovered" in str(text) for state, text in tray_calls), (
            "the cloud ESC path must not show the local 'Recovered' surface"
        )
        app._waveform_bubble.set_state.assert_any_call("cloud_cancel_requested")

    def test_esc_during_local_cycle_keeps_the_existing_recovery_surface(self):
        ctrl, app = _make_controller()
        _arrange_post_stop_window(ctrl, app)

        _esc_during_transcription(ctrl, app, engine=object())

        tray_calls = [(c.args[0], c.args[1] if len(c.args) > 1 else "") for c in app.tray.set_state.call_args_list]
        assert (AppState.IDLE, i18n.t("state.recording_controller.recovered")) in tray_calls
        notify_bodies = [c.args[1] for c in app.tray.notify.call_args_list]
        assert any("took too long" in body for body in notify_bodies)
        assert all(call.args[0] != "cloud_cancel_requested" for call in app._waveform_bubble.set_state.call_args_list)


class TestCloudDetection:
    def test_name_matched_double_is_cloud(self):
        assert is_cloud_backend(CloudEngine()) is True

    def test_real_cloud_engine_is_cloud(self):
        from voice_typer.server.cloud_engines import CloudEngine as RealCloudEngine

        assert is_cloud_backend(RealCloudEngine(provider="openai", api_key="sk-test")) is True

    def test_local_and_missing_engines_are_not_cloud(self):
        assert is_cloud_backend(None) is False
        assert is_cloud_backend(object()) is False

    def test_active_engine_probe_is_exception_shielded(self):
        class _RaisingModels:
            def active_transcriber(self):
                raise RuntimeError("boom")

        class _App:
            models = _RaisingModels()

        assert active_engine_is_cloud(_App()) is False

    def test_active_engine_reads_the_active_transcriber(self):
        import types

        app = types.SimpleNamespace(models=types.SimpleNamespace(active_transcriber=lambda: CloudEngine()))
        assert active_engine_is_cloud(app) is True


class TestCloudCancelLocaleKeys:
    """Every new key ships in all 8 locales (C-I18N-1), genuinely translated."""

    def test_locale_keys_exist_everywhere(self):
        en = json.loads((TRANSLATIONS_DIR / "en.json").read_text(encoding="utf-8"))
        en_bubble = en["bubble"]["cloudCancelRequestedLabel"]
        en_tray = en["trayState"]["recordingController"]["cloudCancelRequested"]
        en_notify = en["notify"]["recording_controller"]["cloud_cancel_requested"]
        for locale in ALL_LOCALES:
            data = json.loads((TRANSLATIONS_DIR / f"{locale}.json").read_text(encoding="utf-8"))
            bubble = data["bubble"]["cloudCancelRequestedLabel"]
            tray = data["trayState"]["recordingController"]["cloudCancelRequested"]
            notify = data["notify"]["recording_controller"]["cloud_cancel_requested"]
            assert bubble and tray and notify, f"{locale}.json is missing a cloud-cancel key"
            if locale != "en":
                assert (bubble, tray, notify) != (en_bubble, en_tray, en_notify), (
                    f"{locale}.json must not paste the English fallback"
                )

    def test_server_registry_keys_match_the_renderer_strings(self):
        from voice_typer.server.i18n import _INITIAL_LABELS

        en = json.loads((TRANSLATIONS_DIR / "en.json").read_text(encoding="utf-8"))
        assert (
            _INITIAL_LABELS["state.recording_controller.cloud_cancel_requested"]
            == en["trayState"]["recordingController"]["cloudCancelRequested"]
        )
        assert (
            _INITIAL_LABELS["notify.recording_controller.cloud_cancel_requested"]
            == en["notify"]["recording_controller"]["cloud_cancel_requested"]
        )
