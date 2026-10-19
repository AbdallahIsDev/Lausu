"""Startup log quality: INFO lines are self-evident and name their process."""

from __future__ import annotations

import contextlib
import logging
import os
import re
import sys
import threading
from types import SimpleNamespace

import voice_typer.server.nvidia_dll_paths as nv
from voice_typer.server.prewarm import cache_probe

_DURATION_RE = re.compile(r" \d+(m \d+)?\.\ds$")


class TestProcessTag:
    def test_main_process_tag(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "voice_typer.worker", raising=False)
        assert nv._process_tag() == "main"

    def test_worker_process_tag(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "voice_typer.worker", SimpleNamespace())
        assert nv._process_tag() == "worker"


class TestMainBannerNamesProcess:
    def test_banner_carries_process_main(self, tmp_path, monkeypatch):
        from voice_typer.server import logging_setup

        cfg = tmp_path / "cfg"
        monkeypatch.setattr(logging_setup, "_config_dir", lambda: cfg)
        monkeypatch.setattr(logging_setup, "_migrate_from_legacy", lambda: None)
        for var in ("VOICE_TYPER_DEBUG", "VOICE_TYPER_QUIET", "VOICE_TYPER_LOG_JSON", "VOICE_TYPER_SESSION_ID"):
            monkeypatch.delenv(var, raising=False)
        logging_setup._setup_logging()
        logging_setup._emit_startup_banner()
        for h in logging.getLogger("voice_typer").handlers:
            with contextlib.suppress(Exception):
                h.flush()
        banner = (cfg / "logs" / "lausu.log").read_text(encoding="utf-8")
        assert "[STARTUP] logging initialized:" in banner
        assert "process=main" in banner


class TestCudaDllLine:
    def test_line_names_process_purpose_and_duration(self, tmp_path, caplog, monkeypatch):
        monkeypatch.delitem(sys.modules, "voice_typer.worker", raising=False)
        # The DLL scan is Windows-loader bookkeeping, so ``_configure_locked``
        # returns early off Windows and the INFO line never exists. Pin the
        # Windows branch instead of skipping: the scan below is pure
        # os/site code, so it exercises identically on every CI leg.
        monkeypatch.setattr(nv, "is_windows", lambda: True)
        pkgroot = tmp_path / "Lib" / "site-packages"
        bindir = pkgroot / "nvidia" / "cublas" / "bin"
        bindir.mkdir(parents=True)
        (bindir / "fake.dll").write_bytes(b"x")
        monkeypatch.setattr(nv.site, "getsitepackages", lambda: [str(pkgroot)])
        monkeypatch.setattr(nv.site, "getusersitepackages", lambda: "")
        monkeypatch.setattr(nv.sys, "prefix", str(tmp_path))
        monkeypatch.setattr(nv.sys, "base_prefix", str(tmp_path))
        old_path = os.environ.get("PATH", "")
        mgr = nv._NvidiaDllPathManager(
            state_dict={
                "_nvidia_dll_path_handles": [],
                "_nvidia_dll_paths_configured": False,
                "_nvidia_config_lock": threading.Lock(),
            }
        )
        try:
            with caplog.at_level(logging.INFO, logger="voice_typer.server.nvidia_dll_paths"):
                mgr.configure()
        finally:
            mgr.free_handles()
            os.environ["PATH"] = old_path
        lines = [r.getMessage() for r in caplog.records if "[CUDA-DLL]" in r.getMessage()]
        assert lines, "expected a [CUDA-DLL] INFO line"
        msg = lines[-1]
        assert "main process" in msg
        assert "GPU transcription" in msg
        assert _DURATION_RE.search(msg), f"missing duration suffix: {msg!r}"


class TestPrewarmWording:
    def test_file_warmed_rollup_states_purpose(self, caplog, monkeypatch):
        monkeypatch.setattr(cache_probe, "_WORKER_WARM_PACKAGES", ("fakepkg",))
        monkeypatch.setattr(cache_probe, "_warm_package_files", lambda pkg: 1024 * 1024)
        monkeypatch.setattr(cache_probe, "_active_model_cache_dirs", lambda: [])
        monkeypatch.setattr(cache_probe, "_warm_model_weights", lambda dirs: 0)
        with caplog.at_level(logging.INFO, logger="voice_typer.server.prewarm"):
            cache_probe._warm_imports()
        matching = [r.getMessage() for r in caplog.records if "file-warmed" in r.getMessage()]
        assert len(matching) == 1
        assert "OS cache" in matching[0]
        assert _DURATION_RE.search(matching[0])

    def test_warm_imports_complete_states_purpose(self, caplog, monkeypatch):
        monkeypatch.setattr(cache_probe, "_WORKER_WARM_PACKAGES", ("fakepkg",))
        monkeypatch.setattr(cache_probe, "_warm_package_files", lambda pkg: 1024 * 1024)
        with caplog.at_level(logging.INFO, logger="voice_typer.server.prewarm"):
            cache_probe._warm_imports()
        matching = [r.getMessage() for r in caplog.records if "worker warm-imports complete" in r.getMessage()]
        assert matching
        assert "pre-read" in matching[-1]
        assert _DURATION_RE.search(matching[-1])


class TestPackWording:
    def test_missing_pack_line_states_next_step(self, caplog, monkeypatch):
        from voice_typer.server import installer_state, startup_launch_checks as checks
        from voice_typer.server.service import offline_pack, update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda: None)
        monkeypatch.setattr(offline_pack, "_publish_event", lambda *a, **k: None)
        monkeypatch.setattr(offline_pack, "_default_offline_pack_root", lambda: "/none")
        monkeypatch.setattr(
            installer_state,
            "load_installer_state",
            lambda: SimpleNamespace(pack_bundled=False, include_offline_engine_pack=False),
        )
        with caplog.at_level(logging.INFO, logger="voice_typer.server.startup_tasks"):
            checks.check_offline_pack_on_launch(SimpleNamespace(config=None))
        pack_lines = [r.getMessage() for r in caplog.records if "[PACK]" in r.getMessage()]
        assert any("not installed" in m and "background" in m for m in pack_lines), pack_lines


class TestUrlAllowlistWording:
    def test_extension_line_states_trust_purpose(self, caplog):
        from voice_typer.server.security.url_allowlist import _user_extensions, extend_url_allowlist

        try:
            with caplog.at_level("INFO", logger="voice_typer.server.security.url_allowlist"):
                extend_url_allowlist(["wording-probe.example.com"], caller="probe-caller")
            joined = " ".join(r.message for r in caplog.records)
            assert "[URL-Allowlist]" in joined
            assert "wording-probe.example.com" in joined
            assert "probe-caller" in joined
            assert "trusted" in joined
        finally:
            _user_extensions.discard("wording-probe.example.com")
