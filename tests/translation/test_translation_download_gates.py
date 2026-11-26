"""Owner-locked translator download rules, tested with a fake downloader.

No network, no model and no binary are used: the transfer function, the
progress poller and the HF cache location are replaced at their seams.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from voice_typer.server import event_bus
from voice_typer.server.asr_setup import ModelDownloadAborted, clear_download_pause_state, is_download_active
from voice_typer.server.service.model.mixin import ModelMixin
from voice_typer.server.translation import service as translation_service
from voice_typer.server.translation.catalogue import (
    INDEX_TRANSLATE_Q4,
    TRANSLATION_MODEL_ID,
)

_REPO_DIR = f"models--{INDEX_TRANSLATE_Q4.repo_id.replace('/', '--')}"


class _Tray:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def notify(self, _title: str, message: str) -> None:
        self.messages.append(message)


def _config(*, consent: bool = True, enabled: bool = True) -> Any:
    return SimpleNamespace(
        huggingface_consent=consent,
        translation_enabled=enabled,
        translation_model=TRANSLATION_MODEL_ID,
        translation_model_path="",
        translation_runtime_path="",
        translation_gpu_enabled=True,
        translation_glossary="",
        language="ar",
    )


class _Harness:
    def __init__(self, consent: bool = True) -> None:
        self.tray = _Tray()
        self.service = ModelMixin()
        self.service._app = SimpleNamespace(config=_config(consent=consent), tray=self.tray)


@pytest.fixture(autouse=True)
def _clean_gate() -> Any:
    clear_download_pause_state()
    yield
    clear_download_pause_state()
    translation_service.shutdown()


def _missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(_config: Any) -> Path:
        raise translation_service.TranslationError("not installed")

    monkeypatch.setattr("voice_typer.server.translation.service.resolve_model_path", refuse)


def _events(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    published: list[dict[str, Any]] = []
    monkeypatch.setattr(event_bus, "publish", lambda event: published.append(event))
    return published


def _fake_downloader(monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]], result=(True, "", None)) -> None:
    def fake(spec: Any, **kwargs: Any) -> tuple[bool, str, Any]:
        calls.append({"spec": spec, **kwargs})
        return result

    monkeypatch.setattr("voice_typer.server.translation.download.download_translation_weights", fake)
    monkeypatch.setattr("voice_typer.server.translation.download._hub_cache_dir", lambda: Path("."))
    monkeypatch.setattr("voice_typer.server.model_availability.shared_hub_dir", lambda: Path("."))
    monkeypatch.setattr("voice_typer.server.asr_setup.get_download_tqdm_class", lambda: object)
    monkeypatch.setattr(
        "voice_typer.server.service._download_helpers.poll_download_progress",
        lambda **_kwargs: ("complete", INDEX_TRANSLATE_Q4.size_bytes),
    )


def test_consent_dialog_gate_runs_before_any_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """No consent -> no transfer; the shared consent event is published."""
    harness = _Harness(consent=False)
    events = _events(monkeypatch)
    calls: list[dict[str, Any]] = []
    _fake_downloader(monkeypatch, calls)

    result = harness.service.download_model(TRANSLATION_MODEL_ID)

    assert result["consent_required"] is True
    assert calls == []
    assert any(event["type"] == "consent_required" for event in events)


def test_verified_download_emits_shared_progress_and_clears_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """One button press -> verified transfer with 0/50/100 progress events."""
    harness = _Harness()
    events = _events(monkeypatch)
    calls: list[dict[str, Any]] = []
    _fake_downloader(monkeypatch, calls)

    def progress(**kwargs: Any) -> tuple[str, int]:
        kwargs["event_bus"].publish(
            {
                "type": "download_progress",
                "data": {"model": TRANSLATION_MODEL_ID, "progress": 50, "status": "Downloading"},
            }
        )
        return ("complete", INDEX_TRANSLATE_Q4.size_bytes)

    monkeypatch.setattr("voice_typer.server.service._download_helpers.poll_download_progress", progress)
    monkeypatch.setattr(
        "voice_typer.server.service.model._status.StatusMixin._invalidate_model_status_cache",
        lambda _self: None,
    )

    result = harness.service.download_model(TRANSLATION_MODEL_ID)

    assert result["success"] is True
    assert calls[0]["spec"].sha256 == INDEX_TRANSLATE_Q4.sha256
    assert calls[0]["tqdm_class"] is not None  # the same pause/abort gate as ASR GGUFs
    assert is_download_active() is False
    progresses = [
        event["data"]["progress"]
        for event in events
        if event["type"] == "download_progress" and event["data"].get("model") == TRANSLATION_MODEL_ID
    ]
    assert progresses[0] == 0 and 50 in progresses and progresses[-1] == 100


def test_cancel_stops_translation_transfer(monkeypatch: pytest.MonkeyPatch) -> None:
    """The named cancel token reaches the translation transfer, not just the poller."""
    harness = _Harness()
    events = _events(monkeypatch)
    calls: list[dict[str, Any]] = []

    def fake(spec: Any, **kwargs: Any) -> tuple[bool, str, Any]:
        calls.append(spec)
        raise ModelDownloadAborted("cancelled")

    def cancelled_poll(**kwargs: Any) -> tuple[str, int]:
        download_id = kwargs["download_id"]
        harness.service._download_cancel_events[download_id].set()
        return ("cancelled", 0)

    monkeypatch.setattr("voice_typer.server.translation.download.download_translation_weights", fake)
    monkeypatch.setattr("voice_typer.server.translation.download._hub_cache_dir", lambda: Path("."))
    monkeypatch.setattr("voice_typer.server.model_availability.shared_hub_dir", lambda: Path("."))
    monkeypatch.setattr("voice_typer.server.asr_setup.get_download_tqdm_class", lambda: object)
    monkeypatch.setattr("voice_typer.server.service._download_helpers.poll_download_progress", cancelled_poll)

    result = harness.service.download_model(TRANSLATION_MODEL_ID)

    assert result["cancelled"] is True
    assert is_download_active() is False
    assert any(event["type"] == "download_progress" for event in events)


def test_disk_check_uses_catalogue_size_and_refuses_before_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """Insufficient space is a clear code, derived from the catalogue size."""
    harness = _Harness()
    calls: list[dict[str, Any]] = []
    _fake_downloader(monkeypatch, calls)
    from voice_typer.server.asr_utils import _DISK_SPACE_MARGIN_MB
    from voice_typer.server.translation import download as td

    expected_mb = -(-INDEX_TRANSLATE_Q4.size_bytes // (1024 * 1024)) + _DISK_SPACE_MARGIN_MB
    monkeypatch.setattr(td, "_hub_cache_dir", lambda: Path("."))
    monkeypatch.setattr(
        "shutil.disk_usage",
        lambda _path: SimpleNamespace(free=(expected_mb - 1) * 1024 * 1024),
    )

    with pytest.raises(RuntimeError) as direct:
        td.check_translation_disk_space(INDEX_TRANSLATE_Q4)
    assert f"Required: {expected_mb} MB" in str(direct.value)

    result = harness.service.download_model(TRANSLATION_MODEL_ID)

    assert result["code"] == "translation_disk_space_insufficient"
    assert calls == []
    assert any("disk space" in message.lower() for message in harness.tray.messages)


def test_integrity_failure_is_reported_without_success(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = _Harness()
    calls: list[dict[str, Any]] = []
    _fake_downloader(monkeypatch, calls, result=(False, "sha256_mismatch", None))

    result = harness.service.download_model(TRANSLATION_MODEL_ID)

    assert result["success"] is False
    assert result["code"] == "translation_sha256_mismatch"
    assert "verification" in result["error"].lower()


def test_delete_removes_the_hub_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    harness = _Harness()
    repo = tmp_path / _REPO_DIR
    repo.mkdir()
    (repo / INDEX_TRANSLATE_Q4.filename).write_bytes(b"gguf")
    monkeypatch.setattr("voice_typer.server.translation.paths.hub_search_dirs", lambda _spec: [repo])
    monkeypatch.setattr("voice_typer.server.translation.service.shutdown", lambda: None)
    monkeypatch.setattr(
        "voice_typer.server.service.model._status.StatusMixin._invalidate_model_status_cache",
        lambda _self: None,
    )

    result = harness.service.delete_model(TRANSLATION_MODEL_ID)

    assert result["success"] is True
    assert not repo.exists()


def test_get_model_status_reports_translation_disk_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = _Harness()
    monkeypatch.setattr("voice_typer.server.translation.paths.model_is_available", lambda *_args: True)
    monkeypatch.setattr(
        "voice_typer.server.service.model._status.StatusMixin._invalidate_model_status_cache",
        lambda _self: None,
    )

    status = harness.service.get_model_status()

    assert status[TRANSLATION_MODEL_ID] == {"downloaded": True, "deps_ok": True}


def test_missing_model_keeps_text_and_notifies_once_without_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rule 3/4: no download, no service construction, one actionable notice."""
    events = _events(monkeypatch)
    _missing_model(monkeypatch)
    monkeypatch.setattr(
        "voice_typer.server.translation.service.get_service",
        lambda _config: pytest.fail("missing model must not construct a translator"),
    )

    cfg = _config()
    first = translation_service.translate_text("hello", cfg, "ar", "en", app=None)
    second = translation_service.translate_text("hello again", cfg, "ar", "en", app=None)

    assert first == "hello" and second == "hello again"
    notices = [
        event for event in events if event["type"] == "notification" and "Post-Processing" in event["data"]["message"]
    ]
    assert len(notices) == 1
    assert "original text was kept" in notices[0]["data"]["message"]


