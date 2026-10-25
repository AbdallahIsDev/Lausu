"""HuggingFace transfer calls must not send deprecated ``snapshot_download`` kwargs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


def _recording_snapshot(calls: list[dict], *, fail_local_probe: bool = False):
    def _snapshot(**kwargs):
        calls.append(kwargs)
        if fail_local_probe and kwargs.get("local_files_only"):
            raise OSError("not cached")
        return "/fake/cache/path"

    return _snapshot


def test_classic_transfer_omits_deprecated_resume_download():
    from voice_typer.server.service.model import _download_whisper as whisper_transfer

    calls: list[dict] = []
    errors: list = []

    whisper_transfer.run_classic_transfer(
        snapshot_download=_recording_snapshot(calls),
        repo_id="openai/whisper-tiny",
        revision="main",
        allow_patterns=["*.bin"],
        ignore_patterns=None,
        tqdm_class=None,
        errors=errors,
    )

    assert errors == []
    assert len(calls) == 1
    assert "resume_download" not in calls[0]


def test_segmented_fallback_transfers_omit_deprecated_resume_download(monkeypatch):
    from voice_typer.server import segmented_download as segdl
    from voice_typer.server.service.model import _download_whisper as whisper_transfer

    def _segmented_boom(**_kwargs):
        raise segdl.SegmentedDownloadError("segment failed")

    monkeypatch.setattr(segdl, "run_segmented_phase", _segmented_boom)

    calls: list[dict] = []
    outcome = whisper_transfer.run_segmented_fast_lane(
        seg_plan=[],
        repo_id="openai/whisper-tiny",
        revision="main",
        cache_dir=Path("cache"),
        snapshot_download=_recording_snapshot(calls, fail_local_probe=True),
        allow_patterns=["*.bin"],
        event_bus=MagicMock(),
        model_name="tiny",
        target_mb=75,
        target_bytes=75 * 1024 * 1024,
    )

    assert outcome is None
    assert len(calls) == 3, f"expected fast-lane fallback + probe + verify fallback, got {calls}"
    assert all("resume_download" not in kwargs for kwargs in calls)
