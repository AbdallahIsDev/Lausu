"""Gemini cloud transcription provider: body shaping, parsing, send path."""

from __future__ import annotations

import base64
import json
from unittest.mock import patch
from urllib.error import HTTPError

import numpy as np
import pytest
from voice_typer.server.asr_errors import (
    CloudEmptyResponseError,
    CloudRateLimitError,
    CloudServerError,
)
from voice_typer.server.cloud._providers import gemini as gemini_provider
from voice_typer.server.cloud_engines import CloudEngine


def _make_fake_resp(body: bytes):
    calls = {"n": 0}

    class _FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, size: int = -1) -> bytes:
            if calls["n"] == 0:
                calls["n"] += 1
                return body
            return b""

        fp = None

    return _FakeResp()


def _gemini_engine(**overrides) -> CloudEngine:
    kwargs = {
        "provider": "gemini",
        "api_key": "test-gemini-key",
        "consent_given": True,
    }
    kwargs.update(overrides)
    return CloudEngine(**kwargs)


class TestGeminiUrl:
    def test_default_url_holds_model_placeholder(self):
        from voice_typer.server.cloud._defaults import _PROVIDER_DEFAULTS

        entry = _PROVIDER_DEFAULTS["gemini"]
        assert entry["url"].startswith("https://generativelanguage.googleapis.com")
        assert "{model}" in entry["url"]
        assert entry["model"] == "gemini-2.0-flash"

    def test_substitutes_model(self):
        url = gemini_provider.build_gemini_url(
            "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            "gemini-2.0-flash",
        )
        assert url == (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent"
        )

    def test_passthrough_without_placeholder(self):
        custom = "https://generativelanguage.googleapis.com/v1beta/models/x:generateContent"
        assert gemini_provider.build_gemini_url(custom, "gemini-2.0-flash") == custom

    def test_rejects_model_injection(self):
        with pytest.raises(RuntimeError, match="invalid characters"):
            gemini_provider.build_gemini_url("https://x/{model}:generateContent", "a&b=1")


class TestGeminiBody:
    def test_base64_wav_plus_prompt_shape(self):
        wav = b"RIFF....WAVEdata"
        body = gemini_provider.build_gemini_body(wav)
        payload = json.loads(body.decode("utf-8"))
        parts = payload["contents"][0]["parts"]
        assert parts[0]["text"] == gemini_provider.TRANSCRIBE_PROMPT
        inline = parts[1]["inline_data"]
        assert inline["mime_type"] == "audio/wav"
        assert base64.b64decode(inline["data"]) == wav


class TestGeminiParser:
    def test_candidates_path(self):
        raw = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "  hello gemini  "}]}}]}
        ).encode()
        assert gemini_provider.parse_gemini_transcript(raw) == "hello gemini"

    def test_empty_candidates_yields_empty(self):
        assert gemini_provider.parse_gemini_transcript(b'{"candidates": []}') == ""

    def test_missing_parts_yields_empty(self):
        raw = json.dumps({"candidates": [{"content": {"parts": []}}]}).encode()
        assert gemini_provider.parse_gemini_transcript(raw) == ""


