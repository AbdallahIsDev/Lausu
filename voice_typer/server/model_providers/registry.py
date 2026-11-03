"""Provider registry: registration, lookup and the capability matrix.

The registry is the only place that knows which provider ids exist. Routing
asks it for a descriptor, then asks the descriptor for a domain client; nothing
imports a concrete client directly at module import time.
"""

from __future__ import annotations

import logging
import threading

from voice_typer.server.model_providers.descriptor import Domain, ProviderDescriptor
from voice_typer.server.model_providers.errors import ProviderNotFoundError

log = logging.getLogger(__name__)

_LOCK = threading.RLock()


class ProviderRegistry:
    """Ordered registry of provider descriptors."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderDescriptor] = {}

    def register(self, descriptor: ProviderDescriptor) -> ProviderDescriptor:
        """Register (or replace) one provider by id."""
        with _LOCK:
            self._providers[descriptor.id] = descriptor
        return descriptor

    def unregister(self, provider_id: str) -> None:
        """Remove one provider (tests / dynamic providers)."""
        with _LOCK:
            self._providers.pop(provider_id, None)

    def get(self, provider_id: str) -> ProviderDescriptor:
        with _LOCK:
            descriptor = self._providers.get(provider_id)
        if descriptor is None:
            raise ProviderNotFoundError(f"unknown provider {provider_id!r}", provider=provider_id)
        return descriptor

    def maybe_get(self, provider_id: str) -> ProviderDescriptor | None:
        with _LOCK:
            return self._providers.get(provider_id)

    def all(self) -> list[ProviderDescriptor]:
        with _LOCK:
            return list(self._providers.values())

    def ids(self) -> list[str]:
        with _LOCK:
            return list(self._providers)

    def for_domain(self, domain: Domain) -> list[ProviderDescriptor]:
        """Only providers whose capability set contains ``domain``."""
        return [p for p in self.all() if p.supports(domain)]

    def capability_matrix(self) -> dict[str, list[str]]:
        """``{provider_id: [domains it advertises]}`` for tests and the UI."""
        return {p.id: sorted(d.value for d in p.domains) for p in self.all()}

    def clear(self) -> None:
        """Drop every registration (test isolation)."""
        with _LOCK:
            self._providers.clear()


_REGISTRY = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    """Return the process-wide registry, registering built-ins on first use."""
    with _LOCK:
        if not _REGISTRY.ids():
            register_builtin_providers(_REGISTRY)
    return _REGISTRY


def register_builtin_providers(registry: ProviderRegistry | None = None) -> ProviderRegistry:
    """Register every in-repo provider (idempotent)."""
    from voice_typer.server.model_providers.builtin import register_all

    target = registry if registry is not None else _REGISTRY
    register_all(target)
    return target


__all__ = [
    "ProviderRegistry",
    "get_registry",
    "register_builtin_providers",
]
