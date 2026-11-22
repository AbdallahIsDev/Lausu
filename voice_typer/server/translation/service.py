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
import contextlib
import json
import logging
import threading
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from voice_typer.server import i18n
from voice_typer.server._paths import config_dir
from voice_typer.server.branding import APP_NAME
from voice_typer.server.translation import paths as translation_paths
from voice_typer.server.translation.catalogue import normalize_language_code, resolve_spec
from voice_typer.server.translation.chat_template import CHAT_TEMPLATE
from voice_typer.server.translation.preservation import protect_spans, restore_spans
from voice_typer.server.translation.prompt import build_user_prompt, needs_translation
from voice_typer.server.tts.runtime_server import RuntimeServer, RuntimeSpec

log = logging.getLogger(__name__)

_ALIAS = "lausu-translate"
_REQUEST_TIMEOUT_S = 120.0


class TranslationError(RuntimeError):
    """Raised when the translation runtime or model cannot be used."""


# One user-facing notice per process while translation stays broken. The text
# is still delivered verbatim, so a repeating toast on every dictation would
# be noise. A later success clears the flag so a new failure is reported.
_translation_failed_notified = False
_translation_failed_lock = threading.Lock()


def _notify_translation_failure() -> None:
    """Publish the existing generic ``notification`` event; never raise.

    Reusing the catalogue event means no new IPC command / event type, no
    parity files and no renderer changes. The Tauri host already turns it into
    a native toast, and the tray fallback drains the same event.
    """
    global _translation_failed_notified
    with _translation_failed_lock:
        if _translation_failed_notified:
            return
        _translation_failed_notified = True
    with contextlib.suppress(Exception):
        from voice_typer.server import event_bus

        event_bus.publish(
            {
                "type": "notification",
                "data": {
                    "title": APP_NAME,
                    "message": i18n.t("notify.dictation_pipeline.translation_failed"),
                    "duration_ms": 0,
                    "critical": False,
                },
            }
        )


def work_dir() -> Path:
    """Dedicated dir for the chat template, runtime log and bundled models."""
    return config_dir() / "translation"


def resolve_runtime_path(config: Any) -> Path:
    """Resolve the bundled llama-server (installer dirs; dev env escape hatch)."""
    path = translation_paths.resolve_runtime_path(config)
    if path is None:
        raise TranslationError(
            f"translation runtime not installed; bundle {translation_paths.RUNTIME_BASENAME} "
            f"with the app or set {translation_paths.RUNTIME_ENV}"
        )
    return path


def resolve_model_path(config: Any) -> Path:
    """Resolve the Q4 GGUF from the shared HF cache (never an Ollama blob)."""
    spec = resolve_spec(str(getattr(config, "translation_model", "") or ""))
    path = translation_paths.resolve_model_path(spec, config)
    if path is None:
        raise TranslationError(
            f"{spec.label} not installed; download {spec.repo_id} / {spec.filename} "
            f"into the HuggingFace hub cache or set {translation_paths.MODEL_ENV}"
        )
    return path


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
        """Translate one Stage A text; returns the source unchanged on error.

        Non-translatable spans are masked before the call and restored after,
        so URLs, emails, inline code and numbers survive byte-identical. A
        failure never overwrites the dictation and surfaces one user-facing
        notice per broken episode.
        """
        global _translation_failed_notified
        target = normalize_language_code(target_code)
        if not target or not text.strip():
            return text
        protected, spans = protect_spans(text)
        markers = tuple(marker for marker, _original in spans)
        try:
            result = self._complete(build_user_prompt(protected, target, self.glossary, markers))
            if not result:
                raise TranslationError("translation response was empty")
            result = restore_spans(result, spans)
        except TranslationError as exc:
            log.warning("[TRANSLATE] %s; keeping original text", exc)
            _notify_translation_failure()
            return text
        except Exception:
            log.exception("[TRANSLATE] unexpected failure; keeping original text")
            _notify_translation_failure()
            return text
        with _translation_failed_lock:
            _translation_failed_notified = False
        return result

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
        _notify_translation_failure()
        return text
    except Exception:
        log.exception("[TRANSLATE] unexpected failure; keeping original text")
        _notify_translation_failure()
        return text


def shutdown() -> None:
    """Stop the cached runtime at process exit."""
    global _SERVICE, _SERVICE_KEY, _translation_failed_notified
    with _SERVICE_LOCK:
        if _SERVICE is not None:
            _SERVICE.stop()
        _SERVICE = None
        _SERVICE_KEY = None
    with _translation_failed_lock:
        _translation_failed_notified = False


atexit.register(shutdown)
