"""Tests for privacy consent flags, cloud/HF/biometric consent enforcement,"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestConfigDeclaresConsentFlags:
    """The Config dataclass declares the consent flags."""

    def test_huggingface_consent_field_exists(self):
        from voice_typer.server.config import Config

        cfg = Config()
        assert hasattr(cfg, "huggingface_consent")
        assert cfg.huggingface_consent is False  # default: not given

    def test_cloud_per_provider_consent_fields_exist(self):
        from voice_typer.server.config import Config

        cfg = Config()
        assert hasattr(cfg, "cloud_openai_consent")
        assert hasattr(cfg, "cloud_groq_consent")
        assert hasattr(cfg, "cloud_deepgram_consent")
        assert cfg.cloud_openai_consent is False
        assert cfg.cloud_groq_consent is False
        assert cfg.cloud_deepgram_consent is False

    def test_voice_biometric_consent_field_exists(self):
        from voice_typer.server.config import Config

        cfg = Config()
        assert hasattr(cfg, "voice_biometric_consent")
        assert cfg.voice_biometric_consent is False

    def test_media_url_consent_field_exists(self):
        """ADR-0023: consent to send media URLs to the yt-dlp extractor."""
        from voice_typer.server.config import Config

        cfg = Config()
        assert hasattr(cfg, "media_url_consent")
        assert cfg.media_url_consent is False  # default: not given

    def test_consent_fields_round_trip_via_save_load(self, tmp_config_dir):
        """Consent flags must survive save → load round trip."""
        from voice_typer.server.config import Config

        cfg = Config()
        cfg.huggingface_consent = True
        cfg.cloud_openai_consent = True
        cfg.voice_biometric_consent = True
        assert cfg.save() is True

        loaded = Config.load()
        assert loaded.huggingface_consent is True
        assert loaded.cloud_openai_consent is True
        assert loaded.cloud_groq_consent is False  # untouched
        assert loaded.voice_biometric_consent is True

    def test_consent_fields_settable_via_ipc_allowlist(self):
        """validate_config_update accepts the consent fields so the renderer can set them."""
        from voice_typer.server.config import validate_config_update

        validated, errors = validate_config_update(
            {
                "huggingface_consent": True,
                "cloud_openai_consent": True,
                "cloud_groq_consent": False,
                "cloud_deepgram_consent": True,
                "voice_biometric_consent": True,
                "media_url_consent": True,
            }
        )
        assert errors == []
        assert validated["huggingface_consent"] is True
        assert validated["cloud_openai_consent"] is True
        assert validated["cloud_deepgram_consent"] is True
        assert validated["voice_biometric_consent"] is True
        assert validated["media_url_consent"] is True

    def test_consent_fields_reject_non_bool(self):
        """Consent fields must be bool, non-bool values are rejected."""
        from voice_typer.server.config import validate_config_update

        validated, errors = validate_config_update(
            {
                "huggingface_consent": "yes",
            }
        )
        assert errors, "Non-bool consent value should be rejected"
        assert "huggingface_consent" not in validated


class TestNoAutoUpdateFetchOnSettingsMount:
    """C-DATA-1 regression guard: PrewarmAndUpdates must NOT issue"""

    PREWARM_UPDATES_TSX = (
        REPO_ROOT
        / "voice_typer"
        / "client"
        / "src"
        / "renderer"
        / "src"
        / "components"
        / "settings"
        / "PrewarmAndUpdates.tsx"
    )

    @pytest.fixture(scope="class")
    @classmethod
    def component_source(cls) -> str:
        if not cls.PREWARM_UPDATES_TSX.exists():
            pytest.skip(f"PrewarmAndUpdates.tsx not found at {cls.PREWARM_UPDATES_TSX}")
        return cls.PREWARM_UPDATES_TSX.read_text(encoding="utf-8")

    def _use_effect_bodies(self, src: str) -> list[str]:
        """Extract each ``useEffect(() => { ... }, [...])`` body."""
        bodies: list[str] = []
        for m in re.finditer(r"useEffect\s*\(\s*\(\s*\)\s*=>\s*\{", src):
            start = m.end()
            depth = 1
            i = start
            while i < len(src) and depth > 0:
                if src[i] == "{":
                    depth += 1
                elif src[i] == "}":
                    depth -= 1
                i += 1
            bodies.append(src[start : i - 1])
        return bodies

    def test_no_autofire_check_for_update_in_use_effect(self, component_source):
        """No ``useEffect`` body may call ``checkForUpdate``."""
        bodies = self._use_effect_bodies(component_source)
        # release check, which is the strongest C-DATA-1 form.
        for idx, body in enumerate(bodies):
            assert "checkForUpdate" not in body, (
                f"PrewarmAndUpdates.tsx useEffect #{idx} references "
                f"'checkForUpdate', regression: auto-firing the "
                f"GitHub release check on mount leaks the user's IP and "
                f"breaks the C-DATA-1 offline guarantee."
            )

    def test_no_api_github_fetch_in_use_effect(self, component_source):
        """No ``useEffect`` body may ``fetch`` the GitHub releases API."""
        bodies = self._use_effect_bodies(component_source)
        github_pattern = re.compile(
            r"(api\.github\.com|LATEST_RELEASE_API|releases/latest)",
            re.IGNORECASE,
        )
        for idx, body in enumerate(bodies):
            assert not github_pattern.search(body), (
                f"PrewarmAndUpdates.tsx useEffect #{idx} fetches the "
                f"GitHub releases API on mount, regression: this leaks "
                f"the user's public IP + app User-Agent on every "
                f"Settings page open. C-DATA-1 forbids any network call "
                f"in the production code path."
            )

    def test_no_api_github_reference_anywhere_in_component(self, component_source):
        """C-DATA-1: the component source must NOT reference the GitHub"""
        github_pattern = re.compile(
            r"(api\.github\.com|LATEST_RELEASE_API|releases/latest)",
            re.IGNORECASE,
        )
        assert not github_pattern.search(component_source), (
            "PrewarmAndUpdates.tsx references the GitHub releases API "
            "(`api.github.com`, `LATEST_RELEASE_API`, or `releases/latest`) "
            "— C-DATA-1 forbids any network call in the production code "
            "path. The 'Check for Updates' button, handleManualCheck "
            "handler, latestVersion state, and LATEST_RELEASE_API constant "
            "were all removed; re-adding any of them is a regression."
        )

    def test_no_handle_manual_check_handler(self, component_source):
        """``api.github.com``."""
        assert "handleManualCheck" not in component_source, (
            "PrewarmAndUpdates.tsx contains 'handleManualCheck', "
            "C-DATA-1 forbids any network call in the production code path. "
            "The manual update-check handler was removed because its "
            "fetch() to api.github.com violated the offline guarantee."
        )

    def test_no_config_auto_update_consent_flag_required(self):
        """No ``Config.auto_update_check_consent`` flag is required."""
        pass


class TestCloudEngineRefusesWithoutConsent:
    """CloudEngine refuses to transcribe without consent."""

    def test_consent_required_error_is_runtime_error(self):
        from voice_typer.server.cloud_engines import ConsentRequiredError

        assert issubclass(ConsentRequiredError, RuntimeError)

    def test_cloud_engine_not_loaded_without_consent(self):
        from voice_typer.server.cloud_engines import CloudEngine

        eng = CloudEngine(
            provider="openai",
            api_key="sk-test-key",
            consent_given=False,
        )
        assert eng.is_loaded is False

    def test_cloud_engine_loaded_with_consent(self):
        from voice_typer.server.cloud_engines import CloudEngine

        eng = CloudEngine(
            provider="openai",
            api_key="sk-test-key",
            consent_given=True,
        )
        assert eng.is_loaded is True

    def test_transcribe_raises_without_consent(self):
        """transcribe() must raise ConsentRequiredError when consent hasn't been given."""
        import numpy as np
        from voice_typer.server.cloud_engines import CloudEngine, ConsentRequiredError

        eng = CloudEngine(
            provider="openai",
            api_key="sk-test-key",
            consent_given=False,
        )
        audio = np.zeros(16000, dtype=np.float32)
        with pytest.raises(ConsentRequiredError):
            eng.transcribe(audio)

    def test_transcribe_does_not_raise_with_consent(self):
        """When consent is given, transcribe should not raise ConsentRequiredError."""
        import numpy as np
        from voice_typer.server.cloud_engines import CloudEngine

        eng = CloudEngine(
            provider="openai",
            api_key="sk-test-key",
            consent_given=True,
        )
        empty_audio = np.array([], dtype=np.float32)
        result = eng.transcribe(empty_audio)
        assert result == ""


