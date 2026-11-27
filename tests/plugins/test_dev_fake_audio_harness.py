"""The fake-audio harness is dev-only; production cannot launch with its flags."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from tools.internal_plugins._common.bridge import chrome_profile

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "scripts" / "dev" / "fake_audio_chrome.ps1"
FAKE_FLAGS = (
    "--use-fake-device-for-media-stream",
    "--use-file-for-fake-audio-capture=",
    "--use-fake-ui-for-media-stream",
)


def test_dev_harness_is_marker_gated_and_lives_outside_the_product():
    assert HARNESS.is_file()
    body = HARNESS.read_text(encoding="utf-8-sig")
    assert "DEVELOPER_DIAGNOSTICS" in body
    assert "VOICE_TYPER_FROZEN" in body
    assert "use-file-for-fake-audio-capture" in body
    assert "scripts" in HARNESS.relative_to(ROOT).parts


def test_production_launcher_cannot_emit_fake_audio_flags():
    body = (ROOT / "tools/internal_plugins/_common/bridge/chrome_profile.py").read_text(encoding="utf-8")
    for flag in FAKE_FLAGS:
        assert flag not in body
    for flag in FAKE_FLAGS:
        with pytest.raises(ValueError):
            chrome_profile._assert_plain(["--user-data-dir=x", flag, "about:blank"])


def test_packaging_sources_never_reference_the_dev_harness_or_fake_flags():
    sources = [
        ROOT / "scripts/build/stage_internal_plugins.py",
        ROOT / "scripts/build/build_sidecar_windows.sh",
        ROOT / "scripts/build/build_sidecar_macos.sh",
        ROOT / "scripts/build/build_sidecar_linux.sh",
        ROOT / "tools/internal_plugins/_common/bridge/chrome_profile.py",
    ]
    for path in sources:
        body = path.read_text(encoding="utf-8", errors="ignore")
        assert "fake_audio_chrome" not in body, path
        for flag in FAKE_FLAGS:
            assert flag not in body, (path, flag)


def test_dev_command_channel_is_absent_in_a_frozen_build(monkeypatch):
    from voice_typer.server import plugin_dev_driver

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert plugin_dev_driver.enabled(SimpleNamespace()) is False
