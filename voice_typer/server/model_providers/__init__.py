"""Provider registry: one entry per provider, three explicit domain contracts.

A provider advertises the domains it can serve through an explicit capability
set (:class:`~.descriptor.ProviderDescriptor.domains`); a domain client is only
ever built for an advertised capability, so a provider can never "almost" fit a
domain it does not implement.

The package is import-light on purpose: descriptors register lazily and the
concrete clients (HTTP, ONNX) are imported only when a client is requested.
"""

from __future__ import annotations

from voice_typer.server.model_providers.catalogue import (
    CatalogueCache,
    clear_catalogue_cache,
    get_catalogue_cache,
)
from voice_typer.server.model_providers.contracts import (
    AsrClient,
    ChatMessage,
    LlmClient,
    TtsAudio,
    TtsClient,
    TtsRequest,
)
from voice_typer.server.model_providers.descriptor import (
    Domain,
    ModelDescriptor,
    ProviderDescriptor,
)
from voice_typer.server.model_providers.errors import (
    ProviderAuthRequiredError,
    ProviderCapabilityError,
    ProviderConsentRequiredError,
    ProviderError,
    ProviderModelNotFoundError,
    ProviderNotFoundError,
    ProviderRuntimeError,
    ProviderUnavailableError,
)
from voice_typer.server.model_providers.registry import (
    ProviderRegistry,
    get_registry,
    register_builtin_providers,
)
from voice_typer.server.model_providers.routing import (
    ResolvedDomain,
    resolve_asr,
    resolve_llm,
    resolve_tts,
)
from voice_typer.server.model_providers.vault import (
    clear_provider_key,
    load_provider_key,
    mask_secret,
    provider_key_field,
    provider_key_status,
    store_provider_key,
)

__all__ = [
    "AsrClient",
    "CatalogueCache",
    "ChatMessage",
    "Domain",
    "LlmClient",
    "ModelDescriptor",
    "ProviderAuthRequiredError",
    "ProviderCapabilityError",
    "ProviderConsentRequiredError",
    "ProviderDescriptor",
    "ProviderError",
    "ProviderModelNotFoundError",
    "ProviderNotFoundError",
    "ProviderRegistry",
    "ProviderRuntimeError",
    "ProviderUnavailableError",
    "ResolvedDomain",
    "TtsAudio",
    "TtsClient",
    "TtsRequest",
    "clear_catalogue_cache",
    "clear_provider_key",
    "get_catalogue_cache",
    "get_registry",
    "load_provider_key",
    "mask_secret",
    "provider_key_field",
    "provider_key_status",
    "register_builtin_providers",
    "resolve_asr",
    "resolve_llm",
    "resolve_tts",
    "store_provider_key",
]
