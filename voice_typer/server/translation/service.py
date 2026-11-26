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
import time
import weakref
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from voice_typer.server import i18n
from voice_typer.server._paths import config_dir
from voice_typer.server.branding import APP_NAME
from voice_typer.server.translation import paths as translation_paths
from voice_typer.server.translation.catalogue import (
    TRANSLATION_TARGETS,
    normalize_language_code,
    resolve_spec,
)
from voice_typer.server.translation.chat_template import CHAT_TEMPLATE
from voice_typer.server.translation.preservation import protect_spans, restore_spans
from voice_typer.server.translation.prompt import build_user_prompt, needs_translation
from voice_typer.server.tts.runtime_server import RuntimeServer, RuntimeSpec

log = logging.getLogger(__name__)

_ALIAS = "lausu-translate"
_REQUEST_TIMEOUT_S = 120.0
_IDLE_UNLOAD_DEFAULT_S = 600
_IDLE_UNLOAD_MAX_S = 86_400

# A translate-at-end waits at most this long for the warm load started at
# recording time. Measured cold llama-server launch: 15.4 s with a warm OS file
# cache, 33.9 s cold; first complete response 16.2 / 34.5 s
# (docs/design/translation-chunking.md §11a). 45 s covers the worst measured
# cold start with headroom without hanging dictation forever. The background
# load itself is NOT cancelled at this deadline; it finishes and is reused.
_WARM_JOIN_TIMEOUT_S = 45.0


class TranslationError(RuntimeError):
    """Raised when the translation runtime or model cannot be used."""


class TranslationCancelledError(RuntimeError):
    """Raised when an explicit caller cancel token fires; never a failure."""


# One user-facing notice per process while translation stays broken. The text
# is still delivered verbatim, so a repeating toast on every dictation would
# be noise. A later success clears the flag so a new failure is reported.
_translation_failed_notified = False
_translation_model_missing_notified = False
_translation_failed_lock = threading.Lock()
# Weak handle to the app, set by translate_text so service-level failures can
# reach the standalone tray without an app reference on the service itself.
_app_ref: Any = None


def _bind_app(app: Any | None) -> None:
    global _app_ref
    if app is None:
        return
    try:
        _app_ref = weakref.proxy(app)
    except TypeError:
        # Test doubles / non-weakrefable objects: the event still surfaces the
        # failure; only the standalone tray fallback is unavailable.
        _app_ref = app


def _publish_notice(message: str, app: Any | None) -> None:
    """Publish one localized notice through the shared catalogue event."""
    with contextlib.suppress(Exception):
        from voice_typer.server import event_bus

        event_bus.publish(
            {
                "type": "notification",
                "data": {
                    "title": APP_NAME,
                    "message": message,
                    "duration_ms": 0,
                    "critical": False,
                },
            }
        )
    if app is not None:
        with contextlib.suppress(Exception):
            from voice_typer.server.tray_types import is_tauri_sidecar

            if not is_tauri_sidecar():
                app.tray.notify(APP_NAME, message)


def _notify_translation_failure(app: Any | None = None) -> None:
    """Surface one generic-failure notice per broken episode; never raise."""
    global _translation_failed_notified
    with _translation_failed_lock:
        if _translation_failed_notified:
            return
        _translation_failed_notified = True
    _publish_notice(i18n.t("notify.dictation_pipeline.translation_failed"), app)


def _notify_translation_model_missing(app: Any | None = None) -> None:
    """Missing GGUF: one actionable notice, never a raw error or a download."""
    global _translation_model_missing_notified
    with _translation_failed_lock:
        if _translation_model_missing_notified:
            return
        _translation_model_missing_notified = True
    _publish_notice(i18n.t("notify.dictation_pipeline.translation_model_missing"), app)


def _model_is_installed(config: Any) -> bool:
    """Use the same resolver the service uses, so tests patch one seam."""
    try:
        resolve_model_path(config)
        return True
    except TranslationError:
        return False


