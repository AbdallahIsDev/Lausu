"""Start-gate: a pinned language the active model cannot decode is refused.

The gate runs on the canonical start path (``RecordingLifecycle._start_impl``)
before the microphone opens, and it must surface the mismatch in three
places: the in-app toast push, the OS notification area (clickable to the
Models page — the recovery action), and the tray tooltip. It must never
fire for the paths that are not the local model's business: a selected
internal plugin, the cloud backend, Auto, or an unknown model id.
"""

from __future__ import annotations

import pytest
from voice_typer.server import event_bus, model_language_gate as gate
from voice_typer.server.model_language_gate import (
    UnsupportedLanguage,
    gate_dictation_language,
    language_display_name,
    unsupported_language,
)


class _Config:
    def __init__(self, *, asr_backend: str, model_size: str, language: str) -> None:
        self.asr_backend = asr_backend
        self.model_size = model_size
        self.language = language


class _Tray:
    def __init__(self) -> None:
        self.states: list[tuple[object, object]] = []
        self.notified: list[tuple[str, str]] = []

    def set_state(self, state: object, message: object = None) -> None:
        self.states.append((state, message))

    def notify(self, title: str, message: str) -> None:
        self.notified.append((title, message))


class _App:
    def __init__(self, config: _Config) -> None:
        self.config = config
        self.tray = _Tray()
        self.timers: list[float] = []

    def _schedule_timer(self, seconds: float, fn: object) -> None:
        self.timers.append(seconds)


