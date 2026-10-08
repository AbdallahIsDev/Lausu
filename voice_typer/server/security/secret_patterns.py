"""Pattern tables and public-vocabulary exemptions for secret redaction.

Extracted verbatim from :mod:`voice_typer.server.security.redaction`
(callers import these names from that facade). Holds the API-key /
bearer-token regex tables, the labeled-value shield patterns, the
public env-var / config-field / IPC-command name sets consulted by the
generic catch-all, and the SEC-9 secret-keyword flag / ``key=value``
patterns.
"""

from __future__ import annotations

import re

from voice_typer.server._paths import IPC_TOKEN_ENV_VAR as _IPC_TOKEN_ENV_VAR

# A "redactable" secret is any string that looks like an API key or

# Order matters: more-specific patterns (with a captured prefix like
_KEY_PATTERNS = [
    # Authorization headers (case-insensitive). Keep "Bearer " / "Token "
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.=]+", re.IGNORECASE),
    re.compile(r"(Token\s+)[A-Za-z0-9_\-\.=]+", re.IGNORECASE),
    # OpenAI-style keys: sk- followed by 8+ word chars.  Replace the
    re.compile(r"sk-[A-Za-z0-9_\-]+"),
    # Groq-style keys: gsk- followed by 8+ word chars.  Added back
    re.compile(r"gsk_[A-Za-z0-9_\-]+"),
    # Generic long alphanumeric run (>= 20 chars).  Dashes are
    # deliberately excluded: dash-joined names (e.g. Hugging Face hub
    # dirs like ``models--org--name-large-v3``) must survive verbatim,
    # and dashed secrets already have dedicated patterns (``sk-`` /
    # ``gsk_`` / ``Bearer`` / ``Token`` / SEC-9 flag forms above).
    re.compile(r"(?<![/\\])\b[A-Za-z0-9_]{20,}\b(?![/\\])"),
]

# Labeled-value shield patterns (see ``redact_api_keys``): exact
# Bare dash-joined names fail closed ONLY as a whole string (a line
# that is nothing but the token). Embedded occurrences are legitimate
# identifiers (binary names, DLL names, model dirs); labeled forms stay
# shielded above regardless of position.
_DASH_JOINED_FULL_RE = re.compile(r"[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)+")
_HASH_LABEL_RE = re.compile(r"sha256=[0-9a-fA-F]{64}(?![0-9a-fA-F])")
_PROPSET_LABEL_RE = re.compile(r"prop_set\s*=\s*\{[0-9a-fA-F\-]{32,40}\}")
_THREAD_LABEL_RE = re.compile(r"thread=(?![0-9a-fA-F]{64}(?![0-9a-fA-F]))([A-Za-z0-9_.\-]{1,64})(?![A-Za-z0-9_.\-])")
_BINARY_LABEL_RE = re.compile(r"binary=(?![0-9a-fA-F]{64}(?![0-9a-fA-F]))([A-Za-z0-9_.\-]{1,64})(?![A-Za-z0-9_.\-])")
_TEARDOWN_LABEL_RE = re.compile(r"\bteardown_[A-Za-z0-9_\-]{1,55}(?![A-Za-z0-9_\-])")


# Caches for the public-vocabulary sets (see
_PUBLIC_CONFIG_FIELD_NAMES_CACHE: frozenset[str] | None = None
_PUBLIC_IPC_COMMAND_NAMES_CACHE: frozenset[str] | None = None


def _public_ipc_command_names() -> frozenset[str]:
    """IPC command NAMES as a set (public protocol vocabulary).

    Command names are parity-tested across the server registry, the
    TS allowlist, and the docs: logging ``[IPC]
    pause_model_download called`` must not render as ``[IPC] ***
    called``. Only the catch-all consults this set (a bare 20+ char
    command token); payload VALUES still redact. Resolved lazily and
    cached; unimportable registry resolves to empty (fail closed).
    """
    global _PUBLIC_IPC_COMMAND_NAMES_CACHE
    cached = _PUBLIC_IPC_COMMAND_NAMES_CACHE
    if cached is None:
        try:
            from voice_typer.server.ipc.registry import _COMMAND_REGISTRY

            cached = frozenset(_COMMAND_REGISTRY)
        except Exception:
            cached = frozenset()
        _PUBLIC_IPC_COMMAND_NAMES_CACHE = cached
    return cached


