"""User-level CUDA runtime install (download → verify → install → activate).

The stack is a fixed, pinned set of Windows CUDA 12 wheels (cuBLAS, cuDNN,
cuDART, nvRTC) plus the CUDA-12 onnxruntime-gpu wheel. They land in
``<config>/cuda/site-packages`` so both the dev ``.venv`` sidecar and the
frozen Nuitka sidecar resolve them through ``nvidia_dll_paths`` and
``sys.path`` without touching the interpreter's own site-packages.
"""

from __future__ import annotations

from voice_typer.server.cuda_install.activation import apply_pending_activation
from voice_typer.server.cuda_install.manifest import (
    Artifact,
    artifacts_for_current_runtime,
    total_bytes,
)
from voice_typer.server.cuda_install.paths import (
    activation_file,
    cuda_root,
    downloads_dir,
    ensure_install_on_sys_path,
    install_dir,
    staging_dir,
)
from voice_typer.server.cuda_install.service import CudaInstallService, get_service

__all__ = [
    "Artifact",
    "CudaInstallService",
    "activation_file",
    "apply_pending_activation",
    "artifacts_for_current_runtime",
    "cuda_root",
    "downloads_dir",
    "ensure_install_on_sys_path",
    "get_service",
    "install_dir",
    "staging_dir",
    "total_bytes",
]
