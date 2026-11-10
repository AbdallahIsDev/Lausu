"""GPU capability: the four states + per-backend readiness.

The UI branches on exactly these four states, so each one is pinned here.
"GPU works" is deliberately NOT global: CTranslate2 (Whisper) needs
cuBLAS/cuDNN while the ONNX backends need a CUDA-enabled onnxruntime, and
Qwen is pinned to CPU by design.
"""

from __future__ import annotations

import pytest
from voice_typer.server import gpu_capability


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    gpu_capability.reset_cache()
    yield
    gpu_capability.reset_cache()


def _patch_probes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    smi: list[str] | None = None,
    driver: bool = False,
    adapter: bool = False,
    whisper_ready: bool = False,
    ort_ready: bool = False,
) -> None:
    monkeypatch.setattr(gpu_capability, "_nvidia_smi_gpus", lambda: smi or [])
    monkeypatch.setattr(gpu_capability, "_driver_present", lambda: driver)
    monkeypatch.setattr(gpu_capability, "_adapter_present", lambda: adapter)
    monkeypatch.setattr(
        gpu_capability, "_ort_cuda_available", lambda: ort_ready
    )

    from voice_typer.server import device_caps

    monkeypatch.setattr(device_caps, "gpu_available", lambda **_: whisper_ready)

    # Never read the real app-data install marker from a unit test.
    from voice_typer.server.cuda_install import installer

    monkeypatch.setattr(installer, "is_installed", lambda _artifacts: False)


def test_no_nvidia_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_probes(monkeypatch)
    snap = gpu_capability.snapshot(refresh=True)
    assert snap["state"] == gpu_capability.NO_GPU
    assert snap["hardware_present"] is False
    assert snap["driver_present"] is False
    assert snap["cuda_ready"] is False
    # Nothing to offer: the sidebar control must stay hidden.
    assert snap["download"]["reason"] == "no_gpu"


def test_driver_missing_when_adapter_exists_without_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_probes(monkeypatch, adapter=True, driver=False)
    snap = gpu_capability.snapshot(refresh=True)
    assert snap["state"] == gpu_capability.DRIVER_MISSING
    # Hardware IS present: the dialog explains the driver gap instead of
    # hiding the control.
    assert snap["hardware_present"] is True
    assert snap["driver_present"] is False
    # Backends are never probed without a driver.
    assert all(
        entry["detail"] == "no_gpu"
        for entry in snap["backends"]
        if entry["gpu_capable"]
    )
    assert snap["driver_url"].startswith("https://www.nvidia.com/")


def test_gpu_present_cuda_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_probes(
        monkeypatch, smi=["GPU 0: NVIDIA GeForce RTX 4070"], driver=True
    )
    snap = gpu_capability.snapshot(refresh=True)
    assert snap["state"] == gpu_capability.CUDA_MISSING
    assert snap["cuda_ready"] is False
    assert snap["gpu_names"] == ["GPU 0: NVIDIA GeForce RTX 4070"]
    assert all(entry["detail"] == "cuda_missing" for entry in snap["backends"] if entry["gpu_capable"])


def test_gpu_ready_when_one_backend_can_serve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_probes(monkeypatch, driver=True, whisper_ready=True)
    snap = gpu_capability.snapshot(refresh=True)
    assert snap["state"] == gpu_capability.READY
    assert snap["cuda_ready"] is True
    # "Any backend" is true, the honest whole-stack signal is not.
    assert snap["stack_complete"] is False


def test_stack_complete_requires_both_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_probes(monkeypatch, driver=True, whisper_ready=True, ort_ready=True)
    snap = gpu_capability.snapshot(refresh=True)
    assert snap["cuda_ready"] is True
    assert snap["stack_complete"] is True

    gpu_capability.reset_cache()
    _patch_probes(monkeypatch, driver=True, whisper_ready=False, ort_ready=True)
    snap = gpu_capability.snapshot(refresh=True)
    assert snap["cuda_ready"] is True
    assert snap["stack_complete"] is False


