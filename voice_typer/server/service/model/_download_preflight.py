"""Pre-download gates: LLM endpoint probe and HuggingFace consent."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from voice_typer.server._secrets import redact_secret, redact_url
from voice_typer.server.service._download_helpers import DownloadOutcome

if TYPE_CHECKING:
    from voice_typer.server.app import LausuApp

log = logging.getLogger(__name__)


class DownloadPreflightMixin:

    """Pre-download gates: LLM endpoint probe and HuggingFace consent.

    Host-state contract: the declarations below are attributes the
    composed ``ModelMixin`` (or a sibling mixin) owns.
    """

    _app: LausuApp


    def test_llm_connection(self) -> dict[str, object]:
        """Test the LLM polish API connection.

        ``LLMPolisher.test_connection`` was previously
        dead, no IPC route or UI button invoked it.  We now expose
        it via the service layer so the renderer can wire up a "Test
        connection" button on the Settings page (where the user
        configures llm_api_key / llm_api_url / llm_model).

        Returns ``{"success": bool, "message": str}``.
        """
        cfg = getattr(self._app, "config", None)
        if cfg is None:
            return {"success": False, "message": "Config not loaded"}

        #  fix: gate on consent BEFORE sending any test request.
        if not getattr(cfg, "llm_polish_consent", False):
            return {
                "success": False,
                "message": "LLM polish consent not given. Enable LLM polish in Settings to test the connection.",
            }

        # Use the same consent + key-resolution logic as the polish path
        effective_key = getattr(cfg, "llm_api_key", "") or ""
        if not effective_key:
            return {"success": False, "message": "API key not configured"}

        try:
            from voice_typer.server.llm_polish import LLMPolisher

            polisher = LLMPolisher(
                api_key=effective_key,
                api_url=getattr(cfg, "llm_api_url", "") or None,
                model=getattr(cfg, "llm_model", "") or None,
                preset=getattr(cfg, "llm_preset", "professional"),
                enabled=True,
            )
            success, message = polisher.test_connection()
            return {"success": success, "message": message}
        except Exception as exc:
            log.warning("[SERVICE] test_llm_connection failed: %s", exc)
            return {"success": False, "message": redact_secret(redact_url(str(exc)))}

    def _require_huggingface_consent(self, model_name: str) -> DownloadOutcome | None:
        """Gate IPC-triggered HuggingFace downloads on explicit consent.

        Mirrors the consent gate in
        :meth:`voice_typer.server.transcription.TranscriptionEngine._pre_download_model`
        (transcription.py:835-849).  The IPC download path previously
        had NO consent check, so clicking "Download" on the Models page
        phoned home to huggingface.co (revealing the user's IP to a
        US-headquartered third party) without the explicit GDPR
        Art. 13/44 consent that ``config.huggingface_consent`` was
        specifically designed to gate ().

        Returns ``None`` when consent has been given, the caller
        proceeds with the download.  Returns a :data:`DownloadOutcome`
        failure dict AND publishes a ``consent_required`` event when
        consent is missing; the renderer is responsible for showing
        the consent dialog and retrying the download after the user
        accepts.

        Defensive: ``self._app.config`` may be ``None`` in degenerate
        paths (test stubs, benchmark harness).  Treat missing config
        as NOT consented, safe default per GDPR Art. 6/13.

        Returns a :data:`DownloadOutcome` (TypedDict) so the caller's
        ``return consent_err`` line type-checks without
        ``# type: ignore[return-value]``. The returned dict's runtime
        shape is preserved verbatim (``success``, ``error``,
        ``consent_required``, ``model``).
        """
        from voice_typer.server import event_bus

        cfg = getattr(self._app, "config", None)
        consent = False if cfg is None else bool(getattr(cfg, "huggingface_consent", False))
        if not consent:
            log.warning(
                "[SERVICE] HuggingFace consent not given, refusing to download "
                "model '%s' via IPC. The renderer should show the consent dialog.",
                model_name,
            )
            try:
                event_bus.publish(
                    {
                        "type": "consent_required",
                        "data": {
                            "provider": "huggingface",
                            "model": model_name,
                            "message": "HuggingFace consent required before downloading model.",
                        },
                    }
                )
            except Exception:
                log.debug("[SERVICE] consent_required event push failed", exc_info=True)
            return {
                "success": False,
                "error": "HuggingFace consent required",
                "consent_required": True,
                "model": model_name,
            }
        return None
