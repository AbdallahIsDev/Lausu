"""Call-time provider resolution for the three domains.

Resolution happens when a call is made, never when config is saved: a provider
may be offline, keyless or still starting at save time. Every failure is a
typed :class:`ProviderError` so the UI can render a specific message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from voice_typer.server.model_providers.descriptor import Domain, ProviderDescriptor
from voice_typer.server.model_providers.errors import (
    ProviderAuthRequiredError,
    ProviderCapabilityError,
    ProviderConsentRequiredError,
    ProviderNotFoundError,
)
from voice_typer.server.model_providers.registry import ProviderRegistry, get_registry
from voice_typer.server.model_providers.vault import PROVIDER_KEY_FIELDS, load_provider_key

#: Providers whose data leaves the machine (consent + auth material required).
REMOTE_PROVIDERS: frozenset[str] = frozenset({"openrouter", "ollama", "lmstudio", "openai", "custom"})

#: ``(config field for the provider choice, model field, consent field, fallback field)``
DOMAIN_FIELDS: dict[Domain, tuple[str, str, str, str]] = {
    Domain.ASR: ("asr_provider", "asr_model_id", "asr_provider_consent", "asr_provider_fallback"),
    Domain.TTS: ("tts_provider", "tts_model_id", "tts_provider_consent", "tts_provider_fallback"),
    Domain.LLM: ("llm_provider", "llm_model_id", "llm_provider_consent", "llm_provider_fallback"),
}


@dataclass(frozen=True)
class ResolvedDomain:
    """One resolved provider choice for one call."""

    domain: Domain
    provider: ProviderDescriptor
    model_id: str
    consent_field: str
    fallback: str

    def client(self) -> Any:
        return self.provider.client(self.domain, self.model_id)

    def describe(self) -> str:
        return f"{self.provider.id}/{self.model_id or 'default'}"


def _default_provider(domain: Domain, config: Any) -> str:
    """Reproduce today's single-provider behaviour when nothing is configured."""
    if domain is Domain.ASR:
        return "cloud_direct" if str(getattr(config, "asr_backend", "whisper")) == "cloud" else "local"
    if domain is Domain.TTS:
        engine = str(getattr(config, "tts_engine", "off") or "off")
        return "local" if engine != "off" else "local"
    return "cloud_direct"


def _default_model(domain: Domain, config: Any, provider: str) -> str:
    if domain is Domain.ASR:
        if provider == "local":
            return str(getattr(config, "model_size", "") or "")
        return str(getattr(config, "cloud_model", "") or "")
    if domain is Domain.TTS:
        return str(getattr(config, "tts_engine", "off") or "")
    if provider == "local_onnx":
        return str(getattr(config, "local_onnx_model_id", "") or "")
    return str(getattr(config, "llm_model", "") or "")


def _is_loopback(url: str) -> bool:
    """True when ``url`` addresses this machine (localhost / 127.0.0.1 / [::1])."""
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    return host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost")


def effective_consent(config: Any, domain: Domain, provider_id: str) -> bool:
    """Consent that also honours the pre-existing single-provider gates.

    A user who already consented to LLM polish (or to a specific cloud ASR
    provider) must never be prompted again by the new per-domain flags.
    """
    if domain is Domain.LLM:
        return bool(getattr(config, "llm_provider_consent", False)) or bool(
            getattr(config, "llm_polish_consent", False)
        )
    if domain is Domain.ASR:
        provider = str(getattr(config, "cloud_provider", "") or provider_id)
        legacy = bool(getattr(config, f"cloud_{provider}_consent", False))
        return bool(getattr(config, "asr_provider_consent", False)) or legacy
    return bool(getattr(config, "tts_provider_consent", False))


def provider_requires_consent(config: Any, provider_id: str, descriptor: ProviderDescriptor) -> bool:
    """True when this call sends the domain's data off the machine.

    ``ollama`` is the case that matters: its descriptor is local (the normal
    deployment is ``localhost:11434``), but a key or a non-loopback base URL
    means the request leaves the device and consent applies.
    """
    if provider_id == "ollama":
        from voice_typer.server.model_providers.ollama import OLLAMA_LOCAL_BASE

        key = _provider_key(config, provider_id)
        base = str(getattr(config, "ollama_base_url", "") or OLLAMA_LOCAL_BASE)
        return bool(key) or not _is_loopback(base)
    return provider_id in REMOTE_PROVIDERS and not descriptor.local


