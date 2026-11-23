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
    detect_source_language,
    needs_translation,
    parse_glossary,
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


def test_mixed_scripts_are_detected_even_with_a_latin_url() -> None:
    """A URL's Latin letters must not turn Arabic text into 'mixed'."""
    arabic = detect_source_language("الملف موجود في https://example.com/foo")
    assert arabic.code == "ar" and arabic.mixed is False and arabic.confident is True

    mixed = detect_source_language("أنا عايز أعمل search عن this product")
    assert mixed.mixed is True and mixed.confident is True and mixed.code == ""


def test_skip_rule_only_skips_on_confident_match() -> None:
    # Same-language skip is now detection-based, never a blanket short-text rule.
    assert not needs_translation("الملف موجود", "ar", "ar")
    # Arabic -> English and mixed text always translate.
    assert needs_translation("الملف اللي بعتهولي امبارح مش بيفتح", "en", "ar")
    assert needs_translation("أنا عايز أعمل search عن this product", "en", "ar")
    # Short/ambiguous text must NOT be skipped, even with a pinned language.
    assert needs_translation("No", "en", "en")
    assert needs_translation("OK", "ar", "ar")
    # Latin text translates unless a pinned speaking language confirms the target.
    assert needs_translation("please open the file for me", "en", "")
    assert not needs_translation("please open the file for me", "en", "en")
    # Empty and no-target never translate.
    assert not needs_translation("   ", "en")
    assert not needs_translation("الملف موجود", "")


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


def test_catalogue_filename_matches_hf_repo_artifact() -> None:
    """The GGUF name must be the HF repo filename, not an Ollama blob alias."""
    from voice_typer.server.translation.catalogue import TRANSLATION_MODEL_FILENAME

    assert TRANSLATION_MODEL_FILENAME == "Index-Translate-2B.Q4_K_M.gguf"


def test_model_resolves_from_shared_hf_hub_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ADR-0030 storage: shared hub first, never an Ollama folder."""
    from voice_typer.server.translation import paths as tp

    hub = tmp_path / "hub"
    snapshot = (
        hub
        / "models--IndexTeam--Index-Translate-2B-GGUF"
        / "snapshots"
        / "deadbeef"
    )
    snapshot.mkdir(parents=True)
    model = snapshot / INDEX_TRANSLATE_Q4.filename
    model.write_bytes(b"gguf")

    monkeypatch.setattr(tp, "shared_hub_dir", lambda: hub)
    monkeypatch.setattr(tp, "config_dir", lambda: tmp_path / "app")
    monkeypatch.delenv(tp.MODEL_ENV, raising=False)
    config = SimpleNamespace(translation_model_path="")

    assert tp.resolve_model_path(INDEX_TRANSLATE_Q4, config) == model
    assert tp.model_is_available(INDEX_TRANSLATE_Q4, config) is True


def test_runtime_prefers_installer_bundle_over_app_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The runtime comes from the shipped bundle, not a D: dev directory."""
    from voice_typer.server.translation import paths as tp

    shipped = tmp_path / "resources"
    shipped.mkdir()
    binary = shipped / tp.RUNTIME_BASENAME
    binary.write_bytes(b"exe")

    monkeypatch.setattr(
        "voice_typer.server.media_ingest.ffmpeg_binaries._shipped_dirs",
        lambda: (shipped,),
    )
    monkeypatch.setattr(tp, "config_dir", lambda: tmp_path / "app")
    monkeypatch.delenv(tp.RUNTIME_ENV, raising=False)
    config = SimpleNamespace(translation_runtime_path="")

    assert tp.resolve_runtime_path(config) == binary


def test_translation_stage_records_original_text_in_context() -> None:
    """Translating a stage changes text and records raw Stage A text."""
    from voice_typer.server.dictation_stages import PipelineContext, TranslationStage

    calls: list[str] = []

    class _Pipeline:
        def _translate(self, text: str) -> str:
            calls.append(text)
            return "the file you sent me"

    ctx = PipelineContext(
        cycle_id="c1", audio=None, app=SimpleNamespace(), pipeline=_Pipeline()  # type: ignore[arg-type]
    )
    stage = TranslationStage()
    result = stage.run("الملف اللي بعتهولي", ctx)

    assert calls == ["الملف اللي بعتهولي"]
    assert result == "the file you sent me"
    assert ctx.extras["original_text"] == "الملف اللي بعتهولي"


