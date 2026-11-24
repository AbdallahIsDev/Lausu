"""download_model must gate every GGUF download on HuggingFace consent."""

from unittest.mock import MagicMock

import pytest
from voice_typer.server.service import LausuService


@pytest.fixture
def captured_events(monkeypatch):
    """Capture all events pushed via ``event_bus.publish``."""
    events: list[dict] = []
    import voice_typer.server.event_bus as event_bus_mod

    monkeypatch.setattr(event_bus_mod, "publish", lambda msg: events.append(msg) or True)
    return events


@pytest.fixture
def gguf_calls(monkeypatch):
    """Record GGUF transfer calls, never touching the network."""
    from voice_typer.server import gguf_download

    calls: list[dict] = []

    def fake_download(model_name, **kwargs):
        calls.append({"model": model_name, **kwargs})
        return (True, "")

    monkeypatch.setattr(gguf_download, "download_gguf_model", fake_download)
    return calls


def _build_service(*, consent: bool) -> LausuService:
    """Build a LausuService with a mock app + explicit consent flag."""
    app = MagicMock()
    app.config.huggingface_consent = consent
    app.config.qwen_model_path = None
    app.tray.notify = MagicMock()
    return LausuService(app)


def _progress_events(captured_events):
    return [e for e in captured_events if e.get("type") == "download_progress"]


def _consent_events(captured_events):
    return [e for e in captured_events if e.get("type") == "consent_required"]


class TestGGUFDownloadConsentGate:
    """Every GGUF ASR model is gated before any network call."""

    @pytest.mark.parametrize("model_name", ["tiny", "parakeet", "large-v3"])
    def test_download_blocked_without_consent(
        self, model_name, captured_events, gguf_calls
    ):
        """No consent: refuse with the consent outcome, never start a transfer."""
        service = _build_service(consent=False)
        result = service.download_model(model_name)

        assert result["success"] is False
        assert result["consent_required"] is True
        assert "consent" in result["error"].lower()
        assert result["model"] == model_name
        assert gguf_calls == [], f"no transfer may start without consent; got: {gguf_calls}"
        consent_events = _consent_events(captured_events)
        assert consent_events, f"Expected at least one consent_required event; got: {captured_events}"
        assert consent_events[0]["data"]["provider"] == "huggingface"
        assert consent_events[0]["data"]["model"] == model_name
        assert _progress_events(captured_events) == []

    @pytest.mark.parametrize("model_name", ["tiny", "parakeet", "large-v3"])
    def test_download_proceeds_with_consent(self, model_name, captured_events, gguf_calls):
        """Consent granted: the shared GGUF downloader runs."""
        service = _build_service(consent=True)
        result = service.download_model(model_name)

        assert result["success"] is True
        assert result["model"] == model_name
        assert [call["model"] for call in gguf_calls] == [model_name]
        assert _consent_events(captured_events) == []


class TestConsentGateIsAdditive:
    """The consent gate must not change non-download branches."""

    def test_unknown_model_still_returns_error(self, captured_events, gguf_calls):
        """An unknown model name still returns success=False without network."""
        service = _build_service(consent=False)
        result = service.download_model("nonexistent-model")

        assert result["success"] is False
        assert "Unknown model" in result["error"]
        assert gguf_calls == []
        assert _consent_events(captured_events) == []

    def test_qwen_variants_require_consent(self, captured_events, gguf_calls):
        """Both Qwen variants download GGUF weights from HF."""
        for model_name in ("qwen3-1.7b", "qwen3-0.6b"):
            service = _build_service(consent=False)
            result = service.download_model(model_name)
            assert result["success"] is False
            assert result["consent_required"] is True
            assert result["model"] == model_name
        assert gguf_calls == []
        gated = [e["data"]["model"] for e in _consent_events(captured_events)]
        assert gated == ["qwen3-1.7b", "qwen3-0.6b"]

    def test_qwen_with_consent_uses_registered_gguf_repo(self, captured_events, gguf_calls):
        """Without a manual path, the registered GGUF repo is downloaded."""
        service = _build_service(consent=True)
        result = service.download_model("qwen3-0.6b")

        assert result["success"] is True
        assert result["model"] == "qwen3-0.6b"
        assert [call["model"] for call in gguf_calls] == ["qwen3-0.6b"]
        assert _consent_events(captured_events) == []

    def test_legacy_manual_path_does_not_bypass_consent(self, captured_events, gguf_calls, tmp_path):
        """GGUF weights resolve from the hub cache only: a legacy ONNX dir
        cannot short-circuit the consent gate or the verified downloader."""
        (tmp_path / "config.json").write_text('{"decoder": {"hidden_size": 1024}}', encoding="utf-8")
        service = _build_service(consent=False)
        service._app.config.qwen_model_path = str(tmp_path)
        result = service.download_model("qwen3-0.6b")

        assert result["success"] is False
        assert result["consent_required"] is True
        assert gguf_calls == []
        assert _consent_events(captured_events)[0]["data"]["model"] == "qwen3-0.6b"


class TestConsentGateDefensive:
    """A missing config fails closed."""

    def test_missing_config_blocks_download(self, captured_events, gguf_calls):
        """When config is None the gate treats consent as False."""
        app = MagicMock()
        app.config = None
        app.tray.notify = MagicMock()
        service = LausuService(app)

        result = service.download_model("tiny")
        assert result["success"] is False
        assert result["consent_required"] is True
        assert gguf_calls == []
        assert _consent_events(captured_events)
