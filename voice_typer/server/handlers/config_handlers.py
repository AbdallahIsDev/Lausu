"""Config IPC handler mixin: get_config, get_defaults, set_config."""

import contextlib
import ipaddress
from typing import cast

from voice_typer.server import event_bus
from voice_typer.server.config import validate_config_update
from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.handlers._log import log
from voice_typer.server.ipc.validation import (  # noqa: F401
    ErrorCodes,
    LegacyErrorCodes,
    ResponseEnvelope,
    _error_response,
)

# ``_config_mutation_lock`` case. The handler runs on every ``set_config``
_CONFIG_LOCK_MISSING_WARNED: bool = False

# Provider endpoint hosts must be trusted when the value is SAVED, not on the
# first request: a persisted URL the allowlist rejects can only fail later as
# an opaque provider error. ``trusted_extra_hosts`` in the same payload counts.
_ENDPOINT_URL_FIELDS: tuple[str, ...] = (
    "cloud_api_url",
    "llm_api_url",
    "tts_api_url",
    "openrouter_base_url",
)


def _untrusted_endpoint_rejection(validated: dict, current: object) -> str | None:
    """Return the first CHANGED endpoint field whose host is not allowlisted.

    An unchanged value is skipped: a config written by an older build must not
    block an unrelated save, and only a new host is a save-time decision.
    """
    from urllib.parse import urlparse

    from voice_typer.server.security.url_allowlist import _normalize_host, get_url_allowlist

    allowed = set(get_url_allowlist())
    pending = validated.get("trusted_extra_hosts")
    if isinstance(pending, list):
        allowed.update(_normalize_host(host) for host in pending if isinstance(host, str))
    for field in _ENDPOINT_URL_FIELDS:
        value = validated.get(field)
        if not isinstance(value, str) or not value.strip():
            continue
        if value == getattr(current, field, None):
            continue
        host = (urlparse(value).hostname or "").lower()
        if host and host not in allowed:
            return f"{field}: host {host!r} is not a trusted endpoint; add it to trusted_extra_hosts first"
    return None


