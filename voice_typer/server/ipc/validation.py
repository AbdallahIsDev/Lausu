"""Shared IPC payload validation + error-envelope helpers.

validates an IPC ``data`` argument against a declarative
schema.  Returns ``(validated_dict, None)`` on success, or
``(None, error_response_dict)`` on validation failure so the handler
can ``return resp`` immediately.

Added :func:`_error_response`
to standardize the error envelope produced by handler-level
``except Exception`` catch-alls.  The helper exists because each
own ``resp["data"] = {"message": str(e)}`` ad-hoc, omitting the
``code`` field that the TCP/WS dispatch paths (and the validation
helper) include in every other error envelope.  Clients branching on
``code`` (e.g. the renderer's toast-dispatch logic) silently fell
through to a generic "unknown error" path for handler exceptions.
The helper stamps ``code: "handler_error"`` and a sanitized message
(the full exception is logged server-side at ERROR with
``exc_info=True`` by the caller).

Schema format::

    schema = {
        "field_name": {
            "type": str,          # required: the expected Python type
            "required": True,     # field MUST be present in data
            "default": "val",    # optional default (only for
                                  #   required=False)
        }
    }

Example::

    validated, error = _validate_dict_payload(data, {
        "hotkey": {"type": str, "required": True},
        "model": {"type": str, "required": False, "default": "tiny"},
    })
    if error:
        return error

(IMPROVE-mode run, 2026-07-19): the schema now supports three
optional rules that the previous inline checks in live handlers
(notably ``save_vocabulary``) reimplemented ad-hoc:

- ``max_value_len`` (int): reject string values longer than N chars.
- ``max_payload_bytes`` (int): reject the whole payload if its
  ``json.dumps`` size exceeds N bytes (DoS guard).
- ``clamp_range`` (tuple ``(lo, hi)``): coerce a numeric value to
  ``max(lo, min(value, hi))`` instead of rejecting out-of-range
  values (historical example: ``duration_ms`` on the retained
  Rust-mirror ``_handle_show_notification``; that command is
  NOT registered in ``_COMMAND_REGISTRY`` — do not cite it as a live
  IPC example).

Split leaves, both re-exported below so every existing import path keeps
resolving:

- :mod:`voice_typer.server.ipc.error_codes`, the namespaced + legacy code
  registry and the derived frozensets (``ErrorCodes``,
  ``LegacyErrorCodes``, ``ERROR_CODES``, ``LEGACY_ERROR_CODES``,
  ``ALL_ERROR_CODES``).
- :mod:`voice_typer.server.ipc.error_envelope`, the typed envelope contract
  and its builder (``ErrorData``, ``ErrorEnvelope``, ``_error_response``).
"""

# ``TypedDict`` is needed for the schema + error-envelope type
import json
from collections.abc import Callable as _Callable
from typing import TypedDict

# Maximum serialized payload size for a single IPC response, derived from
MAX_EXPORT_PAYLOAD_BYTES: int = 1 * 1024 * 1024 - 64 * 1024


