"""Config-backed cloud ASR backend — the registry entry named ``"cloud"``.

``CloudEngine`` is per-transcription by design: it is constructed with a
provider, an API key, a URL, a model and a consent flag, and it keeps no
reference to the Config object. The registry, however, needs a long-lived
object it can register under a name and hand back from ``get_active()``.

:class:`CloudAsrBackend` closes that gap. It *is* a ``CloudEngine`` subclass
rather than a wrapper, because ``dictation_pipeline/transcribe_step.py``
routes on ``isinstance(active, CloudEngine)`` to pick up the cloud→local
fallback and the quality summary; a plain wrapper would silently lose both.

It re-reads provider / key / URL / model / consent from the live Config on
every ``load()`` and every ``transcribe()``, so saving a key in Settings takes
effect on the next dictation without restarting the app.

Resolution rules — only a NAMED provider can activate cloud:

* ``cloud_provider`` names one of :data:`CLOUD_PROVIDER_KEYS`; the endpoint
  comes from :data:`_PROVIDER_DEFAULTS` and the key from that provider's own
  ``<provider>_api_key`` field. ``cloud_api_url`` is deliberately IGNORED on
  this path: honouring it would let a stored key be posted to an arbitrary
  host, which is the SEC-011 endpoint-swap class.
* an empty or unknown ``cloud_provider`` resolves to nothing, and the backend
  reports ``is_loaded == False`` so ``RegistryCore.get_active()`` degrades to
  whisper. The legacy self-hosted trio (``cloud_api_key`` + ``cloud_api_url``
  + ``cloud_model``) is left inert rather than half-honoured: it has no
  provider-known endpoint to pin a key to, and it never had a working
  construction path to begin with.
"""

from __future__ import annotations

import logging
from typing import Any

from voice_typer.server.cloud._defaults import _PROVIDER_DEFAULTS
from voice_typer.server.cloud._engine import CloudEngine
from voice_typer.server.credential_store import PROVIDER_TO_CONFIG_FIELD
from voice_typer.server.i18n import DEFAULT_LOCALE

log = logging.getLogger(__name__)

#: Registry name for this backend (``AsrBackendRegistry._BACKEND_SPECS``).
CLOUD_BACKEND_NAME = "cloud"

#: ``cloud_provider`` values the backend understands. Kept in step with the
#: renderer's catalogue in ``client/src/renderer/src/lib/utils/models.ts`` and
#: with :data:`_PROVIDER_DEFAULTS`.
CLOUD_PROVIDER_KEYS: tuple[str, ...] = ("openai", "groq", "deepgram", "gemini")


def consent_field_for(provider: str) -> str:
    """Config field carrying ``provider``'s explicit audio-transmission consent."""
    return f"cloud_{provider}_consent"


def _clean(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def resolve_cloud_target(config: object) -> tuple[str, str, str, str, bool] | None:
    """Resolve ``(provider, api_key, api_url, model, consent_given)`` from ``config``.

    Returns ``None`` when no usable provider is selected — see the module
    docstring for why an unknown provider is a hard "not configured" rather
    than a silent fallback to the self-hosted trio.
    """
    provider = _clean(getattr(config, "cloud_provider", ""))
    if provider not in CLOUD_PROVIDER_KEYS:
        if provider:
            log.warning(
                "[CLOUD] cloud_provider %r is not a known provider, cloud stays inactive",
                provider,
            )
        return None

    defaults = _PROVIDER_DEFAULTS[provider]
    key_field = PROVIDER_TO_CONFIG_FIELD.get(provider, "")
    api_key = _clean(getattr(config, key_field, "")) if key_field else ""
    # An explicitly chosen model wins; otherwise the provider's documented
    # default, so a freshly activated provider is usable without a second
    # round-trip through Settings.
    model = _clean(getattr(config, "cloud_model", "")) or str(defaults["model"])
    consent = bool(getattr(config, consent_field_for(provider), False))
    return provider, api_key, str(defaults["url"]), model, consent


class CloudAsrBackend(CloudEngine):
    """``CloudEngine`` bound to the live Config, registerable as ``"cloud"``."""

    def __init__(
        self,
        config: Any,
        local_engine_factory: Any | None = None,
    ) -> None:
        self._config = config
        super().__init__(
            provider="",
            api_key="",
            api_url="",
            model="",
            language=getattr(config, "language", DEFAULT_LOCALE) or DEFAULT_LOCALE,
            consent_given=False,
            local_engine_factory=local_engine_factory,
        )
        self._sync_from_config()

    def _sync_from_config(self) -> None:
        """Refresh the provider/key/url/model/consent tuple from the live Config."""
        target = resolve_cloud_target(self._config)
        if target is None:
            self.provider = ""
            self.api_key = ""
            self.api_url = ""
            self.model_name = ""
            self.consent_given = False
            return
        provider, api_key, api_url, model, consent = target
        self.provider = provider
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model
        self.consent_given = consent
        self.language = getattr(self._config, "language", DEFAULT_LOCALE) or DEFAULT_LOCALE

    def load(self, progress_callback: Any | None = None) -> None:
        """Re-resolve the target, then report readiness.

        There is no local model to load; the point of re-resolving here is
        that ``RegistryCore.load_with_fallback`` is the one place every
        activation path funnels through, so a key saved in Settings is picked
        up on the next activation as well as on the next dictation.
        """
        self._sync_from_config()
        super().load(progress_callback)

    def transcribe(self, audio: Any) -> str:
        """Re-resolve the target before every request, then transcribe."""
        self._sync_from_config()
        return super().transcribe(audio)

    def unload(self) -> None:
        """No-op — deliberately does NOT clear ``_loaded``.

        The idle-unload timer calls ``unload()`` on the active backend after
        ``model_idle_unload_minutes`` of silence. ``CloudEngine.unload`` sets
        ``_loaded = False``, and ``is_loaded`` is what ``get_active()`` reads,
        so honouring it would silently demote an idle cloud backend to whisper
        for the rest of the session. Cloud holds no local resources, so there
        is nothing to release.
        """
        return


def is_cloud_backend(backend: object) -> bool:
    """True when ``backend`` is a cloud (network) engine.

    Name check first: test doubles share the class name without sharing
    the import identity.
    """
    if backend is None:
        return False
    if type(backend).__name__ == "CloudEngine":
        return True
    return isinstance(backend, CloudEngine)


def active_engine_is_cloud(app: Any) -> bool:
    """True when the app's active transcriber is a cloud engine.

    Exception-shielded: a probe failure must never break the caller (the
    ESC-cancel path calls this mid-flight).
    """
    try:
        models = getattr(app, "models", None)
        active = models.active_transcriber() if models is not None else None
    except Exception:
        return False
    return is_cloud_backend(active)
