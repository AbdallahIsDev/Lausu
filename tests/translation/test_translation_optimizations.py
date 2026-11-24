"""Fake-process tests for the translation path's no-model optimizations."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
from voice_typer.server import event_bus
from voice_typer.server.translation import prompt as prompt_module, service as svc
from voice_typer.server.translation.chunking import bounded_chunks, translate_segments
from voice_typer.server.translation.preservation import protect_spans

_PARSE_GLOSSARY_CACHED = prompt_module.parse_glossary
_PROMPT_SHELL_CACHED = prompt_module._prompt_shell


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class _CountingRuntime:
    base_url = "http://127.0.0.1:54321"

    def __init__(self) -> None:
        self.stops = 0

    @property
    def running(self) -> bool:
        return True

    def stop(self) -> None:
        self.stops += 1


@pytest.fixture(autouse=True)
def _isolate_translation_globals() -> Any:
    svc.shutdown()
    _PARSE_GLOSSARY_CACHED.cache_clear()
    _PROMPT_SHELL_CACHED.cache_clear()
    yield
    svc.shutdown()
    _PARSE_GLOSSARY_CACHED.cache_clear()
    _PROMPT_SHELL_CACHED.cache_clear()


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        translation_enabled=True,
        translation_model="index-translate-2b-q4-k-m",
        translation_model_path="",
        translation_runtime_path="",
        translation_gpu_enabled=True,
        translation_glossary="",
        language="ar",
    )


def _patch_fake_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    urlopen_impl: Callable[[Any, float], _FakeResponse],
) -> tuple[list[int], list[int]]:
    """Own one fake llama-server process and one fake loopback POST endpoint."""
    starts: list[int] = []

    def _start(*_args: object, **_kwargs: object) -> _CountingRuntime:
        starts.append(1)
        return _CountingRuntime()

    monkeypatch.setattr(svc, "work_dir", lambda: tmp_path)
    monkeypatch.setattr(svc, "resolve_runtime_path", lambda _config: tmp_path / "llama-server.exe")
    monkeypatch.setattr(svc, "resolve_model_path", lambda _config: tmp_path / "model.gguf")
    monkeypatch.setattr(svc.RuntimeServer, "start", _start)
    calls: list[int] = []

    def _urlopen(request: Any, timeout: float) -> _FakeResponse:
        calls.append(1)
        return urlopen_impl(request, timeout)

    monkeypatch.setattr(svc, "urlopen", _urlopen)
    return starts, calls


def _answer(content: str) -> Callable[[Any, float], _FakeResponse]:
    return lambda _request, _timeout: _FakeResponse({"choices": [{"message": {"content": content}}]})


def _notices(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    published: list[dict[str, Any]] = []
    monkeypatch.setattr(event_bus, "publish", lambda event: published.append(event) or True)
    return published


class TestPromptShellCaching:
    def test_glossary_is_parsed_once_for_repeated_source_texts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_parse = prompt_module.parse_glossary
        seen: list[str] = []

        def _spy(raw: str) -> list[tuple[str, str]]:
            seen.append(raw)
            return real_parse(raw)

        monkeypatch.setattr(prompt_module, "parse_glossary", _spy)
        first = prompt_module.build_user_prompt("النص الأول", "en", "a => b")
        second = prompt_module.build_user_prompt("النص الثاني", "en", "a => b")

        assert seen == ["a => b"]
        assert "`a` translates to `b`" in first
        assert first.endswith("النص الأول")
        assert second.endswith("النص الثاني")

    def test_prompt_without_glossary_or_markers_is_byte_identical(self) -> None:
        assert prompt_module.build_user_prompt("hello", "en") == (
            "Translate the following text into English. Note that you should only output "
            "the translated result without any additional explanation:\n\nhello"
        )


class TestRuntimeReuse:
    def test_two_translations_start_one_process_and_post_twice(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        starts, calls = _patch_fake_runtime(monkeypatch, tmp_path, _answer("ok"))
        config = _config()

        assert svc.translate_text("النص الأول", config, "en", "ar") == "ok"
        assert svc.translate_text("النص الثاني", config, "en", "ar") == "ok"

        assert len(starts) == 1
        assert len(calls) == 2

    def test_batch_uses_the_loaded_runtime(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        starts, calls = _patch_fake_runtime(monkeypatch, tmp_path, _answer("ok"))
        service = svc.get_service(_config())

        result = service.translate_batch(["النص الأول", "النص الثاني"], "en")

        assert result == ["ok", "ok"]
        assert len(starts) == 1
        assert len(calls) == 2

    def test_prewarm_is_explicit_once_and_respects_disabled_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        starts, _calls = _patch_fake_runtime(monkeypatch, tmp_path, _answer("ok"))
        config = _config()

        assert svc.prewarm(config) is True
        assert svc.prewarm(config) is True
        assert len(starts) == 1

        disabled = _config()
        disabled.translation_enabled = False
        assert svc.prewarm(disabled) is False
        assert len(starts) == 1


class TestCancellationAndFailures:
    def test_cancel_before_start_never_touches_the_runtime(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        starts, calls = _patch_fake_runtime(monkeypatch, tmp_path, _answer("ok"))
        published = _notices(monkeypatch)
        event = threading.Event()
        event.set()

        with pytest.raises(svc.TranslationCancelledError):
            svc.translate_text("النص الأول", _config(), "en", "ar", cancel_event=event)

        assert starts == [] and calls == [] and published == []

    def test_cancel_while_waiting_for_the_model_is_not_a_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        event = threading.Event()

        def _cancel_during_request(_request: Any, _timeout: float) -> _FakeResponse:
            event.set()
            return _FakeResponse({"choices": [{"message": {"content": "ok"}}]})

        _starts, calls = _patch_fake_runtime(monkeypatch, tmp_path, _cancel_during_request)
        published = _notices(monkeypatch)

        with pytest.raises(svc.TranslationCancelledError):
            svc.translate_text("النص الأول", _config(), "en", "ar", cancel_event=event)

        assert len(calls) == 1
        assert published == []

    def test_timeout_logs_the_budget_and_keeps_the_original(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        def _timeout(_request: Any, _timeout: float) -> _FakeResponse:
            raise TimeoutError("timed out")

        _patch_fake_runtime(monkeypatch, tmp_path, _timeout)
        published = _notices(monkeypatch)
        caplog.set_level(logging.WARNING, logger=svc.log.name)

        source = "النص اللي بعتهولي"
        assert svc.translate_text(source, _config(), "en", "ar") == source
        assert "within 120s" in caplog.text
        assert len([e for e in published if e.get("type") == "notification"]) == 1

    def test_http_error_logs_status_and_keeps_the_original(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        def _http_error(_request: Any, _timeout: float) -> _FakeResponse:
            raise HTTPError("http://127.0.0.1:1", 503, "unavailable", Message(), None)

        _patch_fake_runtime(monkeypatch, tmp_path, _http_error)
        _notices(monkeypatch)
        caplog.set_level(logging.WARNING, logger=svc.log.name)

        source = "النص اللي بعتهولي"
        assert svc.translate_text(source, _config(), "en", "ar") == source
        assert "HTTP 503" in caplog.text

    def test_unsupported_target_never_starts_the_model(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        starts, calls = _patch_fake_runtime(monkeypatch, tmp_path, _answer("ok"))
        published = _notices(monkeypatch)
        caplog.set_level(logging.WARNING, logger=svc.log.name)

        source = "النص اللي بعتهولي"
        assert svc.translate_text(source, _config(), "xx", "ar") == source
        assert starts == [] and calls == []
        assert "unsupported target" in caplog.text
        assert len([e for e in published if e.get("type") == "notification"]) == 1

    def test_failed_request_is_never_auto_retried(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        def _fail(_request: Any, _timeout: float) -> _FakeResponse:
            raise URLError("boom")

        _starts, calls = _patch_fake_runtime(monkeypatch, tmp_path, _fail)
        published = _notices(monkeypatch)

        source = "النص اللي بعتهولي"
        assert svc.translate_text(source, _config(), "en", "ar") == source
        assert len(calls) == 1
        assert len([e for e in published if e.get("type") == "notification"]) == 1


class TestOptInChunking:
    def test_bounded_chunks_lose_no_characters_and_keep_markers_intact(self) -> None:
        protected, spans = protect_spans("First sentence. See https://example.com/a/b?x=1 now.第三次测试。Last one!")
        markers = [marker for marker, _original in spans]
        chunks = bounded_chunks(protected, max_chars=40)

        assert "".join(chunks) == protected
        assert all(len(chunk) <= 40 for chunk in chunks)
        for marker in markers:
            assert any(marker in chunk for chunk in chunks)

    def test_translate_segments_keeps_timestamps_and_unknown_fields(self) -> None:
        segments = [
            {"start": 1.25, "end": 3.5, "text": "مرحبا", "speaker": "A"},
            {"start": 3.5, "end": 7.0, "text": "شكرا", "confidence": 0.9},
        ]

        translated = translate_segments(segments, lambda text: "T:" + text)

        assert [row["text"] for row in translated] == ["T:مرحبا", "T:شكرا"]
        assert [row["start"] for row in translated] == [1.25, 3.5]
        assert [row["end"] for row in translated] == [3.5, 7.0]
        assert translated[0]["speaker"] == "A"
        assert translated[1]["confidence"] == 0.9
        assert [row["text"] for row in segments] == ["مرحبا", "شكرا"]
