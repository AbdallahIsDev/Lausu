"""Registration of every in-repo provider.

Built-ins are registered eagerly (descriptors are cheap); client construction
reads the current ``Config`` at call time, so a provider can be configured,
keyed or brought online after registration.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from voice_typer.server.model_providers.descriptor import (
    AuthKind,
    Domain,
    ModelDescriptor,
    ProviderDescriptor,
)
from voice_typer.server.model_providers.errors import ProviderRuntimeError
from voice_typer.server.model_providers.registry import ProviderRegistry

log = logging.getLogger(__name__)

ConfigGetter = Callable[[], Any]
_config_getter: ConfigGetter | None = None


def install_config_getter(getter: ConfigGetter | None) -> None:
    """Bind the process-wide config accessor used by client factories."""
    global _config_getter
    _config_getter = getter


def _config() -> Any:
    if _config_getter is None:
        raise ProviderRuntimeError("provider layer has no config accessor bound")
    return _config_getter()


def _asr_model_list() -> list[ModelDescriptor]:
    from voice_typer.server.model_registry import MODEL_REGISTRY

    return [
        ModelDescriptor(
            id=name,
            label=meta.display_name or name,
            domains=frozenset({Domain.ASR}),
            note=meta.description,
        )
        for name, meta in MODEL_REGISTRY.items()
    ]


def _local_tts_models() -> list[ModelDescriptor]:
    return [
        ModelDescriptor(id="audio8", label="Audio8 TTS Realistic 0.6B", domains=frozenset({Domain.TTS})),
        ModelDescriptor(id="magpie", label="MagpieTTS Multilingual 357M", domains=frozenset({Domain.TTS})),
    ]


def _local_asr_client(domain: Domain, model_id: str) -> Any:
    raise ProviderRuntimeError(
        "local ASR is served by the dictation pipeline's model manager; "
        "pass local_factory to build_asr_client instead of resolving a bare client",
        provider="local",
        domain=domain.value,
    )


def _local_tts_client(domain: Domain, model_id: str) -> Any:
    from voice_typer.server.model_providers.local_tts import LocalTtsClient

    return LocalTtsClient(config=_config(), engine=model_id or "")


def _cloud_direct_client(domain: Domain, model_id: str) -> Any:
    cfg = _config()
    if domain is Domain.ASR:
        from voice_typer.server.model_providers.legacy import cloud_asr_client

        return cloud_asr_client(cfg, model_id)
    if domain is Domain.LLM:
        from voice_typer.server.model_providers.legacy import legacy_llm_client

        return legacy_llm_client(cfg, model_id)
    raise ProviderRuntimeError("cloud_direct does not serve TTS", provider="cloud_direct", domain="tts")


def _openrouter_models() -> list[ModelDescriptor]:
    from voice_typer.server.model_providers.openrouter import cached_models

    return cached_models()


def _openrouter_client(domain: Domain, model_id: str) -> Any:
    from voice_typer.server.model_providers.openrouter import (
        OPENROUTER_BASE_URL,
        OpenRouterAsrClient,
        OpenRouterLlmClient,
        OpenRouterTtsClient,
        _OpenRouterAuth,
    )
    from voice_typer.server.model_providers.routing import provider_key

    cfg = _config()
    auth = _OpenRouterAuth(
        api_key=provider_key(cfg, "openrouter"),
        base_url=str(getattr(cfg, "openrouter_base_url", "") or OPENROUTER_BASE_URL),
    )
    language = str(getattr(cfg, "language", "en") or "en")
    if domain is Domain.ASR:
        return OpenRouterAsrClient(auth, model_id, language=language)
    if domain is Domain.TTS:
        return OpenRouterTtsClient(auth, model_id, language=language)
    return OpenRouterLlmClient(auth, model_id)


def _openrouter_probe() -> dict[str, Any]:
    from voice_typer.server.model_providers.errors import ProviderAuthRequiredError
    from voice_typer.server.model_providers.openrouter import OPENROUTER_BASE_URL, probe_key
    from voice_typer.server.model_providers.routing import provider_key

    cfg = _config()
    api_key = provider_key(cfg, "openrouter")
    if not api_key:
        raise ProviderAuthRequiredError("OpenRouter needs an API key", provider="openrouter")
    base = str(getattr(cfg, "openrouter_base_url", "") or OPENROUTER_BASE_URL)
    return probe_key(api_key, base_url=base)


def _selected_providers() -> set[str]:
    """Provider ids the three domains currently point at."""
    cfg = _config()
    return {
        str(getattr(cfg, field, "") or "").strip() for field in ("asr_provider", "tts_provider", "llm_provider")
    }


def _ollama_models() -> list[ModelDescriptor]:
    from voice_typer.server.model_providers.local_catalogue import (
        cached_local_catalogue,
        local_catalogue_wanted,
    )
    from voice_typer.server.model_providers.ollama import OLLAMA_LOCAL_BASE, list_local_models

    try:
        custom_base = str(getattr(_config(), "ollama_base_url", "") or "")
        selected = _selected_providers()
    except Exception as exc:
        log.debug("[PROVIDERS] ollama catalogue unavailable: %s", exc)
        return []
    if not local_catalogue_wanted("ollama", custom_base, selected):
        return []
    models, error = cached_local_catalogue(
        "ollama",
        lambda: list_local_models(custom_base or OLLAMA_LOCAL_BASE, timeout_s=2.0),
    )
    if error is not None:
        log.debug("[PROVIDERS] ollama catalogue unavailable: %s", error)
    return models


def _ollama_client(domain: Domain, model_id: str) -> Any:
    from voice_typer.server.model_providers.ollama import (
        OLLAMA_CLOUD_BASE,
        OLLAMA_LOCAL_BASE,
        OllamaChatClient,
        OllamaCloudClient,
    )
    from voice_typer.server.model_providers.routing import provider_key

    cfg = _config()
    key = provider_key(cfg, "ollama")
    base = str(getattr(cfg, "ollama_base_url", "") or "")
    if key and not base:
        return OllamaCloudClient(model_id, key, OLLAMA_CLOUD_BASE)
    return OllamaChatClient(model_id, base or OLLAMA_LOCAL_BASE)


def _lmstudio_models() -> list[ModelDescriptor]:
    from voice_typer.server.model_providers.lmstudio import LMSTUDIO_DEFAULT_BASE, list_models
    from voice_typer.server.model_providers.local_catalogue import (
        cached_local_catalogue,
        local_catalogue_wanted,
    )

    try:
        custom_base = str(getattr(_config(), "lmstudio_base_url", "") or "")
        selected = _selected_providers()
    except Exception as exc:
        log.debug("[PROVIDERS] lm studio catalogue unavailable: %s", exc)
        return []
    if not local_catalogue_wanted("lmstudio", custom_base, selected):
        return []
    models, error = cached_local_catalogue(
        "lmstudio",
        lambda: list_models(custom_base or LMSTUDIO_DEFAULT_BASE, timeout_s=2.0),
    )
    if error is not None:
        log.debug("[PROVIDERS] lm studio catalogue unavailable: %s", error)
    return models


def _lmstudio_client(domain: Domain, model_id: str) -> Any:
    from voice_typer.server.model_providers.lmstudio import LMSTUDIO_DEFAULT_BASE, chat_client

    cfg = _config()
    return chat_client(model_id, str(getattr(cfg, "lmstudio_base_url", "") or LMSTUDIO_DEFAULT_BASE))


def _local_onnx_models() -> list[ModelDescriptor]:
    from voice_typer.server.model_providers.local_onnx.models import list_installed_models

    try:
        return list_installed_models(str(getattr(_config(), "local_onnx_model_dir", "") or ""))
    except Exception as exc:
        log.debug("[PROVIDERS] local ONNX catalogue unavailable: %s", exc)
        return []


def _local_onnx_client(domain: Domain, model_id: str) -> Any:
    from voice_typer.server.model_providers.local_onnx.client import LocalOnnxLlmClient

    return LocalOnnxLlmClient(config=_config(), model_id=model_id)


def _llm_chat_url(endpoint: str) -> str:
    """Accept a base URL or a full chat-completions URL (legacy configs)."""
    url = endpoint.rstrip("/")
    return url if url.endswith("/chat/completions") else f"{url}/chat/completions"


def _openai_compatible_client(domain: Domain, model_id: str) -> Any:
    """One user-supplied OpenAI-compatible endpoint, serving all three domains.

    Each domain reads its own endpoint field, so a user can point dictation,
    speech and polish at different servers. An empty endpoint is refused here
    instead of silently falling back to OpenAI's own host.
    """
    from voice_typer.server.model_providers._http import bearer
    from voice_typer.server.model_providers.hosted_tts import HostedTtsClient
    from voice_typer.server.model_providers.openai_compat import OpenAiCompatibleChatClient
    from voice_typer.server.model_providers.routing import effective_consent, provider_key

    cfg = _config()
    key = provider_key(cfg, "custom")
    if domain is Domain.ASR:
        api_url = str(getattr(cfg, "cloud_api_url", "") or "")
        if not api_url:
            raise ProviderRuntimeError(
                "OpenAI-compatible dictation needs an endpoint URL (cloud_api_url)",
                provider="custom",
                domain=domain.value,
            )
        from voice_typer.server.cloud._engine import CloudEngine
        from voice_typer.server.model_providers.legacy import CloudAsrAdapter

        return CloudAsrAdapter(
            CloudEngine(
                provider="openai",
                api_key=key,
                api_url=api_url,
                model=model_id or str(getattr(cfg, "cloud_model", "") or "") or None,
                language=str(getattr(cfg, "language", "en") or "en"),
                consent_given=effective_consent(cfg, Domain.ASR, "custom"),
            )
        )
    if domain is Domain.TTS:
        api_url = str(getattr(cfg, "tts_api_url", "") or "")
        if not api_url:
            raise ProviderRuntimeError(
                "OpenAI-compatible speech needs an endpoint URL (tts_api_url)",
                provider="custom",
                domain=domain.value,
            )
        return HostedTtsClient(
            provider_id="custom",
            model_id=model_id,
            base_url=api_url,
            api_key=key,
            voices=(),
            languages=(),
        )
    if domain is Domain.LLM:
        api_url = str(getattr(cfg, "llm_api_url", "") or "")
        if not api_url:
            raise ProviderRuntimeError(
                "OpenAI-compatible chat needs an endpoint URL (llm_api_url)",
                provider="custom",
                domain=domain.value,
            )
        return OpenAiCompatibleChatClient(
            provider_id="custom",
            model_id=model_id,
            chat_url=_llm_chat_url(api_url),
            headers=bearer(key),
        )
    raise ProviderRuntimeError(  # pragma: no cover - Domain is exhaustive
        f"openai-compatible does not serve the {domain.value} domain",
        provider="custom",
        domain=domain.value,
    )


def _static_models(domain: Domain, ids: list[tuple[str, str]]) -> Callable[[], list[ModelDescriptor]]:
    return lambda: [ModelDescriptor(id=i, label=label, domains=frozenset({domain})) for i, label in ids]


def register_all(registry: ProviderRegistry) -> None:
    """Register every built-in provider descriptor."""
    registry.register(
        ProviderDescriptor(
            id="local",
            label="Local models",
            domains=frozenset({Domain.ASR, Domain.TTS}),
            auth=AuthKind.NONE,
            local=True,
            model_list=lambda: [*_asr_model_list(), *_local_tts_models()],
            client_factory=lambda domain, model_id: (
                _local_asr_client(domain, model_id) if domain is Domain.ASR else _local_tts_client(domain, model_id)
            ),
            unsupported_reason={Domain.LLM: "Local text generation uses the local_onnx provider."},
        )
    )
    registry.register(
        ProviderDescriptor(
            id="cloud_direct",
            label="Direct cloud API",
            domains=frozenset({Domain.ASR, Domain.LLM}),
            auth=AuthKind.API_KEY,
            model_list=lambda: [
                ModelDescriptor(
                    id="",
                    label="Configured cloud model",
                    domains=frozenset({Domain.ASR, Domain.LLM}),
                )
            ],
            client_factory=_cloud_direct_client,
            free_form_models=True,
            unsupported_reason={Domain.TTS: "Hosted TTS uses the openai or OpenAI-compatible provider."},
        )
    )
    registry.register(
        ProviderDescriptor(
            id="openrouter",
            label="OpenRouter",
            domains=frozenset({Domain.ASR, Domain.TTS, Domain.LLM}),
            auth=AuthKind.API_KEY,
            model_list=_openrouter_models,
            client_factory=_openrouter_client,
            auth_probe=_openrouter_probe,
        )
    )
    registry.register(
        ProviderDescriptor(
            id="ollama",
            label="Ollama",
            domains=frozenset({Domain.LLM}),
            auth=AuthKind.LOCAL_ENDPOINT,
            local=True,
            model_list=_ollama_models,
            client_factory=_ollama_client,
            unsupported_reason={
                Domain.ASR: "Ollama serves text models only.",
                Domain.TTS: "Ollama serves text models only.",
            },
        )
    )
    registry.register(
        ProviderDescriptor(
            id="lmstudio",
            label="LM Studio",
            domains=frozenset({Domain.LLM}),
            auth=AuthKind.LOCAL_ENDPOINT,
            local=True,
            model_list=_lmstudio_models,
            client_factory=_lmstudio_client,
            unsupported_reason={
                Domain.ASR: "LM Studio serves text models only.",
                Domain.TTS: "LM Studio serves text models only.",
            },
        )
    )
    registry.register(
        ProviderDescriptor(
            id="local_onnx",
            label="Local ONNX",
            domains=frozenset({Domain.LLM}),
            auth=AuthKind.NONE,
            local=True,
            model_list=_local_onnx_models,
            client_factory=_local_onnx_client,
            unsupported_reason={
                Domain.ASR: "Local ONNX is a text-generation runtime.",
                Domain.TTS: "Local ONNX is a text-generation runtime.",
            },
        )
    )
    registry.register(
        ProviderDescriptor(
            id="custom",
            label="OpenAI-compatible",
            domains=frozenset({Domain.ASR, Domain.TTS, Domain.LLM}),
            auth=AuthKind.API_KEY,
            model_list=lambda: [],
            client_factory=_openai_compatible_client,
            free_form_models=True,
            config_fields={
                Domain.ASR: "cloud_api_url",
                Domain.TTS: "tts_api_url",
                Domain.LLM: "llm_api_url",
            },
        )
    )


__all__ = ["install_config_getter", "register_all"]