def _idle_seconds(config: Any) -> int:
    """Read the idle-unload setting; absent/invalid values get today's default."""
    raw = getattr(config, "translation_idle_unload_seconds", _IDLE_UNLOAD_DEFAULT_S)
    if isinstance(raw, bool) or not isinstance(raw, int):
        return _IDLE_UNLOAD_DEFAULT_S
    return max(0, min(raw, _IDLE_UNLOAD_MAX_S))


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
        # One model process with one request slot: serialize the HTTP calls and
        # any stop() against them. Without this, a set_config mid-request could
        # kill the runtime under urlopen, or stop() could miss a runtime that a
        # concurrent thread had not yet assigned to self._runtime (process leak).
        self._lock = threading.RLock()
        # Idle unload is a separate lock so the timer never blocks a POST.
        self._idle_seconds = _idle_seconds(config)
        self._idle_lock = threading.Lock()
        self._idle_activity = threading.Event()
        self._idle_stop = threading.Event()
        self._idle_deadline: float | None = None
        self._idle_thread: threading.Thread | None = None

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
            self.note_activity()
            return self._runtime

    def _complete(self, prompt: str, *, cancel_event: threading.Event | None = None) -> str:
        # Hold the lock for the whole request, not just runtime start, so a
        # concurrent stop() (config change / shutdown) cannot tear down the
        # process while a POST is in flight.
        with self._lock:
            if cancel_event is None:
                return self._complete_locked(prompt)
            return self._complete_locked(prompt, cancel_event=cancel_event)

    def _complete_locked(self, prompt: str, *, cancel_event: threading.Event | None = None) -> str:
        if cancel_event is not None and cancel_event.is_set():
            raise TranslationCancelledError("translation cancelled before request")
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
            if cancel_event is not None and cancel_event.is_set():
                raise TranslationCancelledError("translation cancelled while waiting for the model")
        except TimeoutError as exc:
            raise TranslationError(f"translation did not answer within {_REQUEST_TIMEOUT_S:.0f}s") from exc
        except HTTPError as exc:
            raise TranslationError(f"translation service returned HTTP {exc.code}") from exc
        except (URLError, OSError, ValueError) as exc:
            raise TranslationError(f"translation request failed: {exc}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationError("translation response had no message content") from exc
        if not isinstance(content, str):
            raise TranslationError("translation response content was not text")
        return content.strip()

    def ensure_runtime(self) -> None:
        """Start (or reuse) the single model process without translating."""
        self._ensure_runtime()

    def note_activity(self) -> None:
        """Restart the idle countdown after a warm load or a successful POST."""
        if self._idle_seconds <= 0:
            return
        with self._idle_lock:
            self._idle_deadline = time.monotonic() + self._idle_seconds
            self._idle_activity.set()

    def start_idle_monitor(self) -> None:
        """Start the one idle-unload watcher for this cached service."""
        if self._idle_seconds <= 0:
            return
        with self._idle_lock:
            if self._idle_thread is not None:
                return
            thread = threading.Thread(
                target=self._idle_loop,
                name="translation-idle-unload",
                daemon=True,  # RACE-008: idle cleanup must never delay process exit
            )
            self._idle_thread = thread
            self._idle_activity.set()
            thread.start()

    def _idle_loop(self) -> None:
        while not self._idle_stop.is_set():
            with self._idle_lock:
                deadline = self._idle_deadline
            if deadline is None:
                self._idle_activity.wait(timeout=1.0)
                self._idle_activity.clear()
                continue
            remaining = deadline - time.monotonic()
            if remaining > 0:
                if self._idle_stop.wait(timeout=min(remaining, 1.0)):
                    return
                continue
            if self._try_idle_stop():
                with self._idle_lock:
                    self._idle_deadline = None
            else:
                # A request or warm load owns the runtime. Never tear it down
                # under a POST: push the deadline out by a full idle window.
                self.note_activity()

    def _try_idle_stop(self) -> bool:
        """Stop the runtime only when no request or warm load holds its lock."""
        if not self._lock.acquire(blocking=False):
            return False
        try:
            if self._runtime is None or not self._runtime.running:
                return False
            self._runtime.stop()
            self._runtime = None
            log.info("[TRANSLATE] idle unload stopped the translation runtime")
            return True
        finally:
            self._lock.release()

    def translate(
        self,
        text: str,
        target_code: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> str:
        """Translate one Stage A text; returns the source unchanged on error.

        Non-translatable spans are masked before the call and restored after,
        so URLs, emails, inline code and numbers survive byte-identical. A
        failure never overwrites the dictation and surfaces one user-facing
        notice per broken episode. ``cancel_event`` is opt-in and never used
        by the dictation pipeline; a cancellation is not a failure.
        """
        global _translation_failed_notified
        if cancel_event is not None and cancel_event.is_set():
            raise TranslationCancelledError("translation cancelled before start")
        target = normalize_language_code(target_code)
        if not target or not text.strip():
            return text
        protected, spans = protect_spans(text)
        markers = tuple(marker for marker, _original in spans)
        try:
            result = self._complete(
                build_user_prompt(protected, target, self.glossary, markers),
                cancel_event=cancel_event,
            )
            if cancel_event is not None and cancel_event.is_set():
                raise TranslationCancelledError("translation cancelled after the model answered")
            if not result:
                raise TranslationError("translation response was empty")
            result = restore_spans(result, spans)
        except TranslationCancelledError:
            raise
        except TranslationError as exc:
            log.warning("[TRANSLATE] %s; keeping original text", exc)
            _notify_translation_failure(_app_ref)
            return text
        except Exception:
            log.exception("[TRANSLATE] unexpected failure; keeping original text")
            _notify_translation_failure(_app_ref)
            return text
        with _translation_failed_lock:
            _translation_failed_notified = False
            _translation_model_missing_notified = False
        self.note_activity()
        return result

    def translate_batch(
        self,
        texts: list[str],
        target_code: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> list[str]:
        """Translate several already-decided texts through one loaded runtime.

        This is an opt-in helper for callers that own chunking (e.g. the
        benchmark). The dictation path sends the whole Stage A text in one call
        per ADR-0021 §5.2 and never uses this method.
        """
        if cancel_event is not None and cancel_event.is_set():
            raise TranslationCancelledError("batch cancelled before start")
        return [self.translate(text, target_code, cancel_event=cancel_event) for text in texts]

    def stop(self) -> None:
        """Stop the owned runtime and its idle watcher; safe to call twice.

        Waits for any in-flight request: terminating the process mid-POST would
        turn a healthy translation into a spurious failure.
        """
        self._idle_stop.set()
        self._idle_activity.set()
        with self._lock:
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
        _idle_seconds(config),
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
        _SERVICE.start_idle_monitor()
        return _SERVICE


def prewarm(config: Any) -> bool:
    """Start the cached translator ahead of the first dictation, if enabled.

    Explicit and best-effort: startup never blocks on a missing model and no
    user-facing notice is raised here. A later translate() still lazy-loads the
    runtime when this was not called.
    """
    if not bool(getattr(config, "translation_enabled", False)):
        return False
    if not _model_is_installed(config):
        # A missing model is never installed here: prewarm must not download,
        # load or block on a translator the user has not installed.
        return False
    try:
        get_service(config).ensure_runtime()
        return True
    except Exception:
        log.warning("[TRANSLATE] prewarm failed; first translation starts the runtime on demand", exc_info=True)
        return False


# Single-flight warm load. The service cache + its RLock already guarantee one
# process; these globals coalesce the THREADS so a burst of recordings does not
# spawn a warm worker per press.
_warm_lock = threading.Lock()
_warm_thread: threading.Thread | None = None
_warm_done = threading.Event()
_warm_key: tuple[object, ...] | None = None


def _warm_worker(config: Any) -> None:
    try:
        prewarm(config)
    except Exception:
        log.warning("[TRANSLATE] background warm failed; Stage B stays lazy", exc_info=True)
    finally:
        _warm_done.set()


def warm_on_user_record(config: Any) -> bool:
    """Queue a translator load when a USER starts recording.

    Called from the genuine recording-start entry, after the mic is open. All
    checks and the process start run on ONE daemon thread; the caller never
    waits on a model load. A second press while a load is in flight is
    coalesced. Returns True only when a new warm thread was started.
    """
    try:
        from voice_typer.server import dictation_origin

        if dictation_origin.current() not in dictation_origin.USER_ORIGINS:
            return False
    except Exception:
        # Older tree without the origin guard: the recording-start entry is
        # already user-gated (C-START-USER-1), so trust it.
        pass
    if not bool(getattr(config, "translation_warm_on_record", True)):
        return False
    # No local ASR model and no cloud backend means no Stage A text can ever
    # reach Stage B, so there is nothing to warm.
    if not str(getattr(config, "model_size", "") or "") and str(getattr(config, "asr_backend", "") or "") != "cloud":
        return False
    global _warm_thread, _warm_key
    key = _service_key(config)
    with _warm_lock:
        if _warm_thread is not None and _warm_thread.is_alive():
            return False
        _warm_done.clear()
        _warm_key = key
        thread = threading.Thread(
            target=_warm_worker,
            args=(config,),
            name="translation-warm",
            daemon=True,  # RACE-008: best-effort warm must never delay exit
        )
        _warm_thread = thread
        thread.start()
    return True


def _wait_for_inflight_warm(config: Any) -> None:
    """Let a warm load from recording start finish before Stage B begins."""
    with _warm_lock:
        thread, key, done = _warm_thread, _warm_key, _warm_done
    if thread is None or not thread.is_alive() or key != _service_key(config):
        return
    done.wait(_WARM_JOIN_TIMEOUT_S)
    if thread.is_alive():
        # The load is still running (slow cold cache). The service RLock still
        # serializes it with Stage B, so there is no second process; Stage B
        # simply proceeds with its own lazy path after this budget.
        log.warning("[TRANSLATE] warm load still in flight after %.0fs", _WARM_JOIN_TIMEOUT_S)


def translate_text(
    text: str,
    config: Any,
    target_code: str,
    spoken_code: str = "",
    app: Any | None = None,
    *,
    cancel_event: threading.Event | None = None,
) -> str:
    """Entry point used by the dictation pipeline's TranslationStage.

    ``app`` is optional and only used to surface a standalone-mode failure
    toast; the translation decision itself never depends on it.
    """
    _bind_app(app)
    if cancel_event is not None and cancel_event.is_set():
        raise TranslationCancelledError("translation cancelled before start")
    target = normalize_language_code(target_code)
    spoken = normalize_language_code(spoken_code or str(getattr(config, "language", "") or ""))
    if not bool(getattr(config, "translation_enabled", False)):
        return text
    if target and target not in TRANSLATION_TARGETS:
        log.warning("[TRANSLATE] unsupported target %r; keeping original text", target)
        _notify_translation_failure(app)
        return text
    if not needs_translation(text, target, spoken):
        return text
    spec = resolve_spec(str(getattr(config, "translation_model", "") or ""))
    if not _model_is_installed(config):
        # Fast refusal: no service construction, no process start, no download.
        # The original text is always kept and the user gets one actionable
        # notice instead of a raw TranslationError. No notice when Stage B
        # would have been skipped anyway (same language / empty text).
        log.warning("[TRANSLATE] %s not installed; keeping original text", spec.label)
        _notify_translation_model_missing(app)
        return text
    _wait_for_inflight_warm(config)
    try:
        return get_service(config).translate(text, target, cancel_event=cancel_event)
    except TranslationCancelledError:
        raise
    except TranslationError as exc:
        log.warning("[TRANSLATE] %s; keeping original text", exc)
        _notify_translation_failure(app)
        return text
    except Exception:
        log.exception("[TRANSLATE] unexpected failure; keeping original text")
        _notify_translation_failure(app)
        return text


def shutdown() -> None:
    """Stop the cached runtime and its idle watcher at process exit."""
    global _SERVICE, _SERVICE_KEY, _translation_failed_notified, _translation_model_missing_notified
    global _warm_thread, _warm_key
    with _SERVICE_LOCK:
        if _SERVICE is not None:
            _SERVICE.stop()
        _SERVICE = None
        _SERVICE_KEY = None
    with _warm_lock:
        if _warm_thread is None or not _warm_thread.is_alive():
            _warm_thread = None
            _warm_key = None
        _warm_done.set()
    with _translation_failed_lock:
        _translation_failed_notified = False
        _translation_model_missing_notified = False


atexit.register(shutdown)
