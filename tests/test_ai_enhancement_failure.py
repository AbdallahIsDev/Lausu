"""Failure-path tests for the enhancement-steps mixin."""

from __future__ import annotations

import types

import pytest
from voice_typer.server import event_bus
from voice_typer.server.dictation_pipeline.enhancement_steps import _EnhancementStepsMixin


class _FakeTray:
    def __init__(self) -> None:
        self.notifications: list[tuple[str, str]] = []

    def notify(self, title: str, message: str) -> None:
        self.notifications.append((title, message))


class _FakeApp:
    def __init__(self, config: types.SimpleNamespace) -> None:
        self.config = config
        self.tray = _FakeTray()
        self._llm_polisher = None
        self._llm_polish_fail_notified = False


class _EnhancerHost(_EnhancementStepsMixin):
    """Minimal mixin host: only the attributes the steps read."""

    # Defined on the pipeline (orchestrator), not the mixin; the bare
    _LLM_POLISH_PIPELINE_TIMEOUT_S = 4.0

    def __init__(self, app: _FakeApp) -> None:
        self._app = app
        self._templates_applied = False
        self._cycle_id = "test-cycle"


def _make_host(**config_updates: object) -> _EnhancerHost:
    config = types.SimpleNamespace(
        llm_polish=False,
        llm_api_key="",
        openai_api_key="",
        llm_polish_consent=False,
        llm_api_url=None,
        llm_model=None,
        llm_preset=None,
        ai_enhancement_enabled=True,
    )
    for key, value in config_updates.items():
        setattr(config, key, value)
    return _EnhancerHost(_FakeApp(config))


class _EventSpy:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def __call__(self, event: dict) -> None:
        self.events.append(event)


class _RaisingPolisher:
    def polish(self, text: str) -> str:
        raise ValueError("provider down")


@pytest.fixture
def event_spy():
    spy = _EventSpy()
    event_bus.subscribe(spy)
    yield spy
    event_bus.unsubscribe(spy)


class TestLlmPolishFailurePath:
    """Step 7 (LLM): failure keeps its own event name + notify-once."""

    def test_failure_publishes_llm_event_and_notifies_once(self, event_spy: _EventSpy) -> None:
        host = _make_host(llm_polish=True, llm_api_key="sk-test", llm_polish_consent=True)
        host._app._llm_polisher = _RaisingPolisher()
        result1 = host._apply_llm_polish("hello")
        result2 = host._apply_llm_polish("world")
        assert result1 == "hello"
        assert result2 == "world"
        published = [e["type"] for e in event_spy.events]
        assert published == ["llm_polish_failed", "llm_polish_failed"]
        assert len(host._app.tray.notifications) == 1
        assert "LLM polish failed" in host._app.tray.notifications[0][1]

    def test_polish_without_consent_publishes_consent_required(self, event_spy: _EventSpy) -> None:
        host = _make_host(llm_polish=True, llm_api_key="sk-test", llm_polish_consent=False)
        host._app._llm_polisher = _RaisingPolisher()
        result = host._apply_llm_polish("hello")
        assert result == "hello"
        published = [e["type"] for e in event_spy.events]
        assert published == ["consent_required"]