def test_mixed_state_is_not_mistaken_for_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact live case: CTranslate2 sees the GPU, ORT is the CPU wheel.

    `state` is `gpu_ready` and `cuda_ready` is True, so any gate using them
    lets a Parakeet user write `device: "cuda"` with no modal and a silent
    CPU fallback. The honest signals must both say "not for this backend".
    """
    _patch_probes(monkeypatch, driver=True, whisper_ready=True, ort_ready=False)
    snap = gpu_capability.snapshot(active_backend="parakeet", refresh=True)
    assert snap["state"] == gpu_capability.READY
    assert snap["cuda_ready"] is True
    assert snap["stack_complete"] is False
    assert snap["active_backend"] == "parakeet"
    assert snap["active_backend_gpu_ready"] is False
    assert gpu_capability.backend_ready(snap["backends"], "whisper") is True
    assert gpu_capability.backend_ready(snap["backends"], "parakeet") is False


def test_backend_ready_fails_closed_for_unknown_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_probes(monkeypatch, driver=True, whisper_ready=True, ort_ready=True)
    backends = gpu_capability.snapshot(refresh=True)["backends"]
    assert gpu_capability.backend_ready(backends, "whisper") is True
    assert gpu_capability.backend_ready(backends, "parakeet") is True
    # Qwen is CPU-only by design, and a typo must not read as "ready".
    assert gpu_capability.backend_ready(backends, "qwen") is False
    assert gpu_capability.backend_ready(backends, "parakeeet") is False
    assert gpu_capability.backend_ready([], "whisper") is False


def test_snapshot_without_a_backend_falls_back_to_the_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_probes(monkeypatch, driver=True, whisper_ready=True, ort_ready=False)
    snap = gpu_capability.snapshot(refresh=True)
    # Never omit the key: a renderer checking `=== false` must not read
    # `undefined` as "ready".
    assert snap["active_backend"] is None
    assert snap["active_backend_gpu_ready"] is False

    gpu_capability.reset_cache()
    _patch_probes(monkeypatch, driver=True, whisper_ready=True, ort_ready=True)
    snap = gpu_capability.snapshot(refresh=True)
    assert snap["active_backend_gpu_ready"] is True


def test_per_backend_readiness_is_not_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whisper can serve while the ONNX backends cannot (and vice versa)."""
    _patch_probes(monkeypatch, driver=True, whisper_ready=True, ort_ready=False)
    snap = gpu_capability.snapshot(refresh=True)
    by_name = {entry["name"]: entry for entry in snap["backends"]}
    assert by_name["whisper"]["gpu_ready"] is True
    assert by_name["whisper"]["detail"] == "ready"
    assert by_name["parakeet"]["gpu_ready"] is False
    assert by_name["parakeet"]["detail"] == "cuda_missing"
    # Qwen pins its ONNX session to CPU: offering GPU would be a switch
    # that can never take effect.
    assert by_name["qwen"]["gpu_capable"] is False
    assert by_name["qwen"]["detail"] == "cpu_only_backend"
    assert by_name["cloud"]["local"] is False


def test_active_backend_readiness_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_probes(monkeypatch, driver=True, whisper_ready=True, ort_ready=False)
    snap = gpu_capability.snapshot(active_backend="parakeet", refresh=True)
    assert snap["active_backend"] == "parakeet"
    # This is the flag the modal trigger reads: the ACTIVE backend cannot
    # serve GPU even though the machine is `gpu_ready` for Whisper.
    assert snap["active_backend_gpu_ready"] is False

    snap = gpu_capability.snapshot(active_backend="whisper", refresh=True)
    assert snap["active_backend_gpu_ready"] is True


def test_hardware_present_is_a_cheap_cached_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def adapter() -> bool:
        calls["n"] += 1
        return True

    monkeypatch.setattr(gpu_capability, "_nvidia_smi_gpus", lambda: [])
    monkeypatch.setattr(gpu_capability, "_driver_present", lambda: False)
    monkeypatch.setattr(gpu_capability, "_adapter_present", adapter)
    assert gpu_capability.hardware_present() is True
    assert gpu_capability.hardware_present() is True
    # Cached: the registry scan ran once, not twice.
    assert calls["n"] == 1


def test_reset_cache_forces_a_fresh_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_probes(monkeypatch)
    assert gpu_capability.snapshot()["state"] == gpu_capability.NO_GPU
    _patch_probes(monkeypatch, driver=True, whisper_ready=True)
    # Still cached without a refresh…
    assert gpu_capability.snapshot()["state"] == gpu_capability.NO_GPU
    gpu_capability.reset_cache()
    assert gpu_capability.snapshot()["state"] == gpu_capability.READY
