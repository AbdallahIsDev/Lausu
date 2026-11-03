"""Local ONNX model directories + manifest hash verification.

A model directory is accepted only when every file listed in its own
``manifest.json`` matches its SHA-256. A mismatch refuses to load (never a
warning-only pass), because the weights are executed in-process.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from voice_typer.server.model_providers.descriptor import Domain, ModelDescriptor
from voice_typer.server.model_providers.errors import ProviderRuntimeError
from voice_typer.server.model_providers.local_onnx.generation import DEFAULT_EOS_IDS

log = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
GENERATION_CONFIG_NAME = "generation_config.json"
#: Files that must exist for a directory to be a runnable generation model.
REQUIRED_FILES: tuple[str, ...] = ("tokenizer.json",)

#: Name preference for the generation graph (exports ship quantized variants
#: next to their ``.onnx_data`` side files).
_GRAPH_PREFERENCE: tuple[str, ...] = ("q4f16", "q4", "q8", "fp16", "model", "llm")

#: ``(path, size, mtime_ns) -> sha256``. Verification was measured at 17.5 s on
#: the real 1.76 GB model, so a catalogue refresh must not re-hash warm files.
_DIGEST_CACHE: dict[tuple[str, int, int], str] = {}
_DIGEST_LOCK = threading.Lock()
_DIGEST_CACHE_MAX = 4096


def compute_sha256(path: Path) -> str:
    """Return the file's SHA-256, cached until size/mtime changes."""
    stat = path.stat()
    key = (str(path.resolve()), int(stat.st_size), int(stat.st_mtime_ns))
    with _DIGEST_LOCK:
        cached = _DIGEST_CACHE.get(key)
    if cached is not None:
        return cached
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    with _DIGEST_LOCK:
        if len(_DIGEST_CACHE) > _DIGEST_CACHE_MAX:
            _DIGEST_CACHE.clear()
        _DIGEST_CACHE[key] = value
    return value


def _manifest_entries(manifest: Any) -> dict[str, str]:
    """Accept the two manifest shapes seen in the wild."""
    entries: dict[str, str] = {}
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if isinstance(files, dict):
        for name, value in files.items():
            if isinstance(value, str):
                entries[name] = value
            elif isinstance(value, dict) and value.get("sha256"):
                entries[name] = str(value["sha256"])
    elif isinstance(files, list):
        for row in files:
            if isinstance(row, dict) and (row.get("path") or row.get("name")) and row.get("sha256"):
                entries[str(row.get("path") or row.get("name"))] = str(row["sha256"])
    return entries


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_ids(value: Any) -> tuple[int, ...]:
    if isinstance(value, bool) or value is None:
        return ()
    if isinstance(value, int):
        return (value,)
    if isinstance(value, (list, tuple)):
        ids: list[int] = []
        for item in value:
            if isinstance(item, bool):
                continue
            try:
                ids.append(int(item))
            except (TypeError, ValueError):
                continue
        return tuple(ids)
    return ()


@dataclass(frozen=True)
class LocalOnnxModel:
    """A verified local model directory."""

    model_id: str
    path: Path
    manifest: dict[str, Any] = field(default_factory=dict)
    verified_files: int = 0

    @property
    def eos_ids(self) -> tuple[int, ...]:
        """EOS ids from ``generation_config.json``, then the manifest."""
        for base in self._config_search_dirs():
            payload = _read_json(base / GENERATION_CONFIG_NAME)
            if payload is not None:
                parsed = _parse_ids(payload.get("eos_token_id"))
                if parsed:
                    return parsed
        parsed = _parse_ids(self.manifest.get("eos_ids"))
        return parsed or DEFAULT_EOS_IDS

    def _config_search_dirs(self) -> list[Path]:
        """Model root, then the graph's own directory and its parent."""
        dirs = [self.path]
        try:
            graph_dir = self.onnx_path.parent
        except ProviderRuntimeError:
            return dirs
        for candidate in (graph_dir, graph_dir.parent):
            if candidate not in dirs:
                dirs.append(candidate)
        return dirs

    @property
    def chat_template(self) -> str:
        template = self.manifest.get("chat_template")
        if isinstance(template, str) and template.strip():
            return template
        template_path = self.path / "chat_template.jinja"
        return template_path.read_text(encoding="utf-8") if template_path.is_file() else ""

    @property
    def onnx_path(self) -> Path:
        """Recursively resolve the generation graph (exports nest under onnx/)."""
        candidates = sorted(p for p in self.path.rglob("*.onnx") if p.is_file())
        graphs = [p for p in candidates if "decoder" not in p.name.lower()]
        if not graphs:
            found = ", ".join(str(p.relative_to(self.path)) for p in candidates) or "no .onnx files"
            raise ProviderRuntimeError(
                f"no ONNX generation graph in {self.path} (found: {found})",
                provider="local_onnx",
                domain="llm",
            )

        def rank(path: Path) -> tuple[int, int]:
            name = path.name.lower()
            for index, token in enumerate(_GRAPH_PREFERENCE):
                if token in name:
                    return (index, len(str(path)))
            return (len(_GRAPH_PREFERENCE), len(str(path)))

        return min(graphs, key=rank)