class TestGeminiSendPath:
    def test_uses_header_auth_and_120s_timeout(self):
        engine = _gemini_engine()
        body = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}
        ).encode()
        with patch(
            "voice_typer.server.cloud_engines._opener.open",
            return_value=_make_fake_resp(body),
        ) as mock_open:
            assert engine.transcribe(np.zeros(16000, dtype=np.float32)) == "hi"
        req = mock_open.call_args[0][0]
        assert "gemini-2.0-flash:generateContent" in req.full_url
        assert "?key=" not in req.full_url and "key=" not in req.full_url
        assert req.get_header("X-goog-api-key") == "test-gemini-key"
        assert mock_open.call_args[1]["timeout"] == 120.0 == engine._GEMINI_REQUEST_TIMEOUT_SECONDS

    def test_empty_transcript_raises(self):
        engine = _gemini_engine()
        with (
            patch(
                "voice_typer.server.cloud_engines._opener.open",
                return_value=_make_fake_resp(b'{"candidates": []}'),
            ),
            pytest.raises(CloudEmptyResponseError),
        ):
            engine.transcribe(np.zeros(16000, dtype=np.float32))

    def test_429_maps_to_rate_limit(self):
        engine = _gemini_engine()
        err = HTTPError(
            url=engine.api_url, code=429, msg="slow down", hdrs={"Retry-After": "0"}, fp=None
        )
        with (
            patch("voice_typer.server.cloud_engines._opener.open", side_effect=err),
            pytest.raises(CloudRateLimitError),
        ):
            engine.transcribe(np.zeros(16000, dtype=np.float32))

    def test_503_maps_to_server_error(self):
        engine = _gemini_engine()
        err = HTTPError(url=engine.api_url, code=503, msg="unavailable", hdrs=None, fp=None)
        with (
            patch("voice_typer.server.cloud_engines._opener.open", side_effect=err),
            pytest.raises(CloudServerError),
        ):
            engine.transcribe(np.zeros(16000, dtype=np.float32))

    def test_consent_required(self):
        from voice_typer.server.asr_errors import CloudConsentRequiredError

        engine = _gemini_engine(consent_given=False)
        with pytest.raises(CloudConsentRequiredError):
            engine.transcribe(np.zeros(16000, dtype=np.float32))


class TestGeminiConfigPlumbing:
    def test_credential_store_map(self):
        from voice_typer.server.credential_store import PROVIDER_TO_CONFIG_FIELD

        assert PROVIDER_TO_CONFIG_FIELD["gemini"] == "gemini_api_key"

    def test_set_config_allowlist_round_trip(self):
        from voice_typer.server.config_validators import validate_config_update

        validated, errors = validate_config_update(
            {"gemini_api_key": "AIza-test", "cloud_gemini_consent": True}
        )
        assert errors == []
        assert validated == {"gemini_api_key": "AIza-test", "cloud_gemini_consent": True}

    def test_secret_redaction_covers_gemini_key(self):
        from voice_typer.server.config_sanitizer import SECRET_CONFIG_FIELDS

        assert "gemini_api_key" in SECRET_CONFIG_FIELDS

    def test_config_dataclass_defaults(self):
        from voice_typer.server.config import Config

        cfg = Config()
        assert cfg.gemini_api_key == ""
        assert cfg.cloud_gemini_consent is False

    def test_probe_endpoint_uses_header_auth(self):
        from voice_typer.server.handlers import cloud_test_handlers

        assert cloud_test_handlers._PROVIDER_TEST_ENDPOINTS["gemini"]["auth_scheme"] == "X-goog-api-key"

    def test_probe_sends_key_in_header_not_url(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from voice_typer.server.handlers import cloud_test_handlers

        handler = cloud_test_handlers.CloudTestHandlersMixin()
        handler.app = SimpleNamespace(config=SimpleNamespace(gemini_api_key="AIza-test-key"))
        handler.service = MagicMock()
        handler._send = MagicMock()
        resp: dict = {"type": "", "data": {}}

        captured: dict = {}

        def capture_and_raise(req, timeout=None):
            captured["headers"] = dict(req.header_items())
            captured["url"] = req.full_url
            raise cloud_test_handlers.HTTPError(
                url=req.full_url, code=401, msg="unauthorized", hdrs=None, fp=None
            )

        with patch.object(cloud_test_handlers, "_opener") as opener_mock:
            opener_mock.open = MagicMock(side_effect=capture_and_raise)
            handler._handle_test_cloud_connection({"provider": "gemini"}, resp)

        assert captured["headers"].get("X-goog-api-key") == "AIza-test-key"
        assert "Authorization" not in captured["headers"]
        assert "?key=" not in captured["url"] and "key=" not in captured["url"]
