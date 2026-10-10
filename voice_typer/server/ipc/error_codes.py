"""Canonical IPC error-code registry.

One concern only: name every error code the IPC layer may emit, in its
namespaced (``client.*`` / ``server.*``) form plus the legacy non-namespaced
aliases kept for backward compatibility, and derive the frozensets the
dispatch paths and contract tests consume. The payload/schema validators and
the error-envelope builder live in
:mod:`voice_typer.server.ipc.validation`, which re-exports all of this.
"""

from __future__ import annotations


# canonical namespaced error-code registry.
class ErrorCodes:
    """Namespaced IPC error code constants (single source of truth).

    Importing emitters should reference these attributes (e.g.
    ``ErrorCodes.INVALID_PAYLOAD``) instead of bare string literals so
    that typos surface at import time and renames touch one site. The
    :data:`ERROR_CODES` frozenset is derived from this class via
    :func:`vars`, keeping the two in sync automatically.
    """

    # Client-originated errors (4xx analog).
    INVALID_FIELD = "client.invalid_field"
    MISSING_FIELD = "client.missing_field"
    INVALID_PAYLOAD = "client.invalid_payload"
    PAYLOAD_TOO_LARGE = "client.payload_too_large"
    # ``duplicate_entry`` is emitted by ``save_vocabulary`` when the
    DUPLICATE_ENTRY = "client.duplicate_entry"
    RATE_LIMITED = "client.rate_limited"
    PATH_NOT_ALLOWED = "client.path_not_allowed"
    NOT_FOUND = "client.not_found"
    AUTH_FAILED = "client.auth_failed"
    # Structured consent error, the renderer surfaces a consent
    CONSENT_REQUIRED = "client.consent_required"
    # ``onboarding_start`` rejects a re-run of a finished wizard unless the
    # caller passes ``{force: true}``; the renderer surfaces the message.
    ONBOARDING_ALREADY_COMPLETE = "client.onboarding_already_complete"
    # Server-originated errors (5xx analog).
    INTERNAL_ERROR = "server.internal_error"
    HANDLER_ERROR = "server.handler_error"
    FILE_LOCKED = "server.file_locked"
    MODEL_SWITCH_FAILED = "server.model_switch_failed"
    SHUTTING_DOWN = "server.shutting_down"
    UNKNOWN_COMMAND = "server.unknown_command"
    UNKNOWN_TRAY_ITEM = "server.unknown_tray_item"
    SERVER_NOT_FOUND = "server.not_found"
    # ``max_connections_reached`` is emitted by ``sidecar_ws.py`` when
    MAX_CONNECTIONS_REACHED = "server.max_connections_reached"
    # ``duplicate_connection`` is emitted by ``sidecar_ws.py`` when
    DUPLICATE_CONNECTION = "server.duplicate_connection"
    # ``not_initialized`` is the namespaced form of the
    NOT_INITIALIZED = "server.not_initialized"
    # ADR-0023 media ingest: no speech model installed/selected.
    NO_MODEL = "server.no_model"
    # ADR-0023 media ingest: another media job is running / source rejected.
    JOB_BUSY = "server.job_busy"
    NOT_SUPPORTED = "server.not_supported"
    # structured consent-required envelope emitted by the
    SERVER_CONSENT_REQUIRED = "server.consent_required"
    # Typed cloud/LLM exception hierarchy, distinct codes for
    CLOUD_AUTH_FAILED = "server.cloud_auth_failed"
    CLOUD_RATE_LIMITED = "server.cloud_rate_limited"
    CLOUD_SERVER_ERROR = "server.cloud_server_error"
    CLOUD_NETWORK_ERROR = "server.cloud_network_error"
    CLOUD_CONFIG_ERROR = "server.cloud_config_error"
    CLOUD_ENGINE_ERROR = "server.cloud_engine_error"
    # recording-pipeline exception hierarchy, distinct codes
    RECORDING_RESAMPLE_FAILED = "server.recording_resample_failed"
    RECORDING_RESAMPLE_UNAVAILABLE = "server.recording_resample_unavailable"
    # IPC wire-protocol version negotiation. Emitted by the TCP auth
    PROTOCOL_VERSION_MISMATCH = "server.protocol_version_mismatch"
    # Dispatch-queue contention: a state-mutating command waited too long
    # for ``_dispatch_lock`` (holder stuck). The caller retries shortly;
    # readonly commands keep flowing on their reserved pool.
    SERVER_BUSY = "server.busy"


class LegacyErrorCodes:
    """Legacy non-namespaced error code aliases (backward compat).

    New emitters MUST use :class:`ErrorCodes` instead. The
    :data:`LEGACY_ERROR_CODES` frozenset is derived from this class via
    :func:`vars`. Keeping the legacy set explicit (instead of an
    open-ended ``str``) lets us audit which aliases are still emitted
    and remove them once the renderer migrates fully to the namespaced
    form.
    """

    INTERNAL_ERROR = "internal_error"
    SHUTTING_DOWN = "shutting_down"
    UNKNOWN_COMMAND = "unknown_command"
    UNKNOWN_TRAY_ITEM = "unknown_tray_item"
    AUTH_FAILED = "auth_failed"
    RATE_LIMITED = "rate_limited"
    INVALID_PAYLOAD = "invalid_payload"
    INVALID_FIELD = "invalid_field"
    MISSING_FIELD = "missing_field"
    MODEL_SWITCH_FAILED = "model_switch_failed"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    HANDLER_ERROR = "handler_error"
    NOT_INITIALIZED = "not_initialized"
    # Rust-host-only dispatch-cap codes emitted by the Tauri
    PENDING_FULL = "pending_full"
    DATA_TOO_LARGE = "data_too_large"
    # Rust-host-only codes: emitted by the Tauri `#[tauri::command]`
    DISALLOWED_COMMAND = "disallowed_command"
    DISALLOWED_WINDOW = "disallowed_window"
    SIDECAR_DISCONNECTED = "sidecar_disconnected"


def _class_str_values(cls: type) -> frozenset[str]:
    """Derive a frozenset of all ``str`` class-attribute values from *cls*.

    Used to keep :data:`ERROR_CODES` / :data:`LEGACY_ERROR_CODES` in sync
    with :class:`ErrorCodes` / :class:`LegacyErrorCodes` automatically —
    no risk of the frozenset drifting from the class.
    """
    return frozenset(value for name, value in vars(cls).items() if not name.startswith("_") and isinstance(value, str))


# namespaced error codes, the canonical form for new emitters.
ERROR_CODES: frozenset[str] = _class_str_values(ErrorCodes)

# legacy non-namespaced aliases still emitted by some paths for
LEGACY_ERROR_CODES: frozenset[str] = _class_str_values(LegacyErrorCodes)

# convenience union for validation / contract tests. Every
ALL_ERROR_CODES: frozenset[str] = ERROR_CODES | LEGACY_ERROR_CODES
