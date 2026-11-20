"""Import-reachability proof for the at-rest crypto dependency.

``cryptography`` is no longer a direct dependency: the lock carries 50.0.0
Linux-only, transitively via keyring -> secretstorage; this app's code uses
PyCryptodome (``Crypto.Cipher.AES``). The frozen worker excludes that backend;
the sidecar imports it at module scope. Both boundaries are pinned with seams
(source inspection + stubbed/blocked imports), so no real freeze, install or
network access is needed.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import tomllib
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = PROJECT_ROOT / "scripts" / "build"
PYCRYPTODOME_SOURCE = PROJECT_ROOT / "voice_typer" / "server" / "_text_crypto.py"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
LOCKFILE = PROJECT_ROOT / "requirements-lock.txt"
PYINSTALLER_SPEC = BUILD_DIR / "lausu.spec"

WORKER_FREEZE_SCRIPTS = (
    BUILD_DIR / "build_worker_windows.sh",
    BUILD_DIR / "build_worker_macos.sh",
    BUILD_DIR / "build_worker_linux.sh",
)
SIDECAR_FREEZE_SCRIPTS = (
    BUILD_DIR / "build_sidecar_windows.sh",
    BUILD_DIR / "build_sidecar_macos.sh",
    BUILD_DIR / "build_sidecar_linux.sh",
)

NOFOLLOW_CRYPTO = "--nofollow-import-to=Crypto"
INCLUDE_CRYPTO = "--include-package=Crypto"
NOFOLLOW_CRYPTOGRAPHY = "--nofollow-import-to=cryptography"


def _module_level_statements(tree: ast.Module):
    """Yield statements executed at import time, including top-level try blocks."""
    for stmt in tree.body:
        yield stmt
        if isinstance(stmt, ast.Try):
            yield from stmt.body
            for handler in stmt.handlers:
                yield from handler.body
            yield from stmt.orelse
            yield from stmt.finalbody


def _module_level_imported_roots(source: str) -> set[str]:
    """Return top-level package names imported when a module is loaded."""
    tree = ast.parse(source)
    roots: set[str] = set()
    for stmt in _module_level_statements(tree):
        if isinstance(stmt, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in stmt.names)
        elif isinstance(stmt, ast.ImportFrom) and stmt.module:
            roots.add(stmt.module.split(".")[0])
    return roots


def _load_fresh_text_crypto():
    """Load an isolated copy of the sidecar crypto module (no sys.modules edit)."""
    spec = importlib.util.find_spec("voice_typer.server._text_crypto")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sidecar_imports_pycryptodome_at_module_scope() -> None:
    """The sidecar's crypto module imports ``Crypto`` at load time."""
    roots = _module_level_imported_roots(PYCRYPTODOME_SOURCE.read_text(encoding="utf-8"))
    assert "Crypto" in roots
    assert "cryptography" not in roots


def test_sidecar_binds_aes_when_pycryptodome_is_importable(monkeypatch) -> None:
    """With a stubbed Crypto.Cipher present, the sidecar binds its AES class."""
    fake_cipher = types.ModuleType("Crypto.Cipher")

    class _FakeAES:
        MODE_GCM = 9

        @classmethod
        def new(cls, *args, **kwargs):
            raise AssertionError("stub: no cipher construction expected")

    fake_cipher.AES = _FakeAES
    monkeypatch.setitem(sys.modules, "Crypto.Cipher", fake_cipher)

    module = _load_fresh_text_crypto()
    assert module._PYCRYPTODOME_AVAILABLE is True
    assert module._AES is _FakeAES


def test_sidecar_degrades_when_pycryptodome_is_unimportable(monkeypatch) -> None:
    """With Crypto blocked, the sidecar takes its documented plaintext fallback."""

    class _BlockCrypto:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "Crypto" or fullname.startswith("Crypto."):
                raise ImportError("Crypto blocked by import-status proof")
            return None

    monkeypatch.setattr(sys, "meta_path", [_BlockCrypto(), *sys.meta_path])
    for name in list(sys.modules):
        if name == "Crypto" or name.startswith("Crypto."):
            monkeypatch.delitem(sys.modules, name)

    module = _load_fresh_text_crypto()
    assert module._PYCRYPTODOME_AVAILABLE is False
    assert module._AES is None