def verify_manifest(model_dir: str | Path) -> tuple[bool, str, int]:
    """Verify every file in ``manifest.json``; return ``(ok, reason, count)``."""
    path = Path(model_dir)
    manifest_path = path / MANIFEST_NAME
    if not manifest_path.is_file():
        return False, f"missing {MANIFEST_NAME}", 0
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"unreadable {MANIFEST_NAME}: {exc}", 0
    entries = _manifest_entries(manifest)
    if not entries:
        return False, "manifest lists no files", 0
    checked = 0
    for name, expected in entries.items():
        file_path = path / name
        if not file_path.is_file():
            return False, f"missing file {name}", checked
        actual = compute_sha256(file_path)
        if not hmac.compare_digest(actual, expected.lower()):
            return False, f"hash mismatch for {name}", checked
        checked += 1
    return True, "", checked


def load_model(model_dir: str | Path) -> LocalOnnxModel:
    """Verify and return a model, refusing on any hash mismatch."""
    path = Path(model_dir)
    if not path.is_dir():
        raise ProviderRuntimeError(
            f"model directory not found: {path}",
            provider="local_onnx",
            domain="llm",
        )
    ok, reason, checked = verify_manifest(path)
    if not ok:
        raise ProviderRuntimeError(
            f"model integrity check failed ({reason})",
            provider="local_onnx",
            domain="llm",
        )
    for required in REQUIRED_FILES:
        if not (path / required).is_file():
            raise ProviderRuntimeError(
                f"model directory is missing {required}",
                provider="local_onnx",
                domain="llm",
            )
    manifest = json.loads((path / MANIFEST_NAME).read_text(encoding="utf-8"))
    model_id = str(manifest.get("model_id") or path.name)
    model = LocalOnnxModel(model_id=model_id, path=path, manifest=manifest, verified_files=checked)
    # Resolve the graph now so a directory that verifies but cannot load is
    # rejected at load time with the typed "no ONNX graph" error.
    _ = model.onnx_path
    return model


def list_installed_models(root: str | Path) -> list[ModelDescriptor]:
    """List only directories that verify AND can actually load.

    ``root`` may be either a parent of model dirs or one model dir itself (the
    directory a user picks in the UI), so both shapes are advertised.
    """
    if not root:
        return []
    base = Path(root)
    if not base.is_dir():
        return []
    out: list[ModelDescriptor] = []
    candidates = [base] if (base / MANIFEST_NAME).is_file() else []
    candidates.extend(sorted(p for p in base.iterdir() if p.is_dir()))
    for candidate in candidates:
        if not (candidate / "tokenizer.json").is_file():
            continue
        ok, _reason, _count = verify_manifest(candidate)
        if not ok:
            continue
        manifest = _read_json(candidate / MANIFEST_NAME) or {}
        probe = LocalOnnxModel(
            model_id=str(manifest.get("model_id") or candidate.name), path=candidate, manifest=manifest
        )
        try:
            _ = probe.onnx_path
        except ProviderRuntimeError:
            continue
        out.append(
            ModelDescriptor(
                id=candidate.name,
                label=candidate.name,
                domains=frozenset({Domain.LLM}),
            )
        )
    return out


__all__ = [
    "GENERATION_CONFIG_NAME",
    "MANIFEST_NAME",
    "REQUIRED_FILES",
    "LocalOnnxModel",
    "compute_sha256",
    "list_installed_models",
    "load_model",
    "verify_manifest",
]
