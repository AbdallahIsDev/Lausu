"""PK-2 pack state machine: precedence, cache TTL + invalidate, robustness."""

from __future__ import annotations

import threading

import pytest
from voice_typer.server.service.offline_pack import outdated as _outdated, progress as _progress
from voice_typer.server.service.status import StatusMixin

EXPECTED_KEYS = frozenset(
    {
        "installed_version",
        "available",
        "consent_granted",
        "download_progress",
        "state",
        "outdated_info",
    }
)

VALID_STATES = frozenset({"outdated", "downloading", "verifying", "ready", "missing"})


@pytest.fixture(autouse=True)
def _isolated_pack_state():
    _progress.reset_download_progress()
    _outdated.reset_for_tests()
    yield
    _progress.reset_download_progress()
    _outdated.reset_for_tests()


def _mixin():
    mixin = StatusMixin.__new__(StatusMixin)
    mixin._pack_status_cache = None
    mixin._pack_status_cached_at = 0.0
    return mixin


def _patch_scan(monkeypatch, version):
    from voice_typer.server.service import update_check

    monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: version)


def _patch_exists(monkeypatch, value=True):
    import voice_typer.server.service.offline_pack.core as _core

    monkeypatch.setattr(_core, "offline_pack_exists", lambda _v, **_k: value)


class TestPackStatePrecedence:
    def test_missing_when_nothing_installed(self, monkeypatch):
        _patch_scan(monkeypatch, None)
        op = _mixin()._get_offline_pack_status()
        assert set(op) == set(EXPECTED_KEYS)
        assert op["state"] == "missing"
        assert op["outdated_info"] is None
        assert op["available"] is False

    def test_ready_when_installed_and_present(self, monkeypatch):
        _patch_scan(monkeypatch, "v9")
        _patch_exists(monkeypatch, True)
        op = _mixin()._get_offline_pack_status()
        assert op["state"] == "ready"
        assert op["installed_version"] == "v9"
        assert op["available"] is True

    def test_missing_when_installed_but_files_gone(self, monkeypatch):
        _patch_scan(monkeypatch, "v9")
        _patch_exists(monkeypatch, False)
        op = _mixin()._get_offline_pack_status()
        assert op["state"] == "missing"

    def test_downloading_outranks_missing(self, monkeypatch):
        _patch_scan(monkeypatch, None)
        _progress.record_download_started("v10", 100)
        _progress.record_download_progress("v10", 37, 37, 100)
        op = _mixin()._get_offline_pack_status()
        assert op["state"] == "downloading"
        assert op["download_progress"] == 37

    def test_progress_zero_is_downloading(self, monkeypatch):
        _patch_scan(monkeypatch, None)
        _progress.record_download_started("v10", 100)
        op = _mixin()._get_offline_pack_status()
        assert op["state"] == "downloading"

    def test_verifying_at_hundred(self, monkeypatch):
        _patch_scan(monkeypatch, None)
        _progress.record_download_started("v10", 100)
        _progress.record_download_completed("v10")
        op = _mixin()._get_offline_pack_status()
        assert op["state"] == "verifying"

    def test_outdated_outranks_downloading(self, monkeypatch):
        _patch_scan(monkeypatch, None)
        _progress.record_download_started("v10", 100)
        _progress.record_download_progress("v10", 50, 50, 100)
        assert _outdated.record_outdated("v10", 7) is True
        op = _mixin()._get_offline_pack_status()
        assert op["state"] == "outdated"
        assert op["outdated_info"] == {"version": "v10", "min_proto_version": 7}

    def test_outdated_outranks_ready(self, monkeypatch):
        _patch_scan(monkeypatch, "v9")
        _patch_exists(monkeypatch, True)
        assert _outdated.record_outdated("v10", 7) is True
        op = _mixin()._get_offline_pack_status()
        assert op["state"] == "outdated"


