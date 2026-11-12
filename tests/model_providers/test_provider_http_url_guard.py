"""Provider HTTP calls surface an untrusted endpoint as a typed provider error.

A bare ``ValueError`` from the URL allowlist is flattened into
``server.internal_error`` by the IPC catch-all, so the provider page shows
nothing actionable and the log loses the type.
"""

from __future__ import annotations

import pytest
from voice_typer.server.model_providers._http import open_stream, request_json
from voice_typer.server.model_providers.errors import ProviderError, ProviderRuntimeError


def _refuse_request():
    raise AssertionError("no request may be attempted for an untrusted host")


def test_request_json_rejects_an_untrusted_host_as_a_typed_provider_error() -> None:
    with pytest.raises(ProviderRuntimeError) as exc_info:
        request_json("https://evil.example.com/v1/models", provider="openrouter", opener=_refuse_request)

    assert exc_info.value.code == "server.provider_runtime_error"
    assert exc_info.value.provider == "openrouter"
    assert "evil.example.com" in str(exc_info.value)


def test_open_stream_rejects_an_untrusted_host_as_a_typed_provider_error() -> None:
    with pytest.raises(ProviderError) as exc_info:
        open_stream("https://evil.example.com/v1/chat/completions", provider="openrouter", opener=_refuse_request)

    assert exc_info.value.code == "server.provider_runtime_error"
    assert "evil.example.com" in str(exc_info.value)