class TestWhisperLoadRefusesUncachedModel:
    """The GGUF resolver is local-only: no cached model means refuse, never download."""

    MODEL_KEY = "large-v3-turbo"

    @staticmethod
    def _install_fake_hf(monkeypatch, download_impl):
        import sys

        fake_module = type(sys)("huggingface_hub")
        fake_module.hf_hub_download = download_impl
        monkeypatch.setitem(sys.modules, "huggingface_hub", fake_module)
        return fake_module

    def test_cache_miss_raises_not_downloaded_without_network(self, monkeypatch):
        """A cache miss refuses before inference; no network call is made."""
        from voice_typer.worker.asr_runner import gguf_model_path_for_key

        calls = []

        def fake_download(**kwargs):
            calls.append(kwargs)
            if kwargs.get("local_files_only"):
                raise FileNotFoundError("not in cache")
            raise AssertionError("network download attempted from load path")

        self._install_fake_hf(monkeypatch, fake_download)
        with pytest.raises(RuntimeError, match="downloaded"):
            gguf_model_path_for_key(self.MODEL_KEY)
        assert calls, "the local cache probe must run"
        assert all(c.get("local_files_only") for c in calls), "the load path must never trigger a network download"

    def test_cache_miss_raises_even_with_consent(self, monkeypatch):
        """Consent never turns an engine load into a download."""
        from types import SimpleNamespace

        from voice_typer.worker.asr_runner import GgufTranscriptionEngine as TranscriptionEngine

        def fake_download(**kwargs):
            if kwargs.get("local_files_only"):
                raise FileNotFoundError("not in cache")
            raise AssertionError("network download attempted from load path")

        self._install_fake_hf(monkeypatch, fake_download)
        cfg = SimpleNamespace(
            huggingface_consent=True,
            asr_backend="whisper",
            model_size=self.MODEL_KEY,
            language=None,
        )
        with pytest.raises(RuntimeError, match="downloaded"):
            TranscriptionEngine(config=cfg)

    def test_tampered_cache_raises_integrity_error_without_deleting(self, monkeypatch, tmp_path):
        """A tampered GGUF is rejected by verification and left on disk."""
        from types import SimpleNamespace

        from voice_typer.server.gguf_download import download_gguf_model

        tampered = tmp_path / "tampered.gguf"
        tampered.write_bytes(b"not a valid model")
        self._install_fake_hf(monkeypatch, lambda **_kwargs: str(tampered))
        ok, reason = download_gguf_model(self.MODEL_KEY, config=SimpleNamespace(huggingface_consent=True))
        assert ok is False
        assert reason in ("size_mismatch", "sha256_mismatch")
        assert tampered.is_file(), "a tampered GGUF must NOT be deleted automatically"

    def test_cached_and_verified_model_passes(self, monkeypatch, tmp_path):
        """A locally cached GGUF resolves to its path without any download."""
        from voice_typer.worker.asr_runner import gguf_model_path_for_key

        cached = tmp_path / "cached.gguf"
        cached.write_bytes(b"x")
        self._install_fake_hf(monkeypatch, lambda **_kwargs: str(cached))
        assert gguf_model_path_for_key(self.MODEL_KEY) == str(cached)

    def test_non_whisper_models_skip_the_gate(self, monkeypatch):
        """Family routing picks one GGUF per family; legacy ids migrate."""
        from types import SimpleNamespace

        from voice_typer.server.gguf_model_registry import normalize_model_key
        from voice_typer.worker.asr_runner.families import model_key_for

        def fake_download(**_kwargs):
            raise AssertionError("HF cache must not be consulted for family routing")

        self._install_fake_hf(monkeypatch, fake_download)
        assert model_key_for(SimpleNamespace(asr_backend="parakeet")) == "parakeet"
        assert model_key_for(SimpleNamespace(asr_backend="qwen")) == "qwen3-1.7b"
        assert model_key_for(SimpleNamespace(asr_backend="whisper", model_size="")) == self.MODEL_KEY
        assert normalize_model_key("small.en", frozen=True) == self.MODEL_KEY

    def test_missing_huggingface_hub_raises_not_downloaded(self, monkeypatch):
        """No hub client means the cache cannot be confirmed: refuse."""
        import importlib.abc
        import sys

        from voice_typer.worker.asr_runner import gguf_model_path_for_key

        real_hf = sys.modules.pop("huggingface_hub", None)

        class _BlockHF(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "huggingface_hub":
                    raise ImportError("simulated: huggingface_hub not installed")
                return None

        blocker = _BlockHF()
        sys.meta_path.insert(0, blocker)
        try:
            with pytest.raises(RuntimeError, match="downloaded"):
                gguf_model_path_for_key(self.MODEL_KEY)
        finally:
            if blocker in sys.meta_path:
                sys.meta_path.remove(blocker)
            if real_hf is not None:
                sys.modules["huggingface_hub"] = real_hf


class TestEngineAcceptsConfigInRealConstructionPath:
    """TranscriptionEngine constructor accepts a config kwarg with consent flags."""

    def test_engine_accepts_config_kwarg(self, tmp_config_dir):
        from voice_typer.server.config import Config
        from voice_typer.worker.asr_runner import GgufTranscriptionEngine as TranscriptionEngine

        cfg = Config()
        cfg.huggingface_consent = True
        engine = TranscriptionEngine(model_path="model.gguf", model_size="small.en", config=cfg)
        assert engine.config is cfg
        assert engine.config.huggingface_consent is True

    def test_engine_defaults_config_to_none(self, tmp_config_dir):
        from voice_typer.worker.asr_runner import GgufTranscriptionEngine as TranscriptionEngine

        engine = TranscriptionEngine(model_path="model.gguf", model_size="small.en")
        assert engine.config is None

    def test_cache_gate_does_not_crash_without_config(self, tmp_path, monkeypatch):
        """Config=None falls back to the current default model key, not a crash."""
        import sys

        fake_module = type(sys)("huggingface_hub")

        def fake_download(**kwargs):
            if kwargs.get("local_files_only"):
                raise FileNotFoundError("not in cache")
            raise AssertionError("network call from the load path")

        fake_module.hf_hub_download = fake_download
        monkeypatch.setitem(sys.modules, "huggingface_hub", fake_module)

        from voice_typer.worker.asr_runner import GgufTranscriptionEngine as TranscriptionEngine

        with pytest.raises(RuntimeError, match="downloaded"):
            TranscriptionEngine()

    def test_load_path_never_downloads_even_with_consent(self, tmp_path, monkeypatch):
        """Engine construction resolves only local files, even with consent."""
        import sys

        from voice_typer.server.config import Config

        download_calls: list[dict] = []

        def fake_download(**kwargs):
            download_calls.append(kwargs)
            if kwargs.get("local_files_only"):
                raise FileNotFoundError("not in cache")
            raise AssertionError("network download attempted from load path")

        fake_module = type(sys)("huggingface_hub")
        fake_module.hf_hub_download = fake_download
        monkeypatch.setitem(sys.modules, "huggingface_hub", fake_module)

        from voice_typer.worker.asr_runner import GgufTranscriptionEngine as TranscriptionEngine

        cfg = Config()
        cfg.huggingface_consent = True
        cfg.model_size = "large-v3-turbo"
        with pytest.raises(RuntimeError, match="downloaded"):
            TranscriptionEngine(config=cfg)
        non_local_calls = [c for c in download_calls if not c.get("local_files_only")]
        assert len(non_local_calls) == 0


class TestModelManagerWiresConfigIntoWhisper:
    """ModelManager._ensure_engine passes the live Config to TranscriptionEngine."""

    def test_ensure_engine_passes_config_to_whisper(self, tmp_config_dir, monkeypatch):
        from voice_typer.server.config import Config
        from voice_typer.server.model_manager import ModelManager
        from voice_typer.server.tray import AppState

        class FakeTray:
            state = AppState.IDLE

            def set_state(self, *args, **kwargs):
                pass

            def notify(self, *args, **kwargs):
                pass

        class FakeApp:
            def __init__(self):
                self.config = Config()
                self.config.huggingface_consent = True
                self.tray = FakeTray()
                self._ipc_server = None
                self.models = None
                self._cloud_engine = None
                self._llm_polisher = None
                self._template_manager = None

        app = FakeApp()
        app.models = ModelManager(app)
        registry = app.models._registry
        app.models._ensure_engine("whisper")
        engine = registry.get("whisper")
        assert engine is not None
        assert engine.config is app.config
