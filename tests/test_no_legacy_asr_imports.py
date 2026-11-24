"""Fail-closed guard: the retired Python ASR/media stack must stay gone.

Covers imports (including dynamic ones), sys.modules injection in tests,
dependency declarations, freeze flags, live bench/API prose, and a repo-wide
allowlist/ratchet for legacy terms. ADR-0031 (history), one CHANGELOG line and
the legacy model-id migration map may name the old stack; pre-existing hits are
frozen so they can only shrink.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BANNED = ("av", "faster_whisper", "ctranslate2")
PY_ROOTS = ("voice_typer", "scripts", "tests", "bench")
DEPS = ("pyproject.toml", "requirements-lock.txt")

# Prose naming of the retired stack in active bench scripts/docs, not history.
PROSE_TERMS = re.compile(r"\b(?:faster[-_]whisper|ctranslate2|WhisperModel|PyAV)\b", re.IGNORECASE)
_REPO_ID_DATA = re.compile(r"[^\s\"']*/[^\s\"']*")
HISTORICAL_PROSE = frozenset({ROOT / "bench" / "COLDSTART_REPORT.md"})

_REQUIREMENT_RE = re.compile(r"^\s*(av|faster-whisper|ctranslate2)\s*(?:[=<>!~;]|$)", re.IGNORECASE)
_STALE_SCRIPT_RE = re.compile(r"strip_av_cython_shims|include-package=(?:av|faster_whisper|ctranslate2)\b")
_STALE_FLAG_RE = re.compile(
    r"--(?:nofollow-import-to|include-package|include-data-dir)=[^\s\"']*(?:av|faster_whisper|ctranslate2)\b"
)

# Repo-wide term scan. Word boundaries keep unrelated names (e.g. GNU
# ``collect2``) out; the migration map and ADR-0031 are the only sources that
# legitimately spell old model ids.
LEGACY_TERMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ctranslate2", re.compile(r"\bctranslate2\b", re.IGNORECASE)),
    ("ct2", re.compile(r"\bct2\b", re.IGNORECASE)),
    ("faster-whisper", re.compile(r"\bfaster[-_]whisper\b", re.IGNORECASE)),
    ("fasterwhisper", re.compile(r"\bfasterwhisper\b", re.IGNORECASE)),
    ("PyAV", re.compile(r"\bpyav\b", re.IGNORECASE)),
    ("import av", re.compile(r"\bimport\s+av\b", re.IGNORECASE)),
    ("from av", re.compile(r"\bfrom\s+av\b", re.IGNORECASE)),
    ("av.libs", re.compile(r"\bav\.libs\b", re.IGNORECASE)),
    ("WhisperModel", re.compile(r"\bWhisperModel\b")),
    ("Systran", re.compile(r"\bSystran\b")),
    ("andrewleech", re.compile(r"\bandrewleech\b", re.IGNORECASE)),
    ("Masterx", re.compile(r"\bMasterx\b", re.IGNORECASE)),
    ("onnx-asr", re.compile(r"\bonnx[-_]asr\b", re.IGNORECASE)),
)
ALLOWED_TERM_FILES = frozenset(
    {
        "docs/adr/0031-onnx-to-gguf-migration.md",
        "voice_typer/server/gguf_model_registry.py",
        "voice_typer/server/model_registry.py",
    }
)
CHANGELOG_FILE = "CHANGELOG.md"
MAX_CHANGELOG_TERM_LINES = 1
GUARD_TEST_FILE = Path(__file__).relative_to(ROOT).as_posix()

# Files that already contained legacy terms when this gate landed. Only the
# owner may edit AGENTS.md / worklog.md / review.md; ADR-0021 belongs to another
# session. The rest are legacy runtime modules and generated baselines queued
# for a separate deletion. This is a ratchet: no new file, no count growth.
PRE_EXISTING_TERM_FILES: dict[str, int] = {
    'AGENTS.md': 6,
    'docs/adr/0021-transcription-translation-split.md': 22,
    'docs/audit/ui-evidence.mjs': 2,
    'mypy-baseline.json': 3,
    'pyproject.toml': 6,
    'requirements-lock.txt': 3,
    'review.md': 1,
    'scripts/slim_core_ml_ratchet_check.py': 2,
    'scripts/verify_windows_bundle.py': 8,
    'slim-core-ml-baseline.json': 2,
    'src-tauri/src/commands/system_cmds/dialogs.rs': 1,
    'src-tauri/src/sidecar/spawn/event_drain_tests.rs': 1,
    'tests/cuda_install/test_activation.py': 2,
    'tests/cuda_install/test_gpu_capability.py': 2,
    'tests/model_download/test_download_abort_gate.py': 10,
    'tests/model_download/test_download_stall_guard.py': 1,
    'tests/model_download/test_offline_probe_log_quiet.py': 8,
    'tests/model_download/test_segmented_download.py': 2,
    'tests/model_download/test_segmented_lfs_planning.py': 1,
    'tests/packaging/test_third_party_notices_av_version.py': 6,
    'tests/packaging/test_third_party_notices_generated.py': 3,
    'tests/security/test_redact_secret.py': 3,
    'tests/tauri/mig15/test_nuitka_windows_build.py': 13,
    'tests/tauri/mig16/test_autostart_installer_macos.py': 1,
    'tests/tauri/mig16/test_nuitka_macos_build.py': 14,
    'tests/tauri/mig17/test_nuitka_linux_build.py': 13,
    'tests/tauri/mig18/test_macos_signing.py': 1,
    'tests/tauri/mig18/test_openmp_runtimes.py': 22,
    'tests/tauri/mig18/test_per_triple_freeze.py': 21,
    'tests/tauri/test_no_legacy_asr_flags.py': 6,
    'tests/tauri/test_windows_freeze_drift.py': 2,
    'tests/test_allowed_user_models.py': 6,
    'tests/test_asr_registry_busy_flag.py': 1,
    'tests/test_config_validators_split.py': 2,
    'tests/test_dev_model_frozen.py': 2,
    'tests/test_e2e_smoke.py': 13,
    'tests/test_gdpr_delete.py': 2,
    'tests/test_gdpr_export.py': 1,
    'tests/test_gguf_families.py': 2,
    'tests/test_gguf_model_registry.py': 1,
    'tests/test_i18n_completeness.py': 2,
    'tests/test_import_model_security.py': 11,
    'tests/test_language_auto_detect.py': 1,
    'tests/test_log_third_party_levels.py': 2,
    'tests/test_model_switch_logging.py': 2,
    'tests/test_module_split_reexports_wave6.py': 2,
    'tests/test_nuitka_asr_exclusions.py': 12,
    'tests/test_parakeet_cpu_abort.py': 3,
    'tests/test_parakeet_engine.py': 5,
    'tests/test_parakeet_mem_arena.py': 2,
    'tests/test_parakeet_onnx_abort.py': 8,
    'tests/test_parakeet_onnx_gpu_fallback.py': 5,
    'tests/test_parakeet_onnx_load.py': 24,
    'tests/test_parakeet_onnx_sha.py': 6,
    'tests/test_parakeet_onnx_transcribe.py': 3,
    'tests/test_parakeet_warmup.py': 4,
    'tests/test_security_hardening.py': 4,
    'tests/test_slim_core_ml_ratchet.py': 19,
    'tests/test_slim_no_asr_imports.py': 11,
    'tests/test_windows_bundle_gate.py': 3,
    'tests/test_worker_load_parakeet_qwen.py': 2,
    'tests/test_worker_startup.py': 2,
    'tests/test_worker_whisper_fallback.py': 2,
    'voice_typer/client/src/renderer/src/__tests__/behavior-rewrite/host-ipc-build-behavior.test.tsx': 2,
    'voice_typer/client/src/renderer/src/components/gpu/GpuRequestDialog.tsx': 1,
    'voice_typer/client/src/renderer/src/components/gpu/__tests__/GpuRequestDialog.test.tsx': 1,
    'voice_typer/client/src/renderer/src/components/help/PunctuationCheatSheet.tsx': 1,
    'voice_typer/client/src/renderer/src/components/layout/DeviceToggle.tsx': 1,
    'voice_typer/client/src/renderer/src/components/layout/__tests__/DeviceToggle.test.tsx': 1,
    'voice_typer/client/src/renderer/src/hooks/__tests__/useCudaInstallToast.test.tsx': 2,
    'voice_typer/client/src/renderer/src/types/config.ts': 2,
    'voice_typer/server/asr_setup.py': 1,
    'voice_typer/server/dictation_pipeline/enhancement_steps.py': 1,
    'voice_typer/server/log/levels.py': 2,
    'voice_typer/server/model_hashes.json': 19,
    'voice_typer/server/parakeet_engine/_constants.py': 3,
    'voice_typer/server/parakeet_engine/_load.py': 17,
    'voice_typer/server/parakeet_engine/_transcribe.py': 1,
    'voice_typer/server/parakeet_engine/engine.py': 2,
    'voice_typer/server/prewarm/cache_probe.py': 2,
    'voice_typer/server/qwen_engine.py': 2,
    'voice_typer/server/security/model_integrity.py': 15,
    'voice_typer/server/transcription_download.py': 6,
    'voice_typer/server/worker_proxy_asr.py': 1,
    'voice_typer/stubs/onnx_asr.pyi': 8,
    'worklog.md': 28,}
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".superpowers",
        ".cache",
        ".agent-workflow",
        ".claude",
        ".codex",
        ".cursor",
        ".copilot",
        ".gemini",
        ".openclaw",
        ".hypothesis",
        ".workbuddy-ai",
        "coverage",
        "out",
        "dist",
        "build",
        "target",
    }
)
SKIP_FILES = frozenset({"coverage.xml", "pytest-run.txt"})
SKIP_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".webp",
        ".pdf",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".pyc",
        ".so",
        ".dll",
        ".dylib",
        ".exe",
        ".zip",
        ".gz",
        ".bin",
        ".wasm",
        ".mp3",
        ".mp4",
        ".wav",
        ".log",
        ".map",
    }
)


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in PY_ROOTS:
        base = ROOT / root
        if base.is_dir():
            files.extend(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)
    return files


def _prose_files() -> list[Path]:
    files: list[Path] = []
    bench = ROOT / "bench"
    for pattern in ("*.py", "*.md"):
        files.extend(
            path for path in bench.rglob(pattern) if path not in HISTORICAL_PROSE and "__pycache__" not in path.parts
        )
    api = ROOT / "docs" / "API.md"
    if api.is_file():
        files.append(api)
    return files


def _scrub_repo_ids(line: str) -> str:
    """Blank path-like data tokens (HF repo ids) before checking prose."""
    return _REPO_ID_DATA.sub(lambda match: "" if PROSE_TERMS.search(match.group(0)) else match.group(0), line)


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


_LEGACY_TERM_RE = re.compile(
    "(?i)" + "|".join(f"(?P<term{i}>{pattern.pattern})" for i, (_, pattern) in enumerate(LEGACY_TERMS))
)
_LEGACY_TERM_LABELS = {f"term{i}": label for i, (label, _) in enumerate(LEGACY_TERMS)}


def _legacy_term_hits(lines: list[str]) -> list[tuple[int, str]]:
    """Return ``(line number, term)`` for every legacy term in these lines."""
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(lines, 1):
        for match in _LEGACY_TERM_RE.finditer(line):
            hits.append((lineno, _LEGACY_TERM_LABELS[match.lastgroup or ""]))
    return hits


def _repo_text_files() -> list[tuple[str, list[str]]]:
    files: list[tuple[str, list[str]]] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in SKIP_DIRS
            and not name.endswith(".egg-info")
            and not name.startswith(".tmp")
            and not name.startswith(".legacy_")
        )
        for name in filenames:
            path = Path(dirpath) / name
            if name in SKIP_FILES or path.suffix.lower() in SKIP_SUFFIXES:
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            if b"\0" in raw:
                continue
            files.append((path.relative_to(ROOT).as_posix(), raw.decode("utf-8", errors="replace").splitlines()))
    return files


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


def test_no_legacy_stack_wording_in_bench_and_api_docs() -> None:
    failures: list[str] = []
    for path in _prose_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            hit = PROSE_TERMS.search(_scrub_repo_ids(line))
            if hit:
                failures.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}: {hit.group(0)}")
    assert not failures, "retired ASR/media stack named in bench or API docs:\n" + "\n".join(failures)


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


def test_no_legacy_terms_outside_allowlist() -> None:
    """No NEW file may carry a term; a recorded file may only shrink.

    Absolute target: ADR-0031, one CHANGELOG line, the migration map and this
    guard. Files carrying terms when this gate landed are frozen above because
    they are owner-owned history, another session's ADR, generated baselines or
    legacy runtime modules queued for a separate deletion.
    """
    offenders: dict[str, int] = {}
    for rel, lines in _repo_text_files():
        if rel == GUARD_TEST_FILE or rel in ALLOWED_TERM_FILES:
            continue
        hits = _legacy_term_hits(lines)
        if rel == CHANGELOG_FILE and len({lineno for lineno, _ in hits}) <= MAX_CHANGELOG_TERM_LINES:
            continue
        if hits:
            offenders[rel] = len(hits)
    new_files = sorted(set(offenders) - set(PRE_EXISTING_TERM_FILES))
    grown = sorted(
        f"{rel}: {n} > {PRE_EXISTING_TERM_FILES[rel]}"
        for rel, n in offenders.items()
        if rel in PRE_EXISTING_TERM_FILES and n > PRE_EXISTING_TERM_FILES[rel]
    )
    assert not new_files and not grown, (
        "legacy terms spread to a new file or grew in a frozen file:\n"
        + "\n".join(new_files + grown)
    )


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


def test_prose_guard_ignores_repo_ids_and_allows_current_names() -> None:
    assert PROSE_TERMS.search(_scrub_repo_ids('REPO = "Systran/faster-whisper-tiny.en"')) is None
    assert PROSE_TERMS.search(_scrub_repo_ids("loads a faster-whisper model")) is not None
    assert PROSE_TERMS.search(_scrub_repo_ids("the GGUF runner decodes audio")) is None


def test_legacy_term_scan_matches_names_but_not_unrelated_words() -> None:
    assert _legacy_term_hits(["loads a faster-whisper model"]) == [(1, "faster-whisper")]
    assert _legacy_term_hits(["Systran/faster-whisper-tiny", "PyAV 18"]) == [
        (1, "Systran"),
        (1, "faster-whisper"),
        (2, "PyAV"),
    ]
    assert _legacy_term_hits(["collect2 and ld are GNU tools", "the GGUF runner decodes audio"]) == []
