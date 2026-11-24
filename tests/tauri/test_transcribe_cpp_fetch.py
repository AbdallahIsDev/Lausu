"""Pinned runner manifest + fetch-script tests (no network, no download)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "scripts" / "transcribe-cpp-win64.json"
FETCH = ROOT / "scripts" / "build" / "fetch_transcribe_cpp_win64.sh"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_has_real_pinned_asset() -> None:
    data = _manifest()
    assert data["version"] == "0.4.2"
    assert data["asset_name"] == "transcribe-native-0.4.2-windows-x86_64-cpu-vulkan.tar.gz"
    assert data["archive_size_bytes"] == 18052817
    assert re.fullmatch(r"[0-9a-f]{64}", data["sha256"])
    assert data["sha256"] == "6094102cf57b404b050707ceb258b12ce647b92e801b5d46077214e5b030c8aa"
    assert data["download_url"].endswith(data["asset_name"])
    assert data["license"] == "MIT"
    assert data["install_dir"] == "src-tauri/resources/transcribe-cpp"


def test_manifest_carries_source_offer_fields() -> None:
    data = _manifest()
    for key in ("source_offer_url", "build_scripts_source_url", "upstream_repo_url", "install_names"):
        assert data.get(key), key
    assert "transcribe.dll" in data["install_names"]
    assert "contract.json" not in data["install_names"]  # copied separately by the fetch script


def test_fetch_script_gates_hash_and_size() -> None:
    script = FETCH.read_text(encoding="utf-8")
    assert "sha256" in script
    assert "EXPECTED_SIZE" in script
    assert "ACTUAL_SIZE" in script
    assert "curl -fsSL" in script
    assert "tar -xzf" in script
    # No bypasses, no model downloads, no CI-only assumptions.
    assert "|| true" not in script
    assert "continue-on-error" not in script
    assert not re.search(r"\.gguf", script)
    assert "hf_hub_download" not in script
