"""Shared fixtures for the CUDA-install test package.

Every test redirects the install root at a ``tmp_path`` so nothing touches
the real app-data directory, and nothing is ever downloaded from the
network: the downloader tests drive ``urllib`` through an in-memory fake.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from voice_typer.server.cuda_install import paths


@pytest.fixture()
def cuda_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the whole ``cuda_install`` package at an isolated directory."""
    root = tmp_path / "cuda"
    monkeypatch.setattr(paths, "config_dir", lambda: tmp_path)
    root.mkdir(parents=True, exist_ok=True)
    return root
