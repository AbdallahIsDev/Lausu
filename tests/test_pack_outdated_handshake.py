"""Host-relayed outdated-pack signal: extract, store, publish, ingest."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from voice_typer.server.service.offline_pack import outdated as _outdated
from voice_typer.server.service.offline_pack.events import OFFLINE_PACK_EVENT_TYPES


@pytest.fixture(autouse=True)
def _isolated_outdated():
    _outdated.reset_for_tests()
    yield
    _outdated.reset_for_tests()


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(self, event: dict) -> None:
        self.events.append(event)


class _RaisingBus:
    def publish(self, event: dict) -> None:
        raise RuntimeError("bus down")


def _valid_manifest_dict(version: str = "1.0.0", proto: object = 1) -> dict:
    digest = "a" * 64
    return {
        "version": version,
        "sha256": digest,
        "files": [{"name": "worker.exe", "sha256": digest, "size": 10}],
        "min_proto_version": proto,
    }


class TestExtractor:
    def test_valid_payload(self):
        assert _outdated.outdated_from_pack_outdated({"version": "v1", "min_proto_version": 3}) == {
            "version": "v1",
            "min_proto_version": 3,
        }

    @pytest.mark.parametrize("payload", [None, "v1", [], [1], 5, True])
    def test_non_dict_rejected(self, payload):
        assert _outdated.outdated_from_pack_outdated(payload) is None

    @pytest.mark.parametrize(
        "payload",
        [{"min_proto_version": 1}, {"version": "v1"}, {}, {"version": "v1", "min_proto_version": None}],
    )
    def test_missing_keys_rejected(self, payload):
        assert _outdated.outdated_from_pack_outdated(payload) is None

    @pytest.mark.parametrize("proto", [True, False])
    def test_bool_proto_rejected(self, proto):
        assert _outdated.outdated_from_pack_outdated({"version": "v1", "min_proto_version": proto}) is None

    @pytest.mark.parametrize("proto", [-1, -100, "2", 2.0, None, [1]])
    def test_bad_proto_rejected(self, proto):
        assert _outdated.outdated_from_pack_outdated({"version": "v1", "min_proto_version": proto}) is None

    @pytest.mark.parametrize("version", ["", None, 1, True, [], {}])
    def test_bad_version_rejected(self, version):
        assert _outdated.outdated_from_pack_outdated({"version": version, "min_proto_version": 1}) is None


class TestStore:
    def test_record_get_is_outdated(self):
        assert _outdated.is_outdated("v1") is False
        assert _outdated.record_outdated("v1", 2) is True
        assert _outdated.is_outdated("v1") is True
        assert _outdated.is_outdated() is True
        assert _outdated.get_outdated_info("v1") == {"version": "v1", "min_proto_version": 2}
        assert _outdated.get_outdated_info() == {"version": "v1", "min_proto_version": 2}

    def test_record_rejects_garbage_never_raises(self):
        assert _outdated.record_outdated("", 1) is False
        assert _outdated.record_outdated(None, 1) is False
        assert _outdated.record_outdated("v1", True) is False
        assert _outdated.record_outdated("v1", -1) is False
        assert _outdated.record_outdated("v1", "2") is False
        assert _outdated.get_outdated_count() == 0

    def test_clear_single_and_all(self):
        _outdated.record_outdated("v1", 1)
        _outdated.record_outdated("v2", 2)
        _outdated.clear_outdated("v1")
        assert _outdated.is_outdated("v1") is False
        assert _outdated.is_outdated("v2") is True
        _outdated.clear_outdated()
        assert _outdated.get_outdated_count() == 0
        assert _outdated.is_outdated() is False

    def test_cap_eviction(self):
        for i in range(9):
            assert _outdated.record_outdated(f"v{i}", i) is True
        assert _outdated.get_outdated_count() <= 8
        assert _outdated.get_outdated_count() == 8
        assert _outdated.is_outdated("v0") is False
        assert _outdated.is_outdated("v8") is True

    def test_clear_helpers(self):
        _outdated.record_outdated("v1", 1)
        _outdated.clear_on_verified("v1")
        assert _outdated.is_outdated("v1") is False
        _outdated.record_outdated("v2", 2)
        _outdated.clear_on_download_started("v2")
        assert _outdated.is_outdated("v2") is False

    def test_event_name_registered(self):
        assert _outdated.PACK_OUTDATED_EVENT == "offline_pack_outdated"
        assert "offline_pack_outdated" in OFFLINE_PACK_EVENT_TYPES


class TestNotePublish:
    def test_publishes_once_with_right_type(self):
        bus = _FakeBus()
        assert _outdated.note_pack_outdated("v1", 4, bus) is True
        assert len(bus.events) == 1
        assert bus.events[0] == {
            "type": "offline_pack_outdated",
            "data": {"version": "v1", "min_proto_version": 4},
        }
        assert _outdated.is_outdated("v1") is True

    @pytest.mark.parametrize(
        "version,proto",
        [(None, 1), ("", 1), ("v1", True), ("v1", -1), ("v1", "x"), (None, None)],
    )
    def test_garbage_returns_false_never_raises(self, version, proto):
        bus = _FakeBus()
        assert _outdated.note_pack_outdated(version, proto, bus) is False
        assert bus.events == []

    def test_raising_bus_never_raises(self):
        assert _outdated.note_pack_outdated("v1", 1, _RaisingBus()) is True
        assert _outdated.is_outdated("v1") is True


class TestHandleHostFrame:
    def test_end_to_end_stores_and_publishes(self, monkeypatch):
        seen: list[dict] = []
        monkeypatch.setattr(
            "voice_typer.server.event_bus.publish", lambda event: seen.append(event) or True
        )
        frame = {"type": "offline_pack_outdated", "data": {"version": "v9", "min_proto_version": 7}}
        assert _outdated.handle_host_frame(frame) is True
        assert _outdated.get_outdated_info("v9") == {"version": "v9", "min_proto_version": 7}
        assert {"type": "offline_pack_outdated", "data": {"version": "v9", "min_proto_version": 7}} in seen

    @pytest.mark.parametrize(
        "frame",
        [
            None,
            "offline_pack_outdated",
            [],
            {"type": "offline_pack_outdated"},
            {"type": "offline_pack_outdated", "data": None},
            {"type": "offline_pack_outdated", "data": {"version": "v1"}},
            {"type": "offline_pack_outdated", "data": {"version": "v1", "min_proto_version": True}},
            {"type": "offline_pack_outdated", "data": {"version": "v1", "min_proto_version": -2}},
            {"type": "offline_pack_outdated", "data": {"version": "", "min_proto_version": 1}},
        ],
    )
    def test_bad_frames_return_false(self, frame):
        assert _outdated.handle_host_frame(frame) is False
        assert _outdated.get_outdated_count() == 0

    def test_worker_relay_does_not_swallow_outdated_shape(self):
        from voice_typer.server import worker_relay as _relay

        _relay.reset_worker_port()
        try:
            frame = {"type": "offline_pack_outdated", "data": {"version": "v1", "min_proto_version": 3}}
            assert _relay.handle_host_frame(frame) is False
            assert _relay.get_worker_port() is None
        finally:
            _relay.reset_worker_port()


class TestManifestReader:
    def test_missing_file_returns_none(self, tmp_path: Path):
        from voice_typer.server.service.offline_pack.core import load_offline_pack_manifest

        assert load_offline_pack_manifest(tmp_path / "pack-manifest.json") is None

    @pytest.mark.parametrize("proto", [-1, "1", 1.5, None, [1]])
    def test_bad_min_proto_returns_none(self, tmp_path: Path, proto):
        from voice_typer.server.service.offline_pack.core import load_offline_pack_manifest

        path = tmp_path / "pack-manifest.json"
        path.write_text(json.dumps(_valid_manifest_dict(proto=proto)), encoding="utf-8")
        assert load_offline_pack_manifest(path) is None

    def test_valid_manifest_loads(self, tmp_path: Path):
        from voice_typer.server.service.offline_pack.core import load_offline_pack_manifest

        path = tmp_path / "pack-manifest.json"
        path.write_text(json.dumps(_valid_manifest_dict()), encoding="utf-8")
        manifest = load_offline_pack_manifest(path)
        assert manifest is not None
        assert manifest["version"] == "1.0.0"


class TestReadLoopIntercept:
    def test_source_contains_outdated_intercept(self):
        src = (
            Path(__file__).resolve().parents[1]
            / "voice_typer"
            / "server"
            / "sidecar_ws_internals"
            / "read_loop.py"
        ).read_text(encoding="utf-8")
        assert "offline_pack_outdated" in src
        assert "handle_host_frame" in src
        assert src.index("offline_pack_outdated") > src.index("WORKER_STARTED_EVENT")

    def test_unit_call_pins_relay(self, monkeypatch):
        seen: list[dict] = []
        monkeypatch.setattr(
            "voice_typer.server.event_bus.publish", lambda event: seen.append(event) or True
        )
        assert (
            _outdated.handle_host_frame(
                {"type": "offline_pack_outdated", "data": {"version": "vr", "min_proto_version": 2}}
            )
            is True
        )
        assert _outdated.is_outdated("vr") is True


class TestStress:
    def test_threaded_set_clear_no_exception(self):
        errors: list[BaseException] = []

        def _work(n: int) -> None:
            try:
                for i in range(100):
                    _outdated.record_outdated(f"t{n}-{i % 4}", i)
                    _outdated.get_outdated_info(f"t{n}-{i % 4}")
                    _outdated.clear_outdated(f"t{n}-{i % 4}")
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=_work, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30.0)
        assert errors == []
        _outdated.clear_outdated()
        assert _outdated.get_outdated_count() == 0

    def test_outdated_verified_cycles_stay_bounded(self):
        bus = _FakeBus()
        for i in range(50):
            assert _outdated.note_pack_outdated(f"c{i}", i, bus) is True
            _outdated.clear_on_verified(f"c{i}")
            assert _outdated.get_outdated_count() <= 8
        assert _outdated.get_outdated_count() == 0
