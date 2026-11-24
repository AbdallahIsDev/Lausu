"""Fail-closed guard: the retired Python ASR/media stack must stay gone.

Covers imports (including dynamic ones), sys.modules injection in tests,
dependency declarations, and freeze flags. Historical prose in ADRs,
review/worklog/CHANGELOG and HF model repository IDs are not code and are
intentionally out of scope.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BANNED = ("av", "faster_whisper", "ctranslate2")
PY_ROOTS = ("voice_typer", "scripts", "tests")
DEPS = ("pyproject.toml", "requirements-lock.txt")

_REQUIREMENT_RE = re.compile(r"^\s*(av|faster-whisper|ctranslate2)\s*(?:[=<>!~;]|$)", re.IGNORECASE)
_STALE_SCRIPT_RE = re.compile(r"strip_av_cython_shims|include-package=(?:av|faster_whisper|ctranslate2)\b")
_STALE_FLAG_RE = re.compile(
    r"--(?:nofollow-import-to|include-package|include-data-dir)=[^\s\"']*(?:av|faster_whisper|ctranslate2)\b"
)


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in PY_ROOTS:
        base = ROOT / root
        if base.is_dir():
            files.extend(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)
    return files


def _banned_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        name = node.value.split(".", 1)[0]
        return name if name in BANNED else None
    return None


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".", 1)[0]
                if name in BANNED:
                    found.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            name = node.module.split(".", 1)[0]
            if name in BANNED:
                found.append(f"line {node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Call):
            func = node.func
            dynamic_import = (
                isinstance(func, ast.Attribute)
                and func.attr == "import_module"
                and isinstance(func.value, ast.Name)
                and func.value.id == "importlib"
            )
            monkeypatch_modules = (
                isinstance(func, ast.Attribute)
                and func.attr == "setitem"
                and isinstance(func.value, ast.Name)
                and func.value.id == "monkeypatch"
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Attribute)
                and node.args[0].attr == "modules"
            )
            if (dynamic_import or monkeypatch_modules) and node.args:
                banned = _banned_string(node.args[0 if dynamic_import else 1])
                if banned:
                    found.append(f"line {node.lineno}: {banned} injected dynamically")
        elif isinstance(node, ast.Subscript):
            value = node.value
            if (
                isinstance(value, ast.Attribute)
                and value.attr == "modules"
                and isinstance(value.value, ast.Name)
                and value.value.id == "sys"
            ):
                banned = _banned_string(node.slice)
                if banned:
                    found.append(f"line {node.lineno}: sys.modules[{banned!r}]")
    return found


def test_no_legacy_imports_in_code_or_tests() -> None:
    failures: list[str] = []
    for path in _python_files():
        try:
            hits = _violations(path)
        except SyntaxError as exc:
            hits = [f"line {exc.lineno}: unparseable source: {exc.msg}"]
        for hit in hits:
            failures.append(f"{path.relative_to(ROOT).as_posix()}: {hit}")
    assert not failures, "retired ASR/media libraries are still referenced:\n" + "\n".join(failures)


def test_no_legacy_dependency_declarations() -> None:
    failures: list[str] = []
    for name in DEPS:
        path = ROOT / name
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.split("#", 1)[0].strip()
            if stripped and _REQUIREMENT_RE.match(stripped):
                failures.append(f"{name}:{lineno}: {stripped}")
    assert not failures, "retired dependency still declared:\n" + "\n".join(failures)


def test_no_legacy_freeze_flags_or_shim_strip() -> None:
    failures: list[str] = []
    for path in (ROOT / "scripts" / "build").rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if _STALE_SCRIPT_RE.search(line) or _STALE_FLAG_RE.search(line):
                failures.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}: {line.strip()}")
    assert not failures, "retired freeze flag still present:\n" + "\n".join(failures)


@pytest.mark.parametrize("source", ["import faster_whisper", "from av import open", "import ctranslate2 as ct2"])
def test_guard_detects_real_imports(source: str, tmp_path: Path) -> None:
    path = tmp_path / "probe.py"
    path.write_text(source + "\n", encoding="utf-8")
    assert _violations(path)


def test_guard_detects_dynamic_import_and_ignores_model_repo_names(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text('import importlib\nimportlib.import_module("faster_whisper")\n', encoding="utf-8")
    assert _violations(bad)
    good = tmp_path / "good.py"
    good.write_text('REPO = "Systran/faster-whisper-tiny"\n', encoding="utf-8")
    assert not _violations(good)
