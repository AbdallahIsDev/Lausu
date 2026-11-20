"""Network-free checks for the pinned win64 LGPL ffmpeg/ffprobe fetch."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "scripts" / "ffmpeg-lgpl-win64.json"
FETCH_SCRIPT = REPO_ROOT / "scripts" / "build" / "fetch_ffmpeg_lgpl_win64.sh"
NAMING_SCRIPT = REPO_ROOT / "scripts" / "build" / "artifact_names.py"

FORBIDDEN = ("--enable-gpl", "--enable-nonfree", "--enable-libx264", "--enable-libx265")
LGPL_CONFIG = (
    "  configuration: --prefix=/ffbuild/prefix --disable-debug --disable-w32threads "
    "--enable-pthreads --enable-libvorbis --enable-libopus --enable-libvpx "
    "--disable-libx264 --disable-libx265 --disable-fdk-aac"
)
BASH = shutil.which("bash") or shutil.which("bash.exe")


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def check_config(config: str) -> subprocess.CompletedProcess[str]:
    assert BASH is not None, "bash is required to exercise the fetch script gate"
    return subprocess.run(
        [BASH, str(FETCH_SCRIPT), "--check-config", config],
        capture_output=True,
        text=True,
        check=False,
    )


def test_manifest_exists():
    assert MANIFEST_PATH.is_file(), f"missing pinned manifest: {MANIFEST_PATH}"


def test_manifest_uses_immutable_tag():
    manifest = load_manifest()
    tag = manifest["release_tag"]
    assert tag != "latest"
    assert re.fullmatch(r"autobuild-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}", tag), tag
    for field in ("release_url", "download_url", "source_offer_url"):
        assert tag in manifest[field], field
        assert "latest" not in manifest[field], field


def test_manifest_sha256_is_64_hex():
    sha = load_manifest()["sha256"]
    assert re.fullmatch(r"[0-9a-fA-F]{64}", sha), sha


def test_manifest_download_url_is_pinned_asset():
    manifest = load_manifest()
    url = manifest["download_url"]
    assert url.endswith(manifest["asset_name"])
    assert f"/{manifest['release_tag']}/" in url
    assert manifest["asset_name"].endswith(".zip")
    assert "-lgpl" in manifest["asset_name"]
    assert "-gpl" not in manifest["asset_name"].replace("-lgpl", "")


def test_manifest_license_is_lgpl_only():
    license_id = load_manifest()["license"].upper()
    assert license_id.startswith("LGPL"), license_id
    assert "NONFREE" not in license_id


def test_manifest_forbidden_tokens():
    assert tuple(load_manifest()["forbidden_config_tokens"]) == FORBIDDEN


def test_manifest_version_and_source_offer():
    manifest = load_manifest()
    assert manifest["version"]
    assert manifest["ffmpeg_version"]
    assert manifest["source_offer_url"].startswith("https://")
    assert "FFmpeg-Builds" in manifest["source_offer_url"]


def test_manifest_pinned_configuration_if_verified_has_no_forbidden_tokens():
    config = load_manifest()["configuration"]
    if config.startswith("TODO"):
        pytest.skip("configuration not verified yet")
    for token in FORBIDDEN:
        assert token not in config.lower(), token


def test_install_names_follow_artifact_names_rules():
    spec = importlib.util.spec_from_file_location("artifact_names", NAMING_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    install_names = load_manifest()["install_names"]
    for tool in ("ffmpeg", "ffprobe"):
        name = install_names[tool]
        triple = module.SUPPORTED_TRIPLES[0]
        assert name == f"{tool}-{triple}{module._exe_suffix(triple)}"


@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_script_syntax():
    result = subprocess.run([BASH, "-n", str(FETCH_SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_gate_accepts_lgpl_configuration():
    result = check_config(LGPL_CONFIG)
    assert result.returncode == 0, result.stderr
    assert "accepted" in result.stdout


@pytest.mark.parametrize("token", FORBIDDEN)
@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_gate_rejects_each_forbidden_token(token: str):
    result = check_config(f"{LGPL_CONFIG} {token}")
    assert result.returncode == 1
    assert token in result.stderr


@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_gate_rejects_enable_libx264_spelling():
    result = check_config(LGPL_CONFIG + " --enable-libx264")
    assert result.returncode == 1
    assert "libx264" in result.stderr


@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_gate_accepts_disabled_x264_x265():
    result = check_config(LGPL_CONFIG)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_gate_rejects_uppercase_forbidden_token():
    result = check_config(LGPL_CONFIG + " --ENABLE-GPL")
    assert result.returncode == 1


@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_gate_accepts_disable_gpl_token():
    result = check_config(LGPL_CONFIG + " --disable-gpl")
    assert result.returncode == 0, result.stderr


def test_script_structure():
    source = FETCH_SCRIPT.read_text(encoding="utf-8")
    for token in FORBIDDEN:
        assert token in source
    for required in ("sha256sum", "-version", "-L", "--check-config", "check-ignore", "mktemp -d"):
        assert required in source, required
