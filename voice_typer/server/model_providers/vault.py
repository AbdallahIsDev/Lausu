"""Per-provider API-key vault on top of the existing credential store.

One key per provider id. Keys never enter ``config.json`` through this module:
they go through ``credential_store.store_secret`` (OS keychain with the
documented plaintext fallback), and reads return a masked form for display.
"""

from __future__ import annotations

import logging
from typing import Any

from voice_typer.server.credential_store import (
    delete_secret,
    is_keyring_available,
    load_secret,
    store_secret,
)

log = logging.getLogger(__name__)

#: Provider id -> the ``Config`` attribute the key is loaded into. Adding an
#: entry here also makes ``credential_store`` accept the provider id.
PROVIDER_KEY_FIELDS: dict[str, str] = {
    "openrouter": "openrouter_api_key",
    "ollama": "ollama_api_key",
    "lmstudio": "lmstudio_api_key",
    "custom": "custom_tts_api_key",
}


def provider_key_field(provider_id: str) -> str:
    """Return the config attribute that holds this provider's key."""
    return PROVIDER_KEY_FIELDS.get(provider_id, f"{provider_id}_api_key")


def mask_secret(value: str | None, *, visible: int = 4) -> str:
    """Return a display-safe form: ``sk-o…4f2a`` (never the full key)."""
    if not value:
        return ""
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}…{value[-visible:]}"


def store_provider_key(provider_id: str, value: str) -> dict[str, Any]:
    """Store (or rotate) one provider key. Empty value deletes it."""
    stored = store_secret(provider_id, value)
    log.info(
        "[PROVIDERS] key %s for provider=%s",
        "stored" if value else "cleared",
        provider_id,
    )
    return {
        "provider": provider_id,
        "configured": bool(value),
        "keyring": stored,
        "masked": mask_secret(value),
    }


def load_provider_key(provider_id: str) -> str:
    """Load one provider key (empty string when absent)."""
    return load_secret(provider_id) or ""


def clear_provider_key(provider_id: str, config: Any = None) -> dict[str, Any]:
    """Delete one provider key without touching any other provider's key."""
    delete_secret(provider_id, config)
    return {"provider": provider_id, "configured": False}


def provider_key_status(provider_id: str) -> dict[str, Any]:
    """Report whether a key is configured, masked, plus keyring availability."""
    raw = load_provider_key(provider_id)
    return {
        "provider": provider_id,
        "configured": bool(raw),
        "masked": mask_secret(raw),
        "keyring": is_keyring_available(),
    }


__all__ = [
    "PROVIDER_KEY_FIELDS",
    "clear_provider_key",
    "load_provider_key",
    "mask_secret",
    "provider_key_field",
    "provider_key_status",
    "store_provider_key",
]