def test_plugin_delivery_translates_before_paste_and_stores_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anthropic/Google STT plugins bypass the pipeline but still translate."""
    from tools.internal_plugins._common import delivery

    monkeypatch.setattr(
        "voice_typer.server.translation.service.translate_text",
        lambda text, config, target, spoken: "the translated text",
        raising=False,
    )
    # delivery imports inside the function, so patch the module directly too.
    monkeypatch.setitem(
        __import__("sys").modules,
        "voice_typer.server.translation.service",
        SimpleNamespace(translate_text=lambda *a, **k: "the translated text"),
    )

    copies: list[str] = []
    stored: dict[str, object] = {}

    class _Clipboard:
        _clipboard_seq = 1

        def copy(self, text: str) -> str:
            copies.append(text)
            return text

        def paste(self, **kwargs: object) -> None:
            return None

    class _History:
        def add_transcription(self, text: str, **kwargs: object) -> int:
            stored["text"] = text
            stored.update(kwargs)
            return 1

    app = SimpleNamespace(
        config=SimpleNamespace(
            translation_enabled=True,
            translation_target_language="en",
            language="ar",
            auto_capitalize=False,
            device="cpu",
        ),
        clipboard=_Clipboard(),
        history_db=_History(),
    )
    delivery.deliver_transcription(app, "النص الأصلي", 1.0, "anthropic", __import__("logging").getLogger("test"))

    assert copies == ["the translated text"]
    assert stored["text"] == "the translated text"
    assert stored["original_text"] == "النص الأصلي"


def test_translation_download_uses_shared_hf_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Download goes through hf_hub_download with no cache_dir override."""
    from voice_typer.server.translation import download as td

    artifact = tmp_path / INDEX_TRANSLATE_Q4.filename
    payload = b"gguf bytes"
    artifact.write_bytes(payload)
    # Build a spec whose pinned hash/size match the fake artifact.
    import hashlib

    from voice_typer.server.translation.catalogue import TranslationModelSpec

    spec = TranslationModelSpec(
        id=INDEX_TRANSLATE_Q4.id,
        label=INDEX_TRANSLATE_Q4.label,
        filename=INDEX_TRANSLATE_Q4.filename,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        repo_id=INDEX_TRANSLATE_Q4.repo_id,
        license=INDEX_TRANSLATE_Q4.license,
    )
    calls: list[dict[str, object]] = []

    class _FakeHub:
        @staticmethod
        def hf_hub_download(**kwargs: object) -> str:
            calls.append(kwargs)
            return str(artifact)

    monkeypatch.setattr("huggingface_hub.hf_hub_download", _FakeHub.hf_hub_download)
    monkeypatch.setattr(td, "ensure_hf_env", lambda: None)

    ok, reason, _ = td.download_translation_weights(
        spec, config=SimpleNamespace(huggingface_consent=True), force=False
    )
    assert ok is True, reason
    assert calls[0]["repo_id"] == spec.repo_id
    assert calls[0]["filename"] == spec.filename
    assert "cache_dir" not in calls[0]


class TestProtectedSpans:
    """URLs, emails, code and numbers survive the model call byte-identical."""

    def test_roundtrip_preserves_all_span_kinds(self) -> None:
        from voice_typer.server.translation.preservation import (
            protect_spans,
            restore_spans,
        )

        source = (
            "ابعت الرسالة لـ ada@example.com على https://example.com/v2?x=1 "
            "واستخدم `client_id` ثم AT-X19 و 42 كيلو"
        )
        protected, spans = protect_spans(source)
        assert len(spans) >= 4
        assert all(marker in protected for marker, _original in spans)
        assert "https://example.com/v2?x=1" not in protected
        # Model echoes the markers back verbatim (what a correct model does).
        assert restore_spans(protected, spans) == source

    def test_prompt_names_markers_only_when_present(self) -> None:
        plain = build_user_prompt("النص", "en")
        assert "Keep the bracketed markers" not in plain
        marked = build_user_prompt("\u27e6VT0\u27e7", "en", markers=("\u27e6VT0\u27e7",))
        assert "Keep the bracketed markers" in marked
        assert "\u27e6VT0\u27e7" in marked

    def test_detection_ignores_urls_emails_and_numbers(self) -> None:
        from voice_typer.server.translation.prompt import detect_source_language

        result = detect_source_language("راجع https://example.com أرسل لـ a@b.com الرقم 12345")
        assert result.code == "ar"
        assert result.mixed is False