@pytest.fixture()
def published(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Capture every ``event_bus.publish`` and pretend a transport is live."""
    events: list[dict] = []

    def _publish(event: dict) -> bool:
        events.append(event)
        return True

    monkeypatch.setattr(event_bus, "publish", _publish)
    monkeypatch.setattr(event_bus, "has_live_transport", lambda: True)
    # A fresh dedup window per test: the module keeps process-wide state.
    from voice_typer.server.permissions import refusal_notify

    monkeypatch.setattr(refusal_notify, "_last_notified", None)
    return events


class TestUnsupportedLanguageResolution:
    """Which configs the gate considers a mismatch."""

    def test_parakeet_with_arabic_is_a_mismatch(self):
        finding = unsupported_language(_Config(asr_backend="parakeet", model_size="parakeet", language="ar"))
        assert finding == UnsupportedLanguage(model_name="Parakeet Ultra", language="ar")

    def test_parakeet_with_english_is_fine(self):
        assert unsupported_language(_Config(asr_backend="parakeet", model_size="parakeet", language="en")) is None

    def test_parakeet_with_auto_is_fine(self):
        assert unsupported_language(_Config(asr_backend="parakeet", model_size="parakeet", language="")) is None

    def test_whisper_accepts_arabic(self):
        assert unsupported_language(_Config(asr_backend="whisper", model_size="large-v3", language="ar")) is None

    def test_qwen_accepts_arabic(self):
        assert unsupported_language(_Config(asr_backend="qwen", model_size="qwen3-0.6b", language="ar")) is None

    def test_cloud_backend_owns_its_own_language_support(self):
        assert unsupported_language(_Config(asr_backend="cloud", model_size="parakeet", language="ar")) is None

    def test_no_model_selected_is_not_gated(self):
        assert unsupported_language(_Config(asr_backend="whisper", model_size="", language="ar")) is None

    def test_unknown_model_id_is_not_gated(self):
        assert unsupported_language(_Config(asr_backend="whisper", model_size="made-up", language="ar")) is None

    def test_legacy_model_alias_resolves(self):
        """``qwen`` (pre-rename config value) still resolves to a real entry."""
        assert unsupported_language(_Config(asr_backend="qwen", model_size="qwen", language="ar")) is None


class TestGateRefusal:
    """The refusal path: allowed to start? and what the user sees."""

    def test_mismatch_refuses_and_publishes_the_toast_event(self, published: list[dict]):
        app = _App(_Config(asr_backend="parakeet", model_size="parakeet", language="ar"))
        assert gate_dictation_language(app) is False, "a model that cannot decode the pinned language must not start"
        toast = [e for e in published if e.get("type") == "model_language_unsupported"]
        assert toast == [
            {"type": "model_language_unsupported", "data": {"model": "Parakeet Ultra", "language": "ar"}}
        ], f"expected exactly one toast event with the raw code, got {published!r}"

    def test_mismatch_publishes_a_clickable_os_notification(self, published: list[dict]):
        app = _App(_Config(asr_backend="parakeet", model_size="parakeet", language="ar"))
        gate_dictation_language(app)
        notes = [e for e in published if e.get("type") == "notification"]
        assert len(notes) == 1, f"expected one OS notification, got {published!r}"
        data = notes[0]["data"]
        assert data["message"].endswith("does not support Arabic."), data["message"]
        assert "Parakeet Ultra" in data["message"], data["message"]
        assert data["click_path"] == gate.MODELS_PATH, "the recovery action must land on the Models page"

    def test_mismatch_sets_the_tray_state_and_reverts_it(self, published: list[dict]):
        app = _App(_Config(asr_backend="parakeet", model_size="parakeet", language="ar"))
        gate_dictation_language(app)
        assert len(app.tray.states) == 1, f"expected one tray state write, got {app.tray.states!r}"
        assert app.timers == [gate._TRAY_ERROR_REVERT_S], "the tray ERROR state must auto-revert"

    def test_mismatch_logs_a_warning(self, published: list[dict], caplog: pytest.LogCaptureFixture):
        app = _App(_Config(asr_backend="parakeet", model_size="parakeet", language="ar"))
        with caplog.at_level("WARNING"):
            gate_dictation_language(app)
        assert "does not support language=ar" in caplog.text, caplog.text

    def test_repeat_press_does_not_stack_os_notifications(self, published: list[dict]):
        app = _App(_Config(asr_backend="parakeet", model_size="parakeet", language="ar"))
        gate_dictation_language(app)
        gate_dictation_language(app)
        notes = [e for e in published if e.get("type") == "notification"]
        assert len(notes) == 1, f"the same refusal inside the dedup window must stay silent, got {notes!r}"


class TestGateAllows:
    """Every non-mismatch path starts normally and stays silent."""

    @pytest.mark.parametrize(
        "config",
        [
            _Config(asr_backend="whisper", model_size="large-v3", language="ar"),
            _Config(asr_backend="parakeet", model_size="parakeet", language="en"),
            _Config(asr_backend="parakeet", model_size="parakeet", language=""),
            _Config(asr_backend="cloud", model_size="parakeet", language="ar"),
        ],
    )
    def test_supported_paths_start_silently(self, published: list[dict], config: _Config):
        app = _App(config)
        assert gate_dictation_language(app) is True
        assert published == [], f"no event may be published for a supported start, got {published!r}"
        assert app.tray.states == []

    def test_selected_internal_plugin_bypasses_the_local_gate(
        self, published: list[dict], monkeypatch: pytest.MonkeyPatch
    ):
        """The plugin owns its own language support, not the local model list."""
        monkeypatch.setattr(
            "voice_typer.server.internal_plugin_hook.plugin_display_name",
            lambda app=None: "Anthropic STT",
        )
        app = _App(_Config(asr_backend="parakeet", model_size="parakeet", language="ar"))
        assert gate_dictation_language(app) is True
        assert published == [], "a plugin that serves dictation must not be gated on local model languages"

    def test_gate_never_raises_without_live_transport(self, monkeypatch: pytest.MonkeyPatch):
        """No WS transport: the tray balloon is the fallback, never an exception."""
        monkeypatch.setattr(event_bus, "publish", lambda event: False)
        monkeypatch.setattr(event_bus, "has_live_transport", lambda: False)
        from voice_typer.server.permissions import refusal_notify

        monkeypatch.setattr(refusal_notify, "_last_notified", None)
        app = _App(_Config(asr_backend="parakeet", model_size="parakeet", language="ar"))
        assert gate_dictation_language(app) is False
        assert len(app.tray.notified) == 1, f"expected a tray balloon fallback, got {app.tray.notified!r}"


class TestLanguageDisplayName:
    """Naming the language in the OS notification."""

    def test_known_code_uses_the_localized_name(self):
        assert language_display_name("ar") == "Arabic"

    def test_unknown_code_falls_back_to_the_upper_cased_code(self):
        assert language_display_name("xx") == "XX"

    def test_refusal_message_matches_the_agreed_wording(self, published: list[dict]):
        refuse_finding = UnsupportedLanguage(model_name="Parakeet Ultra", language="ar")
        gate.refuse(_App(_Config(asr_backend="parakeet", model_size="parakeet", language="ar")), refuse_finding)
        note = next(e for e in published if e.get("type") == "notification")
        assert note["data"]["message"] == "Parakeet Ultra does not support Arabic.", (
            "owner-approved wording: <model> does not support <language>."
        )
