"""Config schema-field validation impls and the constants they read.

Holds the module-level helpers behind ``Config``'s
``_reset_invalid_enum_fields`` / ``_secret_field_names`` classmethod
delegators (``config/_lifecycle.py``).
"""

import logging
import types

log = logging.getLogger("voice_typer.server.config")

# High-impact ``Literal[...]`` enum fields whose invalid values
_ENUM_FIELDS_TO_RESET_ON_LOAD: frozenset[str] = frozenset(
    {
        "asr_backend",
        "noise_suppression_method",
        "audio_preset",
        "theme_mode",
        "theme_preset",
        "bubble_position",
        "bubble_behavior",
        "tray_left_click_action",
        "recording_mode",
    }
)

# The set of Config dataclass field names that hold secret material
_SECRET_FIELD_NAMES_FALLBACK: frozenset[str] = frozenset(
    {
        "openai_api_key",
        "groq_api_key",
        "deepgram_api_key",
        "gemini_api_key",
        "cloud_api_key",
        "llm_api_key",
    }
)


def _reset_invalid_enum_fields_impl(cls, instance) -> None:
    """Reset invalid ``Literal[...]`` enum fields to their defaults.

    Module-level impl behind the ``Config._reset_invalid_enum_fields``
    classmethod delegator (``config/_lifecycle.py``).

    ``validate_config(instance)`` (called from :meth:`load` just
    before this helper) flags invalid enum values and appends
    human-readable errors to ``instance.last_load_warnings``, but
    it does NOT mutate the field, the invalid value remains on
    the instance and propagates to runtime code, which either
    crashes (KeyError in a dispatch dict) or silently takes the
    wrong branch.

    This helper closes that gap. For each field in
    :data:`_ENUM_FIELDS_TO_RESET_ON_LOAD`:

    1. Look up the field's ``Literal[...]`` annotation via
       :func:`typing.get_type_hints`.
    2. Read the current value from ``instance`` via ``getattr``.
    3. If the value is not in the Literal's allowed set (via
       :func:`typing.get_args`), reset to the default from a
       freshly-constructed ``Config()`` and append a warning to
       ``instance.last_load_warnings``.

    Non-str values (e.g. a hand-edited ``"asr_backend": 123``)
    are also reset, they can never be in a ``Literal[str, ...]``
    allowed set. The ``_validate_non_numeric_fields`` pre-pass
    normally coerces such values to ``str`` first, but this
    helper is defensive against a value that slipped through
    (e.g. a complex type that the str branch didn't catch).

    The reset is idempotent: a value already at the default is a
    no-op (it's in the allowed set). The reset is also safe to
    re-run, calling it twice produces no extra warnings.

    Warnings are appended to ``instance.last_load_warnings`` (NOT
    ``data["_load_warnings"]``, which has already been popped and
    transferred to the instance by the time this runs, see the
    :meth:`load` orchestrator). The warning text mirrors the
    format used by the per-field reset helpers
    (``_validate_model_path`` etc.) so the renderer can display
    them with the same UI treatment.
    """
    import typing

    try:
        hints = typing.get_type_hints(cls)
    except Exception:
        # ``typing.get_type_hints`` resolves forward refs and can
        hints = dict(getattr(cls, "__annotations__", {}))

    # Build the defaults instance ONCE (not per-field), Config()
    defaults = cls()

    for field_name in cls._ENUM_FIELDS_TO_RESET_ON_LOAD:
        ann = hints.get(field_name)
        if ann is None:
            # Field was removed or renamed, skip silently (the
            continue
        # Unwrap ``T | None`` / ``Optional[T]``, none of the 9
        if typing.get_origin(ann) in (typing.Union, types.UnionType):
            args = [a for a in typing.get_args(ann) if a is not type(None)]
            if len(args) == 1:
                ann = args[0]
        if typing.get_origin(ann) is not typing.Literal:
            # Field's annotation isn't a Literal (e.g. it was
            continue
        allowed = set(typing.get_args(ann))
        current = getattr(instance, field_name, None)
        if current in allowed:
            continue
        default_value = getattr(defaults, field_name)
        # Defensive: if the default ITSELF isn't in the allowed
        if default_value not in allowed and allowed:
            default_value = sorted(allowed)[0]
        log.warning(
            "[CONFIG] %s=%r not in Literal allowed values %s; resetting to default %r",
            field_name,
            current,
            sorted(allowed),
            default_value,
        )
        # Use ``object.__setattr__`` to mirror the ``__post_init__``
        object.__setattr__(instance, field_name, default_value)
        # Append to ``last_load_warnings``: initialize the list
        warnings = getattr(instance, "last_load_warnings", None)
        if warnings is None:
            warnings = []
            object.__setattr__(instance, "last_load_warnings", warnings)
        warnings.append(
            f"Config field {field_name!r}={current!r} not in allowed values "
            f"{sorted(allowed)}, reset to default {default_value!r}"
        )


def _secret_field_names_impl() -> frozenset[str]:
    """return the set of Config field names holding secrets.

    Module-level impl behind the ``Config._secret_field_names``
    classmethod delegator (``config/_lifecycle.py``).

    Lazily imports ``credential_store.PROVIDER_TO_CONFIG_FIELD``
    (the canonical provider→field map) so the secret-field list
    stays in sync with the credential-store definition.

    SECURITY (fail-closed): if the import of
    ``PROVIDER_TO_CONFIG_FIELD`` fails for ANY reason (broken
    install, sandbox without the package, partial-import during
    test collection, future refactor that breaks the import path),
    we log ``CRITICAL`` and RE-RAISE. We do NOT fall back to the
    historical ``_SECRET_FIELD_NAMES_FALLBACK`` literal: a silent
    fallback to a stale 5-field set would leave any newly added
    provider's API key un-redacted in ``_warn_and_reset`` /
    ``_warn_and_coerce`` log lines (``val_repr = repr(val)``)
    whenever the fallback kicks in (SEC-003 regression analog).
    Failing the import loudly surfaces the breakage at the first
    call site (typically ``Config.load()`` redaction), which is
    strictly safer than silently degrading the redaction
    boundary. Mirrors the fail-closed pattern in
    ``voice_typer.server.config_sanitizer._derive_secret_fields``
    so the two paths handle the SAME failure identically.
    """
    try:
        from voice_typer.server import credential_store

        return frozenset(credential_store.PROVIDER_TO_CONFIG_FIELD.values())
    except Exception as exc:
        # Fail-closed: do NOT fall back to the hardcoded
        log.critical(
            "[CONFIG] could not import credential_store for "
            "_secret_field_names, secret-field redaction may be "
            "incomplete. Refusing to fall back to a hardcoded "
            "literal (fail-closed). Original error: %s",
            exc,
        )
        raise
