"""Post-transcription enhancement stages (vocabulary, LLM polish hooks)."""

from __future__ import annotations

import contextlib
import hashlib
import logging
import threading
from typing import TYPE_CHECKING, Any

from voice_typer.server import i18n
from voice_typer.server._secrets import redact_secret
from voice_typer.server.branding import APP_NAME
from voice_typer.server.dictation_pipeline.helpers import (
    _EMPTY_SEGMENTS,
    _NO_TRANSCRIPT_CONFIDENCE,
)

if TYPE_CHECKING:
    # Annotation-only import: types the shared polish executor without
    import concurrent.futures

log = logging.getLogger(__name__)


# module-level singleton ``ThreadPoolExecutor`` for LLM polish.
_SHARED_POLISH_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None
_SHARED_POLISH_EXECUTOR_LOCK = threading.Lock()


def _get_shared_polish_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Return the module-level singleton ``ThreadPoolExecutor``."""
    global _SHARED_POLISH_EXECUTOR
    import concurrent.futures

    if _SHARED_POLISH_EXECUTOR is None:
        with _SHARED_POLISH_EXECUTOR_LOCK:
            if _SHARED_POLISH_EXECUTOR is None:
                _SHARED_POLISH_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
                    max_workers=1,
                    thread_name_prefix="llm-polish-shared",
                )
    return _SHARED_POLISH_EXECUTOR


def _reset_shared_polish_executor() -> None:
    """Drop the singleton executor (TEST-ONLY, used by tests to assert"""
    global _SHARED_POLISH_EXECUTOR
    with _SHARED_POLISH_EXECUTOR_LOCK:
        if _SHARED_POLISH_EXECUTOR is not None:
            with contextlib.suppress(Exception):
                _SHARED_POLISH_EXECUTOR.shutdown(wait=False)
        _SHARED_POLISH_EXECUTOR = None


class _EnhancementStepsMixin:
    """Mixin: LLM polish, AI enhancement, vocabulary-automation steps."""

    # Provided by ``_OrchestratorMixin`` in the composed
    _LLM_POLISH_PIPELINE_TIMEOUT_S: float

    # Set by ``_OrchestratorMixin.__init__`` (``app: Any``). Declared on
    _app: Any
    _cycle_id: str
    _templates_applied: bool

    # transcripts above this word count skip LLM polish
    _LLM_POLISH_WORD_LIMIT: int = 1500

    #: Providers served by the chunked local path. A small local model copies
    #: its input past ~150 words, so the length limit must NOT apply here.
    _LOCAL_LLM_PROVIDERS: frozenset[str] = frozenset({"local_onnx", "ollama", "lmstudio"})

    def _call_polish_with_timeout(self, polisher: Any, text: str) -> str:
        """Run ``polisher.polish(text)`` in a side-thread with a hard timeout.

        Returns
        """
        import concurrent.futures

        timeout_s = self._LLM_POLISH_PIPELINE_TIMEOUT_S
        # reuse the shared singleton executor across cycles.
        executor = _get_shared_polish_executor()
        # ``polisher`` is duck-typed (``Any``) with the documented
        future: concurrent.futures.Future[str] = executor.submit(polisher.polish, text)
        try:
            return future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            log.warning(
                "[LLM_POLISH] Polish timed out after %.1fs, returning unpolished text "
                "(the polish thread continues in the background and will exit when the "
                "inner 10s socket timeout fires or the LLM responds). (cycle=%s)",
                timeout_s,
                self._cycle_id,
            )
            return text
        # NO ``executor.shutdown(wait=False)`` here, the

    def _cycle_abort_token(self) -> Any:
        """Scoped abort for chunked local polish (stops at a chunk boundary)."""
        app = self._app
        cycle_id = self._cycle_id

        class _CycleAbort:
            def is_set(self) -> bool:
                from voice_typer.server.cycle_guard import is_cycle_live

                return not is_cycle_live(app, cycle_id)

        return _CycleAbort()

    def _polish_with_provider(self, text: str) -> str:
        """Polish through the resolved provider: chunked local, single-call remote."""
        from voice_typer.server.model_providers import resolve_llm
        from voice_typer.server.model_providers.errors import ProviderError

        try:
            resolved = resolve_llm(self._app.config)
        except ProviderError as exc:
            # Typed, user-renderable failure: never silently switch provider.
            log.warning(
                "[LLM_POLISH] provider resolution failed (code=%s provider=%s): %s; raw transcript returned (cycle=%s)",
                getattr(exc, "code", "server.provider_error"),
                getattr(exc, "provider", ""),
                redact_secret(str(exc)),
                self._cycle_id,
            )
            return text

        provider_id = resolved.provider.id
        model_id = resolved.model_id or "default"
        if provider_id in self._LOCAL_LLM_PROVIDERS:
            from voice_typer.server.llm_polish import system_prompt
            from voice_typer.server.model_providers.local_onnx.chunked import polish_chunked
            from voice_typer.server.model_providers.local_onnx.chunker import chunk_sentences

            polished = polish_chunked(
                resolved.client(),
                text,
                system_prompt(self._app.config.llm_preset),
                abort_event=self._cycle_abort_token(),
            )
            log.info(
                "[LLM_POLISH] provider=%s model=%s chunks=%d words=%d (cycle=%s)",
                provider_id,
                model_id,
                len(chunk_sentences(text)),
                len(text.split()),
                self._cycle_id,
            )
            return polished

        _word_count = len(text.split())
        if _word_count > self._LLM_POLISH_WORD_LIMIT:
            log.info(
                "[LLM_POLISH] Skipping polish for long transcript "
                "(word_count=%d > limit=%d), preserves 4s pipeline "
                "budget for short utterances; raw transcript returned. "
                "(cycle=%s)",
                _word_count,
                self._LLM_POLISH_WORD_LIMIT,
                self._cycle_id,
            )
            return text
        if self._app._llm_polisher is None:
            from voice_typer.server.llm_polish import LLMPolisher

            self._app._llm_polisher = LLMPolisher(
                api_key=self._app.config.llm_api_key or getattr(self._app.config, "openai_api_key", ""),
                api_url=self._app.config.llm_api_url or None,
                model=self._app.config.llm_model or None,
                preset=self._app.config.llm_preset,
                enabled=True,
            )
        out = self._call_polish_with_timeout(self._app._llm_polisher, text)
        log.info(
            "[LLM_POLISH] provider=%s model=%s chunks=1 words=%d (cycle=%s)",
            provider_id,
            model_id,
            _word_count,
            self._cycle_id,
        )
        return out

    def _llm_polish_gates(self) -> tuple[bool, bool]:
        """``(has_credential, consented)`` for the configured Polish provider.

        Mirrors ``model_providers.routing.resolve`` so a provider selected in the
        UI (its key in the vault) is not re-gated by the legacy ``llm_api_key``
        field, while an on-device provider needs neither key nor remote consent.
        """
        config = self._app.config
        raw = getattr(config, "llm_provider", "")
        provider_id = raw.strip() if isinstance(raw, str) else ""
        if not provider_id or provider_id == "cloud_direct":
            legacy_key = config.llm_api_key or getattr(config, "openai_api_key", "")
            return bool(legacy_key), bool(getattr(config, "llm_polish_consent", False))

        from voice_typer.server.model_providers.descriptor import Domain
        from voice_typer.server.model_providers.registry import get_registry
        from voice_typer.server.model_providers.routing import (
            effective_consent,
            provider_key,
            provider_requires_consent,
        )

        descriptor = get_registry().maybe_get(provider_id)
        if descriptor is None:
            # Let ``resolve_llm`` raise the typed ProviderNotFoundError instead.
            return True, True
        remote = provider_requires_consent(config, provider_id, descriptor)
        needs_key = remote and descriptor.auth.value == "api_key"
        has_credential = not needs_key or bool(provider_key(config, provider_id))
        consented = not remote or effective_consent(config, Domain.LLM, provider_id)
        return has_credential, consented

    def _apply_llm_polish(self, text: str) -> str:
        """Step 7: Apply LLM polishing (if consented)."""
        has_credential, consented = self._llm_polish_gates()
        if self._app.config.llm_polish and has_credential and consented:
            # privacy NOTICE when templates were applied
            if self._templates_applied:
                log.info(
                    "[LLM_POLISH] Templates were applied before LLM polish this cycle, "
                    "text MAY contain substituted content (e.g. {clipboard}). The "
                    "redact_pii gate in llm_polish._call_api will strip common PII "
                    "patterns (cards/SSNs/emails/phones/API keys) before the API send. "
                    "(cycle=%s)",
                    self._cycle_id,
                )
                # Defense-in-depth sanity check: verify redact_pii is
                try:
                    from voice_typer.server.security import redact_pii as _redact_pii_sanity_check  # noqa: F401
                except ImportError:
                    log.warning(
                        "[LLM_POLISH] redact_pii not importable (security module broken) "
                        "AND templates were applied this cycle, skipping LLM polish to "
                        "prevent potential clipboard-content exfiltration (fail-closed). "
                        "(cycle=%s)",
                        self._cycle_id,
                    )
                    return text
            try:
                text = self._polish_with_provider(text)
            except Exception as exc:
                # redact the exception message before
                log.warning("[LLM_POLISH] Polish failed: %s", redact_secret(str(exc)))
                # previously this except block only logged a
                if not getattr(self._app, "_llm_polish_fail_notified", False):
                    self._app._llm_polish_fail_notified = True
                    with contextlib.suppress(Exception):
                        self._app.tray.notify(
                            APP_NAME,
                            i18n.t("notify.dictation_pipeline.llm_polish_failed"),
                        )
                with contextlib.suppress(Exception):
                    from voice_typer.server import event_bus

                    event_bus.publish({"type": "llm_polish_failed"})
        elif (self._app.config.llm_polish and has_credential and not consented) and not getattr(
            self._app, "_llm_consent_warned", False
        ):
            log.info("[LLM_POLISH] llm_polish is enabled but llm_polish_consent is False, skipping polish.")
            self._app._llm_consent_warned = True
            # Surface the silent skip: publish a ``consent_required``
            with contextlib.suppress(Exception):
                from voice_typer.server import event_bus

                event_bus.publish(
                    {
                        "type": "consent_required",
                        "data": {"consent_field": "llm_polish_consent"},
                    }
                )
        return text

    def _analyze_vocabulary(self, text: str) -> None:
        """Step 7c: Analyze transcription for vocabulary suggestions (P5)."""
        if not getattr(self._app.config, "vocabulary_automation_enabled", False):
            return
        try:
            automation = getattr(self._app, "_vocabulary_automation", None)
            if automation is None:
                # Lazy-init on first use. The VocabularyAutomation
                from voice_typer.server.vocabulary_automation import VocabularyAutomation

                vm = self._app._vocabulary_manager
                if vm is None:
                    from voice_typer.server.vocabulary import VocabularyManager

                    vm = VocabularyManager()
                    self._app._vocabulary_manager = vm
                automation = VocabularyAutomation(vm, self._app.config)
                self._app._vocabulary_automation = automation

            # Faster-whisper exposes segment-level avg_logprob, not
            segments: tuple = _EMPTY_SEGMENTS
            confidence: float = _NO_TRANSCRIPT_CONFIDENCE
            suggestions = automation.analyze_transcription(
                text,
                segments,
                confidence,
            )
            if not suggestions:
                return

            # Auto-apply high-confidence suggestions.
            auto_threshold = getattr(
                self._app.config,
                "vocabulary_auto_apply_threshold",
                0.95,
            )
            applied = automation.auto_apply_high_confidence_suggestions(auto_threshold)
            if applied > 0:
                log.info("[VOCAB_AUTO] Auto-applied %d high-confidence suggestions", applied)

            # Push any remaining (pending) suggestions to the frontend.
            pending = automation.get_pending_suggestions()
            if pending:
                # only re-publish when the pending list actually
                _current_sig = (
                    len(pending),
                    hashlib.sha256(
                        "\x1f".join(f"{s.original}\x1e{s.corrected}\x1e{s.confidence}" for s in pending).encode(
                            "utf-8", errors="replace"
                        )
                    ).hexdigest(),
                )
                _last_sig = getattr(self._app, "_last_vocab_sig", None)
                if _last_sig == _current_sig:
                    # No change since last publish, skip the redundant
                    log.debug(
                        "[VOCAB_AUTO] pending list unchanged (count=%d, sig=%s…), "
                        "skipping redundant vocabulary_suggestion publish. (cycle=%s)",
                        _current_sig[0],
                        _current_sig[1][:8],
                        self._cycle_id,
                    )
                else:
                    self._app._last_vocab_sig = _current_sig
                    try:
                        from voice_typer.server import event_bus

                        event_bus.publish(
                            {
                                "type": "vocabulary_suggestion",
                                "data": {
                                    "suggestions": [
                                        {
                                            "original": s.original,
                                            "corrected": s.corrected,
                                            "confidence": s.confidence,
                                            "context": s.context,
                                            "timestamp": s.timestamp,
                                        }
                                        for s in pending
                                    ],
                                },
                            }
                        )
                    except Exception:
                        log.debug(
                            "[VOCAB_AUTO] could not push vocabulary_suggestion event",
                            exc_info=True,
                        )
        except Exception:
            log.warning("[VOCAB_AUTO] Analysis failed", exc_info=True)
