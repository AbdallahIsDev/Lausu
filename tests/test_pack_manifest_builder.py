"""Runtime-pack manifest builder (scripts/release/build_pack_manifest.py).

Pins the §4.6 OfflinePackManifest round-trip: a manifest this builder emits
must be accepted by the SAME validator the download-install path uses
(``load_offline_pack_manifest`` / ``validate_offline_pack_manifest_dict``),
and its ``files``/``sha256`` must match the zip it describes.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "scripts" / "release") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "release"))

import build_pack_manifest as bpm  # noqa: E402
from voice_typer.server.service.offline_pack import (  # noqa: E402
    load_offline_pack_manifest,
    validate_offline_pack_manifest_dict,
)

WORKER_NAME = "lausu-worker-x86_64-pc-windows-msvc.exe"
WORKER_BYTES = b"fake-worker-binary-contents"


def _make_pack_zip(
    tmp_path: Path,
    *,
    name: str = "lausu-runtime-pack-3-x86_64-pc-windows-msvc.zip",
    members: dict[str, bytes] | None = None,
) -> Path:
    """Write a runtime-pack zip whose members default to the worker binary."""
    zip_path = tmp_path / name
    contents = members if members is not None else {WORKER_NAME: WORKER_BYTES}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for member, data in contents.items():
            zf.writestr(member, data)
    return zip_path


class TestBuildPackManifest:
    """``build_pack_manifest`` output shape + integrity fields."""

    def test_manifest_fields_describe_the_zip(self, tmp_path: Path):
        zip_path = _make_pack_zip(tmp_path)
        manifest = bpm.build_pack_manifest(zip_path, version="3")

        assert manifest["version"] == "3"
        assert manifest["min_proto_version"] == bpm.DEFAULT_MIN_PROTO_VERSION
        # Top-level sha256 is the ARCHIVE hash (download_offline_pack_with_resume).
        assert manifest["sha256"] == hashlib.sha256(zip_path.read_bytes()).hexdigest()
        assert manifest["files"] == [
            {
                "name": WORKER_NAME,
                "sha256": hashlib.sha256(WORKER_BYTES).hexdigest(),
                "size": len(WORKER_BYTES),
            }
        ]

    def test_files_skip_directory_entries(self, tmp_path: Path):
        zip_path = tmp_path / "pack.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("sub/", b"")
            zf.writestr("sub/inner.bin", b"inner")
        manifest = bpm.build_pack_manifest(zip_path, version="3")
        assert [f["name"] for f in manifest["files"]] == ["sub/inner.bin"]

    def test_multi_member_zip_lists_every_file(self, tmp_path: Path):
        members = {WORKER_NAME: WORKER_BYTES, "libextra.bin": b"extra-bytes"}
        zip_path = _make_pack_zip(tmp_path, members=members)
        manifest = bpm.build_pack_manifest(zip_path, version="3")
        assert {f["name"] for f in manifest["files"]} == set(members)

    def test_min_proto_version_override(self, tmp_path: Path):
        zip_path = _make_pack_zip(tmp_path)
        manifest = bpm.build_pack_manifest(zip_path, version="3", min_proto_version=2)
        assert manifest["min_proto_version"] == 2


class TestBuildPackManifestRejections:
    """Unusable archives must raise before anything is written."""

    def test_missing_zip_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="not found"):
            bpm.build_pack_manifest(tmp_path / "nope.zip", version="3")

    def test_empty_version_raises(self, tmp_path: Path):
        zip_path = _make_pack_zip(tmp_path)
        with pytest.raises(ValueError, match="version"):
            bpm.build_pack_manifest(zip_path, version="")

    def test_empty_archive_raises(self, tmp_path: Path):
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_path, "w"):
            pass
        with pytest.raises(ValueError, match="no files"):
            bpm.build_pack_manifest(zip_path, version="3")

    def test_path_traversal_member_raises(self, tmp_path: Path):
        zip_path = _make_pack_zip(tmp_path, members={"../escape.bin": b"x"})
        with pytest.raises(ValueError, match="unsafe archive member"):
            bpm.build_pack_manifest(zip_path, version="3")

    def test_embedded_manifest_member_raises(self, tmp_path: Path):
        zip_path = _make_pack_zip(
            tmp_path,
            members={WORKER_NAME: WORKER_BYTES, "pack-manifest.json": b"{}"},
        )
        with pytest.raises(ValueError, match="pack-manifest.json"):
            bpm.build_pack_manifest(zip_path, version="3")

    def test_oversized_member_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(bpm, "OFFLINE_PACK_MAX_PER_FILE_BYTES", 8)
        zip_path = _make_pack_zip(tmp_path, members={"big.bin": b"0123456789"})
        with pytest.raises(ValueError, match="per-file cap"):
            bpm.build_pack_manifest(zip_path, version="3")


class TestSchemaRoundTrip:
    """The exact acceptance gate from the task: publisher-emitted manifest
    must pass ``load_offline_pack_manifest`` / ``validate_offline_pack_manifest_dict``."""

    def test_emitted_manifest_passes_validate_offline_pack_manifest_dict(self, tmp_path: Path):
        zip_path = _make_pack_zip(tmp_path)
        manifest = bpm.build_pack_manifest(zip_path, version="3")

        validated = validate_offline_pack_manifest_dict(dict(manifest), source="builder")
        assert validated is not None, "builder-emitted manifest rejected by the client validator"
        assert dict(validated) == dict(manifest)

    def test_written_manifest_passes_load_offline_pack_manifest(self, tmp_path: Path):
        zip_path = _make_pack_zip(tmp_path)
        manifest = bpm.build_pack_manifest(zip_path, version="3")
        out = bpm.write_pack_manifest(manifest, tmp_path / "pack-manifest.json")

        loaded = load_offline_pack_manifest(out)
        assert loaded is not None, "written pack-manifest.json rejected by load_offline_pack_manifest"
        assert dict(loaded) == dict(manifest)

    def test_written_manifest_is_parseable_json_with_expected_keys(self, tmp_path: Path):
        zip_path = _make_pack_zip(tmp_path)
        manifest = bpm.build_pack_manifest(zip_path, version="3")
        out = bpm.write_pack_manifest(manifest, tmp_path / "pack-manifest.json")

        data = json.loads(out.read_text(encoding="utf-8"))
        assert set(data) == {"version", "sha256", "files", "min_proto_version"}
        assert data["version"] == "3"
        assert len(data["sha256"]) == 64
        assert all({"name", "sha256", "size"} <= set(f) for f in data["files"])

    @pytest.mark.parametrize("version", ["1", "3", "42"])
    def test_integer_pack_versions_round_trip(self, tmp_path: Path, version: str):
        """Integer pack versions (the §11.9 naming rule) all validate."""
        zip_path = _make_pack_zip(tmp_path)
        manifest = bpm.build_pack_manifest(zip_path, version=version)
        out = bpm.write_pack_manifest(manifest, tmp_path / "pack-manifest.json")
        assert load_offline_pack_manifest(out) is not None


class TestCli:
    """The CLI entry point (used by the publish workflow)."""

    def test_main_writes_manifest(self, tmp_path: Path):
        zip_path = _make_pack_zip(tmp_path)
        out = tmp_path / "out" / "pack-manifest.json"
        rc = bpm.main(["--zip", str(zip_path), "--pack-version", "3", "--output", str(out)])
        assert rc == 0
        assert out.is_file()
        assert load_offline_pack_manifest(out) is not None

    def test_main_bad_zip_returns_2(self, tmp_path: Path):
        rc = bpm.main(["--zip", str(tmp_path / "missing.zip"), "--pack-version", "3"])
        assert rc == 2

    def test_main_default_output_is_pack_manifest_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        zip_path = _make_pack_zip(tmp_path)
        monkeypatch.chdir(tmp_path)
        rc = bpm.main(["--zip", str(zip_path), "--pack-version", "3"])
        assert rc == 0
        assert (tmp_path / "pack-manifest.json").is_file()
