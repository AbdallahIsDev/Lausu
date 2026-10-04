"""Minimum-Python import floor: nothing may require 3.11+ typing names."""

from __future__ import annotations

import sys
from pathlib import Path


def test_download_helpers_avoids_notrequired():
    src = (
        Path(__file__).resolve().parent.parent
        / "voice_typer"
        / "server"
        / "service"
        / "_download_helpers.py"
    ).read_text(encoding="utf-8")
    assert "from typing import NotRequired" not in src
    assert "import NotRequired" not in src
    from voice_typer.server.service._download_helpers import DownloadOutcome

    assert DownloadOutcome.__total__ is False
    assert set(DownloadOutcome.__annotations__) >= {
        "success",
        "download_already_active",
        "queued",
        "queue_position",
    }


def test_dev_console_reexports_sys():
    from voice_typer.server.autostart import dev_console

    assert dev_console.sys is sys


def test_installer_state_reexports_sys():
    from voice_typer.server import installer_state

    assert installer_state.sys is sys
