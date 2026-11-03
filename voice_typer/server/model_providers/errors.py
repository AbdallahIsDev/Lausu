"""Typed provider errors the UI can render without string matching."""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base for every provider-layer failure (carries an IPC ``code``)."""

    code: str = "server.provider_error"
    provider: str = ""
    domain: str = ""

    def __init__(self, message: str = "", *, provider: str = "", domain: str = "") -> None:
        super().__init__(message)
        if provider:
            self.provider = provider
        if domain:
            self.domain = domain

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "provider": self.provider,
            "domain": self.domain,
            "message": str(self.args[0]) if self.args else "",
        }


class ProviderNotFoundError(ProviderError):
    """Unknown provider id in the routing config."""

    code = "server.provider_unknown"


class ProviderModelNotFoundError(ProviderError):
    """The selected model id is not in the provider's catalogue."""

    code = "server.provider_model_unknown"


class ProviderCapabilityError(ProviderError):
    """The provider does not advertise the requested domain."""

    code = "server.provider_unsupported_domain"


class ProviderConsentRequiredError(ProviderError):
    """Sending this domain's data to a remote provider needs consent."""

    code = "server.provider_consent_required"
    consent_field: str = ""

    def __init__(
        self,
        message: str = "",
        *,
        provider: str = "",
        domain: str = "",
        consent_field: str = "",
    ) -> None:
        super().__init__(message, provider=provider, domain=domain)
        self.consent_field = consent_field or f"{domain}_provider_consent"


class ProviderAuthRequiredError(ProviderError):
    """No API key / auth material for a remote provider."""

    code = "server.provider_auth_required"


class ProviderUnavailableError(ProviderError):
    """The provider endpoint is unreachable or returned a typed remote error."""

    code = "server.provider_unavailable"


class ProviderRuntimeError(ProviderError):
    """A local provider runtime failed (missing model, bad graph, no ORT)."""

    code = "server.provider_runtime_error"


__all__ = [
    "ProviderAuthRequiredError",
    "ProviderCapabilityError",
    "ProviderConsentRequiredError",
    "ProviderError",
    "ProviderModelNotFoundError",
    "ProviderNotFoundError",
    "ProviderRuntimeError",
    "ProviderUnavailableError",
]