def _measure_payload_bytes(payload: object) -> int:
    """Wire size of *payload*: compact UTF-8 bytes, matching the sender.

    ``json.dumps`` defaults would measure ASCII-escaped characters, so a
    non-Latin payload looked ~2-3x larger than the frame the transport
    actually writes (``ensure_ascii=False`` + compact separators).
    """
    return len(json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8"))


def _enforce_payload_size_cap(
    payload: object,
    max_bytes: int = MAX_EXPORT_PAYLOAD_BYTES,
    *,
    error_message: str = "Response payload exceeds the size cap",
) -> dict | None:
    """Check whether *payload* fits within the size cap when serialized.

    Serializes *payload* via ``json.dumps`` (same args as the IPC
    ``_send`` path) and compares the encoded byte length to *max_bytes*.
    Returns an error-envelope dict ``{"type": "error", "data": {"code":
    ..., "message": ...}}`` when the payload exceeds the cap, or
    ``None`` when it fits.

    Callers (handler mixins) can use this to fail fast with a clear
    structured error instead of producing a frame that the transport
    layer silently drops.
    """
    try:
        size = _measure_payload_bytes(payload)
    except (TypeError, ValueError):
        return None
    if size <= max_bytes:
        return None
    return {
        "type": "error",
        "data": {
            "code": ErrorCodes.PAYLOAD_TOO_LARGE,
            "message": f"{error_message} ({size} bytes exceeds {max_bytes} byte cap)",
        },
    }


# Typed schema for the declarative validation rule dict consumed


class FieldRule(TypedDict, total=False):
    """Declarative per-field validation rule for :func:`_validate_dict_payload`.

    See the module docstring of :func:`_validate_dict_payload` for the
    full semantics of each key. All keys are optional, the helper
    reads each via ``rules.get(<key>)`` and treats absence as "rule
    not applied".
    """

    type: type | tuple[type, ...]
    required: bool
    default: object
    max_value_len: int
    clamp_range: tuple[int | float, int | float]
    max_payload_bytes: int
    # when ``True`` (the implicit default for backwards
    none_to_default: bool
    # opt-in bool rejection. When ``True``, a value that is a
    reject_bool: bool


# A schema is a mapping from field name to its rule dict. Used as
Schema = dict[str, FieldRule]


# The whole-payload size cap (``max_payload_bytes``) can be declared
_MAX_PAYLOAD_BYTES_CACHE_MAX = 1024
_MAX_PAYLOAD_BYTES_CACHE: dict[int, tuple[tuple[int, tuple[str, ...]], int | None]] = {}
_MAX_PAYLOAD_BYTES_CACHE_SEEN: set[int] = set()


def _schema_effective_max_payload_bytes(schema: Schema) -> int | None:
    """Return the effective whole-payload byte cap declared in *schema*.

    Scans the schema's field rules for ``max_payload_bytes`` and returns
    the MINIMUM (most restrictive) declared value, or ``None`` if no
    field declares a cap. Results are memoized per schema object so
    repeated validation calls with the same schema dict skip the
    ``schema.values()`` scan.
    """
    key = id(schema)
    fingerprint = (len(schema), tuple(sorted(schema)))
    if key in _MAX_PAYLOAD_BYTES_CACHE:
        cached_fp, cached_val = _MAX_PAYLOAD_BYTES_CACHE[key]
        if cached_fp == fingerprint:
            return cached_val
    field_maxes = [
        rule.get("max_payload_bytes") for rule in schema.values() if rule.get("max_payload_bytes") is not None
    ]
    value = min(field_maxes) if field_maxes else None
    _MAX_PAYLOAD_BYTES_CACHE[key] = (fingerprint, value)
    _MAX_PAYLOAD_BYTES_CACHE_SEEN.add(key)
    if len(_MAX_PAYLOAD_BYTES_CACHE) > _MAX_PAYLOAD_BYTES_CACHE_MAX:
        oldest = next(iter(_MAX_PAYLOAD_BYTES_CACHE))
        del _MAX_PAYLOAD_BYTES_CACHE[oldest]
        _MAX_PAYLOAD_BYTES_CACHE_SEEN.discard(oldest)
    return value


def _validate_dict_payload(
    data: object,
    schema: Schema,
    *,
    max_payload_bytes: int | None = None,
) -> tuple[dict[str, object] | None, "dict[str, object] | None"]:
    """Validate IPC ``data`` against a declarative *schema*.

        Parameters
        ----------
        data :
            The ``data`` field from the IPC message.
        schema :
            Mapping of field name → validation rules.  Each rule dict
            supports:

            - ``type`` (required): the expected Python type (e.g. ``str``,
              ``list``).
            - ``required`` (bool): if ``True``, the field MUST be present
              in ``data``.  Mutually exclusive with ``default``.
            - ``default``: default value when the field is absent.  Only
              valid when ``required=False``.
            - ``none_to_default`` (bool, optional, default ``True``):
    when ``True``, an explicit ``None`` value for
              the field is treated as ABSENT, the ``default`` rule
    fires. Previously a present ``None`` failed the
              ``type`` check (assuming ``type`` didn't include
              ``type(None)``). Set ``False`` to restore the strict
              behavior.
            - ``max_value_len`` (int, optional): if the value is a string
              longer than N characters, return an ``client.invalid_field``
    error. Replaces the ad-hoc per-value length loops in
              ``save_vocabulary``.
            - ``clamp_range`` (tuple ``(lo, hi)``, optional): if the
              value is a number, coerce it to ``max(lo, min(value, hi))``
    before storing it in ``validated``. Replaces inline
              range-clamp coercions (e.g. duration fields).
            - ``max_payload_bytes`` (int, optional, DEPRECATED): if the
              WHOLE ``data`` dict serializes to more than N bytes, return
    an ``client.invalid_payload`` error. Replaces the
    inline 1 MB cap in ``save_vocabulary``. This
              rule is keyed off any field but applies to the WHOLE
              payload, the helper now scans ALL fields and uses the
              MINIMUM declared value (most restrictive), so the
              "first-field-wins" fragility is gone. Prefer the
              top-level ``max_payload_bytes`` keyword argument for new
              schemas; the per-field rule is kept for backward compat.

        max_payload_bytes :
    top-level whole-payload size cap. When provided,
            takes precedence over any per-field ``max_payload_bytes``
            rule. Prefer this for new schemas (the per-field rule was a
            historical workaround that was fragile under multi-field
            schemas, the helper only checked the FIRST field that
            declared it and broke after, silently ignoring any second
            field's value).

        Returns
        -------
        tuple[dict[str, object] | None, dict[str, object] | None]
            ``(validated_dict, None)`` on success.
            ``(None, error_response)`` on failure, the error_response
            is a dict ready to be returned as ``resp`` from the handler.
            The error_response dict conforms to the :class:`ErrorEnvelope`
            contract (``{"type": "error", "data": {"code": ..., ...}}``);
            the return type is plain ``dict[str, object]`` (not
            :class:`ErrorEnvelope`) because TypedDicts are invariant and
            not subtypes of ``dict``, so annotating the return as
            :class:`ErrorEnvelope` would flag every caller that returns
            the error directly from a ``-> dict | None`` handler. The
            contract is documented at construction sites via the
            ``# ErrorEnvelope contract: see validation.py`` comments and
            verified by ``tests/test_error_codes_registry.py``.
    """
    if not isinstance(data, dict):
        # ErrorEnvelope contract: see validation.py
        return None, {
            "type": "error",
            "data": {
                # emit the namespaced ``client.invalid_payload``
                "code": ErrorCodes.INVALID_PAYLOAD,
                "message": "data must be an object",
            },
        }

    # + : ``max_payload_bytes`` is a whole-payload rule.
    effective_max_bytes = max_payload_bytes
    if effective_max_bytes is None:
        # Scan all field rules for a per-field ``max_payload_bytes``
        effective_max_bytes = _schema_effective_max_payload_bytes(schema)
    if effective_max_bytes is not None:
        payload_size = _measure_payload_bytes(data)
        if payload_size > effective_max_bytes:
            # ErrorEnvelope contract: see validation.py
            return None, {
                "type": "error",
                "data": {
                    # namespaced form (canonical).
                    "code": ErrorCodes.INVALID_PAYLOAD,
                    "message": (f"payload too large ({payload_size} bytes; max {effective_max_bytes})"),
                },
            }

    validated = {}
    for field_name, rules in schema.items():
        if field_name in data:
            value = data[field_name]
            # if the field is explicitly ``None`` AND the
            if value is None and rules.get("none_to_default", True) and "default" in rules:
                validated[field_name] = rules["default"]
                continue
            expected_type = rules.get("type")
            if expected_type is not None and not isinstance(value, expected_type):
                # format the expected-type name for the error
                if isinstance(expected_type, tuple):
                    expected_name = "|".join(t.__name__ for t in expected_type)
                else:
                    expected_name = expected_type.__name__
                return None, {
                    # ErrorEnvelope contract: see validation.py
                    "type": "error",
                    "data": {
                        # namespaced form (canonical).
                        "code": ErrorCodes.INVALID_FIELD,
                        "field": field_name,
                        "message": f"'{field_name}' must be of type {expected_name}, got {type(value).__name__}",
                    },
                }
            # opt-in bool rejection. ``bool`` subclasses
            if (
                rules.get("reject_bool", False)
                and isinstance(value, bool)
                # if ``bool`` is in the declared type tuple, the
                and not (isinstance(expected_type, tuple) and bool in expected_type)
                and expected_type is not bool
            ):
                # format the expected-type name for the error
                if isinstance(expected_type, tuple):
                    expected_name = "|".join(t.__name__ for t in expected_type)
                elif expected_type is None:
                    expected_name = "non-bool"
                else:
                    expected_name = expected_type.__name__
                return None, {
                    # ErrorEnvelope contract: see validation.py
                    "type": "error",
                    "data": {
                        # namespaced form (canonical).
                        "code": ErrorCodes.INVALID_FIELD,
                        "field": field_name,
                        "message": (
                            f"'{field_name}' must be of type {expected_name}, "
                            f"got bool (bool is a subclass of int but is "
                            f"semantically a toggle, not a number)"
                        ),
                    },
                }
            # per-value length cap. Only applies to string
            max_value_len = rules.get("max_value_len")
            if max_value_len is not None and isinstance(value, str) and len(value) > max_value_len:
                return None, {
                    # ErrorEnvelope contract: see validation.py
                    "type": "error",
                    "data": {
                        # namespaced form (canonical).
                        "code": ErrorCodes.INVALID_FIELD,
                        "field": field_name,
                        "message": (f"'{field_name}' value too long ({len(value)} > {max_value_len})"),
                    },
                }
            # clamp_range. Coerce numeric values into [lo, hi].
            clamp_range = rules.get("clamp_range")
            if clamp_range is not None and isinstance(value, int | float) and not isinstance(value, bool):
                lo, hi = clamp_range
                value = max(lo, min(value, hi))
            validated[field_name] = value
        elif rules.get("required", False):
            return None, {
                # ErrorEnvelope contract: see validation.py
                "type": "error",
                "data": {
                    # namespaced form (canonical).
                    "code": ErrorCodes.MISSING_FIELD,
                    "field": field_name,
                    "message": f"Missing required field '{field_name}'",
                },
            }
        elif "default" in rules:
            validated[field_name] = rules["default"]

    return validated, None



__all__ = [
    "_validate_dict_payload",
    "_error_response",
    "ERROR_CODES",
    "LEGACY_ERROR_CODES",
    "ALL_ERROR_CODES",
    # Single-source-of-truth code constants (). Emitters should
    "ErrorCodes",
    "LegacyErrorCodes",
    # Typed contract exports.
    "FieldRule",
    "Schema",
    "ErrorData",
    "ErrorEnvelope",
    # export-payload size cap + guard helper.
    "MAX_EXPORT_PAYLOAD_BYTES",
    "_enforce_payload_size_cap",
]

# canonical home for the ResponseEnvelope type alias and
ResponseEnvelope = dict[str, object]

# ``CommandHandler`` is the signature every ``_handle_*`` method follows:
CommandHandler = _Callable[[object | None, ResponseEnvelope], ResponseEnvelope | None]
del _Callable

# previously a SECOND top-level ``__all__ = [...]`` literal
__all__ += [
    "CommandHandler",
    "ResponseEnvelope",
]

# Facade re-exports: the code registry (``error_codes``) and the typed
# envelope contract (``error_envelope``) keep resolving through this module,
# so every handler/test import path stays intact.
from voice_typer.server.ipc.error_codes import (  # noqa: E402,F401  # facade re-export
    ALL_ERROR_CODES,
    ERROR_CODES,
    LEGACY_ERROR_CODES,
    ErrorCodes,
    LegacyErrorCodes,
)
from voice_typer.server.ipc.error_envelope import (  # noqa: E402,F401  # facade re-export
    ErrorData,
    ErrorEnvelope,
    _error_response,
)