@pytest.mark.parametrize("script", WORKER_FREEZE_SCRIPTS, ids=lambda p: p.name)
def test_frozen_worker_excludes_pycryptodome(script: Path) -> None:
    """Every worker freeze excludes the crypto backend; no stale pin remains."""
    text = script.read_text(encoding="utf-8")
    assert NOFOLLOW_CRYPTO in text, f"{script.name} no longer excludes the crypto backend"
    assert NOFOLLOW_CRYPTOGRAPHY not in text, f"{script.name} still excludes the retired cryptography package"


@pytest.mark.parametrize("script", SIDECAR_FREEZE_SCRIPTS, ids=lambda p: p.name)
def test_sidecar_freeze_keeps_pycryptodome(script: Path) -> None:
    """No sidecar freeze excludes the crypto backend: at-rest encryption works."""
    text = script.read_text(encoding="utf-8")
    assert INCLUDE_CRYPTO in text, f"{script.name} does not bundle the crypto backend"
    assert NOFOLLOW_CRYPTO not in text, f"{script.name} excludes the crypto backend from the sidecar"
    assert NOFOLLOW_CRYPTOGRAPHY not in text, f"{script.name} still references the retired cryptography package"


def test_cryptography_is_not_a_declared_dependency() -> None:
    """The retired dependency is gone; PyCryptodome is the direct dependency."""
    deps = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    roots = {dep.split(";", 1)[0].strip().split(">")[0].split("<")[0].strip().lower() for dep in deps}
    assert "cryptography" not in roots
    assert "pycryptodome" in roots


def test_cryptography_is_not_a_direct_lockfile_dependency() -> None:
    """No lock entry pulls cryptography in for lausu; Linux keeps it only via keyring."""
    lines = LOCKFILE.read_text(encoding="utf-8").splitlines()
    crypto_entries = [line for line in lines if line.startswith("cryptography==")]
    assert len(crypto_entries) == 1, f"expected one transitive cryptography entry, got {crypto_entries}"
    assert "sys_platform == 'linux'" in crypto_entries[0], crypto_entries[0]
    assert "darwin" not in crypto_entries[0] and "win32" not in crypto_entries[0]
    idx = lines.index(crypto_entries[0])
    via_block: list[str] = []
    for line in lines[idx + 1 :]:
        if line and not line.startswith(" "):
            break
        via_block.append(line.strip())
    assert "# via secretstorage" in via_block, via_block
    assert "#   lausu (pyproject.toml)" not in via_block, via_block


def test_pyinstaller_fallback_spec_includes_pycryptodome() -> None:
    """The PyInstaller fallback explicitly collects Crypto, not just via the hook.

    PyCryptodome's AES extension is loaded dynamically, so a hook alone is a
    single point of failure. The worker freezes keep excluding Crypto; see
    ``test_frozen_worker_excludes_pycryptodome`` above.
    """
    text = PYINSTALLER_SPEC.read_text(encoding="utf-8")
    for module in ("Crypto", "Crypto.Cipher", "Crypto.Cipher.AES", "Crypto.Cipher._raw_aes"):
        assert f'"{module}"' in text, f"lausu.spec lost explicit hiddenimport for {module}"


def test_linux_only_crypto_chain_markers() -> None:
    """secretstorage and jeepney are Linux-only in the lock, both via keyring."""
    lines = LOCKFILE.read_text(encoding="utf-8").splitlines()
    for package in ("secretstorage", "jeepney"):
        entries = [line for line in lines if line.startswith(f"{package}==")]
        assert len(entries) == 1, entries
        assert "sys_platform == 'linux'" in entries[0], entries[0]
        assert "darwin" not in entries[0] and "win32" not in entries[0]
        idx = lines.index(entries[0])
        via_block: list[str] = []
        for line in lines[idx + 1 :]:
            if line and not line.startswith(" "):
                break
            via_block.append(line.strip())
        assert any("keyring" in line for line in via_block), via_block