class ConfigHandlersMixin(HandlerBase):
    """Mixin: config-related IPC handlers (get_config / get_defaults / set_config)."""

    def _handle_get_config(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``get_config`` IPC command."""
        resp["type"] = "config"
        # SEC-003: service.get_config() returns a sanitized view — secret
        resp["data"] = self.service.get_config()
        return resp

    def _handle_get_defaults(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``get_defaults`` IPC command."""
        # Defaults from the Python Config dataclass (renderer Reset path).
        try:
            resp["type"] = "defaults"
            resp["data"] = self.service.get_defaults()
        except Exception as exc:
            self._respond_with_error(resp, exc, "get_defaults")
        return resp

    def _validate_set_config_payload(
        self, data: object | None, resp: ResponseEnvelope
    ) -> tuple[dict | None, ResponseEnvelope | None, list[str], list[str]]:
        """Validate the ``set_config`` payload against the allowlist."""
        if not isinstance(data, dict):
            log.warning("[IPC] set_config rejected: data is %s, not dict", type(data).__name__)
            return (
                None,
                _error_response(
                    resp,
                    "set_config requires data: object",
                    code=LegacyErrorCodes.INVALID_PAYLOAD,
                ),
                [],
                [],
            )
        # SEC-002: validate against IPC_CONFIG_ALLOWLIST before touching
        validated, errors = validate_config_update(data, current=self.app.config)
        if errors:
            log.warning("[IPC] set_config rejected: %s", "; ".join(errors))
            resp["type"] = "error"
            resp["data"] = {
                "code": LegacyErrorCodes.INVALID_FIELD,
                "message": errors[0],
                "errors": list(errors),
            }
            return None, resp, [], []
        endpoint_rejection = _untrusted_endpoint_rejection(validated, self.app.config)
        if endpoint_rejection is not None:
            log.warning("[IPC] set_config rejected: %s", endpoint_rejection)
            resp["type"] = "error"
            resp["data"] = {
                "code": LegacyErrorCodes.INVALID_FIELD,
                "message": endpoint_rejection,
                "errors": [endpoint_rejection],
            }
            return None, resp, [], []
        if "bubble_position" in validated:
            validated.setdefault("bubble_x", None)
            validated.setdefault("bubble_y", None)
        # CPU-retention guard (GPU switch + CUDA install flow): a
        # `device: "cuda"` request is refused while the install job runs
        # or the CUDA stack is not proven ready. The renderer gates the
        # same states, this is the backend half of the contract — a
        # persisted `cuda` that no backend can serve is the C-UI-15 lie.
        from voice_typer.server.handlers.cuda_handlers import (
            device_request_rejection,
        )

        rejection = device_request_rejection(validated, self.app.config)
        if rejection is not None:
            log.warning("[IPC] set_config device=cuda refused: %s", rejection)
            resp["type"] = "error"
            resp["data"] = {
                "code": rejection,
                "message": rejection,
            }
            return None, resp, [], []
        accepted_keys = list(validated.keys())
        rejected_keys = [k for k in data if k not in validated]
        return validated, None, accepted_keys, rejected_keys

    def _apply_set_config_under_lock(self, validated: dict) -> tuple[list, list, list, set]:
        """Apply model/backend swaps and persist under the mutation lock."""
        model_errors: list[dict] = []
        applied: list[str] = []
        model_loading: list[dict] = []
        failed_keys: set[str] = set()
        app_ref = self.app
        config_lock = getattr(app_ref, "_config_mutation_lock", None)
        global _CONFIG_LOCK_MISSING_WARNED
        if config_lock is None and not _CONFIG_LOCK_MISSING_WARNED:
            _CONFIG_LOCK_MISSING_WARNED = True
            log.warning(
                "[IPC] set_config: app has no _config_mutation_lock, "
                "running lock-free; concurrent set_config / change_model "
                "may interleave (this warning fires once per process)"
            )
        # RACE-011: hold _config_mutation_lock across change_model + persist.
        with contextlib.ExitStack() as stack:
            if config_lock is not None:
                stack.enter_context(config_lock)
            self._swap_set_config_models(validated, applied, model_errors, model_loading, failed_keys)
        return model_errors, applied, model_loading, failed_keys

    def _swap_set_config_models(
        self, validated: dict, applied: list, model_errors: list, model_loading: list, failed_keys: set
    ) -> dict:
        """Swap model/backend inside the held lock; return the persist set."""
        if "model_size" in validated and validated["model_size"] != getattr(self.app.config, "model_size", None):
            old_model_size = getattr(self.app.config, "model_size", None)
            old_backend = getattr(self.app.config, "asr_backend", None)
            try:
                self.service.change_model(validated["model_size"])
                applied.append("model_size")
                model_loading.append(
                    {
                        "field": "model_size",
                        "status": "loading",
                        "previous": {
                            "backend": old_backend,
                            "model_size": old_model_size,
                        },
                        "pending": {"model_size": validated["model_size"]},
                    }
                )
            except Exception as e:
                log.error(
                    "[IPC] change_model(model_size=%s) failed: %s",
                    validated["model_size"],
                    e,
                    exc_info=True,
                )
                model_errors.append(
                    {
                        "code": LegacyErrorCodes.MODEL_SWITCH_FAILED,
                        "field": "model_size",
                        "value": validated["model_size"],
                    }
                )
                failed_keys.add("model_size")
        if "asr_backend" in validated and validated["asr_backend"] != getattr(self.app.config, "asr_backend", None):
            old_backend = getattr(self.app.config, "asr_backend", None)
            old_model_size = getattr(self.app.config, "model_size", None)
            try:
                self.service.set_active_backend(validated["asr_backend"])
                applied.append("asr_backend")
                model_loading.append(
                    {
                        "field": "asr_backend",
                        "status": "loading",
                        "previous": {
                            "backend": old_backend,
                            "model_size": old_model_size,
                        },
                        "pending": {"backend": validated["asr_backend"]},
                    }
                )
            except Exception as e:
                log.error(
                    "[IPC] set_active_backend(asr_backend=%s) failed: %s",
                    validated["asr_backend"],
                    e,
                    exc_info=True,
                )
                model_errors.append(
                    {
                        "code": LegacyErrorCodes.MODEL_SWITCH_FAILED,
                        "field": "asr_backend",
                        "value": validated["asr_backend"],
                    }
                )
                failed_keys.add("asr_backend")
        to_persist = {k: v for k, v in validated.items() if k not in failed_keys}
        self.service.apply_config(to_persist)
        if "trusted_extra_hosts" in to_persist:
            try:
                from voice_typer.server._secrets import extend_url_allowlist

                extend_url_allowlist(
                    cast(list[str], to_persist["trusted_extra_hosts"]),
                    caller="set_config.trusted_extra_hosts",
                )
            except Exception:
                log.debug("[IPC] set_config trusted_extra_hosts allowlist re-apply failed", exc_info=True)
        applied.extend(k for k in to_persist if k not in applied)
        return to_persist

    def _run_set_config_side_effects(self, validated: dict, to_persist: dict) -> None:
        # Unlocking the developer surface must prepare the workspace and arm
        # the dictation seam BEFORE the renderer is told the flag changed:
        # the Plugins page it now offers resolves the plugin directory, and a
        # packaged build has no writable one until this seeds it. Turning the
        # flag off closes the surface and stops whatever a plugin was doing.
        if "developer_mode" in validated:
            try:
                from voice_typer.server import internal_plugin_hook

                if to_persist.get("developer_mode"):
                    internal_plugin_hook.install(self.app)
                else:
                    internal_plugin_hook.teardown(self.app)
            except Exception:
                log.warning("[IPC] developer mode switch failed", exc_info=True)
        # Selecting a plugin has to have an immediate effect: the plugin owns
        # dictation from that moment, so its browser has to come up (or go
        # away) now rather than on the next hotkey press. Off-thread — a cold
        # Chrome boot takes seconds and must not stall the IPC response.
        if "active_plugin" in validated:
            try:
                import threading

                from voice_typer.server import internal_plugin_hook

                threading.Thread(
                    target=internal_plugin_hook.sync_selection,
                    args=(self.app,),
                    name="plugin-selection-sync",
                    daemon=True,
                ).start()
            except Exception:
                log.debug("[IPC] plugin selection sync failed", exc_info=True)
        try:
            from voice_typer.server.tray_models import invalidate_model_availability_cache

            invalidate_model_availability_cache()
        except Exception:
            log.debug("[IPC] invalidate_model_availability_cache failed", exc_info=True)
        try:
            # Publish the EFFECTIVE hotkey values: a failed re-registration
            # restores the previous spec, so Settings must see that rather
            # than the request it just sent. Every other key was applied by
            # ``apply_config`` before its side effects, so the payload stands.
            effective = dict(to_persist)
            for key in ("hotkey", "repaste_hotkey"):
                if key not in effective:
                    continue
                value = getattr(self.app.config, key, None)
                if isinstance(value, str):
                    effective[key] = value
            event_bus.publish({"type": "config_changed", "data": effective})
        except Exception:
            log.debug("[IPC] config_changed push failed", exc_info=True)
        if any(
            k in validated
            for k in (
                "bubble_behavior",
                "bubble_click_to_toggle",
                "bubble_mic_button",
                "bubble_position",
                "text_size",
            )
        ):
            try:
                self.app.push_bubble_config(self.app.config)
            except Exception:
                log.debug("[IPC] bubble_config push failed", exc_info=True)

    def _build_set_config_response(
        self,
        resp: ResponseEnvelope,
        accepted_keys: list,
        rejected_keys: list,
        model_errors: list,
        applied: list,
        model_loading: list,
    ) -> None:
        resp["type"] = "ack"
        response_data: dict = {}
        if rejected_keys:
            response_data["accepted"] = accepted_keys
            response_data["rejected"] = rejected_keys
        if model_errors:
            response_data["status"] = "partial"
            response_data["model_errors"] = model_errors
            response_data["applied"] = applied
        if model_loading:
            response_data["model_loading"] = model_loading
        if response_data:
            resp["data"] = response_data

    def _handle_set_config(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``set_config`` IPC command."""
        # SEC-002: payload allowlist enforced in _validate_set_config_payload.
        try:
            validated, error_resp, accepted_keys, rejected_keys = self._validate_set_config_payload(data, resp)
            if validated is None:
                return error_resp
            model_errors, applied, model_loading, failed_keys = self._apply_set_config_under_lock(validated)
            to_persist = {k: v for k, v in validated.items() if k not in failed_keys}
            self._run_set_config_side_effects(validated, to_persist)
            self._build_set_config_response(resp, accepted_keys, rejected_keys, model_errors, applied, model_loading)
        except Exception as exc:
            self._respond_with_error(resp, exc, "set_config")
        return resp

    def _handle_add_trusted_endpoint(self, data: object | None, resp: ResponseEnvelope) -> ResponseEnvelope | None:
        """Handle the ``add_trusted_endpoint`` IPC command."""
        try:
            if not isinstance(data, dict) or not isinstance(data.get("host"), str):
                log.warning("[IPC] add_trusted_endpoint rejected: data.host must be a string")
                return _error_response(
                    resp,
                    "add_trusted_endpoint requires data.host: string",
                    code=LegacyErrorCodes.INVALID_PAYLOAD,
                )
            raw_host = data["host"].strip()
            # Reject scheme/path/whitespace on the RAW value first —
            if not raw_host or "://" in raw_host or "/" in raw_host or " " in raw_host:
                log.warning("[IPC] add_trusted_endpoint rejected: invalid host %r", raw_host)
                return _error_response(
                    resp,
                    f"invalid host {raw_host!r}, expected a bare hostname like 'my-vllm.lan'",
                    code=LegacyErrorCodes.INVALID_FIELD,
                )
            # ``_normalize_host`` in ``security.url_allowlist`` and the
            if raw_host.startswith("["):
                # Bracketed IPv6 (with optional ``:port``): ``[fc00::1]``
                closing = raw_host.find("]")
                if closing <= 0:
                    return _error_response(
                        resp,
                        f"invalid host {raw_host!r}, is not a valid IPv6 literal",
                        code=LegacyErrorCodes.INVALID_FIELD,
                    )
                inner = raw_host[1:closing]
                try:
                    ipaddress.ip_address(inner)
                except ValueError:
                    return _error_response(
                        resp,
                        f"invalid host {raw_host!r}, is not a valid IPv6 literal",
                        code=LegacyErrorCodes.INVALID_FIELD,
                    )
                host = inner
            elif raw_host.count(":") > 1:
                # Bare IPv6 literal (``fc00::1``) OR a multi-colon
                try:
                    ipaddress.ip_address(raw_host)
                except ValueError:
                    return _error_response(
                        resp,
                        f"invalid host {raw_host!r}, is not a valid IPv6 literal",
                        code=LegacyErrorCodes.INVALID_FIELD,
                    )
                host = raw_host
            else:
                # Generic hostname / IPv4 / hostname:port, strip the
                host = raw_host.split(":")[0]
            host = host.strip().lower()
            if not host:
                log.warning("[IPC] add_trusted_endpoint rejected: invalid host %r", raw_host)
                return _error_response(
                    resp,
                    f"invalid host {raw_host!r}, expected a bare hostname like 'my-vllm.lan'",
                    code=LegacyErrorCodes.INVALID_FIELD,
                )
            if not all(c.isalnum() or c in "-._" or c == ":" for c in host):
                return _error_response(
                    resp,
                    f"invalid host {raw_host!r}, contains invalid characters",
                    code=LegacyErrorCodes.INVALID_FIELD,
                )

            from voice_typer.server._secrets import extend_url_allowlist

            # Apply to the runtime allowlist first, then persist.
            extend_url_allowlist([host], caller="add_trusted_endpoint")

            # Persist to config.json under trusted_extra_hosts (idempotent).
            current = list(getattr(self.app.config, "trusted_extra_hosts", []) or [])
            if host not in current:
                current.append(host)
                self.service.apply_config({"trusted_extra_hosts": current})

            resp["type"] = "ack"
            resp["data"] = {"host": host}
            return resp
        except Exception as exc:
            self._respond_with_error(resp, exc, "add_trusted_endpoint")
            return resp
