"""Network-free checks for the pinned win64 LGPL ffmpeg-only fetch."""

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

MIRROR_URL = (
    "https://github.com/AbdallahIsDev/Lausu/releases/download/"
    "ffmpeg-lgpl-n9.0.2-20261120/ffmpeg-n9.0.2-61-gd59078794d-win64-lgpl-9.0.zip"
)
PINNED_SHA = "814c62c35ca7e2b15d85b0a2a5b79bbf21783176520154f26a6df1e9df72761e"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    assert BASH is not None, "bash is required to exercise the fetch script"
    return subprocess.run(
        [BASH, str(FETCH_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def check_config(config: str) -> subprocess.CompletedProcess[str]:
    return run_script("--check-config", config)


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
    # The pinned binary was built with --enable-version3 and `ffmpeg -L`
    # declares "GNU Lesser General Public License ... version 3 or later".
    assert license_id == "LGPL-3.0-OR-LATER", license_id


def test_manifest_version_is_release_branch():
    """A release-branch n9.0.x build, never a floating master snapshot."""
    manifest = load_manifest()
    assert re.fullmatch(r"n9\.0\.\d+-\d+-g[0-9a-f]+-20261120", manifest["version"]), manifest["version"]
    assert manifest["ffmpeg_version"].startswith(f"ffmpeg version {manifest['version']} ")
    assert manifest["asset_name"].startswith(f"ffmpeg-{manifest['version'].removesuffix('-20261120')}-")
    assert "9.0" in manifest["asset_name"]
    assert "N-" not in manifest["asset_name"]  # master snapshot naming, retired


def test_manifest_forbidden_tokens():
    assert tuple(load_manifest()["forbidden_config_tokens"]) == FORBIDDEN


def test_manifest_version_and_source_offer():
    manifest = load_manifest()
    assert manifest["version"]
    assert manifest["ffmpeg_version"]
    assert manifest["source_offer_url"].startswith("https://")
    assert "FFmpeg-Builds" in manifest["source_offer_url"]


def test_manifest_ffmpeg_only_no_ffprobe():
    """ffprobe is not shipped — duration probing parses ffmpeg's stderr."""
    manifest = load_manifest()
    assert manifest["component"] == "ffmpeg"
    assert set(manifest["install_names"]) == {"ffmpeg"}
    assert "ffprobe" not in manifest["asset_name"]
    assert manifest["install_names"]["ffmpeg"] == "ffmpeg-x86_64-pc-windows-msvc.exe"


def test_manifest_mirror_points_at_verified_release():
    """The mirror is the verified byte-identical copy, not a placeholder."""
    manifest = load_manifest()
    assert manifest["mirror_url"] == MIRROR_URL
    assert manifest["mirror_sha256"] == PINNED_SHA
    assert manifest["sha256"] == PINNED_SHA
    assert manifest["mirror_sha256"] == manifest["sha256"]


def test_manifest_mirror_sha256_is_64_hex():
    mirror_sha = load_manifest()["mirror_sha256"]
    assert re.fullmatch(r"[0-9a-fA-F]{64}", mirror_sha), mirror_sha


def test_manifest_mirror_url_is_pinned_asset():
    manifest = load_manifest()
    mirror = manifest["mirror_url"]
    assert mirror.startswith("https://github.com/")
    assert "/releases/download/" in mirror
    assert mirror.endswith(manifest["asset_name"])
    assert "latest" not in mirror.lower()
    assert not any(part in mirror for part in ("OWNER", "REPO", "TAG", "<", ">"))


def test_manifest_retention_note_documents_upstream_policy():
    note = load_manifest()["retention_note"].lower()
    assert "two years" in note and "last 14 daily" in note
    assert "latest" in note and "float" in note
    assert "mirror" in note and "fallback" in note


def test_manifest_configuration_has_verified_lgpl_tokens():
    """Pin the exact measured config: version3 on, x264/x265 disabled only."""
    config = load_manifest()["configuration"]
    for required in (
        "configuration:",
        "--enable-version3",
        "--disable-libx264",
        "--disable-libx265",
        "--extra-version=20261120",
    ):
        assert required in config, required
    for token in FORBIDDEN:
        assert token not in config.lower(), token


def test_manifest_archive_size_is_measured():
    assert load_manifest()["archive_size_bytes"] == 171850189


def test_manifest_ffmpeg_source_url_points_at_pinned_commit():
    assert load_manifest()["ffmpeg_source_url"] == "https://github.com/FFmpeg/FFmpeg/tree/d59078794d"


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
    assert set(install_names) == {"ffmpeg"}, "ffprobe is no longer shipped"
    for tool in install_names:
        name = install_names[tool]
        triple = module.SUPPORTED_TRIPLES[0]
        assert name == f"{tool}-{triple}{module._exe_suffix(triple)}"


@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_script_syntax():
    bash = BASH
    assert bash is not None, "bash is required to exercise the fetch script"
    result = subprocess.run([bash, "-n", str(FETCH_SCRIPT)], capture_output=True, text=True, check=False)
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
    for required in (
        "sha256sum",
        "archive_size_bytes",
        "wc -c",
        "-version",
        "-L",
        "--check-config",
        "check-ignore",
        "mktemp -d",
        "Lesser General Public License",
        'wanted = ("ffmpeg.exe",)',
    ):
        assert required in source, required
    assert "ffprobe.exe" not in source, "ffprobe must not be extracted or installed"


@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_gate_accepts_the_exact_pinned_configuration():
    """Round trip: the gate accepts the config string actually pinned in the manifest."""
    result = check_config(load_manifest()["configuration"])
    assert result.returncode == 0, result.stderr
    assert "accepted" in result.stdout


@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_gate_rejects_enable_libx264_even_when_disable_is_present():
    result = check_config(LGPL_CONFIG + " --disable-libx264 --enable-libx264")
    assert result.returncode == 1
    assert "--enable-libx264" in result.stderr


@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_gate_accepts_disable_fdk_aac_and_version3():
    result = check_config(LGPL_CONFIG + " --enable-version3 --disable-fdk-aac")
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(BASH is None, reason="bash is required to exercise the fetch script")
def test_fetch_plan_tries_mirror_before_fallback():
    """Pure network-free helper exposes the exact source order and hashes."""
    result = run_script("--fetch-plan")
    assert result.returncode == 0, result.stderr
    rows = [line.split("\t") for line in result.stdout.strip().splitlines()]
    assert [row[0] for row in rows] == ["mirror", "fallback"]
    assert rows[0][1] == MIRROR_URL
    assert rows[0][2] == PINNED_SHA
    assert rows[1][1] == load_manifest()["download_url"]
    assert rows[1][2] == PINNED_SHA


def test_script_fetch_order_and_auth_structure():
    source = FETCH_SCRIPT.read_text(encoding="utf-8")
    for required in (
        "--fetch-plan",
        "MIRROR_URL",
        "MIRROR_SHA",
        "download_asset",
        "archive_ok",
        "for label in mirror fallback; do",
        "gh release download",
        "gh auth status",
        "--repo",
        "--pattern",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "Authorization: Bearer $token",
        "FFMPEG_LOCAL_ARCHIVE",
        "neither mirror nor fallback",
    ):
        assert required in source, required


def test_script_license_gate_sample_strings():
    source = FETCH_SCRIPT.read_text(encoding="utf-8")
    assert "FORBIDDEN_TOKENS=(" + " ".join(FORBIDDEN) + ")" in source
    assert "config_gate" in source
    assert "grep -qiF --" in source
