"""Provider + model descriptors and the explicit domain capability set."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from voice_typer.server.model_providers.errors import (
    ProviderCapabilityError,
    ProviderModelNotFoundError,
)


class Domain(StrEnum):
    """The three first-class model domains."""

    ASR = "asr"
    TTS = "tts"
    LLM = "llm"


class AuthKind(StrEnum):
    """How a provider authenticates."""

    NONE = "none"
    API_KEY = "api_key"
    LOCAL_ENDPOINT = "local_endpoint"


@dataclass(frozen=True)
class ModelDescriptor:
    """One selectable model in a provider's catalogue."""

    id: str
    label: str
    domains: frozenset[Domain]
    context_length: int | None = None
    prompt_price: float | None = None
    completion_price: float | None = None
    free: bool = False
    note: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports(self, domain: Domain) -> bool:
        return domain in self.domains

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "domains": sorted(str(d) for d in self.domains),
            "context_length": self.context_length,
            "prompt_price": self.prompt_price,
            "completion_price": self.completion_price,
            "free": self.free,
            "note": self.note,
            "metadata": dict(self.metadata),
        }


ModelListFn = Callable[[], list[ModelDescriptor]]
ClientFactory = Callable[[Domain, str], Any]
ProbeFn = Callable[[], dict[str, Any]]


@dataclass
class ProviderDescriptor:
    """A provider: identity, capability set, catalogue and client factory.

    ``unsupported_reason`` documents why a domain is missing instead of silently
    hiding the row (WP4: ASR/TTS must be listed as unsupported *with a reason*).
    """

    id: str
    label: str
    domains: frozenset[Domain]
    auth: AuthKind = AuthKind.NONE
    model_list: ModelListFn | None = None
    client_factory: ClientFactory | None = None
    unsupported_reason: dict[Domain, str] = field(default_factory=dict)
    config_fields: dict[str, str] = field(default_factory=dict)
    local: bool = False
    #: The model id is user-configured (legacy cloud slot / custom endpoint),
    #: so it may not appear in a catalogue we can enumerate.
    free_form_models: bool = False
    #: Authenticated reachability check for ``provider_test``. A public
    #: catalogue endpoint cannot prove a key works, so keyed providers supply
    #: a probe that raises a typed error when the key is rejected.
    auth_probe: ProbeFn | None = None

    def supports(self, domain: Domain) -> bool:
        return domain in self.domains

    def models(self, domain: Domain | None = None) -> list[ModelDescriptor]:
        """Return the catalogue, optionally filtered to one domain."""
        if self.model_list is None:
            return []
        models = list(self.model_list())
        if domain is None:
            return models
        return [m for m in models if m.supports(domain)]

    def find_model(self, model_id: str) -> ModelDescriptor | None:
        for model in self.models():
            if model.id == model_id:
                return model
        return None

    def probe(self) -> dict[str, Any] | None:
        """Run the authenticated probe (``None`` when the provider has none)."""
        if self.auth_probe is None:
            return None
        return self.auth_probe()

    def client(self, domain: Domain, model_id: str) -> Any:
        """Build a domain client, refusing an unadvertised capability."""
        if domain not in self.domains:
            raise ProviderCapabilityError(
                f"{self.id} does not serve the {domain} domain",
                provider=self.id,
                domain=domain.value,
            )
        if self.client_factory is None:
            raise ProviderCapabilityError(
                f"{self.id} has no client for the {domain.value} domain",
                provider=self.id,
                domain=domain.value,
            )
        if model_id and not self.free_form_models and self.model_list is not None and self.find_model(model_id) is None:
            raise ProviderModelNotFoundError(
                f"{self.id} does not offer model {model_id!r}",
                provider=self.id,
                domain=domain.value,
            )
        return self.client_factory(domain, model_id)

    def to_dict(self, domain: Domain | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "domains": sorted(d.value for d in self.domains),
            "auth": self.auth.value,
            "local": self.local,
            "models": [m.to_dict() for m in self.models(domain)],
            "unsupported_reason": {d.value: reason for d, reason in self.unsupported_reason.items()},
        }


__all__ = [
    "AuthKind",
    "ClientFactory",
    "Domain",
    "ModelDescriptor",
    "ModelListFn",
    "ProbeFn",
    "ProviderDescriptor",
]
