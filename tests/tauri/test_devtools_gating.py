"""DevTools must reach developers in dev and never reach end users in release.

User decision: the WebView DevTools (F12 / Inspect, main AND bubble
windows) are a development aid. They are enabled by the local
``tauri dev`` wrapper and must stay out of every shipped installer.
The gate is the ``dev`` cargo feature (``tauri/devtools``); release
builds compile with default features only.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CARGO_TOML = PROJECT_ROOT / "src-tauri" / "Cargo.toml"
TAURI_DEV_MJS = PROJECT_ROOT / "voice_typer" / "client" / "scripts" / "tauri-dev.mjs"
WORKFLOWS_DIR = PROJECT_ROOT / ".github" / "workflows"


def test_devtools_behind_opt_in_dev_feature():
    text = CARGO_TOML.read_text(encoding="utf-8")
    assert 'dev = ["tauri/devtools"]' in text
    assert "default = []" in text


def test_default_dependency_set_excludes_devtools():
    """The base ``tauri`` dependency must not enable devtools unconditionally."""
    text = CARGO_TOML.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("tauri = ") and "features" in stripped:
            assert "devtools" not in stripped, f"base tauri dependency must not enable devtools: {stripped}"


def test_dev_workflow_enables_devtools():
    """Local ``tauri dev`` must pass the feature so F12/Inspect work in dev."""
    text = TAURI_DEV_MJS.read_text(encoding="utf-8")
    assert '"--features"' in text and '"dev"' in text


def test_no_release_build_enables_devtools():
    """No CI release build may compile the ``dev`` feature in."""
    offenders = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        for lineno, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"--features[= ]+[\"']?dev[\"']?", line):
                offenders.append(f"{workflow.name}:{lineno}: {line.strip()}")
    assert not offenders, "release workflows must not enable the dev feature:\n" + "\n".join(offenders)
