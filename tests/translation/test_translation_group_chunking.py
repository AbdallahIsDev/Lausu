"""Fake-runtime tests for token-bounded group chunking of over-long Stage B text."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.error import URLError

import pytest
from voice_typer.server import event_bus
from voice_typer.server.translation import chunking, service as svc
from voice_typer.server.translation.preservation import protect_spans
from voice_typer.server.translation.prompt import build_user_prompt

_AR_SENTENCE = "يكتب برنامج التسجيل العينات في مخزن دائري ويفرغ عامل منفصل هذا المخزن كل نصف ثانية."
_EN_SENTENCE = "Audio capture writes samples into a ring buffer and a worker drains it every half second."


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")


class _CountingRuntime:
    base_url = "http://127.0.0.1:54321"

    @property
    def running(self) -> bool:
        return True

    def stop(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _isolate_translation_globals() -> Any:
    svc.shutdown()
    yield
    svc.shutdown()


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


def _patch_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    answers: list[str],
    *,
    fail_at: int | None = None,
    hook: Callable[[int], None] | None = None,
) -> tuple[list[int], list[int], list[str]]:
    starts: list[int] = []
    calls: list[int] = []
    prompts: list[str] = []

    def _start(*_args: object, **_kwargs: object) -> _CountingRuntime:
        starts.append(1)
        return _CountingRuntime()

    def _urlopen(request: Any, timeout: float) -> _FakeResponse:
        index = len(calls)
        calls.append(1)
        payload = json.loads(request.data.decode("utf-8"))
        prompts.append(payload["messages"][1]["content"])
        if hook is not None:
            hook(index)
        if fail_at is not None and index == fail_at:
            raise URLError("boom")
        content = answers[min(index, len(answers) - 1)]
        return _FakeResponse({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(svc, "work_dir", lambda: tmp_path)
    monkeypatch.setattr(svc, "resolve_runtime_path", lambda _cfg: tmp_path / "llama-server.exe")
    monkeypatch.setattr(svc, "resolve_model_path", lambda _cfg: tmp_path / "model.gguf")
    monkeypatch.setattr(svc.RuntimeServer, "start", _start)
    monkeypatch.setattr(svc, "urlopen", _urlopen)
    return starts, calls, prompts


def _notices(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    published: list[dict[str, Any]] = []
    monkeypatch.setattr(event_bus, "publish", lambda event: published.append(event) or True)
    return published


class TestMeasuredBound:
    def test_safe_input_budget_matches_context_math(self) -> None:
        assert chunking.CONTEXT_TOKENS == 4096
        assert chunking.MAX_OUTPUT_TOKENS == 1024
        assert chunking.SHELL_RESERVE_TOKENS >= 54  # measured system + shell + template framing
        assert (
            chunking.SAFE_INPUT_TOKENS
            == chunking.CONTEXT_TOKENS
            - chunking.MAX_OUTPUT_TOKENS
            - chunking.SHELL_RESERVE_TOKENS
            - chunking.SAFETY_MARGIN_TOKENS
        )
        assert chunking.SAFE_INPUT_TOKENS > 0

    def test_estimator_covers_real_tokenize_densities(self) -> None:
        # Real /tokenize measurements, build b12521-6f311d7ad (see r4-s2-token-evidence.txt).
        assert chunking.estimate_tokens(_AR_SENTENCE) >= 0.2983 * len(_AR_SENTENCE)
        assert chunking.estimate_tokens(_EN_SENTENCE) >= 0.1924 * len(_EN_SENTENCE)

    def test_runtime_and_payload_use_the_same_constants(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        payloads: list[dict[str, Any]] = []

        def _start(*_args: object, **_kwargs: object) -> _CountingRuntime:
            return _CountingRuntime()

        def _urlopen(request: Any, timeout: float) -> _FakeResponse:
            payloads.append(json.loads(request.data.decode("utf-8")))
            return _FakeResponse({"choices": [{"message": {"content": "ok"}}]})

        monkeypatch.setattr(svc, "work_dir", lambda: tmp_path)
        monkeypatch.setattr(svc, "resolve_runtime_path", lambda _cfg: tmp_path / "llama-server.exe")
        monkeypatch.setattr(svc, "resolve_model_path", lambda _cfg: tmp_path / "model.gguf")
        monkeypatch.setattr(svc.RuntimeServer, "start", _start)
        monkeypatch.setattr(svc, "urlopen", _urlopen)

        assert svc.translate_text(_AR_SENTENCE, _config(), "en", "ar") == "ok"
        spec = svc.get_service(_config())._spec()
        assert spec.argv[spec.argv.index("-c") + 1] == str(chunking.CONTEXT_TOKENS)
        assert payloads[0]["max_tokens"] == chunking.MAX_OUTPUT_TOKENS


class TestShortTextUnchanged:
    def test_short_text_is_one_call_with_the_unchanged_prompt(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        starts, calls, prompts = _patch_runtime(monkeypatch, tmp_path, ["TRADOTTO"])
        config = _config()
        config.translation_glossary = "buffer => مخزن"
        source = "النص الأول www.example.com/A/B?x=1 ورقم 42."

        assert svc.translate_text(source, config, "en", "ar") == "TRADOTTO"

        assert len(starts) == 1
        assert len(calls) == 1
        protected, spans = protect_spans(source)
        assert prompts[0] == build_user_prompt(protected, "en", "buffer => مخزن", tuple(marker for marker, _ in spans))

    def test_short_text_over_old_char_bound_still_uses_one_call(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        starts, calls, _prompts = _patch_runtime(monkeypatch, tmp_path, ["ok"])
        source = " ".join([_EN_SENTENCE] * 12)

        assert svc.translate_text(source, _config(), "en", "ar") == "ok"
        assert len(starts) == 1
        assert len(calls) == 1


class TestGroupChunking:
    def test_long_text_groups_sentences_and_keeps_markers(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(svc, "SAFE_INPUT_TOKENS", 60)
        source = " ".join([_AR_SENTENCE] * 8) + " راجع https://example.com/a/b?x=1 الآن."
        protected, spans = protect_spans(source)
        groups = chunking.group_chunks(protected, 60)
        assert 2 <= len(groups) < 9  # groups, not one sentence per call

        answers = [f"T{index}" for index in range(len(groups))]
        answers[-1] += " " + spans[0][0]
        _starts, calls, prompts = _patch_runtime(monkeypatch, tmp_path, answers)
        published = _notices(monkeypatch)

        result = svc.translate_text(source, _config(), "en", "ar")

        assert len(calls) == len(groups)
        assert published == []
        assert spans[0][1] in result
        assert all("Translate the following text into English" in prompt for prompt in prompts)

    def test_each_chunk_prompt_keeps_glossary_and_its_own_markers(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(svc, "SAFE_INPUT_TOKENS", 60)
        source = " ".join([_AR_SENTENCE] * 8) + " راجع https://example.com/a/b?x=1 الآن."
        protected, spans = protect_spans(source)
        groups = chunking.group_chunks(protected, 60)
        config = _config()
        config.translation_glossary = "buffer => مخزن"
        _starts, calls, prompts = _patch_runtime(
            monkeypatch, tmp_path, [f"T{index} {spans[0][0]}" for index in range(len(groups))]
        )
        marker_index = next(index for index, group in enumerate(groups) if spans[0][0] in group)

        result = svc.translate_text(source, config, "en", "ar")

        assert len(calls) == len(groups)
        assert all("`buffer` translates to `مخزن`" in prompt for prompt in prompts)
        assert spans[0][0] in prompts[marker_index]
        assert all(spans[0][0] not in prompt for index, prompt in enumerate(prompts) if index != marker_index)
        assert spans[0][1] in result

    def test_grouping_only_engages_above_the_bound(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(svc, "SAFE_INPUT_TOKENS", 60)
        _starts, calls, _prompts = _patch_runtime(monkeypatch, tmp_path, ["ok", "ok", "ok"])
        config = _config()

        assert svc.translate_text(_AR_SENTENCE, config, "en", "ar") == "ok"
        assert len(calls) == 1
        calls_after_short = len(calls)
        long_source = " ".join([_AR_SENTENCE] * 8)
        expected_groups = len(chunking.group_chunks(long_source, 60))
        assert svc.translate_text(long_source, config, "en", "ar") == " ".join(["ok"] * expected_groups)
        assert len(calls) - calls_after_short == expected_groups
        assert expected_groups > 1


class TestBoundaryPreference:
    def test_paragraph_boundaries_beat_sentence_boundaries(self) -> None:
        paragraph = " ".join([_AR_SENTENCE] * 2)
        source = paragraph + "\n\n" + paragraph
        groups = chunking.group_chunks(source, 60)

        assert "".join(groups) == source
        assert len(groups) == 2
        assert groups[0].endswith("\n\n")
        assert groups[1] == paragraph


class TestExactJoin:
    def test_join_preserves_a_space_that_was_in_the_source(self) -> None:
        assert chunking.boundary_separator("A. ", "B.") == " "
        assert chunking.join_translations(["A. ", "B."], ["X", "Y"]) == "X Y"

    def test_join_preserves_zero_space_script(self) -> None:
        assert chunking.boundary_separator("甲。", "乙。") == ""
        assert chunking.join_translations(["甲。", "乙。"], ["A", "B"]) == "AB"

    def test_join_preserves_paragraph_break(self) -> None:
        assert chunking.join_translations(["A.\n\n", "B."], ["X", "Y"]) == "X\n\nY"

    def test_join_refuses_mismatched_counts(self) -> None:
        with pytest.raises(ValueError):
            chunking.join_translations(["A", "B"], ["X"])

    def test_service_join_uses_the_source_separator_not_a_fixed_space(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(svc, "SAFE_INPUT_TOKENS", 60)
        spaced = " ".join([_AR_SENTENCE] * 8)
        groups = chunking.group_chunks(spaced, 60)
        _starts, calls, _prompts = _patch_runtime(monkeypatch, tmp_path, [f"T{index}" for index in range(len(groups))])

        result = svc.translate_text(spaced, _config(), "en", "ar")
        assert len(calls) == len(groups)
        assert result == " ".join(f"T{index}" for index in range(len(groups)))

    def test_service_join_adds_no_space_for_cjk(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(svc, "SAFE_INPUT_TOKENS", 20)
        source = "".join(["这是一个测试句子。"] * 8)
        groups = chunking.group_chunks(source, 20)
        assert len(groups) >= 2
        _starts, calls, _prompts = _patch_runtime(monkeypatch, tmp_path, [f"T{index}" for index in range(len(groups))])

        result = svc.translate_text(source, _config(), "en", "zh")
        assert len(calls) == len(groups)
        assert result == "".join(f"T{index}" for index in range(len(groups)))


class TestFailureAndCancellation:
    def test_one_failing_chunk_keeps_all_original_text_with_one_notice(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(svc, "SAFE_INPUT_TOKENS", 60)
        source = " ".join([_AR_SENTENCE] * 8)
        groups = chunking.group_chunks(source, 60)
        assert len(groups) >= 3
        starts, calls, _prompts = _patch_runtime(
            monkeypatch, tmp_path, [f"T{index}" for index in range(len(groups))], fail_at=1
        )
        published = _notices(monkeypatch)

        assert svc.translate_text(source, _config(), "en", "ar") == source
        assert len(starts) == 1
        assert len(calls) == 2  # stops at the failure, no retry and no later chunk
        assert len([event for event in published if event.get("type") == "notification"]) == 1

    @pytest.mark.parametrize("fail_at", [0, 1])
    def test_failure_in_any_chunk_keeps_whole_original(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fail_at: int
    ) -> None:
        monkeypatch.setattr(svc, "SAFE_INPUT_TOKENS", 60)
        source = " ".join([_AR_SENTENCE] * 8)
        groups = chunking.group_chunks(source, 60)
        _starts, calls, _prompts = _patch_runtime(
            monkeypatch, tmp_path, [f"T{index}" for index in range(len(groups))], fail_at=fail_at
        )
        published = _notices(monkeypatch)

        assert svc.translate_text(source, _config(), "en", "ar") == source
        assert len(calls) == fail_at + 1
        assert len([event for event in published if event.get("type") == "notification"]) == 1

    def test_empty_chunk_response_keeps_whole_original(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(svc, "SAFE_INPUT_TOKENS", 60)
        source = " ".join([_AR_SENTENCE] * 8)
        groups = chunking.group_chunks(source, 60)
        _starts, calls, _prompts = _patch_runtime(monkeypatch, tmp_path, [""] * len(groups))
        published = _notices(monkeypatch)

        assert svc.translate_text(source, _config(), "en", "ar") == source
        assert len(calls) == 1
        assert len([event for event in published if event.get("type") == "notification"]) == 1

    def test_cancel_between_chunks_never_notifies(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(svc, "SAFE_INPUT_TOKENS", 60)
        source = " ".join([_AR_SENTENCE] * 8)
        groups = chunking.group_chunks(source, 60)
        event = threading.Event()
        completed = svc.TranslationService._complete

        def _cancel_after_first(self: svc.TranslationService, prompt: str, **kwargs: Any) -> str:
            result = completed(self, prompt, **kwargs)
            event.set()
            return result

        monkeypatch.setattr(svc.TranslationService, "_complete", _cancel_after_first)
        _starts, calls, _prompts = _patch_runtime(monkeypatch, tmp_path, [f"T{index}" for index in range(len(groups))])
        published = _notices(monkeypatch)

        with pytest.raises(svc.TranslationCancelledError):
            svc.translate_text(source, _config(), "en", "ar", cancel_event=event)

        assert len(calls) == 1
        assert published == []

    def test_skip_decision_stays_once_on_the_whole_text(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(svc, "SAFE_INPUT_TOKENS", 60)
        _starts, calls, _prompts = _patch_runtime(monkeypatch, tmp_path, ["ok"])
        source = " ".join([_AR_SENTENCE] * 8)

        assert svc.translate_text(source, _config(), "ar", "ar") == source
        assert calls == []


class TestOverlongSentence:
    def test_single_sentence_falls_back_to_whitespace_boundaries(self) -> None:
        source = " ".join([_EN_SENTENCE] * 4)
        chunks = chunking.group_chunks(source, 20)

        assert len(chunks) >= 3
        assert "".join(chunks) == source
        assert all(chunking.estimate_tokens(chunk) <= 20 for chunk in chunks)

    def test_marker_survives_the_fallback(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(svc, "SAFE_INPUT_TOKENS", 30)
        source = "全新的测试句子 " * 12 + "https://example.com/very/long/path?x=1"
        protected, spans = protect_spans(source)
        groups = chunking.group_chunks(protected, 30)
        assert len(groups) >= 3
        assert "".join(groups) == protected
        assert any(spans[0][0] in group for group in groups)

        marker_index = next(index for index, group in enumerate(groups) if spans[0][0] in group)
        answers = [f"T{index} {spans[0][0]}" if index == marker_index else f"T{index}" for index in range(len(groups))]
        _starts, calls, _prompts = _patch_runtime(monkeypatch, tmp_path, answers)

        result = svc.translate_text(source, _config(), "en", "zh")
        assert len(calls) == len(groups)
        assert spans[0][1] in result
