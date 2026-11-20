"""Packaging regressions for the sdist manifest (MANIFEST.in contents)."""

from __future__ import annotations

from pathlib import Path


class TestManifestIn:
    """PLAT-036: MANIFEST.in file exists in repo root."""

    def test_manifest_in_exists(self):
        repo_root = Path(__file__).resolve().parents[2]
        manifest_path = repo_root / "MANIFEST.in"
        assert manifest_path.exists(), "MANIFEST.in must exist in repo root"

    def test_manifest_in_includes_server(self):
        repo_root = Path(__file__).resolve().parents[2]
        manifest = (repo_root / "MANIFEST.in").read_text()
        assert "voice_typer/server" in manifest
        assert "LICENSE" in manifest
        assert "README.md" in manifest
