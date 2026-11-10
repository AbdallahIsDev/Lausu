"""Activation: prove the stack, then persist ``cuda``; never lie.

Also pins the two correctness fixes that make the automatic switch work at
all:

* ``_reset_probes`` must drop the cached ``gpu_capability`` verdict, and
  must evict an ``onnxruntime`` imported BEFORE the install existed (the
  sidecar pre-warms that probe on a background thread, so the CPU-only
  wheel otherwise owns the module name for the whole process).
* The CPU-retention guard refuses ``set_config {device: "cuda"}`` while the
  job runs or the stack is not ready.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from voice_typer.server import gpu_capability
from voice_typer.server.cuda_install import activation, paths, state


class _FakeConfig:
    def __init__(self, device: str = "cpu", save_result: bool = True) -> None:
        self.device = device
        self._save_result = save_result
        self.saved = 0

    def save(self) -> bool:
        self.saved += 1
        return self._save_result


class _FakeApp:
    def __init__(self, device: str = "cpu", save_result: bool = True) -> None:
        self.config = _FakeConfig(device, save_result)
        self._config_mutation_lock = None


# The exact live shape on the owner's machine: CTranslate2 sees the GPU, the
# installed onnxruntime is the CPU-only wheel. `state` is still `gpu_ready`
# and `cuda_ready` is still True, which is precisely why neither may be used
# as a decision signal.
MIXED_BACKENDS: list[dict] = [
    {"name": "whisper", "local": True, "gpu_capable": True, "gpu_ready": True, "detail": "ready"},
    {"name": "parakeet", "local": True, "gpu_capable": True, "gpu_ready": False, "detail": "cuda_missing"},
    {"name": "qwen", "local": True, "gpu_capable": False, "gpu_ready": False, "detail": "cpu_only_backend"},
    {"name": "cloud", "local": False, "gpu_capable": False, "gpu_ready": False, "detail": "not_local"},
]

MIXED_BACKENDS_ALL_READY: list[dict] = [
    {**entry, "gpu_ready": True, "detail": "ready"} if entry["gpu_capable"] else entry
    for entry in MIXED_BACKENDS
]


def _mixed_snapshot(active_backend: str | None = None, **_kw: object) -> dict:
    """A faithful stand-in for ``gpu_capability.snapshot`` in the live state."""
    ready = any(
        entry["name"] == active_backend and entry["gpu_ready"]
        for entry in MIXED_BACKENDS
    )
    return {
        "state": "gpu_ready",
        "cuda_ready": True,
        "stack_complete": False,
        "backends": MIXED_BACKENDS,
        "active_backend": active_backend,
        "active_backend_gpu_ready": ready if active_backend else False,
    }


@pytest.fixture()
def ready_stack(cuda_home: Path, monkeypatch: pytest.MonkeyPatch):
    """Pretend the install is on sys.path and reports CUDA-ready."""
    monkeypatch.setattr(paths, "install_dir", lambda: cuda_home / "site-packages")
    (cuda_home / "site-packages").mkdir(parents=True, exist_ok=True)
    # Never mutate the real ``sys.path`` from a unit test.
    monkeypatch.setattr(activation, "ensure_install_on_sys_path", lambda: True)
    monkeypatch.setattr(
        gpu_capability,
        "snapshot",
        lambda **_: {
            "state": "gpu_ready",
            "cuda_ready": True,
            "stack_complete": True,
            "backends": MIXED_BACKENDS_ALL_READY,
            "active_backend": None,
            "active_backend_gpu_ready": True,
        },
    )
    return cuda_home


@pytest.fixture()
def published(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    from voice_typer.server import event_bus

    events: list[dict] = []
    monkeypatch.setattr(event_bus, "publish", lambda event: events.append(event))
    return events


def test_no_pending_record_is_a_noop(cuda_home: Path) -> None:
    app = _FakeApp()
    assert activation.apply_pending_activation(app) is False
    assert app.config.saved == 0


def test_activation_persists_cuda_when_the_stack_is_ready(
    ready_stack: Path, published: list[dict]
) -> None:
    state.write_pending(["fake.whl"])
    app = _FakeApp()

    assert activation.apply_pending_activation(app) is True
    assert app.config.device == "cuda"
    assert app.config.saved == 1
    # The record is cleared and the renderer is told.
    assert state.read() is None
    assert any(event["type"] == "config_changed" for event in published)


def test_activation_keeps_cpu_when_the_stack_is_not_ready(
    cuda_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths, "install_dir", lambda: cuda_home / "site-packages")
    (cuda_home / "site-packages").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(activation, "ensure_install_on_sys_path", lambda: True)
    monkeypatch.setattr(
        gpu_capability,
        "snapshot",
        lambda **_: {
            "state": "gpu_present_cuda_missing",
            "cuda_ready": False,
            "stack_complete": False,
            "backends": MIXED_BACKENDS,
            "active_backend": None,
            "active_backend_gpu_ready": False,
        },
    )
    state.write_pending(["fake.whl"])
    app = _FakeApp()

    assert activation.apply_pending_activation(app) is False
    assert app.config.device == "cpu"
    assert app.config.saved == 0
    record = state.read()
    assert record is not None
    assert record["state"] == state.FAILED
    assert record["reason"] == activation.REASON_NOT_READY


def test_activation_records_a_persist_failure(ready_stack: Path) -> None:
    state.write_pending(["fake.whl"])
    app = _FakeApp(save_result=False)

    assert activation.apply_pending_activation(app) is False
    assert app.config.device == "cuda"  # in-memory flip happened…
    record = state.read()
    assert record is not None
    assert record["reason"] == activation.REASON_PERSIST_FAILED


def test_acknowledge_clears_a_failure_record(cuda_home: Path) -> None:
    state.write_failure(activation.REASON_NOT_READY)
    assert state.read() is not None
    activation.acknowledge()
    assert state.read() is None


def test_reset_probes_drops_the_capability_cache(
    ready_stack: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}
    real_reset = gpu_capability.reset_cache

    def counting_reset() -> None:
        calls["n"] += 1
        real_reset()

    monkeypatch.setattr(gpu_capability, "reset_cache", counting_reset)
    activation._reset_probes()
    # Without this the 30 s snapshot TTL would keep a pre-install
    # `cuda_missing` verdict alive for the rest of the process.
    assert calls["n"] == 1


def test_reset_probes_evicts_a_stale_cpu_only_onnxruntime(
    ready_stack: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ordering hazard the respawned sidecar actually hits.

    ``device_caps`` imports ``onnxruntime`` through ``importlib`` during the
    early probe pre-warm (``ipc/entrypoint.py`` spawns that on a background
    thread). ``importlib.import_module`` returns the cached module from
    ``sys.modules`` regardless of ``sys.path``, so without the eviction the
    freshly installed GPU wheel can never be seen.
    """
    install_dir = paths.install_dir()
    stale_dir = install_dir.parent / "python-site-packages"
    stale_dir.mkdir(parents=True, exist_ok=True)
    stale = types.ModuleType("onnxruntime")
    stale.__file__ = str(stale_dir / "onnxruntime" / "__init__.py")
    child = types.ModuleType("onnxruntime.capi")
    child.__file__ = str(stale_dir / "onnxruntime" / "capi" / "__init__.py")
    monkeypatch.setitem(sys.modules, "onnxruntime", stale)
    monkeypatch.setitem(sys.modules, "onnxruntime.capi", child)
    monkeypatch.setattr(
        paths, "ensure_install_on_sys_path", lambda: True
    )
    sys.path.insert(0, str(install_dir))
    try:
        activation._reset_probes()
    finally:
        sys.path.remove(str(install_dir))
    assert "onnxruntime" not in sys.modules
    assert "onnxruntime.capi" not in sys.modules


