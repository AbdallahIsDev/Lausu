"""Focused tests for the transcription.py refactors."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock


class TestNvidiaDllPathManagerIsolation:
    """The manager class lets tests construct a fresh instance with its"""

    def test_fresh_instance_has_empty_state(self):
        from voice_typer.server.transcription import _NvidiaDllPathManager

        mgr = _NvidiaDllPathManager(
            state_dict={
                "_nvidia_dll_path_handles": [],
                "_nvidia_dll_paths_configured": False,
                "_nvidia_config_lock": threading.Lock(),
            }
        )
        assert mgr.handles == []
        assert mgr.configured is False
        assert isinstance(mgr.lock, type(threading.Lock()))

    def test_free_handles_clears_list_and_calls_close(self):
        from voice_typer.server.transcription import _NvidiaDllPathManager

        mgr = _NvidiaDllPathManager(
            state_dict={
                "_nvidia_dll_path_handles": [],
                "_nvidia_dll_paths_configured": False,
                "_nvidia_config_lock": threading.Lock(),
            }
        )
        fake_handle = MagicMock()
        mgr.handles.append(fake_handle)
        mgr.free_handles()
        assert mgr.handles == []
        fake_handle.close.assert_called_once()

    def test_module_singleton_reflects_module_global_writes(self):
        """Production singleton reads/writes through ``globals()`` so"""
        import voice_typer.server.transcription as mod

        # Save and restore original state.
        orig_handles = mod._nvidia_dll_path_handles
        orig_configured = mod._nvidia_dll_paths_configured
        try:
            mod._nvidia_dll_path_handles = [MagicMock()]
            mod._nvidia_dll_paths_configured = True
            assert mod._nvidia_dll_paths.handles == mod._nvidia_dll_path_handles
            assert mod._nvidia_dll_paths.configured is True
            mod._nvidia_dll_paths.free_handles()
            assert mod._nvidia_dll_path_handles == []
        finally:
            mod._nvidia_dll_path_handles = orig_handles
            mod._nvidia_dll_paths_configured = orig_configured

    def test_module_level_functions_delegate_to_singleton(self):
        """singleton."""
        import voice_typer.server.transcription as mod

        orig_handles = mod._nvidia_dll_path_handles
        try:
            mod._nvidia_dll_path_handles = [MagicMock()]
            mod._free_nvidia_dll_path_handles()
            assert mod._nvidia_dll_path_handles == []
        finally:
            mod._nvidia_dll_path_handles = orig_handles






# ─── load-path cache gate (_probe_cache / _require_model_downloaded) ─




# Late import so the autouse fixture can install the mock first.
