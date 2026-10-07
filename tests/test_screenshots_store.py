"""Screenshot store tests: one-shot rule, clear, prune, history cleanup."""

import os
import time
from pathlib import Path

import pytest
from voice_typer.server.screenshots import paths, store


def _seed_shot(tmp_path: Path, cycle: str, old: bool = False) -> Path:
    dest = paths.shot_path(cycle, base=tmp_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\x89PNG" + b"0" * 64)
    if old:
        ancient = time.time() - 31 * 86400
        os.utime(dest, (ancient, ancient))
    return dest


def test_one_shot_per_cycle(tmp_path: Path) -> None:
    dest = paths.shot_path("2026-10-07_A", base=tmp_path)
    store.register_shot("2026-10-07_A", str(dest), base=tmp_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\x89PNG" + b"0" * 64)
    assert store.cycle_captured("2026-10-07_A", base=tmp_path) is True
    with pytest.raises(store.AlreadyCapturedError):
        store.register_shot("2026-10-07_A", str(dest), base=tmp_path)


def test_clear_cycle(tmp_path: Path) -> None:
    _seed_shot(tmp_path, "2026-10-07_B")
    assert store.clear_cycle("2026-10-07_B", base=tmp_path) is True
    assert store.cycle_captured("2026-10-07_B", base=tmp_path) is False
    assert store.clear_cycle("2026-10-07_B", base=tmp_path) is False


def test_prune_removes_stale_and_empty_dirs(tmp_path: Path) -> None:
    _seed_shot(tmp_path, "2020-01-01_old", old=True)
    _seed_shot(tmp_path, "2026-10-07_new")
    out = store.prune_screenshots(base=tmp_path)
    assert out["removed"] >= 1
    assert store.cycle_captured("2020-01-01_old", base=tmp_path) is False


def test_prune_enforces_size_cap(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(store, "MAX_BYTES", 100)
    _seed_shot(tmp_path, "2026-10-07_C")
    _seed_shot(tmp_path, "2026-10-07_D")
    out = store.prune_screenshots(base=tmp_path)
    assert out["removed"] >= 1


def test_delete_for_history_id(tmp_path: Path) -> None:
    shot = str(_seed_shot(tmp_path, "2026-10-07_E"))
    store.write_meta("2026-10-07_E", {"shots": [shot], "history_id": 42}, base=tmp_path)
    assert store.delete_screenshots_for_history_id(42, base=tmp_path) == 1
    assert Path(shot).exists() is False
