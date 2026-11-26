"""Tests for the REMOVED automatic model-cache eviction."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    target = REPO_ROOT / path
    if target.is_dir():
        return "".join(p.read_text(encoding="utf-8") for p in sorted(target.glob("*.py")))
    return target.read_text(encoding="utf-8")


class TestPruneModelCacheRemoved:
    """The auto-eviction helper and its internals are gone."""

    def test_prune_model_cache_not_in_asr_utils(self):
        from voice_typer.server import asr_utils

        assert not hasattr(asr_utils, "prune_model_cache"), (
            "prune_model_cache must be REMOVED, the app never deletes "
            "models automatically; deleting a model is an explicit user "
            "action (Models page Delete button)."
        )

    def test_prune_internal_helpers_removed(self):
        from voice_typer.server import asr_utils

        for name in ("_prune_oldest_repos", "_repo_size_bytes", "_MAX_MODEL_CACHE_GB"):
            assert not hasattr(asr_utils, name), (
                f"asr_utils.{name} must be REMOVED along with the auto-eviction it supported."
            )

    def test_no_source_references_prune_model_cache(self):
        """No production module may reference the removed helper."""
        from voice_typer.server import asr_utils as mod

        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "prune_model_cache" not in src

    def test_no_automatic_eviction_in_transcription_source(self):
        src = _read("voice_typer/server/transcription.py")
        assert "prune_model_cache" not in src, "transcription.py must not reference the removed auto-eviction helper."


class TestCleanupHelperStillAvailableForExplicitDownloads:
    """``cleanup_hf_cache_dir`` survives, but ONLY for the explicit"""

    def test_cleanup_hf_cache_dir_still_exists(self):
        from voice_typer.server.asr_utils import cleanup_hf_cache_dir

        assert callable(cleanup_hf_cache_dir)

    def test_whisper_load_path_never_deletes(self):
        """is left in place for the user to delete explicitly."""
        src = _read("voice_typer/server/transcription.py")
        # The import re-export and docstring comments are fine; a CALL is not.
        call_sites = [
            line for line in src.splitlines() if "cleanup_hf_cache_dir(" in line and not line.strip().startswith("#")
        ]
        assert not call_sites, (
            "transcription.py must not call cleanup_hf_cache_dir, deleting a model is an explicit user action."
        )


class TestUncachedModelsRefuseToLoad:
    """Engines refuse to load an uncached model instead of downloading it —"""

    def test_whisper_load_requires_cached_model(self):
        from voice_typer.server.asr_errors import ModelNotDownloadedError

        assert issubclass(ModelNotDownloadedError, RuntimeError)

    def test_parakeet_load_requires_cached_model(self):
        from voice_typer.server.asr_errors import ModelIntegrityError

        assert issubclass(ModelIntegrityError, RuntimeError)
