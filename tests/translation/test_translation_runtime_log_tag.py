"""Readiness log tag belongs to the runtime domain, not always to TTS."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from voice_typer.server.tts import runtime_server as rs


class _Process:
    returncode = 0

    def poll(self) -> None:
        return None

    def terminate(self) -> None:
        return None

    def wait(self, timeout: float | None = None) -> None:
        return None

    def kill(self) -> None:
        return None


class _Healthy:
    status = 200

    def __enter__(self) -> _Healthy:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


@pytest.fixture(autouse=True)
def _fake_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    monkeypatch.setattr(rs, "free_port", lambda: 54321)
    monkeypatch.setattr(rs.subprocess, "Popen", lambda *_a, **_k: _Process())
    monkeypatch.setattr(rs, "urlopen", lambda _url, timeout: _Healthy())
    return tmp_path


@pytest.mark.parametrize(
    ("name", "log_tag", "expected"),
    [
        ("translation", "TRANSLATE", "[TRANSLATE] translation ready"),
        ("magpie", "TTS", "[TTS] magpie ready"),
        ("audio8", "TTS", "[TTS] audio8 ready"),
    ],
)
def test_readiness_uses_the_caller_domain_tag(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    name: str,
    log_tag: str,
    expected: str,
) -> None:
    caplog.set_level(logging.INFO, logger=rs.log.name)
    spec = rs.RuntimeSpec(
        name=name, argv=["fake-runtime", "--port", "{port}"], log_path=tmp_path / "runtime.log", log_tag=log_tag
    )

    rs.RuntimeServer.start(spec)

    assert expected in caplog.text
    assert "ready on http://127.0.0.1:54321" in caplog.text


def test_translation_service_spec_requests_the_translate_tag(tmp_path: Path) -> None:
    from voice_typer.server.translation.service import TranslationService

    config = type(
        "Config",
        (),
        {
            "translation_model": "index-translate-2b-q4-k-m",
            "translation_gpu_enabled": True,
            "translation_glossary": "",
        },
    )()
    service = TranslationService.__new__(TranslationService)
    service.config = config
    service.spec = None
    service.runtime_path = tmp_path / "llama-server.exe"
    service.model_path = tmp_path / "model.gguf"
    service.gpu_enabled = True
    service.glossary = ""

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr("voice_typer.server.translation.service.work_dir", lambda: tmp_path)
        spec = service._spec()

    assert spec.name == "translation"
    assert spec.log_tag == "TRANSLATE"
