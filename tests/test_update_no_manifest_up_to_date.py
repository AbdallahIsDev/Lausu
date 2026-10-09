"""No published pack manifest is steady state, not a connection failure."""

from __future__ import annotations

from types import SimpleNamespace

from voice_typer.server.service import update_check


def _raise_404(url, **kwargs):
    raise RuntimeError(f"unexpected HTTP status 404 for {url}")


def _raise_down(url, **kwargs):
    raise OSError("simulated DNS failure")


def test_default_both_404_is_up_to_date_not_failed(monkeypatch):
    monkeypatch.delenv("VT_PACK_MANIFEST_URL", raising=False)
    monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda root=None: None)
    result = update_check.check_offline_pack_update(
        SimpleNamespace(offline_pack_consent=True),
        None,
        http_get=_raise_404,
        trigger_download=False,
    )
    assert result["success"] is True
    assert result["update_available"] is False
    assert result["remote_version"] is None
    assert result["download_triggered"] is False
    assert result.get("reason") == "no_remote_manifest"


def test_explicit_url_404_stays_fetch_failed(monkeypatch):
    monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda root=None: None)
    result = update_check.check_offline_pack_update(
        SimpleNamespace(offline_pack_consent=True),
        None,
        http_get=_raise_404,
        manifest_url="https://github.com/AbdallahIsDev/lausu/releases/latest/download/pack-manifest.json",
        trigger_download=False,
    )
    assert result["success"] is False
    assert result["reason"] == "fetch_failed"


def test_default_mixed_404_and_network_error_stays_failed(monkeypatch):
    monkeypatch.delenv("VT_PACK_MANIFEST_URL", raising=False)
    monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda root=None: "1.0.0")

    def fake_get(url, **kwargs):
        if "latest" in url:
            raise RuntimeError(f"unexpected HTTP status 404 for {url}")
        raise OSError("simulated DNS failure")

    result = update_check.check_offline_pack_update(
        SimpleNamespace(offline_pack_consent=True), None, http_get=fake_get, trigger_download=False
    )
    assert result["success"] is False
    assert result["reason"] == "fetch_failed"


def test_default_network_error_stays_failed(monkeypatch):
    monkeypatch.delenv("VT_PACK_MANIFEST_URL", raising=False)
    monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda root=None: "1.0.0")
    result = update_check.check_offline_pack_update(
        SimpleNamespace(offline_pack_consent=True), None, http_get=_raise_down, trigger_download=False
    )
    assert result["success"] is False
    assert result["reason"] == "fetch_failed"
