"""ChatManager: phase order, single-flight, history window and failure paths.

The manager never touches the IPC layer, so every dependency is injected:
``capture`` and ``service`` arrive through the constructor, the LLM through
``conversation.manager.resolve_llm`` (monkeypatched per test). No test opens a
microphone, a model or a network connection.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from voice_typer.server.conversation import manager as manager_mod
from voice_typer.server.conversation.manager import DEFAULT_SYSTEM_PROMPT, ChatManager
from voice_typer.server.model_providers.contracts import ChatMessage
from voice_typer.server.model_providers.errors import ProviderError, ProviderUnavailableError

# ── fakes ────────────────────────────────────────────────────────────────────


class FakeCapture:
    """Stands in for ``ChatCapture``: returns canned audio, counts calls."""

    def __init__(self, audio: np.ndarray | None = None) -> None:
        self.audio = np.full(1600, 0.1, dtype=np.float32) if audio is None else audio
        self.started: list[str | None] = []
        self.stops = 0
        self.cancels = 0

    def start(self, mic_id: str | None = None) -> int:
        self.started.append(mic_id)
        return 16000

    def stop(self) -> np.ndarray:
        self.stops += 1
        return self.audio

    def cancel(self) -> None:
        self.cancels += 1


class FakeTts:
    """Stands in for the service mixin the manager calls for playback."""

    def __init__(self, fail: bool = False) -> None:
        self.spoken: list[str] = []
        self.stops = 0
        self.fail = fail

    def tts_speak(self, text: str) -> None:
        if self.fail:
            raise RuntimeError("no output device")
        self.spoken.append(text)

    def tts_stop(self) -> None:
        self.stops += 1


class FakeLlm:
    """Stands in for the resolved ``LlmClient``."""

    def __init__(
        self,
        reply: str = "Hi there.",
        error: Exception | None = None,
        block: Any = None,
    ) -> None:
        self.reply = reply
        self.error = error
        self._block = block
        self.calls: list[list[ChatMessage]] = []
        self.abort_events: list[threading.Event | None] = []

    def complete(
        self,
        messages: Any,
        *,
        max_tokens: int = 1024,
        timeout_s: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> str:
        self.calls.append(list(messages))
        self.abort_events.append(abort_event)
        if self._block is not None:
            self._block(abort_event)
        if self.error is not None:
            raise self.error
        return self.reply


def _config(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "microphone": None,
        "chat_history_turns": 8,
        "chat_system_prompt": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class Harness:
    """One manager wired to fakes, with its published phases recorded."""

    def __init__(
        self,
        *,
        audio: np.ndarray | None = None,
        reply: str = "Hi there.",
        error: Exception | None = None,
        tts_fail: bool = False,
        config: SimpleNamespace | None = None,
        transcript: str = "hello",
        block: Any = None,
    ) -> None:
        self.payloads: list[dict[str, Any]] = []
        self.idle = threading.Event()
        self.capture = FakeCapture(audio)
        self.tts = FakeTts(fail=tts_fail)
        self.llm = FakeLlm(reply=reply, error=error, block=block)
        engine = SimpleNamespace(
            is_loaded=True,
            transcribe_with_fallback=lambda _audio: transcript,
        )
        app = SimpleNamespace(models=SimpleNamespace(active_transcriber=lambda: engine))
        self.manager = ChatManager(
            app,
            config or _config(),
            self._publish,
            service=self.tts,
            capture=self.capture,
        )

    def _publish(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)
        if payload.get("phase") == "idle":
            self.idle.set()

    @property
    def phases(self) -> list[str]:
        return [str(p.get("phase")) for p in self.payloads]

    def run_turn(self, timeout: float = 10.0) -> None:
        self.idle.clear()
        assert self.manager.listen_start()["started"] is True
        assert self.manager.listen_stop()["accepted"] is True
        assert self.idle.wait(timeout), f"turn never reached idle; phases={self.phases}"


@pytest.fixture
def resolve_llm(monkeypatch: pytest.MonkeyPatch):
    """Install a fake ``resolve_llm``; returns the installer."""

    def install(fake: FakeLlm) -> FakeLlm:
        monkeypatch.setattr(
            manager_mod,
            "resolve_llm",
            lambda _config: SimpleNamespace(client=lambda: fake),
        )
        return fake

    return install


# ── phase order + single-flight ─────────────────────────────────────────────


def test_phase_order_is_exactly_transcribing_thinking_speaking_idle(resolve_llm) -> None:
    harness = Harness()
    resolve_llm(harness.llm)

    harness.run_turn()

    assert harness.phases == ["listening", "transcribing", "thinking", "speaking", "idle"]
    # The transcript rides the thinking phase, the reply rides speaking.
    thinking = harness.payloads[2]
    speaking = harness.payloads[3]
    assert (thinking["role"], thinking["text"]) == ("user", "hello")
    assert (speaking["role"], speaking["text"]) == ("assistant", "Hi there.")
    assert harness.tts.spoken == ["Hi there."]


def test_second_listen_start_while_busy_is_refused() -> None:
    harness = Harness()

    assert harness.manager.listen_start()["started"] is True
    assert harness.manager.listen_start() == {"started": False, "sample_rate": 0}
    # Exactly one capture arm: the second call never reached the capture.
    assert harness.capture.started == [None]
    harness.manager.reset()


def test_listen_stop_without_a_capture_is_refused() -> None:
    harness = Harness()

    assert harness.manager.listen_stop() == {"accepted": False}
    assert harness.capture.stops == 0


# ── history window + system prompt ──────────────────────────────────────────


def test_history_trims_to_two_turns_plus_the_system_message(resolve_llm) -> None:
    harness = Harness(config=_config(chat_history_turns=2))
    resolve_llm(harness.llm)
    harness.manager.messages = [
        ChatMessage("user" if index % 2 == 0 else "assistant", f"m{index}") for index in range(10)
    ]

    harness.run_turn()

    sent = harness.llm.calls[0]
    assert sent[0].role == "system"
    assert [message.content for message in sent[1:]] == ["m7", "m8", "m9", "hello"]
    assert len(sent) == 1 + 2 * 2


def test_history_turns_is_clamped_into_the_allowed_range(resolve_llm) -> None:
    harness = Harness(config=_config(chat_history_turns=999))
    resolve_llm(harness.llm)
    harness.manager.messages = [ChatMessage("user", f"m{index}") for index in range(70)]

    harness.run_turn()

    # 32 turns → 64 replayed messages, never the whole 70-message list.
    assert len(harness.llm.calls[0]) == 1 + 64


def test_builtin_system_prompt_is_used_when_the_override_is_empty(resolve_llm) -> None:
    harness = Harness(config=_config(chat_system_prompt="   "))
    resolve_llm(harness.llm)

    harness.run_turn()

    assert harness.llm.calls[0][0].content == DEFAULT_SYSTEM_PROMPT


def test_configured_system_prompt_wins(resolve_llm) -> None:
    harness = Harness(config=_config(chat_system_prompt="Answer like a pirate."))
    resolve_llm(harness.llm)

    harness.run_turn()

    assert harness.llm.calls[0][0].content == "Answer like a pirate."


# ── failure paths ───────────────────────────────────────────────────────────


def test_empty_transcript_never_calls_the_llm_and_emits_no_speech(resolve_llm) -> None:
    harness = Harness(transcript="   ")
    resolve_llm(harness.llm)

    harness.run_turn()

    assert harness.llm.calls == []
    assert {"phase": "error", "error_code": "no_speech"} in harness.payloads
    assert harness.phases[-1] == "idle"
    assert harness.manager.busy is False


def test_no_audio_emits_no_speech_without_transcribing(resolve_llm) -> None:
    harness = Harness(audio=np.empty(0, dtype=np.float32))
    resolve_llm(harness.llm)

    harness.run_turn()

    assert harness.llm.calls == []
    assert {"phase": "error", "error_code": "no_speech"} in harness.payloads


def test_tts_failure_keeps_the_reply_and_ends_idle(resolve_llm) -> None:
    harness = Harness(reply="Visible reply.", tts_fail=True)
    resolve_llm(harness.llm)

    harness.run_turn()

    assert {"phase": "speaking", "role": "assistant", "text": "Visible reply."} in harness.payloads
    assert harness.manager.messages[-1] == ChatMessage("assistant", "Visible reply.")
    assert harness.phases[-1] == "idle"
    assert harness.manager.busy is False


def test_provider_error_publishes_its_code_and_returns_to_idle(resolve_llm) -> None:
    harness = Harness(error=ProviderUnavailableError("provider down"))
    resolve_llm(harness.llm)

    harness.run_turn()

    assert {"phase": "error", "error_code": "server.provider_unavailable"} in harness.payloads
    assert harness.phases[-1] == "idle"
    assert harness.manager.busy is False
    # The user transcript is kept so the thread reads continuously.
    assert harness.manager.messages == [ChatMessage("user", "hello")]


def test_generic_provider_error_class_falls_back_to_its_base_code(resolve_llm) -> None:
    harness = Harness(error=ProviderError("boom"))
    resolve_llm(harness.llm)

    harness.run_turn()

    assert {"phase": "error", "error_code": "server.provider_error"} in harness.payloads


def test_reset_aborts_an_inflight_turn_and_clears_history(resolve_llm) -> None:
    started = threading.Event()

    def block(abort_event: threading.Event | None) -> None:
        started.set()
        assert abort_event is not None
        abort_event.wait(5.0)

    harness = Harness(block=block)
    resolve_llm(harness.llm)
    harness.manager.messages = [ChatMessage("user", "older")]

    assert harness.manager.listen_start()["started"] is True
    assert harness.manager.listen_stop()["accepted"] is True
    assert started.wait(5.0), "the turn never reached the LLM call"

    harness.manager.reset()

    assert harness.llm.abort_events[0] is not None
    assert harness.llm.abort_events[0].is_set(), "reset must abort the in-flight completion"
    assert harness.manager.messages == []
    assert harness.manager.phase == "idle"
    assert harness.manager.busy is False
    assert harness.capture.cancels == 1


# ── abandoned capture (bounded auto-finish) ─────────────────────────────────


def test_capture_without_a_release_is_finished_at_the_cap(monkeypatch: pytest.MonkeyPatch, resolve_llm) -> None:
    monkeypatch.setattr(manager_mod, "_CAPTURE_AUTO_FINISH_SECONDS", 0.05)
    harness = Harness()
    resolve_llm(harness.llm)

    assert harness.manager.listen_start()["started"] is True
    # No listen_stop: the page unmounted while the button was held.
    assert harness.idle.wait(10.0), f"watchdog never finished the turn; phases={harness.phases}"

    assert harness.capture.stops == 1
    assert harness.manager.busy is False
    assert [message.content for message in harness.manager.messages] == ["hello", "Hi there."]
    assert harness.phases[-1] == "idle"


def test_a_released_capture_disarms_the_watchdog(resolve_llm) -> None:
    harness = Harness()
    resolve_llm(harness.llm)

    harness.run_turn()

    assert harness.capture.stops == 1
    assert harness.manager._capture_watchdog_stop is None, "a released capture must disarm the watchdog"


def test_reset_disarms_the_watchdog() -> None:
    harness = Harness()

    assert harness.manager.listen_start()["started"] is True
    assert harness.manager._capture_watchdog_stop is not None

    harness.manager.reset()

    assert harness.manager._capture_watchdog_stop is None
