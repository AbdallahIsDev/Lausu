"""Pinned CUDA 12 artifact set (URLs, sizes, SHA256) for the GPU install.

One CUDA 12 stack serves every local backend: CTranslate2 (Whisper) needs
cuBLAS + cuDNN 9, and the CUDA-12 ``onnxruntime-gpu`` build (Parakeet, Qwen,
local ONNX polish) is itself built against CUDA 12.8 + cuDNN 9. CUDA 13 is
deliberately excluded: its cuDNN ships the same ``cudnn64_9.dll`` file names
into the same directory, so mixing majors silently breaks whichever backend
loads second.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Artifact:
    """One pinned wheel: immutable identity + where to get it."""

    key: str
    filename: str
    url: str
    sha256: str
    size: int


CUDA_RUNTIME_ARTIFACTS: tuple[Artifact, ...] = (
    Artifact(
        key="cublas",
        filename="nvidia_cublas_cu12-12.9.2.10-py3-none-win_amd64.whl",
        url=(
            "https://files.pythonhosted.org/packages/20/e2/fc9a0e985249d873150276d5afb02e39a66817fedbf1a385724393e505ed/"
            "nvidia_cublas_cu12-12.9.2.10-py3-none-win_amd64.whl"
        ),
        sha256="623f43027d40d44ceadf0043f002bd25cf353e8f13ce90b9a87057019f560661",
        size=553162896,
    ),
    Artifact(
        key="cudnn",
        filename="nvidia_cudnn_cu12-9.28.1.4-py3-none-win_amd64.whl",
        url=(
            "https://files.pythonhosted.org/packages/c7/bd/1d6709d2223e99f04079f16005f8ae6e11a14ee16b5eab6833686cf72fe1/"
            "nvidia_cudnn_cu12-9.28.1.4-py3-none-win_amd64.whl"
        ),
        sha256="3467aafa9b260e6adf5fbbfc0e21d180133305b42032aa1160be2d3142bb8b09",
        size=696300805,
    ),
    Artifact(
        key="cudart",
        filename="nvidia_cuda_runtime_cu12-12.9.79-py3-none-win_amd64.whl",
        url=(
            "https://files.pythonhosted.org/packages/59/df/e7c3a360be4f7b93cee39271b792669baeb3846c58a4df6dfcf187a7ffab/"
            "nvidia_cuda_runtime_cu12-12.9.79-py3-none-win_amd64.whl"
        ),
        sha256="8e018af8fa02363876860388bd10ccb89eb9ab8fb0aa749aaf58430a9f7c4891",
        size=3591604,
    ),
    Artifact(
        key="nvrtc",
        filename="nvidia_cuda_nvrtc_cu12-12.9.86-py3-none-win_amd64.whl",
        url=(
            "https://files.pythonhosted.org/packages/52/de/823919be3b9d0ccbf1f784035423c5f18f4267fb0123558d58b813c6ec86/"
            "nvidia_cuda_nvrtc_cu12-12.9.86-py3-none-win_amd64.whl"
        ),
        sha256="72972ebdcf504d69462d3bcd67e7b81edd25d0fb85a2c46d3ea3517666636349",
        size=76408187,
    ),
)

# CUDA-12 ORT feed (not PyPI: PyPI's onnxruntime-gpu is CUDA 13 from 1.27).
_ORT_FEED = (
    "https://aiinfra.pkgs.visualstudio.com/2692857e-05ef-43b4-ba9c-ccf1c22c437c/"
    "_packaging/9387c3aa-d9ad-4513-968c-383f6f7f53b8/pypi/download/onnxruntime-gpu/1.29"
)

ORT_WHEELS: dict[tuple[int, int], Artifact] = {
    (3, 11): Artifact(
        key="onnxruntime",
        filename="onnxruntime_gpu-1.29.0-cp311-cp311-win_amd64.whl",
        url=f"{_ORT_FEED}/onnxruntime_gpu-1.29.0-cp311-cp311-win_amd64.whl",
        sha256="00592622fa1a82f770c4f89b5d1318fc65ecb022b4c79728e7723f0701f6f3af",
        size=349493698,
    ),
    (3, 12): Artifact(
        key="onnxruntime",
        filename="onnxruntime_gpu-1.29.0-cp312-cp312-win_amd64.whl",
        url=f"{_ORT_FEED}/onnxruntime_gpu-1.29.0-cp312-cp312-win_amd64.whl",
        sha256="118569fe3e60b8d09b13ffc0886b38d8adc62b368703dd0e5ad4dcd6155d8c79",
        size=349491310,
    ),
    (3, 13): Artifact(
        key="onnxruntime",
        filename="onnxruntime_gpu-1.29.0-cp313-cp313-win_amd64.whl",
        url=f"{_ORT_FEED}/onnxruntime_gpu-1.29.0-cp313-cp313-win_amd64.whl",
        sha256="7a293c0cb4c336f4586f6db6f59ad20b647565aea433a7cffdb397c32cd34fbc",
        size=349495903,
    ),
    (3, 14): Artifact(
        key="onnxruntime",
        filename="onnxruntime_gpu-1.29.0-cp314-cp314-win_amd64.whl",
        url=f"{_ORT_FEED}/onnxruntime_gpu-1.29.0-cp314-cp314-win_amd64.whl",
        sha256="8f6ec91e8a8b75844c20b41165c8bb96fb0e5ff9f306b2d3321c990d44be3644",
        size=353507391,
    ),
}

# DLLs every install must prove before it is allowed to activate. cuBLAS
# needs cudart, cuDNN 9 is what CTranslate2 links against, and nvRTC backs
# the CUDA execution provider's runtime kernel compilation.
REQUIRED_DLLS: tuple[str, ...] = (
    "cublas64_12.dll",
    "cublasLt64_12.dll",
    "cudnn64_9.dll",
    "cudart64_12.dll",
    "nvrtc64_120_0.dll",
)

REQUIRED_ORT_FILES: tuple[str, ...] = (
    "onnxruntime_providers_cuda.dll",
)


def ort_artifact(python_version: tuple[int, int] | None = None) -> Artifact | None:
    """The ORT wheel matching the running interpreter, or ``None``."""
    version = python_version or (sys.version_info.major, sys.version_info.minor)
    return ORT_WHEELS.get(version)


def artifacts_for_current_runtime(
    python_version: tuple[int, int] | None = None,
) -> tuple[Artifact, ...]:
    """Full pinned download set for this interpreter (empty when unsupported)."""
    ort = ort_artifact(python_version)
    if ort is None:
        return ()
    return (*CUDA_RUNTIME_ARTIFACTS, ort)


def total_bytes(artifacts: tuple[Artifact, ...]) -> int:
    return sum(a.size for a in artifacts)
