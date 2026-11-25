"""The shared Chrome profile was renamed from a Google-only name.

The signed-in folder must be MOVED once, never recreated: a fresh folder would
lose the owner's sessions and the unpacked extension registration.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tools.internal_plugins._common.bridge import install_paths


@pytest.fixture
def roots(tmp_path, monkeypatch):
    root = tmp_path / "LocalAppData"
    (root / "voice-typer-internal-plugins").mkdir(parents=True)
    monkeypatch.setattr(install_paths, "data_root", lambda: root)
    legacy = root / Path(install_paths.LEGACY_PROFILE_RELATIVE_PATH)
    target = root / Path(install_paths.PROFILE_RELATIVE_PATH)
    return legacy, target


def test_legacy_profile_is_used_until_it_is_moved(roots):
    legacy, target = roots
    legacy.mkdir(parents=True)
    (legacy / "Secure Preferences").write_text("{}", encoding="utf-8")

    assert install_paths.profile_dir() == legacy
    assert install_paths.migrate_profile() is True
    assert install_paths.profile_dir() == target


def test_migration_moves_state_instead_of_recreating_it(roots):
    legacy, target = roots
    legacy.mkdir(parents=True)
    (legacy / "Secure Preferences").write_text('{"signed-in": true}', encoding="utf-8")

    assert install_paths.migrate_profile() is True
    assert not legacy.exists()
    assert (target / "Secure Preferences").read_text(encoding="utf-8") == '{"signed-in": true}'


def test_a_stale_config_cannot_launch_the_old_profile_path(roots, monkeypatch):
    from types import SimpleNamespace

    from tools.internal_plugins._common.bridge import session

    legacy, target = roots
    legacy.mkdir(parents=True)
    assert install_paths.migrate_profile() is True

    launches: list[tuple[str, str]] = []
    session.launch_profile_if_due(
        last_ts=0.0,
        config_fn=lambda: {"profileDir": str(legacy), "claudeUrl": "https://claude.ai/new"},
        launch_fn=lambda profile, url: launches.append((profile, url)) or True,
        clock=SimpleNamespace(monotonic=lambda: 100.0),
    )

    assert launches == [(str(target), "about:blank")]


def test_migration_is_idempotent_and_never_overwrites(roots):
    legacy, target = roots
    legacy.mkdir(parents=True)
    (legacy / "old").write_text("old", encoding="utf-8")
    target.mkdir(parents=True)
    (target / "new").write_text("new", encoding="utf-8")

    assert install_paths.migrate_profile() is False
    assert (target / "new").read_text(encoding="utf-8") == "new"
    assert legacy.exists()
