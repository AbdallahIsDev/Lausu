"""Contracts of the whisper-family download split.

The transfer mechanics of ``DownloadsMixin._download_whisper_family`` live in
``service/model/_download_whisper.py`` (classic snapshot transfer + segmented
fast lane); the facade keeps the orchestration. Splitting a single method must
not move a single byte of observable behavior, so this file pins three things:

1. the wiring (the facade drives the sibling module and no longer owns the
   transfer closure),
2. the call-time patch seams the covering suites rely on (``_download_helpers``
   names are re-read when the lane runs, so a late monkeypatch is honoured),
3. the ``DownloadOutcome`` shapes of both transfer paths — including that a
   cancel maps to the SAME outcome from either path.

Offline by construction: the transport (``huggingface_hub.snapshot_download``)
and the retry wrapper are always stubbed.
"""

from __future__ import annotations

import importlib
import inspect
from unittest.mock import MagicMock

import pytest
from voice_typer.server.service._download_helpers import DownloadOutcome

SIBLING_MODULE = "voice_typer.server.service.model._download_whisper"
EXTRACTED_ENTRIES = ("run_classic_transfer", "run_segmented_fast_lane")

CANCEL_MESSAGE = (
    "Download of tiny cancelled. Partial files remain in cache; retry to resume."
)


def _make_service(tmp_config_dir):
    from voice_typer.server import service as svc_mod

    class FakeApp:
        config = type("FakeConfig", (), {})()
        _microphones: list = []
        tray = MagicMock()

    return svc_mod.LausuService(FakeApp())


def _make_meta(size_mb: int = 1):
    meta = MagicMock()
    meta.repo_id = "org/target"
    meta.backend = "whisper"
    meta.download_size_mb = size_mb
    return meta


@pytest.fixture(autouse=True)
def _clean_gate_state():
    """The single-flight guard reads module-level gate state; isolate it."""
    import voice_typer.server.asr_setup as asr

    asr.clear_download_pause_state()
    yield
    asr.clear_download_pause_state()


def _drive(svc, monkeypatch, *, plan, segmented_phase, retry):
    """Run the whisper branch offline, with every transport seam stubbed."""
    import voice_typer.server.event_bus as event_bus
    import voice_typer.server.segmented_download as segdl

    monkeypatch.setattr(event_bus, "publish", lambda event: None)
    monkeypatch.setattr(
        "voice_typer.server.tray_models.invalidate_model_availability_cache",
        lambda: None,
    )

    def fake_snapshot(**kwargs):
        if kwargs.get("local_files_only"):
            raise FileNotFoundError("not cached, drive into the download branch")
        return "/cache/snap"

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot)
    monkeypatch.setattr("voice_typer.server.transcription._download_with_retry", retry)
    monkeypatch.setattr(segdl, "plan_segmented_files", lambda **kwargs: plan)
    monkeypatch.setattr(segdl, "run_segmented_phase", segmented_phase)
    monkeypatch.setattr(svc, "_require_huggingface_consent", lambda name: None)
    monkeypatch.setattr(svc, "_invalidate_model_status_cache", lambda: None)

    return svc._download_whisper_family("tiny", _make_meta(1))


def _raise_abort(*_args, **_kwargs):
    from voice_typer.server.asr_setup import ModelDownloadAborted

    raise ModelDownloadAborted("cancelled mid-transfer")


def _pass_through(fn, **kwargs):
    return fn(**kwargs)


def _assert_conforms_to_outcome(outcome: dict) -> None:
    unknown = set(outcome) - set(DownloadOutcome.__annotations__)
    assert not unknown, f"outcome carries keys outside DownloadOutcome: {sorted(unknown)}"
    assert "model" in outcome, "every outcome must name the model"


class TestSplitWiring:
    def test_facade_drives_the_sibling_module_object(self):
        from voice_typer.server.service.model import _downloads

        assert _downloads._whisper_download is importlib.import_module(SIBLING_MODULE)

    @pytest.mark.parametrize("name", EXTRACTED_ENTRIES)
    def test_extracted_entries_are_plain_module_level_functions(self, name: str):
        module = importlib.import_module(SIBLING_MODULE)
        entry = getattr(module, name)

        assert callable(entry)
        assert entry.__module__ == SIBLING_MODULE
        params = list(inspect.signature(entry).parameters)
        assert "self" not in params, (
            "the extracted entry must take explicit values, never a host object"
        )

    def test_facade_method_no_longer_owns_the_transfer_closure(self):
        from voice_typer.server.service.model._downloads import DownloadsMixin

        src = inspect.getsource(DownloadsMixin._download_whisper_family)
        assert "def _do_download(" not in src, "the transfer closure must live in the sibling"
        assert "run_classic_transfer" in src
        assert "run_segmented_fast_lane" in src
        # the pause/resume handoff stays in the facade (its file-text pins live there)
        assert "poll_download_progress(" in src

    def test_facade_and_sibling_log_under_the_same_namespace(self):
        from voice_typer.server.service.model import _downloads

        sibling = importlib.import_module(SIBLING_MODULE)
        assert sibling.log.name == "voice_typer.server.service.model._downloads"
        assert sibling.log.name == _downloads.log.name


