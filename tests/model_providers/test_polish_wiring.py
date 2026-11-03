"""Routing wiring: startup binds the config getter; polish picks the local path."""

from __future__ import annotations

import logging
from types import SimpleNamespace

from voice_typer.server.dictation_pipeline import enhancement_steps
from voice_typer.server.dictation_pipeline.enhancement_steps import _EnhancementStepsMixin


class _App:
    def __init__(self, **overrides) -> None:
        base = {
            "llm_polish": True,
            "llm_api_key": "test-key",
            "llm_api_url": "",
            "llm_model": "gpt-test",
            "llm_preset": "professional",
            "llm_polish_consent": True,
            "llm_provider": "",
            "llm_model_id": "",
            "llm_provider_consent": False,
            "llm_provider_fallback": "off",
            "openai_api_key": "",
        }
        base.update(overrides)
        self.config = SimpleNamespace(**base)
        self._llm_polisher = None
        self._llm_polish_fail_notified = False
        self.tray = SimpleNamespace(notify=lambda *args, **kwargs: None)


class _Steps(_EnhancementStepsMixin):
    def __init__(self, app: _App) -> None:
        self._app = app
        self._cycle_id = "cycle-1"
        self._templates_applied = False
        self._LLM_POLISH_PIPELINE_TIMEOUT_S = 4.0


def test_startup_binding_lets_provider_clients_build() -> None:
    from voice_typer.server import startup_tasks
    from voice_typer.server.model_providers import builtin
    from voice_typer.server.model_providers.local_tts import LocalTtsClient

    app = SimpleNamespace(config=SimpleNamespace(tts_engine="magpie", tts_voice="Aria", tts_language="en-US"))
    startup_tasks.bind_provider_layer(app)

    assert builtin._config() is app.config
    client = LocalTtsClient(config=builtin._config(), engine="magpie")
    assert client.model_id == "magpie"


def test_cloud_direct_accepts_a_configured_model_id() -> None:
    from voice_typer.server.model_providers import resolve_llm

    app = SimpleNamespace(
        llm_provider="",
        llm_model_id="",
        llm_model="gpt-4o-mini",
        llm_api_key="key",
        llm_polish_consent=True,
        llm_provider_consent=False,
        llm_preset="professional",
        llm_api_url="",
        asr_backend="whisper",
        model_size="large-v3-turbo",
        tts_engine="off",
    )

    resolved = resolve_llm(app)

    assert resolved.provider.id == "cloud_direct"
    assert resolved.model_id == "gpt-4o-mini"


def test_local_provider_uses_chunked_polish(monkeypatch) -> None:
    calls: dict = {}

    def fake_polish_chunked(client, text, system_prompt, **kwargs):
        calls.update(text=text, system=system_prompt, abort=kwargs.get("abort_event"))
        return "polished"

    from voice_typer.server.model_providers import local_onnx

    monkeypatch.setattr(local_onnx.chunked, "polish_chunked", fake_polish_chunked)
    monkeypatch.setattr(
        "voice_typer.server.model_providers.resolve_llm",
        lambda config, **kw: SimpleNamespace(
            provider=SimpleNamespace(id="local_onnx"),
            model_id="minicpm5-2b",
            client=lambda: object(),
        ),
    )

    steps = _Steps(_App(llm_provider="local_onnx", llm_model_id="minicpm5-2b"))
    text = "This is one sentence. This is another sentence."
    assert steps._apply_llm_polish(text) == "polished"
    assert calls["text"] == text
    assert calls["abort"] is not None


def test_local_provider_polishes_without_an_api_key_or_consent(monkeypatch) -> None:
    """On-device polish needs neither a cloud key nor remote consent."""
    calls: dict = {}

    def fake_polish_chunked(client, text, system_prompt, **kwargs):
        calls.update(text=text)
        return "polished"

    from voice_typer.server.model_providers import local_onnx

    monkeypatch.setattr(local_onnx.chunked, "polish_chunked", fake_polish_chunked)
    monkeypatch.setattr(
        "voice_typer.server.model_providers.resolve_llm",
        lambda config, **kw: SimpleNamespace(
            provider=SimpleNamespace(id="local_onnx"),
            model_id="minicpm5-2b",
            client=lambda: object(),
        ),
    )

    steps = _Steps(
        _App(llm_provider="local_onnx", llm_model_id="minicpm5-2b", llm_api_key="", llm_polish_consent=False)
    )
    assert steps._apply_llm_polish("Hello there.") == "polished"
    assert calls["text"] == "Hello there."


def test_remote_provider_still_needs_a_key_and_consent(monkeypatch) -> None:
    """The legacy remote gate is untouched: no key or no consent skips polish."""
    from voice_typer.server.model_providers import local_onnx

    def fail(*args, **kwargs):
        raise AssertionError("no provider may be used without key + consent")

    monkeypatch.setattr(local_onnx.chunked, "polish_chunked", fail)
    monkeypatch.setattr("voice_typer.server.model_providers.resolve_llm", fail)

    no_key = _Steps(_App(llm_api_key=""))
    assert no_key._apply_llm_polish("keep me") == "keep me"
    no_consent = _Steps(_App(llm_polish_consent=False))
    assert no_consent._apply_llm_polish("keep me") == "keep me"


def test_remote_provider_key_from_the_vault_satisfies_the_gate(monkeypatch) -> None:
    """A key stored for the provider (not in ``llm_api_key``) still polishes."""
    from voice_typer.server.model_providers import routing

    monkeypatch.setattr(routing, "provider_key", lambda config, provider_id: "sk-vault")
    monkeypatch.setattr(
        "voice_typer.server.model_providers.resolve_llm",
        lambda config, **kw: SimpleNamespace(
            provider=SimpleNamespace(id="openrouter"),
            model_id="deepseek/chat",
            client=lambda: object(),
        ),
    )
    monkeypatch.setattr(_EnhancementStepsMixin, "_call_polish_with_timeout", lambda self, polisher, text: "polished")

    steps = _Steps(_App(llm_provider="openrouter", llm_api_key="", llm_polish_consent=False, llm_provider_consent=True))
    assert steps._apply_llm_polish("Hello there.") == "polished"


def test_remote_provider_keeps_the_word_limit(monkeypatch, caplog) -> None:
    long_text = " ".join(["word"] * (steps_limit := 1600))
    steps = _Steps(_App())

    with caplog.at_level(logging.INFO, logger=enhancement_steps.__name__):
        out = steps._apply_llm_polish(long_text)

    assert out == long_text
    assert "Skipping polish for long transcript" in caplog.text
    assert steps_limit > steps._LLM_POLISH_WORD_LIMIT


def test_resolution_failure_returns_raw_text_without_a_silent_fallback(monkeypatch, caplog) -> None:
    from voice_typer.server.model_providers.errors import ProviderNotFoundError

    def boom(config, **kwargs):
        raise ProviderNotFoundError("unknown provider 'nope'", provider="nope", domain="llm")

    monkeypatch.setattr("voice_typer.server.model_providers.resolve_llm", boom)
    steps = _Steps(_App(llm_provider="nope"))

    with caplog.at_level(logging.WARNING, logger=enhancement_steps.__name__):
        assert steps._apply_llm_polish("hello world") == "hello world"
    assert "provider resolution failed" in caplog.text
