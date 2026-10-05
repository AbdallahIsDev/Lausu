"""Connect-storm hardening: cached storage summary + probe pre-warm."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from voice_typer.server.handlers import status_handlers as _sh
from voice_typer.server.handlers.status_handlers import StatusHandlersMixin


def _mixin():
    mixin = StatusHandlersMixin.__new__(StatusHandlersMixin)
    mixin.app = SimpleNamespace()
    mixin.service = MagicMock()
    return mixin


class TestCachedStorageSummary:
    def setup_method(self):
        _sh._storage_cache.clear()

    def test_second_call_served_from_cache(self, monkeypatch, tmp_path):
        walks = []
        monkeypatch.setattr(
            StatusHandlersMixin,
            "_dir_size_bytes",
            staticmethod(lambda root: walks.append(root) or 1234),
        )
        mixin = _mixin()
        hub = str(tmp_path)
        first = mixin._cached_storage_summary(hub, "/cfg")
        second = mixin._cached_storage_summary(hub, "/cfg")
        assert first == second == {"used_bytes": 1234, "hub_path": hub, "config_dir": "/cfg"}
        assert len(walks) == 1, "second call must not re-walk the disk"

    def test_cache_expires_after_ttl(self, monkeypatch, tmp_path):
        walks = []
        monkeypatch.setattr(
            StatusHandlersMixin,
            "_dir_size_bytes",
            staticmethod(lambda root: walks.append(root) or 7),
        )
        mixin = _mixin()
        hub = str(tmp_path)
        mixin._cached_storage_summary(hub, "/cfg")
        _sh._storage_cache[hub] = (time.monotonic() - _sh._STORAGE_CACHE_TTL_S - 1.0, {"stale": True})
        fresh = mixin._cached_storage_summary(hub, "/cfg")
        assert fresh["used_bytes"] == 7
        assert len(walks) == 2

    def test_missing_hub_skips_walk(self, monkeypatch, tmp_path):
        called = []
        monkeypatch.setattr(
            StatusHandlersMixin,
            "_dir_size_bytes",
            staticmethod(lambda root: called.append(root) or 9),
        )
        mixin = _mixin()
        out = mixin._cached_storage_summary(str(tmp_path / "nope"), "/cfg")
        assert out["used_bytes"] == 0
        assert called == []


class TestPrewarmConnectProbes:
    def test_warms_both_caches_and_never_raises(self, monkeypatch):
        from voice_typer.server import startup_tasks

        seen = []
        monkeypatch.setattr(
            "voice_typer.server.device_caps.gpu_available",
            lambda: seen.append("gpu") or False,
        )
        monkeypatch.setattr(
            "voice_typer.server.credential_store.get_keyring_status",
            lambda: seen.append("keyring") or {},
        )
        startup_tasks.prewarm_connect_probes()
        assert seen == ["gpu", "keyring"]

    def test_probe_failure_is_swallowed(self, monkeypatch):
        from voice_typer.server import startup_tasks

        def _boom():
            raise RuntimeError("boom")

        monkeypatch.setattr("voice_typer.server.device_caps.gpu_available", _boom)
        monkeypatch.setattr("voice_typer.server.credential_store.get_keyring_status", _boom)
        startup_tasks.prewarm_connect_probes()
