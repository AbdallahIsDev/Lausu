"""Unit tests for ``ProviderHandlersMixin`` (provider IPC surface).

The point of these tests is the ENVELOPE: every failure path must carry a typed
``server.provider_*`` code the renderer can branch on, a stored key must never be
echoed back, and the per-domain write must go through ``set_config`` (SEC-002).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from voice_typer.server.model_providers.errors import ProviderAuthRequiredError, ProviderRuntimeError

MODULE = "voice_typer.server.handlers.provider_handlers"


class TestProviderList:
    def test_lists_every_provider_with_domains_and_selections(self, ipc_server, monkeypatch):
        monkeypatch.setattr(
            f"{MODULE}.provider_key_status",
            lambda provider: {"provider": provider, "configured": True, "masked": "sk-o***cdef"},
        )
        monkeypatch.setattr(f"{MODULE}.provider_requires_consent", lambda *a, **k: True)
        monkeypatch.setattr(f"{MODULE}.effective_consent", lambda *a, **k: False)

        resp = ipc_server._handle_provider_list({}, {})

        assert resp["type"] == "provider_list_result"
        providers = {p["id"]: p for p in resp["data"]["providers"]}
        assert {"openrouter", "ollama", "lmstudio", "local_onnx", "local", "cloud_direct"} <= set(providers)
        # Capability matrix is explicit, never implicit.
        assert providers["openrouter"]["domains"] == ["asr", "llm", "tts"]
        assert providers["local_onnx"]["domains"] == ["llm"]
        # A keyed provider reports the MASKED form only.
        assert providers["openrouter"]["key"]["masked"] == "sk-o***cdef"
        assert set(resp["data"]["domains"]) == {"asr", "tts", "llm"}

    def test_never_returns_raw_key_material(self, ipc_server, monkeypatch):
        raw = "sk-or-v1-SECRETSECRETSECRET"
        monkeypatch.setattr(
            f"{MODULE}.provider_key_status",
            lambda provider: {"provider": provider, "configured": True, "masked": "sk-o***CRET"},
        )
        monkeypatch.setattr(f"{MODULE}.provider_requires_consent", lambda *a, **k: False)
        monkeypatch.setattr(f"{MODULE}.effective_consent", lambda *a, **k: False)

        payload = repr(ipc_server._handle_provider_list({}, {}))

        assert raw not in payload


class TestProviderModels:
    def test_missing_provider_is_a_typed_field_error(self, ipc_server):
        resp = ipc_server._handle_provider_models({}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "client.missing_field"
        assert resp["data"]["field"] == "provider"

    def test_unknown_provider_is_typed(self, ipc_server):
        resp = ipc_server._handle_provider_models({"provider": "nope"}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.provider_unknown"

    def test_unknown_domain_rejected_before_any_work(self, ipc_server):
        resp = ipc_server._handle_provider_models({"provider": "openrouter", "domain": "video"}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "client.invalid_field"
        assert resp["data"]["field"] == "domain"


class TestProviderTest:
    def test_unknown_provider_is_typed(self, ipc_server):
        resp = ipc_server._handle_provider_test({"provider": "nope"}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.provider_unknown"

    def test_rejected_key_surfaces_as_auth_required(self, ipc_server, monkeypatch):
        descriptor = MagicMock()
        descriptor.models.return_value = []
        descriptor.probe.side_effect = ProviderAuthRequiredError("key rejected", provider="openrouter")
        registry = MagicMock()
        registry.get.return_value = descriptor
        monkeypatch.setattr(f"{MODULE}.get_registry", lambda: registry)

        resp = ipc_server._handle_provider_test({"provider": "openrouter"}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.provider_auth_required"
        assert resp["data"]["provider"] == "openrouter"

    def test_keyless_provider_fails_before_any_network_call(self, ipc_server, monkeypatch):
        descriptor = MagicMock()
        descriptor.auth = SimpleNamespace(value="api_key")
        registry = MagicMock()
        registry.get.return_value = descriptor
        monkeypatch.setattr(f"{MODULE}.get_registry", lambda: registry)
        monkeypatch.setattr(
            f"{MODULE}.provider_key_status", lambda provider: {"provider": provider, "configured": False}
        )

        resp = ipc_server._handle_provider_test({"provider": "openrouter"}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.provider_auth_required"
        descriptor.probe.assert_not_called()
        descriptor.models.assert_not_called()

    def test_successful_probe_reports_authentication(self, ipc_server, monkeypatch):
        descriptor = MagicMock()
        descriptor.auth = SimpleNamespace(value="api_key")
        descriptor.label = "OpenRouter"
        descriptor.domains = set()
        descriptor.models.return_value = []
        descriptor.probe.return_value = {"authenticated": True}
        registry = MagicMock()
        registry.get.return_value = descriptor
        monkeypatch.setattr(f"{MODULE}.get_registry", lambda: registry)
        monkeypatch.setattr(
            f"{MODULE}.provider_key_status", lambda provider: {"provider": provider, "configured": True}
        )

        resp = ipc_server._handle_provider_test({"provider": "openrouter"}, {})

        assert resp["type"] == "provider_test_result"
        assert resp["data"]["ok"] is True
        assert resp["data"]["auth"] == {"authenticated": True}


class TestProviderKeys:
    def test_set_key_unknown_provider_is_typed(self, ipc_server):
        resp = ipc_server._handle_provider_set_key({"provider": "nope", "key": "abc"}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.provider_unknown"

    def test_set_key_requires_a_key(self, ipc_server):
        resp = ipc_server._handle_provider_set_key({"provider": "openrouter", "key": "   "}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "client.missing_field"
        assert resp["data"]["field"] == "key"

    def test_set_key_returns_masked_status_never_the_secret(self, ipc_server, monkeypatch):
        stored: dict[str, str] = {}

        def _store(provider: str, key: str):
            stored[provider] = key
            return {"provider": provider, "configured": True, "masked": "sk-o***cdef"}

        monkeypatch.setattr(f"{MODULE}.store_provider_key", _store)
        monkeypatch.setattr(f"{MODULE}.get_catalogue_cache", lambda: MagicMock())

        resp = ipc_server._handle_provider_set_key({"provider": "openrouter", "key": "sk-or-v1-SECRETSECRET"}, {})

        assert resp["type"] == "provider_set_key_result"
        assert stored == {"openrouter": "sk-or-v1-SECRETSECRET"}
        assert "SECRETSECRET" not in repr(resp["data"])

    def test_clear_key_unknown_provider_is_typed(self, ipc_server):
        resp = ipc_server._handle_provider_clear_key({"provider": "nope"}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.provider_unknown"


class TestProviderSetDomain:
    def _capture_set_config(self, ipc_server) -> dict:
        captured: dict = {}

        def _set_config(data, resp):
            captured["payload"] = data
            resp["type"] = "config_result"
            resp["data"] = {"applied": sorted(data)}
            return resp

        ipc_server._handle_set_config = _set_config  # type: ignore[method-assign]
        return captured

    def test_selection_is_written_through_set_config(self, ipc_server):
        captured = self._capture_set_config(ipc_server)

        resp = ipc_server._handle_provider_set_domain(
            {"domain": "llm", "provider": "openrouter", "model_id": "", "consent": True}, {}
        )

        assert resp["type"] == "provider_domain_result"
        assert captured["payload"]["llm_provider"] == "openrouter"
        assert captured["payload"]["llm_provider_consent"] is True
        assert resp["data"]["domain"] == "llm"

    def test_disabling_clears_the_selection(self, ipc_server):
        captured = self._capture_set_config(ipc_server)

        resp = ipc_server._handle_provider_set_domain({"domain": "tts", "enabled": False}, {})

        assert resp["type"] == "provider_domain_result"
        assert captured["payload"]["tts_provider"] == ""

    def test_unknown_provider_is_typed(self, ipc_server):
        self._capture_set_config(ipc_server)

        resp = ipc_server._handle_provider_set_domain({"domain": "llm", "provider": "nope"}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.provider_unknown"

    def test_unsupported_domain_is_typed(self, ipc_server):
        self._capture_set_config(ipc_server)

        # lmstudio serves llm only; asking it for dictation must fail loudly.
        resp = ipc_server._handle_provider_set_domain({"domain": "asr", "provider": "lmstudio"}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.provider_unsupported_domain"

    def test_unadvertised_model_is_typed(self, ipc_server, monkeypatch):
        self._capture_set_config(ipc_server)
        descriptor = MagicMock()
        descriptor.supports.return_value = True
        descriptor.models.return_value = [MagicMock(id="known-model")]
        descriptor.free_form_models = False
        descriptor.find_model.return_value = None
        registry = MagicMock()
        registry.maybe_get.return_value = descriptor
        monkeypatch.setattr(f"{MODULE}.get_registry", lambda: registry)

        resp = ipc_server._handle_provider_set_domain(
            {"domain": "llm", "provider": "openrouter", "model_id": "not-in-catalogue"}, {}
        )

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.provider_model_unknown"
        assert resp["data"]["field"] == "model_id"

    def test_runtime_failure_keeps_its_typed_code(self, ipc_server, monkeypatch):
        self._capture_set_config(ipc_server)
        descriptor = MagicMock()
        descriptor.supports.return_value = True
        descriptor.models.side_effect = ProviderRuntimeError("catalogue down", provider="openrouter")
        registry = MagicMock()
        registry.maybe_get.return_value = descriptor
        monkeypatch.setattr(f"{MODULE}.get_registry", lambda: registry)

        resp = ipc_server._handle_provider_set_domain({"domain": "llm", "provider": "openrouter", "model_id": "x"}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "server.provider_runtime_error"

    def test_invalid_domain_is_typed(self, ipc_server):
        resp = ipc_server._handle_provider_set_domain({"domain": "video"}, {})

        assert resp["type"] == "error"
        assert resp["data"]["code"] == "client.invalid_field"
        assert resp["data"]["field"] == "domain"


@pytest.mark.parametrize("command", ["provider_set_key", "provider_clear_key", "provider_set_domain"])
def test_write_commands_are_registered(ipc_server, command):
    from voice_typer.server.ipc.registry import _COMMAND_REGISTRY

    assert command in _COMMAND_REGISTRY
