"""download_model progress-event contract for the GGUF transfer path."""

import time

import pytest
from voice_typer.server.service import LausuService


@pytest.fixture
def service():
    """Build a LausuService with consent already granted."""
    from unittest.mock import MagicMock

    app = MagicMock()
    app.config.qwen_model_path = None
    app.config.huggingface_consent = True
    app.tray.notify = MagicMock()
    return LausuService(app)


@pytest.fixture
def captured_events(monkeypatch):
    """Capture all events pushed via event_bus.publish."""
    events = []
    import voice_typer.server.event_bus as event_bus_mod

    monkeypatch.setattr(event_bus_mod, "publish", lambda msg: events.append(msg) or True)
    return events


@pytest.fixture
def fake_gguf_download(monkeypatch):
    """Replace the network transfer; return the recorded call arguments."""
    from voice_typer.server import gguf_download

    calls: list[dict] = []

    def install(outcome=(True, ""), error=None):
        def fake(model_name, **kwargs):
            calls.append({"model": model_name, **kwargs})
            if error is not None:
                raise error
            return outcome

        monkeypatch.setattr(gguf_download, "download_gguf_model", fake)
        return calls

    install()
    return install, calls


class TestDownloadModelPushesProgressEvents:
    """download_model pushes progress events to the renderer."""

    def test_unknown_model_returns_error_no_progress(self, service, captured_events):
        """An unknown model name returns success=False without progress events."""
        result = service.download_model("nonexistent-model")
        assert result["success"] is False
        assert "Unknown model" in result["error"]
        assert [e for e in captured_events if e.get("type") == "download_progress"] == []

    def test_qwen_already_cached_pushes_progress_100(self, service, captured_events, fake_gguf_download):
        """A verified cache hit reports completion with a terminal 100 event."""
        install, _calls = fake_gguf_download
        install(outcome=(True, ""))

        result = service.download_model("qwen3-1.7b")
        assert result["success"] is True
        progress_events = [e for e in captured_events if e.get("type") == "download_progress"]
        assert any(e["data"]["progress"] == 100 for e in progress_events), progress_events

    def test_qwen_without_override_delegates_to_hf_downloader(self, service, captured_events, fake_gguf_download):
        """Without a manual path the registered GGUF repo is downloaded."""
        _install, calls = fake_gguf_download

        result = service.download_model("qwen3-1.7b")
        assert result["success"] is True
        assert len(calls) == 1
        assert calls[0]["model"] == "qwen3-1.7b"
        assert calls[0]["config"] is service._app.config

    def test_progress_event_shape(self, service, captured_events, fake_gguf_download):
        """Each download_progress event must have the correct shape."""
        service.download_model("qwen3-1.7b")
        progress_events = [e for e in captured_events if e.get("type") == "download_progress"]
        assert progress_events
        for event in progress_events:
            assert "data" in event
            assert "model" in event["data"]
            assert "progress" in event["data"]
            assert "status" in event["data"]
            assert isinstance(event["data"]["progress"], int)
            assert 0 <= event["data"]["progress"] <= 100
            assert event["data"]["model"] == "qwen3-1.7b"


class TestWhisperDownloadWithProgressEvents:
    """Whisper-family GGUF transfers report progress and notify the tray."""

    def test_whisper_already_cached_skips_download(self, service, captured_events, fake_gguf_download):
        """A cache hit pushes 100 and fires the success notification."""
        install, calls = fake_gguf_download
        install(outcome=(True, ""))

        result = service.download_model("tiny")
        assert result["success"] is True
        assert result["model"] == "tiny"
        assert len(calls) == 1
        progress_events = [e for e in captured_events if e.get("type") == "download_progress"]
        assert progress_events
        assert progress_events[-1]["data"]["progress"] == 100
        assert service._app.tray.notify.called
        notify_args = service._app.tray.notify.call_args
        assert "tiny" in notify_args[0][1]

    def test_whisper_download_failure_pushes_error_progress_and_notifies(
        self, service, captured_events, fake_gguf_download
    ):
        """A transfer error pushes progress=0 and fires the failure notification."""
        install, _calls = fake_gguf_download
        install(error=RuntimeError("network error"))

        result = service.download_model("tiny")
        assert result["success"] is False
        assert "network error" in result["error"]
        assert service._app.tray.notify.called
        progress_events = [e for e in captured_events if e.get("type") == "download_progress"]
        assert any(e["data"]["progress"] == 0 for e in progress_events), progress_events


class TestGgufProgressPoll:
    """The poll follows the real HF cache blob path (dev-only tiny included)."""

    def test_growing_gguf_blob_moves_the_progress_bar(self, service, captured_events, monkeypatch, tmp_path):
        import sys
        from types import ModuleType

        from voice_typer.server import gguf_download, model_availability

        cache = tmp_path / "hub"
        blob_dir = cache / "models--handy-computer--whisper-tiny-gguf" / "blobs"
        blob_dir.mkdir(parents=True)
        blob = blob_dir / "gguf-partial"

        def fake_download(model_name, **kwargs):
            with blob.open("wb") as stream:
                for _ in range(12):
                    stream.write(b"\x00" * (1024 * 1024))
                    stream.flush()
                    time.sleep(0.02)
            return (True, "")

        monkeypatch.setattr(gguf_download, "download_gguf_model", fake_download)
        monkeypatch.setattr(model_availability, "shared_hub_dir", lambda: cache)

        # The GGUF downloader imports the hub inside the transfer; a stub keeps
        # this test offline even when a real hub is installed.
        hub = ModuleType("huggingface_hub")
        hub.hf_hub_download = lambda **_kw: ""
        monkeypatch.setitem(sys.modules, "huggingface_hub", hub)

        result = service.download_model("tiny")
        assert result["success"] is True
        progress_events = [
            e["data"] for e in captured_events if e.get("type") == "download_progress"
        ]
        moving = [e for e in progress_events if e["progress"] > 10 and e.get("downloaded_bytes", 0) > 0]
        assert moving, f"poll never observed the growing GGUF blob: {progress_events}"
