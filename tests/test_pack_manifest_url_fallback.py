"""Multi-URL pack-manifest fallback (latest + rolling offline-pack tag)."""

from __future__ import annotations

import json

from voice_typer.server.service import update_check


def _manifest(version: str = "1.2.3") -> str:
    return json.dumps(
        {
            "version": version,
            "sha256": "a" * 64,
            "files": [{"name": "worker.exe", "sha256": "b" * 64, "size": 10}],
            "min_proto_version": 1,
        }
    )


def test_candidates_default_order(monkeypatch):
    monkeypatch.delenv("VT_PACK_MANIFEST_URL", raising=False)
    urls = update_check.pack_manifest_url_candidates()
    assert urls[0] == update_check.DEFAULT_OFFLINE_PACK_MANIFEST_URL
    assert urls[1] == update_check.ROLLING_OFFLINE_PACK_MANIFEST_URL
    assert "offline-pack" in urls[1]


def test_explicit_url_is_single_candidate():
    urls = update_check.pack_manifest_url_candidates("https://example.com/m.json")
    assert urls == ["https://example.com/m.json"]


def test_env_override_is_single_candidate(monkeypatch):
    monkeypatch.setenv("VT_PACK_MANIFEST_URL", "https://example.com/env.json")
    assert update_check.pack_manifest_url_candidates() == ["https://example.com/env.json"]


def test_first_success_prefers_earlier_candidate():
    calls: list[str] = []

    def fake_get(url, **_kwargs):
        calls.append(url)
        if "latest" in url:
            raise RuntimeError("404")
        return _manifest("2.0.0")

    manifest, used = update_check.fetch_remote_manifest_first_success(
        [
            update_check.DEFAULT_OFFLINE_PACK_MANIFEST_URL,
            update_check.ROLLING_OFFLINE_PACK_MANIFEST_URL,
        ],
        http_get=fake_get,
    )
    assert manifest is not None
    assert manifest["version"] == "2.0.0"
    assert used == update_check.ROLLING_OFFLINE_PACK_MANIFEST_URL
    assert len(calls) == 2


def test_first_success_stops_at_first_hit():
    calls: list[str] = []

    def fake_get(url, **_kwargs):
        calls.append(url)
        return _manifest("1.0.0")

    manifest, used = update_check.fetch_remote_manifest_first_success(
        [update_check.DEFAULT_OFFLINE_PACK_MANIFEST_URL, "https://github.com/x/y"],
        http_get=fake_get,
    )
    assert manifest is not None
    assert used == update_check.DEFAULT_OFFLINE_PACK_MANIFEST_URL
    assert len(calls) == 1


def test_first_success_all_fail_returns_none():
    def fake_get(url, **_kwargs):
        raise RuntimeError("down")

    manifest, used = update_check.fetch_remote_manifest_first_success(
        ["https://github.com/a/b", "https://github.com/c/d"],
        http_get=fake_get,
    )
    assert manifest is None
    assert used is None


def test_check_update_uses_fallback_when_latest_404(monkeypatch):
    def fake_get(url, **_kwargs):
        if "latest" in url:
            raise RuntimeError("HTTP 404")
        return _manifest("9.9.9")

    result = update_check.check_offline_pack_update(
        None,
        None,
        http_get=fake_get,
        local_version="1.0.0",
        trigger_download=False,
    )
    assert result["success"] is True
    assert result["remote_version"] == "9.9.9"
    assert result["update_available"] is True