class TestCallTimePatchSeams:
    def test_segmented_lane_resolves_progress_helpers_when_it_runs(
        self, tmp_config_dir, monkeypatch
    ):
        """A late patch on ``_download_helpers`` must reach the lane.

        The covering suites patch those names on the helper module and expect
        the download to pick them up; resolving them at import time would
        silently ignore the patch.
        """
        import voice_typer.server.segmented_download as segdl
        from voice_typer.server.service import _download_helpers as helpers

        seen: list[str] = []
        plan = [
            segdl.PlannedFile(
                filename="model.bin",
                size=3_000_000_000,
                blob_id="a" * 64,
                sha256="a" * 64,
            )
        ]

        def fake_tracker(**_kwargs):
            seen.append("tracker")
            return lambda *_args: None

        monkeypatch.setattr(helpers, "make_segmented_progress_tracker", fake_tracker)
        monkeypatch.setattr(helpers, "push_progress", lambda *_a, **_k: seen.append("push"))

        svc = _make_service(tmp_config_dir)
        outcome = _drive(
            svc,
            monkeypatch,
            plan=plan,
            segmented_phase=lambda **kwargs: None,
            retry=_pass_through,
        )

        assert outcome["success"] is True, outcome
        assert "tracker" in seen, "the lane must call the patched tracker factory"
        assert "push" in seen, "the lane must go through the patched progress push"

    def test_lane_receives_the_patterns_and_revision_from_the_facade(
        self, tmp_config_dir, monkeypatch
    ):
        """The lane must run against the facade's plan/revision, not its own."""
        import voice_typer.server.segmented_download as segdl

        captured: list[dict] = []
        plan = [
            segdl.PlannedFile(
                filename="model.bin",
                size=3_000_000_000,
                blob_id="b" * 64,
                sha256="b" * 64,
            )
        ]

        def fake_phase(**kwargs):
            captured.append(kwargs)
            return None

        svc = _make_service(tmp_config_dir)
        outcome = _drive(
            svc,
            monkeypatch,
            plan=plan,
            segmented_phase=fake_phase,
            retry=_pass_through,
        )

        assert outcome["success"] is True, outcome
        assert len(captured) == 1
        assert captured[0]["seg_plan"] == plan
        assert captured[0]["repo_id"] == "org/target"
        assert captured[0]["model_name"] == "tiny"
        assert captured[0]["gate_check"] is not None


class TestOutcomeParity:
    def test_classic_success_shape_is_unchanged(self, tmp_config_dir, monkeypatch):
        svc = _make_service(tmp_config_dir)
        outcome = _drive(
            svc,
            monkeypatch,
            plan=[],
            segmented_phase=lambda **kwargs: None,
            retry=_pass_through,
        )

        assert outcome == {"success": True, "model": "tiny"}
        _assert_conforms_to_outcome(outcome)

    def test_no_big_files_means_the_segmented_lane_never_runs(
        self, tmp_config_dir, monkeypatch
    ):
        import voice_typer.server.segmented_download as segdl

        phases: list[dict] = []
        monkeypatch.setattr(
            segdl, "run_segmented_phase", lambda **kwargs: phases.append(kwargs)
        )
        svc = _make_service(tmp_config_dir)

        outcome = _drive(
            svc,
            monkeypatch,
            plan=[],
            segmented_phase=lambda **kwargs: phases.append(kwargs),
            retry=_pass_through,
        )

        assert outcome["success"] is True, outcome
        assert phases == []

    def test_cancel_maps_to_the_same_outcome_on_both_transfer_paths(
        self, tmp_config_dir, monkeypatch
    ):
        """A cancel during the classic transfer and during the segmented lane
        must return byte-identical outcomes — the two paths now live in
        different modules, so this is the parity that could silently drift.
        """
        import voice_typer.server.asr_setup as asr
        import voice_typer.server.segmented_download as segdl

        classic = _drive(
            _make_service(tmp_config_dir),
            monkeypatch,
            plan=[],
            segmented_phase=lambda **kwargs: None,
            retry=_raise_abort,
        )

        plan = [
            segdl.PlannedFile(
                filename="model.bin",
                size=3_000_000_000,
                blob_id="c" * 64,
                sha256="c" * 64,
            )
        ]

        def aborting_phase(**_kwargs):
            raise asr.ModelDownloadAborted("simulated cancel")

        segmented = _drive(
            _make_service(tmp_config_dir),
            monkeypatch,
            plan=plan,
            segmented_phase=aborting_phase,
            retry=_pass_through,
        )

        assert classic == segmented, (classic, segmented)
        assert classic["success"] is False
        assert classic["cancelled"] is True
        assert classic["model"] == "tiny"
        assert classic["message"] == CANCEL_MESSAGE
        _assert_conforms_to_outcome(classic)
        assert asr.is_download_active() is False, "a cancel must release the single-flight gate"
