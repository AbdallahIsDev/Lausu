"""XV-1 / XV-2 / XV-5 service.py fix regression tests."""

from __future__ import annotations

import inspect
import time
from pathlib import Path
from unittest.mock import MagicMock


def _make_service(tmp_config_dir):
    """Build a ``LausuService`` against a minimal fake app."""
    from voice_typer.server import service as svc_mod

    class FakeApp:
        config = type("FakeConfig", (), {})()
        _microphones: list = []
        tray = MagicMock()

    return svc_mod.LausuService(FakeApp())


# XV-1 deps-probe tests removed 2026-08-15: ``_check_qwen_deps`` /


class TestDownloadPollScopedToModelDir:
    """XV-2: ``download_model``'s progress-polling loop walks ONLY the"""

    def test_poll_uses_per_repo_subdir_construction(self):
        """Source guard: the polling loop must construct"""
        from voice_typer.server.service._download_helpers import poll_download_progress

        src = inspect.getsource(poll_download_progress)
        assert 'model_dir = cache_dir / f"models--{repo_id.replace' in src, (
            "XV-2: the progress poll must construct the per-repo subdir "
            "via cache_dir / f\"models--{repo_id.replace('/', '--')}\" "
            "before walking it."
        )
        assert 'model_dir.rglob("*")' in src, (
            "XV-2: progress polling must walk model_dir (the per-repo subdir), not the whole cache_dir."
        )
        # The old wide-scan form must NOT appear in the polling block.
        assert 'cache_dir.rglob("*")' not in src, (
            "XV-2 regression: download_model still walks the entire cache_dir tree via cache_dir.rglob('*')."
        )

    def test_poll_does_not_stat_unrelated_repos(self, tmp_config_dir, monkeypatch):
        """The GGUF progress poll walks only the target repo's cache dir."""
        import threading as _threading

        from voice_typer.server.service._download_helpers import poll_download_progress

        cache_root = tmp_config_dir / "huggingface" / "hub"
        other_repo = cache_root / "models--unrelated--other" / "snapshots" / "rev1"
        other_repo.mkdir(parents=True)
        (other_repo / "model.safetensors").write_bytes(b"\x00" * 4096)

        target_repo = cache_root / "models--org--target" / "blobs"
        target_repo.mkdir(parents=True)
        (target_repo / "gguf-blob").write_bytes(b"\x01" * 8192)

        stat_paths: list[str] = []
        real_stat = Path.stat

        def spy_stat(self, *args, **kwargs):
            stat_paths.append(str(self))
            return real_stat(self, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", spy_stat)

        release = _threading.Event()
        transfer = _threading.Thread(target=release.wait, args=(0.2,), daemon=True)
        transfer.start()
        try:
            outcome, total = poll_download_progress(
                thread=transfer,
                target_bytes=1024 * 1024,
                target_mb=1,
                model_name="target-model",
                repo_id="org/target",
                cache_dir=cache_root,
                download_id="dlid",
                event_bus=MagicMock(),
                is_cancelled_fn=lambda _id: False,
            )
        finally:
            release.set()
            transfer.join(timeout=2.0)

        assert outcome == "complete"
        assert total >= 8192
        assert not any("models--unrelated--other" in p for p in stat_paths), (
            f"XV-2: the GGUF progress poll stat'd a file in an UNRELATED repo. Stats seen: {stat_paths[:5]}..."
        )
        assert any("models--org--target" in p for p in stat_paths), (
            "XV-2: expected the target repo's blob to be stat'd during the "
            f"progress poll. Stats seen: {stat_paths[:5]}..."
        )


class TestMicrophonesCacheEmptyList:
    """XV-5: ``_microphones_cache`` starts as ``None`` (not ``[]``) and"""

    def test_cache_initialised_to_none(self, tmp_config_dir):
        svc = _make_service(tmp_config_dir)
        assert svc._microphones_cache is None, (
            "XV-5: _microphones_cache must be initialised to None (not "
            "[]) so the truthiness check doesn't bypass the cache when "
            "PortAudio returns an empty list."
        )

    def test_refresh_uses_is_not_none_source(self):
        """Source guard: the truthiness check must be ``is not None``,"""
        from voice_typer.server.service import LausuService

        src = inspect.getsource(LausuService.refresh_microphones)
        assert "self._microphones_cache is not None" in src, (
            "XV-5: refresh_microphones must use 'is not None' (not bare "
            "truthiness) so an empty cached list is still served from cache."
        )
        code_lines = [line for line in src.splitlines() if line.lstrip() and not line.lstrip().startswith("#")]
        code_only = "\n".join(code_lines)
        assert "if self._microphones_cache and " not in code_only, (
            "XV-5 regression: refresh_microphones still uses bare-truthiness "
            "cache check, this skips the cache when PortAudio returns 0 mics."
        )

    def test_empty_list_served_from_cache(self, tmp_config_dir, monkeypatch):
        """When the cache holds an empty list (legitimate \"0 mics\"),"""
        svc = _make_service(tmp_config_dir)
        svc._microphones_cache = []
        svc._microphones_cache_ts = time.monotonic()

        call_count = {"n": 0}

        def fake_list_microphones():
            call_count["n"] += 1
            return [{"name": "should-not-be-returned", "index": 0}]

        monkeypatch.setattr(
            "voice_typer.server.server_platform.microphone_list.list_microphones",
            fake_list_microphones,
        )

        result = svc.refresh_microphones()
        assert result == [], (
            "XV-5: refresh_microphones must serve the cached empty list "
            "instead of re-querying PortAudio when the cache is empty."
        )
        assert call_count["n"] == 0, (
            "XV-5: list_microphones must NOT be called when the cache (even if empty) is fresh."
        )

    def test_non_empty_list_still_served_from_cache(self, tmp_config_dir, monkeypatch):
        """Sanity: a non-empty cache continues to be served (regression"""
        svc = _make_service(tmp_config_dir)
        cached_mics = [{"name": "USB Mic", "index": 0}]
        svc._microphones_cache = cached_mics
        svc._microphones_cache_ts = time.monotonic()

        call_count = {"n": 0}

        def fake_list_microphones():
            call_count["n"] += 1
            return []

        monkeypatch.setattr(
            "voice_typer.server.server_platform.microphone_list.list_microphones",
            fake_list_microphones,
        )

        result = svc.refresh_microphones()
        assert result == cached_mics
        assert call_count["n"] == 0

    def test_first_call_queries_portaudio(self, tmp_config_dir, monkeypatch):
        """When the cache is ``None`` (never queried), the first"""
        svc = _make_service(tmp_config_dir)
        assert svc._microphones_cache is None

        call_count = {"n": 0}
        real_mics = [{"name": "Built-in Mic", "index": 0}]

        def fake_list_microphones():
            call_count["n"] += 1
            return real_mics

        monkeypatch.setattr(
            "voice_typer.server.server_platform.microphone_list.list_microphones",
            fake_list_microphones,
        )

        result = svc.refresh_microphones()
        assert result == real_mics
        assert call_count["n"] == 1, (
            "XV-5: the first refresh_microphones call (cache is None) must query PortAudio exactly once."
        )
        assert svc._microphones_cache == real_mics