class TestPackStatusCache:
    def test_cached_scan_with_fresh_progress(self, monkeypatch):
        _patch_scan(monkeypatch, None)
        mixin = _mixin()
        first = mixin._get_offline_pack_status()
        assert first["download_progress"] is None
        _progress.record_download_started("v1", 100)
        _progress.record_download_progress("v1", 64, 64, 100)
        second = mixin._get_offline_pack_status()
        assert second["download_progress"] == 64
        assert second["state"] == "downloading"

    def test_cached_scan_holds_version_within_ttl(self, monkeypatch):
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: "v1")
        mixin = _mixin()
        assert mixin._get_offline_pack_status()["installed_version"] == "v1"
        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: "v2")
        assert mixin._get_offline_pack_status()["installed_version"] == "v1"

    def test_invalidate_forces_rescan(self, monkeypatch):
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: "v1")
        mixin = _mixin()
        assert mixin._get_offline_pack_status()["installed_version"] == "v1"
        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: "v2")
        mixin.invalidate_pack_status_cache()
        assert mixin._pack_status_cache is None
        _patch_exists(monkeypatch, True)
        assert mixin._get_offline_pack_status()["installed_version"] == "v2"

    def test_ttl_expiry_rescans(self, monkeypatch):
        import time

        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: "v1")
        mixin = _mixin()
        assert mixin._get_offline_pack_status()["installed_version"] == "v1"
        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: "v2")
        mixin._pack_status_cached_at = time.monotonic() - 30.0
        assert mixin._get_offline_pack_status()["installed_version"] == "v2"

    def test_cached_copy_rederives_outdated(self, monkeypatch):
        _patch_scan(monkeypatch, None)
        mixin = _mixin()
        assert mixin._get_offline_pack_status()["state"] == "missing"
        assert _outdated.record_outdated("v10", 7) is True
        second = mixin._get_offline_pack_status()
        assert second["state"] == "outdated"
        assert second["outdated_info"] == {"version": "v10", "min_proto_version": 7}


class TestPackStatusNeverRaises:
    def test_broken_stores_return_degraded_dict(self, monkeypatch):
        from voice_typer.server.service import update_check

        def _boom(*a, **k):
            raise RuntimeError("broken store")

        monkeypatch.setattr(_progress, "get_download_progress", _boom)
        monkeypatch.setattr(update_check, "_local_offline_pack_version", _boom)
        monkeypatch.setattr(_outdated, "get_outdated_info", _boom)
        import voice_typer.server.service.offline_pack.core as _core

        monkeypatch.setattr(_core, "offline_pack_exists", _boom)
        op = _mixin()._get_offline_pack_status()
        assert set(op) == set(EXPECTED_KEYS)
        assert op["state"] == "missing"
        assert op["outdated_info"] is None
        assert op["download_progress"] is None

    def test_broken_exists_check_with_version_falls_back_to_ready(self, monkeypatch):
        _patch_scan(monkeypatch, "v9")
        import voice_typer.server.service.offline_pack.core as _core

        def _boom(_v, **_k):
            raise RuntimeError("broken store")

        monkeypatch.setattr(_core, "offline_pack_exists", _boom)
        op = _mixin()._get_offline_pack_status()
        assert op["state"] == "ready"


class TestPackStatusConcurrent:
    def test_eight_threads_stable_keys(self, monkeypatch):
        _patch_scan(monkeypatch, "v9")
        _patch_exists(monkeypatch, True)
        _progress.record_download_started("v10", 100)
        _progress.record_download_progress("v10", 42, 42, 100)
        assert _outdated.record_outdated("v10", 7) is True
        mixin = _mixin()
        errors: list[BaseException] = []
        seen: list[dict] = []
        seen_lock = threading.Lock()

        def _read_many():
            try:
                for _ in range(25):
                    op = mixin._get_offline_pack_status()
                    assert set(op) == set(EXPECTED_KEYS)
                    assert op["state"] in VALID_STATES
                    with seen_lock:
                        seen.append(op)
            except BaseException as exc:  # noqa: BLE001 - collected, then asserted
                with seen_lock:
                    errors.append(exc)

        threads = [threading.Thread(target=_read_many) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not [t for t in threads if t.is_alive()]
        assert errors == []
        assert len(seen) == 200
