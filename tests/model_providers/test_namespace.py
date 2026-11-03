"""Namespace pin: ``voice_typer.server.providers`` is a MODULE, not a package.

A ``server/providers/`` package shadowed ``server/providers.py`` (AppProtocol +
build_ipc_server) once; this test makes that regression impossible to merge.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import voice_typer.server


def test_providers_module_is_not_shadowed() -> None:
    spec = importlib.util.find_spec("voice_typer.server.providers")
    assert spec is not None, "voice_typer.server.providers must be importable"
    assert spec.origin is not None
    assert Path(spec.origin).name == "providers.py", f"providers resolved to {spec.origin!r}, expected providers.py"
    assert spec.submodule_search_locations is None, "providers must be a module, not a package"


def test_providers_module_public_surface_imports() -> None:
    from voice_typer.server.providers import AppProtocol, build_ipc_server

    assert AppProtocol is not None
    assert callable(build_ipc_server)


def test_no_providers_package_directory_on_disk() -> None:
    server_dir = Path(voice_typer.server.__file__).parent
    assert not (server_dir / "providers").is_dir(), "a server/providers/ package would shadow server/providers.py"


def test_model_providers_package_imports_and_registers() -> None:
    import voice_typer.server.model_providers as model_providers

    registry = model_providers.get_registry()
    assert "openrouter" in registry.ids()
    assert "local" in registry.ids()
    assert registry.capability_matrix()["local_onnx"] == ["llm"]