def test_prewarm_never_downloads_or_loads_a_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _missing_model(monkeypatch)
    monkeypatch.setattr(
        "voice_typer.server.translation.service.get_service",
        lambda _config: pytest.fail("prewarm must not construct a translator without the GGUF"),
    )
    assert translation_service.prewarm(_config()) is False


def test_no_automatic_translator_download_call_site() -> None:
    """Rule 2: only the explicit IPC branch may call the transfer function."""
    root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    for path in (root / "voice_typer/server").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "download_translation_weights(" not in text.replace("def download_translation_weights(", ""):
            continue
        if path.name != "_download_translation.py":
            offenders.append(str(path))
    assert offenders == []

    startup_files = [root / "voice_typer/server/startup_tasks.py"]
    startup_files.extend((root / "voice_typer/server/startup_sequence").rglob("*.py"))
    startup_files.append(root / "voice_typer/server/autostart_launcher.py")
    for path in startup_files:
        text = path.read_text(encoding="utf-8")
        assert "translation.prewarm" not in text
        assert "from voice_typer.server.translation import prewarm" not in text


def test_client_model_id_matches_catalogue() -> None:
    """Cross-layer id parity: the Settings row downloads the catalogued id."""
    source = (
        Path(__file__).resolve().parents[2]
        / "voice_typer/client/src/renderer/src/components/settings/translationModel.ts"
    ).read_text(encoding="utf-8")
    assert f'"{TRANSLATION_MODEL_ID}"' in source
