"""Wheel extraction: layout proof, marker, and the failure codes.

The install is only "complete" when the marker records every pinned
artifact by hash AND the DLLs a GPU backend needs are physically present.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from voice_typer.server.cuda_install import installer, paths
from voice_typer.server.cuda_install.installer import InstallError, install
from voice_typer.server.cuda_install.manifest import (
    REQUIRED_DLLS,
    REQUIRED_ORT_FILES,
    Artifact,
)


def _wheel(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return path


def _artifact(name: str = "cudart", filename: str = "fake-1.0-py3-none-win_amd64.whl") -> Artifact:
    return Artifact(
        key=name,
        filename=filename,
        url=f"https://example.invalid/{filename}",
        sha256="a" * 64,
        size=1234,
    )


def _full_payload() -> dict[str, bytes]:
    return {
        "nvidia/cublas/bin/cublas64_12.dll": b"x",
        "nvidia/cublas/bin/cublasLt64_12.dll": b"x",
        "nvidia/cudnn/bin/cudnn64_9.dll": b"x",
        "nvidia/cuda_runtime/bin/cudart64_12.dll": b"x",
        "nvidia/cuda_nvrtc/bin/nvrtc64_120_0.dll": b"x",
        "onnxruntime/capi/onnxruntime_providers_cuda.dll": b"x",
    }


def test_install_writes_every_dll_and_the_marker(
    cuda_home: Path, tmp_path: Path
) -> None:
    artifact = _artifact()
    wheel = _wheel(tmp_path / artifact.filename, _full_payload())

    install((artifact,), {artifact.key: wheel})

    root = paths.install_dir()
    assert (root / "nvidia/cublas/bin/cublas64_12.dll").is_file()
    assert (root / "onnxruntime/capi/onnxruntime_providers_cuda.dll").is_file()
    marker = json.loads((root / installer.MARKER_NAME).read_text(encoding="utf-8"))
    assert marker["artifacts"] == {artifact.filename: artifact.sha256}
    assert installer.is_installed((artifact,)) is True
    assert installer.verify_layout() == []


def test_marker_alone_is_not_enough(cuda_home: Path, tmp_path: Path) -> None:
    """A marker without the DLLs must not read as installed."""
    artifact = _artifact()
    root = paths.install_dir()
    root.mkdir(parents=True, exist_ok=True)
    (root / installer.MARKER_NAME).write_text(
        json.dumps({"artifacts": {artifact.filename: artifact.sha256}}),
        encoding="utf-8",
    )
    assert installer.is_installed((artifact,)) is True
    missing = installer.verify_layout()
    # Every required file is still reported missing.
    assert set(missing) == {*REQUIRED_DLLS, *REQUIRED_ORT_FILES}


def test_missing_dll_fails_the_install(cuda_home: Path, tmp_path: Path) -> None:
    payload = _full_payload()
    payload.pop("nvidia/cudnn/bin/cudnn64_9.dll")
    artifact = _artifact()
    wheel = _wheel(tmp_path / artifact.filename, payload)

    with pytest.raises(InstallError) as excinfo:
        install((artifact,), {artifact.key: wheel})
    assert excinfo.value.code == "incomplete_install"
    assert "cudnn64_9.dll" in excinfo.value.detail
    # Nothing is recorded as installed when the layout proof fails.
    assert installer.is_installed((artifact,)) is False


def test_missing_wheel_is_reported(cuda_home: Path) -> None:
    artifact = _artifact()
    with pytest.raises(InstallError) as excinfo:
        install((artifact,), {})
    assert excinfo.value.code == "missing_wheel"


def test_corrupt_wheel_is_reported(cuda_home: Path, tmp_path: Path) -> None:
    artifact = _artifact()
    bad = tmp_path / artifact.filename
    bad.write_bytes(b"not a zip")
    with pytest.raises(InstallError) as excinfo:
        install((artifact,), {artifact.key: bad})
    assert excinfo.value.code == "corrupt_wheel"


def test_path_traversal_member_is_refused(
    cuda_home: Path, tmp_path: Path
) -> None:
    artifact = _artifact()
    wheel = _wheel(
        tmp_path / artifact.filename,
        {"../escaped.dll": b"x"},
    )
    with pytest.raises(InstallError) as excinfo:
        install((artifact,), {artifact.key: wheel})
    assert excinfo.value.code == "unsafe_wheel_path"
    assert not (paths.cuda_root().parent / "escaped.dll").exists()


def test_empty_artifact_set_is_unsupported(cuda_home: Path) -> None:
    with pytest.raises(InstallError) as excinfo:
        install((), {})
    assert excinfo.value.code == "unsupported_runtime"


def test_is_installed_requires_matching_hashes(
    cuda_home: Path, tmp_path: Path
) -> None:
    artifact = _artifact()
    wheel = _wheel(tmp_path / artifact.filename, _full_payload())
    install((artifact,), {artifact.key: wheel})

    other = Artifact(
        key="other",
        filename="other-1.0-py3-none-win_amd64.whl",
        url="https://example.invalid/other.whl",
        sha256="b" * 64,
        size=1,
    )
    assert installer.is_installed((artifact,)) is True
    assert installer.is_installed((artifact, other)) is False
    assert installer.is_installed(()) is False
