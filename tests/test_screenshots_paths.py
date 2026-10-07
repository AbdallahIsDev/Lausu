"""Screenshot beta path resolver tests (tmp base only, never real profile)."""

from pathlib import Path

from voice_typer.server.screenshots import paths


def test_shot_and_meta_live_under_cycle_dir(tmp_path: Path) -> None:
    shot = paths.shot_path("2026-10-07_120000", base=tmp_path)
    assert shot.name == "shot-1.png"
    assert shot.parent.name != ""
    assert paths.meta_path("2026-10-07_120000", base=tmp_path).name == "meta.json"
    assert str(tmp_path) in str(shot)


def test_cycle_id_sanitized(tmp_path: Path) -> None:
    assert paths.sanitize_cycle_id("a/b\\c:d") == "a_b_c_d"
    assert paths.sanitize_cycle_id("   ") == "manual"


def test_ensure_cycle_dir_creates(tmp_path: Path) -> None:
    created = paths.ensure_cycle_dir("2026-10-07_120000", base=tmp_path)
    assert created.is_dir()
