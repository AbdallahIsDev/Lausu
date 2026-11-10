"""Install job service: single-flight, cancel, failure, completion.

No network and no real wheels: ``download`` / ``installer.install`` are
replaced, and the job's thread is awaited through its published snapshot.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from voice_typer.server import event_bus
from voice_typer.server.cuda_install import service as service_module
from voice_typer.server.cuda_install.downloader import CancelledError, DownloadError
from voice_typer.server.cuda_install.installer import InstallError
from voice_typer.server.cuda_install.manifest import Artifact
from voice_typer.server.cuda_install.service import CudaInstallService

ARTIFACT = Artifact(
    key="cudart",
    filename="fake-1.0-py3-none-win_amd64.whl",
    url="https://example.invalid/fake.whl",
    sha256="a" * 64,
    size=1024,
)


@pytest.fixture()
def published(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    events: list[dict] = []
    monkeypatch.setattr(event_bus, "publish", lambda event: events.append(event))
    return events


@pytest.fixture()
def svc(cuda_home: Path, monkeypatch: pytest.MonkeyPatch) -> CudaInstallService:
    """A service wired to the isolated install root and a fake wheel set."""
    monkeypatch.setattr(
        service_module, "artifacts_for_current_runtime", lambda: (ARTIFACT,)
    )
    monkeypatch.setattr(service_module, "is_windows", lambda: True)
    monkeypatch.setattr(service_module, "cuda_root", lambda: cuda_home)
    monkeypatch.setattr(service_module, "downloads_dir", lambda: cuda_home / "dl")
    monkeypatch.setattr(service_module, "verify_file", lambda *a, **k: False)
    monkeypatch.setattr(service_module.state, "write_pending", lambda names: None)
    monkeypatch.setattr(service_module.installer, "install", lambda *a, **k: None)
    (cuda_home / "dl").mkdir(parents=True, exist_ok=True)
    return CudaInstallService()


def _wait_status(svc: CudaInstallService, status: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = svc.snapshot()
        if snapshot["status"] == status:
            return snapshot
        time.sleep(0.01)
    raise AssertionError(
        f"job never reached {status!r}; last snapshot: {svc.snapshot()}"
    )


def _wait_thread(svc: CudaInstallService) -> None:
    thread = getattr(svc, "_thread", None)
    if thread is not None:
        thread.join(timeout=5)


def test_start_is_single_flight(
    svc: CudaInstallService, cuda_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = threading.Event()
    entered = threading.Event()
    calls: list[int] = []

    def blocking_download(*_a, **_k):
        calls.append(1)
        entered.set()
        gate.wait(timeout=5)
        raise CancelledError()

    monkeypatch.setattr(service_module, "download", blocking_download)

    first = svc.start()
    # Wait until the job's thread is genuinely inside the transfer, so the
    # second/third calls race a RUNNING job rather than a not-yet-started one.
    assert entered.wait(timeout=5)
    second = svc.start()
    third = svc.start()

    assert first["status"] == "downloading"
    assert second["status"] == "downloading"
    assert third["status"] == "downloading"
    # The job was started exactly once.
    assert len(calls) == 1
    gate.set()
    _wait_status(svc, "cancelled")
    _wait_thread(svc)


def test_cancel_reaches_the_download(
    svc: CudaInstallService, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = threading.Event()

    def slow_download(*_a, cancel: threading.Event | None = None, **_k):
        started.set()
        assert cancel is not None
        if cancel.wait(timeout=5):
            raise CancelledError()
        raise AssertionError("cancel never arrived")

    monkeypatch.setattr(service_module, "download", slow_download)

    svc.start()
    assert started.wait(timeout=5)
    snapshot = svc.cancel()
    assert snapshot["status"] == "downloading"

    final = _wait_status(svc, "cancelled")
    assert final["error"] is None
    _wait_thread(svc)


def test_cancel_is_a_noop_when_nothing_runs(svc: CudaInstallService) -> None:
    assert svc.cancel()["status"] == "idle"
    assert svc.is_running() is False


def test_download_failure_is_published_with_its_code(
    svc: CudaInstallService,
    published: list[dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_download(*_a, **_k):
        raise DownloadError("checksum_mismatch", ARTIFACT.filename)

    monkeypatch.setattr(service_module, "download", failing_download)

    svc.start()
    final = _wait_status(svc, "failed")
    assert final["error"] == "checksum_mismatch"
    _wait_thread(svc)
    assert any(
        event["type"] == "cuda_progress" and event["data"]["status"] == "failed"
        for event in published
    )


def test_install_failure_is_published_with_its_code(
    svc: CudaInstallService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        service_module, "download", lambda *a, **k: ARTIFACT.filename
    )
    monkeypatch.setattr(
        service_module.installer,
        "install",
        lambda *a, **k: (_ for _ in ()).throw(InstallError("incomplete_install")),
    )

    svc.start()
    final = _wait_status(svc, "failed")
    assert final["error"] == "incomplete_install"
    _wait_thread(svc)


def test_unexpected_exception_never_leaves_the_job_running(
    svc: CudaInstallService, monkeypatch: pytest.MonkeyPatch
) -> None:
    def exploding_download(*_a, **_k):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(service_module, "download", exploding_download)

    svc.start()
    final = _wait_status(svc, "failed")
    assert final["error"] == "internal"
    _wait_thread(svc)


def test_completed_job_stages_the_activation_record(
    svc: CudaInstallService, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged: list[list[str]] = []
    monkeypatch.setattr(
        service_module, "download", lambda *a, **k: ARTIFACT.filename
    )
    monkeypatch.setattr(service_module.state, "write_pending", staged.append)

    svc.start()
    final = _wait_status(svc, "completed")
    assert final["error"] is None
    assert final["percent"] == 100.0
    # The job never writes config.device: it stages the activation record
    # and the respawned sidecar proves the stack.
    assert staged == [[ARTIFACT.filename]]
    _wait_thread(svc)


def test_cached_verified_wheel_skips_the_transfer(
    svc: CudaInstallService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service_module, "verify_file", lambda *a, **k: True)

    def explode(*_a, **_k):
        raise AssertionError("a verified cached wheel must not be re-fetched")

    monkeypatch.setattr(service_module, "download", explode)

    svc.start()
    final = _wait_status(svc, "completed")
    assert final["percent"] == 100.0
    _wait_thread(svc)


def test_unsupported_platform_fails_fast(
    svc: CudaInstallService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service_module, "is_windows", lambda: False)
    snapshot = svc.start()
    assert snapshot["status"] == "failed"
    assert snapshot["error"] == "unsupported_platform"
    assert svc.is_running() is False


def test_unsupported_python_fails_fast(
    svc: CudaInstallService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        service_module, "artifacts_for_current_runtime", lambda: ()
    )
    snapshot = svc.start()
    assert snapshot["status"] == "failed"
    assert snapshot["error"] == "unsupported_python"


def test_snapshot_shape_matches_the_push_contract(svc: CudaInstallService) -> None:
    snapshot = svc.snapshot()
    assert set(snapshot) == {
        "status",
        "artifact",
        "artifact_index",
        "artifact_count",
        "bytes_done",
        "bytes_total",
        "percent",
        "speed_bps",
        "eta_seconds",
        "error",
    }
