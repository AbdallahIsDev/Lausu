"""The loopback pack harness opt-in must be impossible in a frozen build."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest
from voice_typer.server.media_ingest import ffmpeg_binaries
from voice_typer.server.service import offline_pack
from voice_typer.server.service.offline_pack import local_dev

URL = "http://127.0.0.1:18473/pack-manifest.json"


@pytest.fixture
def opt_in(monkeypatch):
    monkeypatch.setenv(local_dev.ENV_LOCAL_PACK_DEV_SERVER, "1")
    return URL


def test_loopback_http_blocked_without_opt_in(monkeypatch):
    monkeypatch.delenv(local_dev.ENV_LOCAL_PACK_DEV_SERVER, raising=False)
    assert local_dev.allow_local_pack_dev_server(URL) is False
    with pytest.raises(ValueError):
        offline_pack.assert_offline_pack_url_allowed(URL)


def test_opt_in_allows_loopback_http_in_source_checkout(opt_in):
    assert local_dev.allow_local_pack_dev_server(opt_in) is True
    offline_pack.assert_offline_pack_url_allowed(opt_in)


@pytest.mark.parametrize("frozen_signal", ["sys_frozen", "nuitka_compiled"])
def test_opt_in_is_inert_in_frozen_build(opt_in, monkeypatch, frozen_signal):
    """Simulate both frozen markers; neither may activate the harness seam."""
    if frozen_signal == "sys_frozen":
        monkeypatch.setattr(sys, "frozen", True, raising=False)
    else:
        monkeypatch.setattr(ffmpeg_binaries, "__compiled__", object(), raising=False)

    assert local_dev.allow_local_pack_dev_server(opt_in) is False
    with pytest.raises(ValueError):
        offline_pack.assert_offline_pack_url_allowed(opt_in)


def test_non_loopback_http_still_blocked_with_opt_in(opt_in):
    url = "http://example.com/pack-manifest.json"
    assert local_dev.allow_local_pack_dev_server(url) is False
    with pytest.raises(ValueError):
        offline_pack.assert_offline_pack_url_allowed(url)


def test_frozen_simulator_uses_the_shared_frozen_authority(monkeypatch):
    """The seam reads the same helper the media/worker code uses (E7)."""
    seen: list[bool] = []

    def fake_is_frozen() -> bool:
        seen.append(True)
        return True

    monkeypatch.setattr(local_dev, "is_frozen_build", fake_is_frozen)
    assert local_dev.allow_local_pack_dev_server(URL) is False
    assert seen == [True]


def test_payload_never_exports_a_frozen_activation_flag():
    """No second flag: only the env opt-in + shared frozen check exist."""
    names = {name for name in dir(local_dev) if name.upper() == name}
    assert local_dev.ENV_LOCAL_PACK_DEV_SERVER == "VT_PACK_DEV_LOCAL_SERVER"
    assert "ENV_LOCAL_PACK_DEV_SERVER" in names
    assert not any(name.startswith("FORCE_") for name in names)
    assert isinstance(ffmpeg_binaries, ModuleType)
