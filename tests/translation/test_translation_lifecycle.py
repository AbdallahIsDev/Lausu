"""Translator adapter to the shared model lifecycle: real service entry points.

Fakes stay at the process boundary (llama-server spawn, loopback POST); the
service cache, the policy and the dictation stage are the production objects.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from voice_typer.server.dictation_pipeline import translation_steps
from voice_typer.server.translation import lifecycle, service as svc
from voice_typer.server.translation.service import TranslationService


class _Runtime:
    base_url = "http://127.0.0.1:54321"

    def __init__(self, spec: Any) -> None:
        self.spec = spec
        self.running = True
        self.stops = 0

    def stop(self) -> None:
        self.stops += 1
        self.running = False


class _Response:
    def __init__(self, content: str = "ok") -> None:
        self._content = content

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        import json

        return json.dumps({"choices": [{"message": {"content": self._content}}]}).encode("utf-8")


def _config(*, gpu: bool = True, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        translation_enabled=enabled,
        translation_model="index-translate-2b-q4-k-m",
        translation_model_path="",
        translation_runtime_path="",
        translation_gpu_enabled=gpu,
        translation_glossary="",
        translation_target_language="en",
        language="ar",
        model_size="turbo",
        asr_backend="whisper",
    )


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    svc.shutdown()
    monkeypatch.setattr(lifecycle, "_last_attempt_key", None)
    monkeypatch.setattr(svc, "work_dir", lambda: tmp_path)
    monkeypatch.setattr(svc, "resolve_runtime_path", lambda _cfg: tmp_path / "llama-server.exe")
    monkeypatch.setattr(svc, "resolve_model_path", lambda _cfg: tmp_path / "model.gguf")
    yield
    svc.shutdown()


def _fake_spawn(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    specs: list[Any] = []
    monkeypatch.setattr(
        svc.RuntimeServer,
        "start",
        lambda spec, timeout_s: specs.append(spec) or _Runtime(spec),
    )
    return specs


class TestSharedRegistration:
    def test_translator_is_an_optional_shared_kind(self) -> None:
        from voice_typer.server import model_lifecycle

        lifecycle.register()
        policy = model_lifecycle.get(lifecycle.KIND)

        assert policy is not None
        assert policy.name == "translation"
        assert policy.residency == "optional"
        assert policy.estimate_private_bytes == 1_800_000_000

    @pytest.mark.parametrize(
        ("enabled", "model_size", "backend", "installed", "expected"),
        [
            (True, "turbo", "whisper", True, True),
            (False, "turbo", "whisper", True, False),
            (True, "", "whisper", True, False),
            (True, "", "cloud", True, True),
            (True, "turbo", "whisper", False, False),
        ],
    )
    def test_applicability_matrix(
        self,
        monkeypatch: pytest.MonkeyPatch,
        enabled: bool,
        model_size: str,
        backend: str,
        installed: bool,
        expected: bool,
    ) -> None:
        monkeypatch.setattr(svc, "_model_is_installed", lambda _cfg: installed)
        config = _config(enabled=enabled)
        config.model_size = model_size
        config.asr_backend = backend

        assert lifecycle.is_applicable(config) is expected


class TestSkippedKindRecovery:
    def test_skipped_kind_loads_once_on_demand_then_reuses_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        specs = _fake_spawn(monkeypatch)
        config = _config()

        assert lifecycle.ensure_translation_loaded(config, timeout_s=1.0) is True
        assert lifecycle.ensure_translation_loaded(config, timeout_s=1.0) is True
        assert len(specs) == 1  # no second process for the same settings

    def test_failed_load_is_not_retried_by_the_next_wait(self, monkeypatch: pytest.MonkeyPatch) -> None:
        attempts: list[int] = []

        def _fail(*_args: object, **_kwargs: object) -> None:
            attempts.append(1)
            raise RuntimeError("fake process start failed")

        monkeypatch.setattr(svc.RuntimeServer, "start", _fail)
        config = _config()

        assert lifecycle.ensure_translation_loaded(config, timeout_s=1.0) is False
        assert lifecycle.ensure_translation_loaded(config, timeout_s=1.0) is False
        assert len(attempts) == 1


class TestGpuSwitch:
    def test_toggle_while_loaded_stops_old_process_and_new_spec_uses_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        specs = _fake_spawn(monkeypatch)
        config = _config(gpu=True)
        first: TranslationService = svc.get_service(config)
        first._ensure_runtime()
        old = first._runtime
        assert old is not None and old.stops == 0
        assert "-ngl" in specs[0].argv and "99" in specs[0].argv

        switched = _config(gpu=False)
        assert svc.is_loaded(switched) is False  # old GPU runtime is not valid for CPU config
        second: TranslationService = svc.get_service(switched)
        assert old.stops == 1  # the old process was retired, not left running
        second._ensure_runtime()

        assert len(specs) == 2
        assert specs[1].argv[-2:] == ["-ngl", "0"]
        assert svc.is_loaded(switched) is True


class TestStageBSharedWait:
    @staticmethod
    def _step(config: Any) -> Any:
        step = translation_steps._TranslationStepMixin()
        step._app = SimpleNamespace(config=config)
        return step

    def test_success_waits_before_translating(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []
        monkeypatch.setattr(translation_steps._lifecycle, "is_applicable", lambda _cfg: True)
        monkeypatch.setattr(
            translation_steps._lifecycle,
            "ensure_translation_loaded",
            lambda cfg, timeout_s: calls.append("wait") or True,
        )
        monkeypatch.setattr(svc, "translate_text", lambda *_a, **_k: calls.append("translate") or "translated")

        assert self._step(_config())._translate("orig") == "translated"
        assert calls == ["wait", "translate"]

    def test_timeout_keeps_original_text_with_one_notice_and_no_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        waits: list[float] = []
        notices: list[Any] = []
        monkeypatch.setattr(translation_steps._lifecycle, "is_applicable", lambda _cfg: True)
        monkeypatch.setattr(
            translation_steps._lifecycle,
            "ensure_translation_loaded",
            lambda _cfg, timeout_s: waits.append(timeout_s) or False,
        )
        monkeypatch.setattr(svc, "notify_translation_failure", lambda app: notices.append(app))
        monkeypatch.setattr(svc, "translate_text", lambda *_a, **_k: pytest.fail("no retry after timeout"))

        assert self._step(_config())._translate("original text") == "original text"
        assert waits == [45.0]
        assert len(notices) == 1


class TestUseRecording:
    def test_successful_post_touches_the_shared_idle_clock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_spawn(monkeypatch)
        monkeypatch.setattr(svc, "urlopen", lambda _req, timeout: _Response())
        from voice_typer.server.model_lifecycle import idle

        touched: list[str] = []
        monkeypatch.setattr(idle, "touch", touched.append)

        assert svc.translate_text("النص", _config(), "en", "ar") == "ok"
        assert touched == [lifecycle.KIND]