def _public_config_field_names() -> frozenset[str]:
    """Config field NAMES as a set (public identifiers, not secrets).

    Field names are schema, docs, and IPC-allowlist vocabulary: logging
    ``voice_biometric_consent is False`` must not render as ``*** is
    False``. Only the catch-all consults this set (a bare 24-char
    field name); secret-bearing ``key=value`` forms and the
    Bearer/Token/sk-/gsk_ prefix patterns still fire on VALUES.
    Resolved lazily (import at call time, never at module import: this
    module loads before config in the logging path) and cached; an
    unimportable config resolves to empty (fail closed).
    """
    global _PUBLIC_CONFIG_FIELD_NAMES_CACHE
    cached = _PUBLIC_CONFIG_FIELD_NAMES_CACHE
    if cached is None:
        try:
            from voice_typer.server.config import Config

            cached = frozenset(Config.__dataclass_fields__)
        except Exception:
            cached = frozenset()
        _PUBLIC_CONFIG_FIELD_NAMES_CACHE = cached
    return cached


# Env-var NAMES are public (documented in docs, ADRs, source code, and
_PUBLIC_ENV_VAR_NAMES: frozenset[str] = frozenset(
    {
        # Lausu config / runtime
        "VOICE_TYPER_CONFIG_DIR",
        _IPC_TOKEN_ENV_VAR,  # imported from _paths to avoid bare literal
        "VOICE_TYPER_NATIVE_DIR",
        "VOICE_TYPER_PREWARM_EXE",
        "VOICE_TYPER_RESTART",
        "VOICE_TYPER_QUIET",
        "VOICE_TYPER_DEBUG",
        "VOICE_TYPER_NO_TRAY",
        "VOICE_TYPER_STREAMING",
        "VOICE_TYPER_TRUSTED_HOSTS",
        "VOICE_TYPER_DEBUG_EVENTS",
        "VOICE_TYPER_LOG_JSON",
        "VOICE_TYPER_LOG_LEVEL_MODULES",
        "VOICE_TYPER_SKIP_ACCESSIBILITY_CHECK",
        "VOICE_TYPER_DEFER_MODEL_LOAD",
        # Hugging Face
        "HUGGING_FACE_HUB_TOKEN",
        "HF_HOME",
        "HF_ENDPOINT",
        "HF_TOKEN",
        # NVIDIA CUDA visibility (public documented names;
        # CUDA_VISIBLE_DEVICES is exactly 20 chars and tripped the
        # generic catch-all, rendering log lines as ``Set ***=''``).
        "CUDA_VISIBLE_DEVICES",
        "CUDA_MODULE_LOADING",
        # Tauri host contract
        "TAURI_SIDECAR",
        # Cloud-provider API key env-var names (the NAMES are public —
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "DEEPGRAM_API_KEY",
        "GROQ_API_KEY",
    }
)

# a previous defense-in-depth heuristic

# explicit flag / key=value forms for secret-bearing keywords.
_SECRET_KEYWORDS = (
    "token",
    "apikey",
    "api_key",
    "api-key",
    "secret",
    "password",
    "passwd",
    "pwd",
    "auth",
    "authorization",
    "authentication",
    "access_token",
    "access-token",
    "refreshtoken",
    "refresh_token",
    "refresh-token",
    "client_secret",
    "client-secret",
    "private_key",
    "private-key",
    # Bare ``key=`` is included last in the alternation so longer
    "key",
)
_KEYWORD_ALT = "|".join(re.escape(k) for k in _SECRET_KEYWORDS)

# SEC-9 fix: the ``--`` prefix and the ``(?:=|\s+)``
_FLAG_VALUE_PATTERN = re.compile(rf"(?i)(--(?:{_KEYWORD_ALT})(?:=|\s+))([^\s=]+)")

# SEC-9 fix: the ``=`` must be INSIDE capture group 1 so
_BARE_KEY_VALUE_PATTERN = re.compile(rf"(?i)\b((?:{_KEYWORD_ALT})=)([^\s=]+)")

# Ordered list: pattern A (flag form) runs before pattern B (bare
_FLAG_KEY_PATTERNS = [_FLAG_VALUE_PATTERN, _BARE_KEY_VALUE_PATTERN]


def _flag_sub(m: re.Match[str]) -> str:
    """SEC-9 replacement for flag / key=value patterns.

    Keeps the prefix (group 1, e.g. ``--token=`` or ``token=``) and
    redacts the value (group 2) to ``***``.
    """
    return m.group(1) + "***"


# Minimum length below which we don't bother redacting, too likely
_MIN_REDACT_LEN = 20
