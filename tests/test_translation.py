"""Tests for the ADR-0021 Stage B / ADR-0030 text translator wiring."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from voice_typer.server.config_validators import validate_config_update
from voice_typer.server.dictation_stages import build_default_stages
from voice_typer.server.translation import service as translation_service
from voice_typer.server.translation.catalogue import (
    INDEX_TRANSLATE_Q4,
    TRANSLATION_MODEL_SIZE_BYTES,
)
from voice_typer.server.translation.prompt import (
    build_user_prompt,
    needs_translation,
    parse_glossary,
    split_for_translation,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class _FakeRuntime:
    base_url = "http://127.0.0.1:54321"

    @property
    def running(self) -> bool:
        return True

    def stop(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _reset_translation_service() -> Any:
    translation_service.shutdown()
    yield
    translation_service.shutdown()


def test_catalogue_pins_exact_q4_artifact() -> None:
    assert INDEX_TRANSLATE_Q4.id == "index-translate-2b-q4-k-m"
    assert TRANSLATION_MODEL_SIZE_BYTES == 1_312_164_352
    assert INDEX_TRANSLATE_Q4.license == "Apache-2.0"


def test_parse_glossary_supports_both_written_formats() -> None:
    raw = (
        "# pinned terms\n"
        "`الهيرو سكشن` translates to `hero section`\n"
        "MCTA button text => MCTA button text\n"
        "checkout -> الخصم\n"
    )
    assert parse_glossary(raw) == [
        ("الهيرو سكشن", "hero section"),
        ("MCTA button text", "MCTA button text"),
        ("checkout", "الخصم"),
    ]


def test_prompt_keeps_the_evaluated_instruction_and_glossary_block() -> None:
    prompt = build_user_prompt("النص", "en", "hero section => الهيرو سكشن")
    assert "Reference the following translations:" in prompt
    assert "`hero section` translates to `الهيرو سكشن`" in prompt
    assert "Translate the following text into English." in prompt
    assert "without any additional explanation:\n\nالنص" in prompt


def test_sentence_routing_preserves_target_script() -> None:
    chunks = split_for_translation("الملف موجود. Please open it. شكراً", "ar")
    assert [(text, translate) for text, translate in chunks if text.strip()] == [
        ("الملف موجود.", False),
        ("Please open it.", True),
        ("شكراً", False),
    ]
    chunks_en = split_for_translation("الملف موجود. Please open it.", "en")
    assert [(text, translate) for text, translate in chunks_en if text.strip()] == [
        ("الملف موجود.", True),
        ("Please open it.", False),
    ]


def test_skip_rule_protects_short_text_and_matching_language() -> None:
    assert not needs_translation("hello", "en")
    assert not needs_translation("الملف موجود", "ar", "ar")
    assert needs_translation("الملف اللي بعتهولي امبارح مش بيفتح", "en", "ar")


def test_config_fields_are_allowlisted_and_validated() -> None:
    validated, errors = validate_config_update(
        {
            "translation_enabled": True,
            "translation_model": "index-translate-2b-q4-k-m",
            "translation_target_language": "ar",
            "translation_gpu_enabled": False,
        }
    )
    assert errors == []
    assert validated["translation_enabled"] is True
    assert validated["translation_target_language"] == "ar"

    _validated, errors = validate_config_update({"translation_model": "not-a-model"})
    assert errors


def test_pipeline_inserts_translation_after_empty_check() -> None:
    names = [stage.name for stage in build_default_stages()]
    assert names[2] == "translate"
    assert names[-2:] == ["store", "paste"]


def test_translate_text_calls_llama_server_with_greedy_template_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setattr(translation_service, "work_dir", lambda: tmp_path)
    monkeypatch.setattr(
        translation_service,
        "resolve_runtime_path",
        lambda _config: tmp_path / "llama-server.exe",
    )
    monkeypatch.setattr(
        translation_service,
        "resolve_model_path",
        lambda _config: tmp_path / "model.gguf",
    )
    monkeypatch.setattr(translation_service.RuntimeServer, "start", lambda *_a, **_k: _FakeRuntime())

    def _fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _FakeResponse({"choices": [{"message": {"content": "the file you sent me"}}]})

    monkeypatch.setattr(translation_service, "urlopen", _fake_urlopen)

    config = SimpleNamespace(
        translation_enabled=True,
        translation_model="index-translate-2b-q4-k-m",
        translation_model_path="",
        translation_runtime_path="",
        translation_gpu_enabled=True,
        translation_glossary="hero section => الهيرو سكشن",
        language="ar",
    )
    result = translation_service.translate_text(
        "الملف اللي بعتهولي امبارح مش بيفتح", config, "en", "ar"
    )

    assert result == "the file you sent me"
    assert captured["url"].endswith("/v1/chat/completions")
    body = captured["body"]
    assert body["temperature"] == 0
    assert body["seed"] == 0
    assert body["cache_prompt"] is False
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert "Reference the following translations:" in body["messages"][1]["content"]
    assert (tmp_path / "index_translate_chat_template.jinja").is_file()
