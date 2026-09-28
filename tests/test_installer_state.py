"""installer-state.json reader (pack split §4.8)."""

from __future__ import annotations

import json

from voice_typer.server.installer_state import (
    InstallerState,
    installer_state_path,
    load_installer_state,
    pack_download_allowed,
)


def test_missing_file_uses_defaults(tmp_path):
    st = load_installer_state(tmp_path / "nope.json")
    assert st.include_offline_engine_pack is True
    assert st.pack_bundled is False
    assert pack_download_allowed(st) is True


def test_checkbox_opt_out_blocks_download(tmp_path):
    p = tmp_path / "installer-state.json"
    p.write_text(
        json.dumps(
            {
                "include_offline_engine_pack": False,
                "installer_version": "1.0.0",
                "pack_bundled": False,
            }
        ),
        encoding="utf-8",
    )
    st = load_installer_state(p)
    assert st.include_offline_engine_pack is False
    assert pack_download_allowed(st) is False


def test_pack_bundled_blocks_download(tmp_path):
    p = tmp_path / "installer-state.json"
    p.write_text(
        json.dumps(
            {
                "include_offline_engine_pack": True,
                "installer_version": "1.0.0",
                "pack_bundled": True,
            }
        ),
        encoding="utf-8",
    )
    st = load_installer_state(p)
    assert st.pack_bundled is True
    assert pack_download_allowed(st) is False


def test_corrupt_file_fails_open_to_download(tmp_path):
    p = tmp_path / "installer-state.json"
    p.write_text("{not json", encoding="utf-8")
    st = load_installer_state(p)
    assert st.include_offline_engine_pack is True
    assert pack_download_allowed(st) is True


def test_defaults_dataclass():
    st = InstallerState()
    assert st.include_offline_engine_pack is True
    assert st.pack_bundled is False


def test_string_false_is_not_truthy(tmp_path):
    """bool('false') is True in Python — the reader must reject that."""
    p = tmp_path / "installer-state.json"
    p.write_text(
        json.dumps({"include_offline_engine_pack": "false", "pack_bundled": "false"}),
        encoding="utf-8",
    )
    st = load_installer_state(p)
    assert st.include_offline_engine_pack is False
    assert st.pack_bundled is False


def test_bom_json_accepted(tmp_path):
    p = tmp_path / "installer-state.json"
    p.write_text(
        "\ufeff" + json.dumps({"include_offline_engine_pack": True, "pack_bundled": False}),
        encoding="utf-8",
    )
    st = load_installer_state(p)
    assert st.include_offline_engine_pack is True


def test_non_string_installer_version_dropped(tmp_path):
    p = tmp_path / "installer-state.json"
    p.write_text(json.dumps({"installer_version": 123}), encoding="utf-8")
    st = load_installer_state(p)
    assert st.installer_version is None


def test_opt_out_wins_even_when_pack_missing():
    st = InstallerState(include_offline_engine_pack=False, pack_bundled=False)
    assert pack_download_allowed(st, pack_present=False) is False


def test_bundled_but_missing_allows_redownload():
    """Full-offline extract failed or a cleaner deleted the pack."""
    st = InstallerState(include_offline_engine_pack=True, pack_bundled=True)
    assert pack_download_allowed(st, pack_present=False) is True


def test_bundled_and_present_skips_download():
    st = InstallerState(include_offline_engine_pack=True, pack_bundled=True)
    assert pack_download_allowed(st, pack_present=True) is False


def test_bundled_unknown_present_skips_download():
    """Historical default: assume the bundled pack landed."""
    st = InstallerState(include_offline_engine_pack=True, pack_bundled=True)
    assert pack_download_allowed(st, pack_present=None) is False


def test_installer_state_path_respects_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("voice_typer.server.installer_state.sys.platform", "win32")
    p = installer_state_path()
    assert p == tmp_path / "lausu" / "installer-state.json"
