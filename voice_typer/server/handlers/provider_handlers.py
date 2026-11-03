"""Provider IPC handlers: catalogue, keys and per-domain routing.

The renderer never sees a stored key: reads return ``masked`` only, and the
write path goes through the credential store (never ``config.json``). Per-domain
selection is persisted through ``set_config`` so the SEC-002 allowlist and
``config_changed`` push stay the single write path (C-CONF-1).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.handlers._log import log
from voice_typer.server.ipc.validation import ErrorCodes, ResponseEnvelope
from voice_typer.server.model_providers import (
    Domain,
    ProviderError,
    clear_provider_key,
    get_catalogue_cache,
    get_registry,
    provider_key_status,
    store_provider_key,
)
from voice_typer.server.model_providers.errors import ProviderAuthRequiredError
from voice_typer.server.model_providers.routing import DOMAIN_FIELDS, effective_consent, provider_requires_consent

#: Commands whose payload is a provider id only.
_PROVIDER_ONLY = {"provider": {"type": str, "required": True}}


class ProviderHandlersMixin(HandlerBase):
    """Mixin: model-provider registry + per-domain selection."""

    if TYPE_CHECKING:  # defined by ConfigHandlersMixin on the composed server

        def _handle_set_config(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None: ...

    def _provider_error(self, resp: ResponseEnvelope, exc: Exception, cmd: str) -> ResponseEnvelope:
        """Emit a typed provider envelope, never a bare internal error."""
        if isinstance(exc, ProviderError):
            log.warning("[PROVIDERS] %s failed: %s", cmd, exc)
            resp["type"] = "error"
            resp["data"] = {
                "code": getattr(exc, "code", ErrorCodes.PROVIDER_RUNTIME_ERROR),
                "message": str(exc),
                "provider": getattr(exc, "provider", ""),
                "domain": getattr(exc, "domain", ""),
            }
            return resp
        return self._respond_with_error(resp, exc, cmd)

    def _provider_id(self, data: object | None) -> str:
        if not isinstance(data, dict):
            return ""
        raw = data.get("provider")
        return raw.strip() if isinstance(raw, str) else ""

    # ------------------------------------------------------------------ reads

    def _handle_provider_list(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``provider_list`` (read-only): providers + domain selections."""
        try:
            registry = get_registry()
            config = self.app.config
            providers: list[dict[str, Any]] = []
            for descriptor in registry.all():
                entry = descriptor.to_dict()
                if descriptor.auth.value == "api_key":
                    entry["key"] = provider_key_status(descriptor.id)
                    entry["consent_required"] = provider_requires_consent(config, descriptor.id, descriptor)
                else:
                    entry["key"] = {"provider": descriptor.id, "configured": False, "masked": ""}
                    entry["consent_required"] = False
                providers.append(entry)
            domains: dict[str, Any] = {}
            for domain, (provider_field, model_field, consent_field, fallback_field) in DOMAIN_FIELDS.items():
                configured = getattr(config, provider_field, "")
                provider = configured.strip() if isinstance(configured, str) else ""
                model = getattr(config, model_field, "")
                domains[domain.value] = {
                    "provider": provider,
                    "model_id": model if isinstance(model, str) else "",
                    "consent_field": consent_field,
                    "consent": effective_consent(config, domain, provider or "local"),
                    "fallback": str(getattr(config, fallback_field, "off") or "off"),
                    "enabled": bool(provider),
                }
            resp["type"] = "provider_list_result"
            resp["data"] = {"providers": providers, "domains": domains}
        except Exception as exc:
            return self._provider_error(resp, exc, "provider_list")
        return resp

    def _handle_provider_models(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``provider_models`` (read-only): one provider's catalogue."""
        provider = self._provider_id(data)
        if not provider:
            return self._error_response(
                resp, "Missing 'provider' parameter", code=ErrorCodes.MISSING_FIELD, field="provider"
            )
        raw_domain = data.get("domain") if isinstance(data, dict) else None
        domain: Domain | None = None
        if isinstance(raw_domain, str) and raw_domain:
            try:
                domain = Domain(raw_domain)
            except ValueError:
                return self._error_response(
                    resp, f"Unknown domain {raw_domain!r}", code=ErrorCodes.INVALID_FIELD, field="domain"
                )
        refresh = bool(isinstance(data, dict) and data.get("refresh"))
        try:
            descriptor = get_registry().get(provider)
            cache = get_catalogue_cache()
            snapshot = None if refresh else cache.read(provider)
            stale = False
            if snapshot is not None and (snapshot.models or descriptor.local):
                models = snapshot.models
                stale = snapshot.stale
            else:
                models = []
                for model in descriptor.models(domain):
                    entry = model.to_dict()
                    if domain is not None:
                        entry["domains"] = [domain.value]
                    models.append(entry)
                if models and descriptor.auth.value == "api_key":
                    cache.write(provider, models)
            if domain is not None:
                models = [m for m in models if domain.value in (m.get("domains") or [])]
            resp["type"] = "provider_models_result"
            resp["data"] = {
                "provider": provider,
                "domain": domain.value if domain else None,
                "models": models,
                "stale": stale,
            }
        except Exception as exc:
            return self._provider_error(resp, exc, "provider_models")
        return resp

    # ----------------------------------------------------------------- writes

    def _handle_provider_test(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``provider_test``: prove the provider answers with its config."""
        provider = self._provider_id(data)
        if not provider:
            return self._error_response(
                resp, "Missing 'provider' parameter", code=ErrorCodes.MISSING_FIELD, field="provider"
            )
        try:
            descriptor = get_registry().get(provider)
            # Testing a keyed provider before a key exists can only produce a
            # remote 401; answer it locally instead of sending a request.
            if descriptor.auth.value == "api_key" and not provider_key_status(provider).get("configured"):
                raise ProviderAuthRequiredError(f"{provider} has no API key configured", provider=provider)
            models = descriptor.models()
            # A public catalogue says nothing about the stored key, so keyed
            # providers run an authenticated probe and fail on a bad key.
            probe = descriptor.probe()
            resp["type"] = "provider_test_result"
            resp["data"] = {
                "provider": provider,
                "ok": True,
                "models": len(models),
                "label": descriptor.label,
                "domains": sorted(d.value for d in descriptor.domains),
                "auth": probe,
            }
        except Exception as exc:
            return self._provider_error(resp, exc, "provider_test")
        return resp

    def _handle_provider_set_key(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``provider_set_key``: store/rotate one key (never echoed)."""
        provider = self._provider_id(data)
        if not provider:
            return self._error_response(
                resp, "Missing 'provider' parameter", code=ErrorCodes.MISSING_FIELD, field="provider"
            )
        raw_key = data.get("key") if isinstance(data, dict) else None
        if not isinstance(raw_key, str) or not raw_key.strip():
            return self._error_response(resp, "Missing 'key' parameter", code=ErrorCodes.MISSING_FIELD, field="key")
        if get_registry().maybe_get(provider) is None:
            return self._error_response(
                resp, f"Unknown provider {provider!r}", code=ErrorCodes.PROVIDER_UNKNOWN, field="provider"
            )
        try:
            result = store_provider_key(provider, raw_key.strip())
            get_catalogue_cache().invalidate(provider)
            resp["type"] = "provider_set_key_result"
            resp["data"] = result
        except Exception as exc:
            return self._provider_error(resp, exc, "provider_set_key")
        return resp

    def _handle_provider_clear_key(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``provider_clear_key``: forget one key, return the new status."""
        provider = self._provider_id(data)
        if not provider:
            return self._error_response(
                resp, "Missing 'provider' parameter", code=ErrorCodes.MISSING_FIELD, field="provider"
            )
        if get_registry().maybe_get(provider) is None:
            return self._error_response(
                resp, f"Unknown provider {provider!r}", code=ErrorCodes.PROVIDER_UNKNOWN, field="provider"
            )
        try:
            clear_provider_key(provider, self.app.config)
            get_catalogue_cache().invalidate(provider)
            resp["type"] = "provider_clear_key_result"
            resp["data"] = provider_key_status(provider)
        except Exception as exc:
            return self._provider_error(resp, exc, "provider_clear_key")
        return resp

    def _handle_provider_set_domain(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle ``provider_set_domain``: persist one domain's selection."""
        if not isinstance(data, dict):
            return self._error_response(
                resp, "provider_set_domain requires data: object", code=ErrorCodes.INVALID_PAYLOAD
            )
        raw_domain = data.get("domain")
        try:
            domain = Domain(raw_domain) if isinstance(raw_domain, str) else Domain("")
        except ValueError:
            return self._error_response(
                resp, "Invalid 'domain' parameter", code=ErrorCodes.INVALID_FIELD, field="domain"
            )
        provider_field, model_field, consent_field, _fallback_field = DOMAIN_FIELDS[domain]
        provider = self._provider_id(data)
        model_id = data.get("model_id")
        enabled = data.get("enabled")
        consent = data.get("consent")
        if provider and enabled is False:
            provider = ""
        payload: dict[str, Any] = {}
        try:
            descriptor = get_registry().maybe_get(provider) if provider else None
            if provider:
                if descriptor is None:
                    return self._error_response(
                        resp, f"Unknown provider {provider!r}", code=ErrorCodes.PROVIDER_UNKNOWN, field="provider"
                    )
                if not descriptor.supports(domain):
                    return self._error_response(
                        resp,
                        f"{provider} does not serve the {domain.value} domain",
                        code=ErrorCodes.PROVIDER_UNSUPPORTED_DOMAIN,
                        field="provider",
                    )
                payload[provider_field] = provider
            elif enabled is False:
                payload[provider_field] = ""
            if isinstance(model_id, str):
                catalogue = descriptor.models(domain) if descriptor is not None else []
                if (
                    model_id
                    and descriptor is not None
                    and catalogue
                    and not descriptor.free_form_models
                    and descriptor.find_model(model_id) is None
                ):
                    return self._error_response(
                        resp,
                        f"{provider} does not offer model {model_id!r}",
                        code=ErrorCodes.PROVIDER_MODEL_UNKNOWN,
                        field="model_id",
                    )
                payload[model_field] = model_id
            if isinstance(consent, bool):
                payload[consent_field] = consent
            if not payload:
                return self._error_response(resp, "Nothing to change", code=ErrorCodes.INVALID_PAYLOAD, field="domain")
        except ProviderError as exc:
            return self._provider_error(resp, exc, "provider_set_domain")
        # SEC-002: reuse the single write path (validation + persistence + push).
        envelope = self._handle_set_config(payload, resp)
        if envelope is None or envelope.get("type") == "error":
            return envelope
        previous = envelope.get("data")
        merged: dict[str, Any] = dict(previous) if isinstance(previous, dict) else {}
        merged.update({"domain": domain.value, "fields": sorted(payload)})
        envelope["type"] = "provider_domain_result"
        envelope["data"] = merged
        return envelope
