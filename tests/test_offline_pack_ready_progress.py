"""SP-1 slice C: ready publish + download progress through get_status."""

from __future__ import annotations

import pytest
from voice_typer.server.service.offline_pack import progress as _progress, ready as _ready


@pytest.fixture(autouse=True)
def _isolated_pack_state():
    _progress.reset_download_progress()
    _ready.reset_for_tests()
    yield
    _progress.reset_download_progress()
    _ready.reset_for_tests()


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(self, event: dict) -> None:
        self.events.append(event)

    def of_type(self, event_type: str) -> list[dict]:
        return [e for e in self.events if e["type"] == event_type]


def _reset() -> None:
    _progress.reset_download_progress()
    _ready.reset_for_tests()


class TestReadyPublish:
    def test_worker_then_verified_publishes_ready(self):
        _reset()
        bus = _FakeBus()
        assert _ready.note_worker_started(123, "v1", bus) is False
        assert bus.of_type("offline_pack_ready") == []
        assert _ready.note_pack_verified("v1", bus) is True
        ready = bus.of_type("offline_pack_ready")
        assert len(ready) == 1
        assert ready[0]["data"] == {"version": "v1", "worker_pid": 123}

    def test_verified_then_worker_publishes_ready(self):
        _reset()
        bus = _FakeBus()
        assert _ready.note_pack_verified("v2", bus) is False
        assert _ready.note_worker_started(7, "v2", bus) is True
        ready = bus.of_type("offline_pack_ready")
        assert len(ready) == 1
        assert ready[0]["data"]["worker_pid"] == 7

    def test_prewarm_complete_alias_publishes_ready(self):
        _reset()
        bus = _FakeBus()
        _ready.note_worker_started(9, "v3", bus)
        assert _ready.note_prewarm_complete("v3", bus) is True
        assert len(bus.of_type("offline_pack_ready")) == 1

    def test_no_duplicate_publish(self):
        _reset()
        bus = _FakeBus()
        _ready.note_worker_started(1, "v1", bus)
        _ready.note_pack_verified("v1", bus)
        _ready.note_worker_started(1, "v1", bus)
        _ready.note_pack_verified("v1", bus)
        assert len(bus.of_type("offline_pack_ready")) == 1

    def test_invalid_inputs_never_raise(self):
        _reset()
        bus = _FakeBus()
        assert _ready.note_worker_started("bad", "v1", bus) is False
        assert _ready.note_worker_started(-1, "v1", bus) is False
        assert _ready.note_pack_verified("", bus) is False
        assert _ready.note_pack_verified(None, bus) is False
        assert bus.of_type("offline_pack_ready") == []

    def test_worker_relay_publishes_ready_when_verified(self, monkeypatch):
        _reset()
        import voice_typer.server.worker_relay as _relay

        monkeypatch.setattr(_relay, "_notify_shared_client", lambda data: True)
        _relay.reset_worker_port()
        seen: list[dict] = []
        monkeypatch.setattr(
            "voice_typer.server.service.offline_pack.events._publish_event",
            lambda bus, typ, payload: seen.append({"type": typ, "data": payload}),
        )
        monkeypatch.setattr(
            "voice_typer.server.service.offline_pack.ready._publish_event",
            lambda bus, typ, payload: seen.append({"type": typ, "data": payload}),
        )
        assert _relay.handle_host_frame({"data": {"pid": 11, "version": "v9", "port": 51234}}) is True
        assert [e for e in seen if e["type"] == "worker_started"] != []
        # Verified arrives after the worker: the join publishes ready.
        from voice_typer.server.service.offline_pack import ready as _ready_mod

        assert _ready_mod.note_pack_verified("v9", None) is True


class TestDownloadProgressStore:
    def test_started_sets_zero(self):
        _reset()
        _progress.record_download_started("v1", 1000)
        assert _progress.get_download_progress() == 0

    def test_progress_clamped(self):
        _reset()
        _progress.record_download_started("v1", 100)
        _progress.record_download_progress("v1", 42, 42, 100)
        assert _progress.get_download_progress() == 42
        _progress.record_download_progress("v1", 250, 250, 100)
        assert _progress.get_download_progress() == 100
        _progress.record_download_progress("v1", -5, 0, 100)
        assert _progress.get_download_progress() == 0

    def test_completed_pins_hundred_failed_clears(self):
        _reset()
        _progress.record_download_started("v1", 10)
        _progress.record_download_completed("v1")
        assert _progress.get_download_progress() == 100
        _progress.record_download_failed("v1")
        assert _progress.get_download_progress() is None

    def test_snapshot_shape_stable(self):
        _reset()
        _progress.record_download_started("v1", 200)
        snap = _progress.get_download_snapshot()
        assert snap["download_progress"] == 0
        assert snap["download_version"] == "v1"


class TestStatusCarriesProgress:
    def _mixin(self):
        from voice_typer.server.service.status import StatusMixin

        mixin = StatusMixin.__new__(StatusMixin)
        mixin._pack_status_cache = None
        mixin._pack_status_cached_at = 0.0
        return mixin

    def test_get_status_offline_pack_has_progress(self, monkeypatch):
        _reset()
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: None)
        _progress.record_download_started("v1", 100)
        _progress.record_download_progress("v1", 37, 37, 100)
        op = self._mixin()._get_offline_pack_status()
        assert op["download_progress"] == 37
        assert op["available"] is False

    def test_cached_state_still_reports_fresh_progress(self, monkeypatch):
        _reset()
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: None)
        mixin = self._mixin()
        first = mixin._get_offline_pack_status()
        assert first["download_progress"] is None
        _progress.record_download_started("v1", 100)
        _progress.record_download_progress("v1", 64, 64, 100)
        second = mixin._get_offline_pack_status()
        assert second["download_progress"] == 64

    def test_no_pack_still_raises_missing(self):
        from voice_typer.server.asr_errors import OfflinePackMissingError
        from voice_typer.server.service import update_check
        from voice_typer.server.worker_backed_asr import WorkerBackedAsr

        orig = update_check._local_offline_pack_version
        update_check._local_offline_pack_version = lambda *a, **k: None  # type: ignore[assignment]
        try:
            backend = WorkerBackedAsr(model_size="tiny")
            try:
                backend.load()
            except OfflinePackMissingError:
                pass
            else:
                raise AssertionError("missing pack must still raise")
        finally:
            update_check._local_offline_pack_version = orig  # type: ignore[assignment]
