"""Local Index-Translate Q4 text translation service.

One llama-server process is kept alive and reused for every dictation cycle.
The runtime is the small Vulkan-capable llama.cpp binary (about 39 MB) rather
than the 1.5 GB CUDA bundle; on a compatible GPU the driver already provides
Vulkan, so there is no first-run download and no popup.

Failures are deliberately non-fatal: a broken translation setup must never
block or corrupt dictation. The original text is returned and the error is
logged with the runtime log tail available in the translation work dir.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from voice_typer.server._paths import config_dir
from voice_typer.server.platform_utils import is_windows
from voice_typer.server.translation.catalogue import normalize_language_code, resolve_spec
from voice_typer.server.translation.chat_template import CHAT_TEMPLATE
from voice_typer.server.translation.prompt import build_user_prompt, needs_translation
from voice_typer.server.tts.runtime_server import RuntimeServer, RuntimeSpec

log = logging.getLogger(__name__)

_RUNTIME_ENV = "LAUSU_TRANSLATION_RUNTIME"
_MODEL_ENV = "LAUSU_TRANSLATION_MODEL"
_ALIAS = "lausu-translate"
_REQUEST_TIMEOUT_S = 120.0


class TranslationError(RuntimeError):
    """Raised when the translation runtime or model cannot be used."""


def work_dir() -> Path:
    """Dedicated dir for the chat template, runtime log and bundled models."""
    return config_dir() / "translation"


def _existing_path(value: str, label: str, *, directory: bool = False) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    if directory and path.is_dir():
        return path
    if path.is_file():
        return path
    raise TranslationError(f"{label} not found: {path}")


def resolve_runtime_path(config: Any) -> Path:
    """Resolve llama-server from config, env override, then the app data dir."""
    configured = _existing_path(str(getattr(config, "translation_runtime_path", "") or ""), "translation runtime")
    if configured is not None:
        return configured
    env_value = os.environ.get(_RUNTIME_ENV, "")
    from_env = _existing_path(env_value, "translation runtime (env)")
    if from_env is not None:
        return from_env
    name = "llama-server.exe" if is_windows() else "llama-server"
    bundled = work_dir() / name
    if bundled.is_file():
        return bundled
    raise TranslationError(
        f"translation runtime not installed; put llama-server in {work_dir()} "
        f"or set {_RUNTIME_ENV}"
    )


def resolve_model_path(config: Any) -> Path:
    """Resolve the Q4 GGUF from config, env override, then the app data dir."""
    spec = resolve_spec(str(getattr(config, "translation_model", "") or ""))
    configured = _existing_path(
        str(getattr(config, "translation_model_path", "") or ""),
        "translation model",
        directory=True,
    )
    if configured is not None:
        return configured / spec.filename if configured.is_dir() else configured
    env_value = os.environ.get(_MODEL_ENV, "")
    from_env = _existing_path(env_value, "translation model (env)", directory=True)
    if from_env is not None:
        return from_env / spec.filename if from_env.is_dir() else from_env
    bundled = work_dir() / "models" / spec.filename
    if bundled.is_file():
        return bundled
    raise TranslationError(
        f"{spec.label} not installed; put {spec.filename} in {work_dir() / 'models'} "
        f"or set {_MODEL_ENV}"
    )


def _write_template(path: Path) -> None:
    """Write the embedded template with LF newlines, only when it changes."""
    try:
        if path.read_text(encoding="utf-8") == CHAT_TEMPLATE:
            return
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    # Jinja accepts CRLF, but a stable LF file keeps the runtime log diffable.
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(CHAT_TEMPLATE)


class TranslationService:
    """Owns one llama-server subprocess and answers greedy translation calls."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.spec = resolve_spec(str(getattr(config, "translation_model", "") or ""))
        self.runtime_path = resolve_runtime_path(config)
        self.model_path = resolve_model_path(config)
        self.gpu_enabled = bool(getattr(config, "translation_gpu_enabled", True))
        self.glossary = str(getattr(config, "translation_glossary", "") or "")
        self._runtime: RuntimeServer | None = None
        self._lock = threading.Lock()

    def _spec(self) -> RuntimeSpec:
        root = work_dir()
        root.mkdir(parents=True, exist_ok=True)
        template_path = root / "index_translate_chat_template.jinja"
        _write_template(template_path)
        argv = [
            str(self.runtime_path),
            "-m",
            str(self.model_path),
            "--port",
            "{port}",
            "-c",
            "4096",
            "--jinja",
            "--chat-template-file",
            str(template_path),
            "--temp",
            "0",
            "-s",
            "0",
            "--reasoning",
            "off",
            "--alias",
            _ALIAS,
        ]
        if self.gpu_enabled:
            argv.extend(["-ngl", "99", "-fa", "on"])
        else:
            argv.extend(["-ngl", "0"])
        return RuntimeSpec(name="translation", argv=argv, log_path=root / "llama-server.log")

    def _ensure_runtime(self) -> RuntimeServer:
        with self._lock:
            if self._runtime is None or not self._runtime.running:
                self._runtime = RuntimeServer.start(self._spec(), timeout_s=180.0)
            return self._runtime

    def _complete(self, prompt: str) -> str:
        runtime = self._ensure_runtime()
        payload = {
            "model": _ALIAS,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a translation engine. Output only the translation, never an explanation.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "seed": 0,
            "cache_prompt": False,
            "reasoning_effort": "none",
            "chat_template_kwargs": {"enable_thinking": False},
            "max_tokens": 1024,
            "stream": False,
        }
        request = Request(
            f"{runtime.base_url}/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=_REQUEST_TIMEOUT_S) as response:  # noqa: S310 - loopback
                body = json.loads(response.read().decode("utf-8"))
        except (URLError, OSError, ValueError) as exc:
            raise TranslationError(f"translation request failed: {exc}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationError("translation response had no message content") from exc
        if not isinstance(content, str):
            raise TranslationError("translation response content was not text")
        return content.strip()

    def translate(self, text: str, target_code: str) -> str:
        """Translate one Stage A text; returns the source unchanged on error."""
        target = normalize_language_code(target_code)
        if not target or not text.strip():
            return text
        try:
            return self._complete(build_user_prompt(text, target, self.glossary)) or text
        except TranslationError as exc:
            log.warning("[TRANSLATE] %s; keeping original text", exc)
            return text
        except Exception:
            log.exception("[TRANSLATE] unexpected failure; keeping original text")
            return text

    def stop(self) -> None:
        """Stop the owned runtime; safe to call more than once."""
        runtime = self._runtime
        if runtime is not None:
            runtime.stop()
            self._runtime = None


_SERVICE: TranslationService | None = None
_SERVICE_KEY: tuple[object, ...] | None = None
_SERVICE_LOCK = threading.Lock()


def _service_key(config: Any) -> tuple[object, ...]:
    return (
        str(getattr(config, "translation_model", "") or ""),
        str(getattr(config, "translation_model_path", "") or ""),
        str(getattr(config, "translation_runtime_path", "") or ""),
        bool(getattr(config, "translation_gpu_enabled", True)),
        str(getattr(config, "translation_glossary", "") or ""),
    )


def get_service(config: Any) -> TranslationService:
    """Return the cached service, replacing it when translation settings change."""
    global _SERVICE, _SERVICE_KEY
    key = _service_key(config)
    with _SERVICE_LOCK:
        if _SERVICE is None or key != _SERVICE_KEY:
            if _SERVICE is not None:
                _SERVICE.stop()
            _SERVICE = TranslationService(config)
            _SERVICE_KEY = key
        return _SERVICE


def translate_text(text: str, config: Any, target_code: str, spoken_code: str = "") -> str:
    """Entry point used by the dictation pipeline's TranslationStage."""
    target = normalize_language_code(target_code)
    spoken = normalize_language_code(spoken_code or str(getattr(config, "language", "") or ""))
    if not bool(getattr(config, "translation_enabled", False)):
        return text
    if not needs_translation(text, target, spoken):
        return text
    try:
        return get_service(config).translate(text, target)
    except TranslationError as exc:
        log.warning("[TRANSLATE] %s; keeping original text", exc)
        return text


def shutdown() -> None:
    """Stop the cached runtime at process exit."""
    global _SERVICE, _SERVICE_KEY
    with _SERVICE_LOCK:
        if _SERVICE is not None:
            _SERVICE.stop()
        _SERVICE = None
        _SERVICE_KEY = None


atexit.register(shutdown)