def test_reset_probes_keeps_an_onnxruntime_from_the_install(
    ready_stack: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = paths.install_dir()
    good = types.ModuleType("onnxruntime")
    good.__file__ = str(install_dir / "onnxruntime" / "__init__.py")
    monkeypatch.setitem(sys.modules, "onnxruntime", good)
    sys.path.insert(0, str(install_dir))
    try:
        activation._reset_probes()
    finally:
        sys.path.remove(str(install_dir))
    # Already resolved through the install: keep it, re-importing a live ORT
    # session would be pointless churn.
    assert sys.modules.get("onnxruntime") is good


def test_reset_probes_is_a_noop_without_an_install(
    cuda_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths, "install_dir", lambda: cuda_home / "missing")
    stale = types.ModuleType("onnxruntime")
    stale.__file__ = "C:/elsewhere/onnxruntime/__init__.py"
    monkeypatch.setitem(sys.modules, "onnxruntime", stale)
    activation._reset_probes()
    # Nothing to resolve to, so nothing is evicted.
    assert sys.modules.get("onnxruntime") is stale


# ── CPU-retention guard ──────────────────────────────────────────────


def test_guard_allows_a_cpu_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from voice_typer.server.handlers.cuda_handlers import device_request_rejection

    assert device_request_rejection({"device": "cpu"}) is None
    assert device_request_rejection({"language": "en"}) is None


def test_guard_refuses_cuda_while_the_job_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from voice_typer.server.cuda_install.service import get_service
    from voice_typer.server.handlers.cuda_handlers import (
        REJECT_DOWNLOAD_RUNNING,
        device_request_rejection,
    )

    monkeypatch.setattr(get_service(), "is_running", lambda: True)
    assert device_request_rejection({"device": "cuda"}) == REJECT_DOWNLOAD_RUNNING


def test_guard_refuses_cuda_when_the_stack_is_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from voice_typer.server.cuda_install.service import get_service
    from voice_typer.server.handlers.cuda_handlers import (
        REJECT_STACK_NOT_READY,
        device_request_rejection,
    )

    monkeypatch.setattr(get_service(), "is_running", lambda: False)
    monkeypatch.setattr(
        gpu_capability,
        "snapshot",
        lambda **_: {
            "state": "gpu_present_cuda_missing",
            "cuda_ready": False,
            "stack_complete": False,
            "backends": MIXED_BACKENDS,
            "active_backend": None,
            "active_backend_gpu_ready": False,
        },
    )
    assert device_request_rejection({"device": "cuda"}) == REJECT_STACK_NOT_READY


def test_guard_allows_cuda_when_the_stack_is_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from voice_typer.server.cuda_install.service import get_service
    from voice_typer.server.handlers.cuda_handlers import device_request_rejection

    monkeypatch.setattr(get_service(), "is_running", lambda: False)
    monkeypatch.setattr(
        gpu_capability,
        "snapshot",
        lambda **_: {
            "state": "gpu_ready",
            "cuda_ready": True,
            "stack_complete": True,
            "backends": MIXED_BACKENDS_ALL_READY,
            "active_backend": None,
            "active_backend_gpu_ready": True,
        },
    )
    assert device_request_rejection({"device": "cuda"}) is None


# ── Mixed state: the live "Whisper ready, ORT not" case ──────────────


def test_activation_refuses_the_mixed_state(
    cuda_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CUDA set that fixes CTranslate2 but not ORT must not flip the device.

    ``cuda_ready`` is True here, so the old gate would have persisted
    ``cuda`` on Whisper alone and left a Parakeet user on a silent CPU
    fallback.
    """
    monkeypatch.setattr(paths, "install_dir", lambda: cuda_home / "site-packages")
    (cuda_home / "site-packages").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(activation, "ensure_install_on_sys_path", lambda: True)
    monkeypatch.setattr(gpu_capability, "snapshot", _mixed_snapshot)
    state.write_pending(["fake.whl"])
    app = _FakeApp()

    assert activation.apply_pending_activation(app) is False
    assert app.config.device == "cpu"
    assert app.config.saved == 0
    record = state.read()
    assert record is not None
    assert record["reason"] == activation.REASON_NOT_READY


def test_activation_passes_the_active_backend_into_the_probe(
    cuda_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    def capture(*, active_backend=None, refresh=False):
        seen["active_backend"] = active_backend
        seen["refresh"] = refresh
        return _mixed_snapshot(active_backend=active_backend)

    monkeypatch.setattr(paths, "install_dir", lambda: cuda_home / "site-packages")
    (cuda_home / "site-packages").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(activation, "ensure_install_on_sys_path", lambda: True)
    monkeypatch.setattr(gpu_capability, "snapshot", capture)
    state.write_pending(["fake.whl"])
    app = _FakeApp()
    app.config.asr_backend = "parakeet"

    activation.apply_pending_activation(app)
    assert seen["active_backend"] == "parakeet"
    # A finished install must re-probe, never trust the 30 s cache.
    assert seen["refresh"] is True


def test_guard_refuses_cuda_for_the_unready_active_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from voice_typer.server.cuda_install.service import get_service
    from voice_typer.server.handlers.cuda_handlers import (
        REJECT_STACK_NOT_READY,
        device_request_rejection,
    )

    monkeypatch.setattr(get_service(), "is_running", lambda: False)
    monkeypatch.setattr(gpu_capability, "snapshot", _mixed_snapshot)
    parakeet = _FakeConfig()
    parakeet.asr_backend = "parakeet"
    assert (
        device_request_rejection({"device": "cuda"}, parakeet)
        == REJECT_STACK_NOT_READY
    )


def test_guard_allows_cuda_for_a_ready_active_backend_in_the_mixed_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whisper is ready, so a Whisper user may switch even though ORT is not."""
    from voice_typer.server.cuda_install.service import get_service
    from voice_typer.server.handlers.cuda_handlers import device_request_rejection

    monkeypatch.setattr(get_service(), "is_running", lambda: False)
    monkeypatch.setattr(gpu_capability, "snapshot", _mixed_snapshot)
    whisper = _FakeConfig()
    whisper.asr_backend = "whisper"
    assert device_request_rejection({"device": "cuda"}, whisper) is None


def test_guard_allows_cuda_for_a_cpu_only_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Qwen is pinned to CPU by design: `device` is a global preference."""
    from voice_typer.server.cuda_install.service import get_service
    from voice_typer.server.handlers.cuda_handlers import device_request_rejection

    monkeypatch.setattr(get_service(), "is_running", lambda: False)
    monkeypatch.setattr(gpu_capability, "snapshot", _mixed_snapshot)
    qwen = _FakeConfig()
    qwen.asr_backend = "qwen"
    assert device_request_rejection({"device": "cuda"}, qwen) is None


def test_guard_without_a_config_uses_the_whole_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from voice_typer.server.cuda_install.service import get_service
    from voice_typer.server.handlers.cuda_handlers import (
        REJECT_STACK_NOT_READY,
        device_request_rejection,
    )

    monkeypatch.setattr(get_service(), "is_running", lambda: False)
    monkeypatch.setattr(gpu_capability, "snapshot", _mixed_snapshot)
    # No backend information: only a complete stack can vouch for `cuda`.
    assert device_request_rejection({"device": "cuda"}) == REJECT_STACK_NOT_READY
