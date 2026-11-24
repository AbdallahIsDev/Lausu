"""Cross-layer parity for the compute-device vocabulary.

The sidebar switch, the IPC config validator and the runner capability
probe must agree on the same three device names (ADR-0031: cpu/vulkan/
cuda). A renderer-only or backend-only addition silently breaks either
the toggle or the persisted preference.
"""

from __future__ import annotations

import re
from pathlib import Path

from voice_typer.server import active_device, device_caps
from voice_typer.server.config_validators import validate_config_update

_RENDERER_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "voice_typer/client/src/renderer/src/lib/computeDevices.ts"
)


def _renderer_device_values() -> set[str]:
    source = _RENDERER_SOURCE.read_text(encoding="utf-8")
    match = re.search(
        r"COMPUTE_DEVICE_VALUES\s*=\s*\[([^\]]+)\]", source
    )
    assert match is not None, "COMPUTE_DEVICE_VALUES constant is missing"
    return set(re.findall(r'"([a-z_]+)"', match.group(1)))


class TestComputeDeviceParity:
    def test_renderer_validator_and_runner_share_the_device_names(self) -> None:
        renderer_values = _renderer_device_values()
        assert renderer_values == {"cpu", "vulkan", "cuda"}

        for device in ("cpu", "vulkan", "cuda"):
            accepted, errors = validate_config_update({"device": device})
            assert accepted == {"device": device}
            assert errors == []

        _, errors = validate_config_update({"device": "rocm"})
        assert errors


    def test_runner_contract_vulkan_alone_is_a_gpu(self, monkeypatch) -> None:
        device_caps.reset_cache()
        monkeypatch.setattr(
            "voice_typer.server.platform_utils.is_macos", lambda: False
        )
        monkeypatch.setattr(
            "voice_typer.server.nvidia_dll_paths._cuda_runtime_available",
            lambda: True,
        )
        monkeypatch.setattr(
            device_caps, "_runner_backends", lambda: {"cpu", "vulkan"}
        )
        assert device_caps.gpu_available(refresh=True) is True

        monkeypatch.setattr(device_caps, "_runner_backends", lambda: {"cpu"})
        assert device_caps.gpu_available(refresh=True) is False
        device_caps.reset_cache()

    def test_engine_vulkan_report_keeps_the_gpu_position(self) -> None:
        assert active_device.normalize_device("Vulkan") == "vulkan"
        assert active_device.normalize_device("GPU (Vulkan)") == "vulkan"
        assert active_device.normalize_device("GPU") == "cuda"
        assert active_device.normalize_device("CPU") == "cpu"