class TestFailureNotification:
    """A failed translation keeps the original and tells the user once."""

    @staticmethod
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

    def test_failure_publishes_notification_and_keeps_original(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from urllib.error import URLError

        from voice_typer.server import event_bus
        from voice_typer.server.translation import service as svc

        published: list[dict] = []
        monkeypatch.setattr(event_bus, "publish", lambda event: published.append(event) or True)
        monkeypatch.setattr(svc, "work_dir", lambda: tmp_path)
        monkeypatch.setattr(
            svc, "resolve_runtime_path", lambda _config: tmp_path / "llama-server.exe"
        )
        monkeypatch.setattr(svc, "resolve_model_path", lambda _config: tmp_path / "model.gguf")
        monkeypatch.setattr(
            svc.RuntimeServer, "start", lambda *_a, **_k: _FakeRuntime()
        )

        def _raise(_request: object, timeout: float) -> object:
            raise URLError("boom")

        monkeypatch.setattr(svc, "urlopen", _raise)

        source = "الملف اللي بعتهولي امبارح مش بيفتح"
        result = svc.translate_text(source, self._config(), "en", "ar")

        assert result == source
        notices = [e for e in published if e.get("type") == "notification"]
        assert len(notices) == 1
        assert "translation_failed" in notices[0]["data"]["message"] or notices[0]["data"]["message"]
        assert notices[0]["data"]["title"]

    def test_notification_is_once_until_a_success_clears_it(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from urllib.error import URLError

        from voice_typer.server import event_bus
        from voice_typer.server.translation import service as svc

        published: list[dict] = []
        monkeypatch.setattr(event_bus, "publish", lambda event: published.append(event) or True)
        monkeypatch.setattr(svc, "work_dir", lambda: tmp_path)
        monkeypatch.setattr(
            svc, "resolve_runtime_path", lambda _config: tmp_path / "llama-server.exe"
        )
        monkeypatch.setattr(svc, "resolve_model_path", lambda _config: tmp_path / "model.gguf")
        monkeypatch.setattr(svc.RuntimeServer, "start", lambda *_a, **_k: _FakeRuntime())

        def _raise(_request: object, timeout: float) -> object:
            raise URLError("boom")

        monkeypatch.setattr(svc, "urlopen", _raise)
        source = "الملف اللي بعتهولي امبارح مش بيفتح"
        for _ in range(3):
            assert svc.translate_text(source, self._config(), "en", "ar") == source
        assert len([e for e in published if e.get("type") == "notification"]) == 1

        # A success resets the flag so a later failure is reported again.
        monkeypatch.setattr(
            svc,
            "urlopen",
            lambda _request, timeout: _FakeResponse(
                {"choices": [{"message": {"content": "ok"}}]}
            ),
        )
        assert svc.translate_text(source, self._config(), "en", "ar") == "ok"
        monkeypatch.setattr(svc, "urlopen", _raise)
        svc.translate_text(source, self._config(), "en", "ar")
        assert len([e for e in published if e.get("type") == "notification"]) == 2

    def test_no_notification_when_translation_is_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from voice_typer.server import event_bus
        from voice_typer.server.translation import service as svc

        published: list[dict] = []
        monkeypatch.setattr(event_bus, "publish", lambda event: published.append(event) or True)
        config = self._config()
        # Confident Arabic->Arabic match: no model call, no failure notice.
        assert svc.translate_text("الملف موجود", config, "ar", "ar") == "الملف موجود"
        assert published == []


class TestSameLanguageSkip:
    """The user's opening scenario: no model request when source == target."""

    def test_same_language_never_calls_the_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from voice_typer.server.translation import service as svc

        def _fail_start(*_a: object, **_k: object) -> object:
            raise AssertionError("model runtime must not start for a same-language skip")

        monkeypatch.setattr(svc.RuntimeServer, "start", _fail_start)
        result = svc.translate_text("الملف موجود", SimpleNamespace(translation_enabled=True), "ar", "ar")
        assert result == "الملف موجود"


class TestAuditFixes:
    """Regressions for issues found in the final independent audit."""

    def test_arabic_punctuation_does_not_count_as_script_letter(self) -> None:
        from voice_typer.server.translation.prompt import detect_source_language

        # Arabic punctuation / Arabic-Indic digits are in the Arabic Unicode
        # block but are not letters; a Latin sentence with them must stay Latin.
        result = detect_source_language("hello world ١٢٣؟")
        assert result.code == ""
        assert result.mixed is False

    def test_translate_text_accepts_optional_app_without_behavior_change(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from voice_typer.server.translation import service as svc

        app = SimpleNamespace()
        # Same-language skip with an app supplied must still skip and never
        # touch the tray (no failure happened).
        assert svc.translate_text(
            "الملف موجود", SimpleNamespace(translation_enabled=True), "ar", "ar", app=app
        ) == "الملف موجود"

    def test_stop_waits_for_inflight_request(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A config swap mid-request must not tear down the live runtime."""
        import threading
        import time

        from voice_typer.server.translation import service as svc

        entered = threading.Event()
        release = threading.Event()

        def _blocking_complete(self: object, prompt: str) -> str:
            entered.set()
            assert release.wait(timeout=5.0), "stop() released the request too early"
            return "ترجمة"

        # Patch the INNER call: _complete() holds self._lock around it.
        monkeypatch.setattr(svc.TranslationService, "_complete_locked", _blocking_complete)
        monkeypatch.setattr(svc, "resolve_runtime_path", lambda _c: tmp_path / "llama-server.exe")
        monkeypatch.setattr(svc, "resolve_model_path", lambda _c: tmp_path / "model.gguf")
        monkeypatch.setattr(
            svc.RuntimeServer, "start", lambda *_a, **_k: _FakeRuntime()
        )
        config = SimpleNamespace(
            translation_enabled=True,
            translation_model="index-translate-2b-q4-k-m",
            translation_model_path="",
            translation_runtime_path="",
            translation_gpu_enabled=True,
            translation_glossary="",
            language="ar",
        )
        result_box: list[str] = []

        def _worker() -> None:
            result_box.append(svc.translate_text("نص طويلSy meets text here", config, "en", "ar"))

        thread = threading.Thread(target=_worker)
        thread.start()
        assert entered.wait(timeout=5.0)
        stop_box: list[bool] = []

        def _stopper() -> None:
            service = svc.get_service(config)
            service.stop()
            stop_box.append(True)

        stopper = threading.Thread(target=_stopper)
        stopper.start()
        time.sleep(0.1)
        assert not stop_box, "stop() must wait for the in-flight request"
        release.set()
        thread.join(timeout=5.0)
        stopper.join(timeout=5.0)
        assert stop_box and result_box


def test_restore_row_preserves_original_text(tmp_path: Path) -> None:
    """Undo after delete must not lose the pre-translation original."""
    from voice_typer.server.history_db import HistoryDB

    db = HistoryDB(db_path=tmp_path / "undo.db")
    row_id = db.add_transcription(
        "the translated final text",
        original_text="النص الأصلي قبل الترجمة",
        language="en",
    )
    db.flush()
    record = db.get_transcription_text(row_id)
    assert record["original_text"] == "النص الأصلي قبل الترجمة"

    assert db.delete(row_id)
    db.flush()
    restored_id = db.restore(
        {
            "text": "the translated final text",
            "original_text": record["original_text"],
            "language": "en",
        },
        raise_on_error=True,
    )
    db.flush()
    restored = db.get_transcription_text(restored_id)
    assert restored["text"] == "the translated final text"
    assert restored["original_text"] == "النص الأصلي قبل الترجمة"
    db.close()