def _provider_key(config: Any, provider_id: str, domain: Domain | None = None) -> str:
    if provider_id == "cloud_direct":
        # The legacy single-provider slot: LLM polish reads llm_api_key (falling
        # back to openai_api_key), cloud ASR reads cloud_api_key.
        if domain is Domain.ASR:
            return str(getattr(config, "cloud_api_key", "") or "")
        if domain is Domain.LLM:
            return str(getattr(config, "llm_api_key", "") or getattr(config, "openai_api_key", "") or "")
    field = PROVIDER_KEY_FIELDS.get(provider_id)
    if field:
        return str(getattr(config, field, "") or "")
    return str(getattr(config, f"{provider_id}_api_key", "") or "")


def resolve(
    domain: Domain,
    config: Any,
    *,
    registry: ProviderRegistry | None = None,
    model_id: str | None = None,
    require_consent: bool = True,
    require_auth: bool = True,
) -> ResolvedDomain:
    """Resolve ``domain`` to a provider descriptor + model id at call time."""
    reg = registry or get_registry()
    provider_field, model_field, consent_field, fallback_field = DOMAIN_FIELDS[domain]

    # Only a real string is a provider id: a test double (or a corrupt config)
    # must fall back to today's default, never become a MagicMock provider name.
    raw_provider = getattr(config, provider_field, "")
    configured = raw_provider.strip() if isinstance(raw_provider, str) else ""
    provider_id = configured or _default_provider(domain, config)
    descriptor = reg.maybe_get(provider_id)
    if descriptor is None:
        raise ProviderNotFoundError(
            f"unknown {domain.value} provider {provider_id!r}",
            provider=provider_id,
            domain=domain.value,
        )
    if not descriptor.supports(domain):
        raise ProviderCapabilityError(
            f"{provider_id} does not serve the {domain.value} domain",
            provider=provider_id,
            domain=domain.value,
        )

    raw_model = getattr(config, model_field, "")
    configured_model = raw_model if isinstance(raw_model, str) else ""
    chosen_model = (model_id or configured_model).strip()
    if not chosen_model:
        chosen_model = _default_model(domain, config, provider_id).strip()

    remote = provider_requires_consent(config, provider_id, descriptor)
    if remote and require_consent and not effective_consent(config, domain, provider_id):
        raise ProviderConsentRequiredError(
            f"{domain.value} provider {provider_id!r} needs explicit consent before data leaves the device",
            provider=provider_id,
            domain=domain.value,
            consent_field=consent_field,
        )
    if (
        remote
        and require_auth
        and descriptor.auth.value == "api_key"
        and not _provider_key(config, provider_id, domain)
    ):
        raise ProviderAuthRequiredError(
            f"{provider_id} needs an API key",
            provider=provider_id,
            domain=domain.value,
        )

    return ResolvedDomain(
        domain=domain,
        provider=descriptor,
        model_id=chosen_model,
        consent_field=consent_field,
        fallback=str(getattr(config, fallback_field, "off") or "off"),
    )


def resolve_asr(config: Any, **kwargs: Any) -> ResolvedDomain:
    return resolve(Domain.ASR, config, **kwargs)


def resolve_tts(config: Any, **kwargs: Any) -> ResolvedDomain:
    return resolve(Domain.TTS, config, **kwargs)


def resolve_llm(config: Any, **kwargs: Any) -> ResolvedDomain:
    return resolve(Domain.LLM, config, **kwargs)


def provider_key(config: Any, provider_id: str) -> str:
    """Public accessor used by the registry's client factories."""
    return _provider_key(config, provider_id) or load_provider_key(provider_id)


__all__ = [
    "DOMAIN_FIELDS",
    "REMOTE_PROVIDERS",
    "ResolvedDomain",
    "effective_consent",
    "provider_key",
    "provider_requires_consent",
    "resolve",
    "resolve_asr",
    "resolve_llm",
    "resolve_tts",
]
