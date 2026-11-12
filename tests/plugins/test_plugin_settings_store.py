"""Plugin setting persistence: validation + round-trip.

Settings are written beside the manifest (``settings.json``) and never into
app config, so these tests own the whole contract: unknown keys and mistyped
or out-of-range values are rejected, undeclared entries are ignored on read,
and one accepted value survives a fresh discovery.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from voice_typer.server.plugins import get_plugin
from voice_typer.server.plugins.settings_store import (
    PluginSettingError,
    load_values,
    set_value,
)


@pytest.fixture
def plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    workspace = tmp_path / "internal_plugins"
    directory = workspace / "acme_stt"
    directory.mkdir(parents=True)
    (directory / "plugin.json").write_text(
        json.dumps(
            {
                "id": "acme_stt",
                "name": "Acme STT",
                "settings": [
                    {"key": "visible", "type": "bool", "label": "Show"},
                    {"key": "pollMs", "type": "int", "label": "Poll", "min": 50, "max": 1000},
                    {"key": "mode", "type": "enum", "label": "Mode", "choices": ["a", "b"]},
                    {"key": "label", "type": "string", "label": "Label"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VOICE_TYPER_PLUGINS_DIR", str(workspace))
    info = get_plugin("acme_stt")
    assert info is not None
    return info


def test_defaults_are_absent_until_written(plugin) -> None:
    assert load_values(plugin) == {}


def test_value_round_trips_through_the_store(plugin) -> None:
    assert set_value(plugin, "visible", False) is False
    assert set_value(plugin, "pollMs", 200) == 200
    assert load_values(plugin) == {"visible": False, "pollMs": 200}
    stored = json.loads((Path(plugin.directory) / "settings.json").read_text(encoding="utf-8"))
    assert stored == {"visible": False, "pollMs": 200}


def test_writes_merge_instead_of_replacing(plugin) -> None:
    set_value(plugin, "visible", True)
    set_value(plugin, "mode", "b")
    assert load_values(plugin) == {"visible": True, "mode": "b"}


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("missing", True),
        ("visible", 1),  # int is not a bool
        ("pollMs", True),  # bool is not an int
        ("pollMs", 10.5),  # int setting
        ("pollMs", 49),  # below min
        ("pollMs", 1001),  # above max
        ("mode", "c"),  # not a declared choice
        ("label", 7),
    ],
)
def test_invalid_writes_are_rejected(plugin, key: str, value: object) -> None:
    with pytest.raises(PluginSettingError):
        set_value(plugin, key, value)
    assert load_values(plugin) == {}


def test_undeclared_and_mistyped_entries_are_ignored_on_read(plugin) -> None:
    (Path(plugin.directory) / "settings.json").write_text(
        json.dumps({"visible": True, "removed_key": 1, "pollMs": "fast"}),
        encoding="utf-8",
    )
    assert load_values(plugin) == {"visible": True}


def test_corrupt_store_reads_as_empty(plugin) -> None:
    (Path(plugin.directory) / "settings.json").write_text("{not json", encoding="utf-8")
    assert load_values(plugin) == {}
