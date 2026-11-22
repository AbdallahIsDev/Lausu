"""End-to-end stop-time destination tests for Gemini (DictationPipeline) and Anthropic (stt-bridge)."""

from __future__ import annotations

import contextlib
import ctypes
import json
import time
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from tools.internal_plugins.anthropic_stt import plugin as anthropic_plugin
from voice_typer.server import clipboard as clip_mod, event_bus
from voice_typer.server.clipboard import ClipboardManager
from voice_typer.server.clipboard_target_safety import caret_text, targets
from voice_typer.server.cloud_engines import CloudEngine

from tests.fixtures.app_helpers import join_model_load_thread, make_sine, make_voice_typer_app
from tests.fixtures.clipboard_helpers import make_clipboard_manager
from tests.fixtures.wait_helpers import wait_for_busy_clear


@dataclass
class _FakeWindow:
    hwnd: int
    pid: int
    process_name: str
    caret: str | None


class _FakeDesktopEnv:
    """Stateful fake Win32 desktop with live focus, caret, clipboard, and SendInput logs."""

    def __init__(self, windows: dict[int, _FakeWindow], initial_hwnd: int) -> None:
        self.windows = windows
        self.focus_hwnd = initial_hwnd
        self.clipboard = {"text": "", "seq": 10}
        self.sendinputs: list[tuple[int, int]] = []
        self.shift_inserts: list[int] = []
        self.set_foreground_calls: list[object] = []

    def switch_to(self, hwnd: int) -> None:
        self.focus_hwnd = hwnd

    def current(self) -> _FakeWindow | None:
        return self.windows.get(self.focus_hwnd)


def _install_fake_desktop(
    monkeypatch: pytest.MonkeyPatch,
    env: _FakeDesktopEnv,
) -> dict[str, MagicMock]:
    mock_user32 = MagicMock()
    mock_kernel32 = MagicMock()
    mock_advapi32 = MagicMock()
    mock_windll = MagicMock()
    mock_windll.user32 = mock_user32
    mock_windll.kernel32 = mock_kernel32
    mock_windll.advapi32 = mock_advapi32

    proc_name_bufs: dict[int, str] = {}

    def _get_foreground_window() -> int:
        return env.focus_hwnd

    def _get_thread_pid(hwnd: int, byref_obj: object) -> int:
        win = env.windows.get(hwnd)
        byref_obj._obj.value = win.pid if win is not None else 0  # type: ignore[attr-defined]
        return 1

    def _open_process(_access: int, _inherit: bool, pid: int) -> int:
        for win in env.windows.values():
            if win.pid == pid:
                proc_name_bufs[pid] = f"C:\\Apps\\{win.process_name}"
                return pid
        return 0

    def _query_full_name(handle: int, _flags: int, buf: object, _size_ref: object) -> int:
        path = proc_name_bufs.get(handle)
        if not path:
            return 0
        buf.value = path  # type: ignore[attr-defined]
        return 1

    def _send_input(count: int, _ptr: object, _size: int) -> int:
        env.sendinputs.append((env.focus_hwnd, count))
        return count

    def _set_foreground(hwnd: object) -> int:
        env.set_foreground_calls.append(hwnd)
        return 1

    def _make_unicode_buf(_size: int) -> MagicMock:
        b = MagicMock()
        b.value = "Edit"
        return b

    mock_user32.GetForegroundWindow.side_effect = _get_foreground_window
    mock_user32.GetWindowThreadProcessId.side_effect = _get_thread_pid
    mock_user32.SendInput.side_effect = _send_input
    mock_user32.SetForegroundWindow.side_effect = _set_foreground
    mock_kernel32.OpenProcess.side_effect = _open_process
    mock_kernel32.QueryFullProcessImageNameW.side_effect = _query_full_name
    mock_kernel32.CloseHandle.return_value = 1
    mock_user32.GetClassNameW.return_value = 0

    def _copy_to_clipboard(text: str) -> None:
        env.clipboard["text"] = text
        env.clipboard["seq"] += 1

    def _paste_from_clipboard() -> str:
        return str(env.clipboard["text"])

    monkeypatch.setattr(clip_mod, "is_windows", lambda: True)
    monkeypatch.setattr(clip_mod, "is_macos", lambda: False)
    monkeypatch.setattr(clip_mod, "is_linux", lambda: False)
    monkeypatch.setattr(clip_mod, "_Controller", object())
    monkeypatch.setattr(clip_mod, "_Key", MagicMock(ctrl="ctrl", shift="shift", alt="alt", cmd="cmd", insert="insert"))
    monkeypatch.setattr(clip_mod, "_copy_to_clipboard", _copy_to_clipboard)
    monkeypatch.setattr(clip_mod, "_paste_from_clipboard", _paste_from_clipboard)
    monkeypatch.setattr(clip_mod, "_win32_empty_clipboard", lambda: None)
    monkeypatch.setattr(clip_mod, "_win32_exclude_clipboard_from_monitoring", lambda: None)
    monkeypatch.setattr(clip_mod.Win32Clipboard, "get_sequence_number", staticmethod(lambda: env.clipboard["seq"]))
    monkeypatch.setattr(ClipboardManager, "_is_safe_paste_target", staticmethod(lambda: True))
    monkeypatch.setattr(ClipboardManager, "_check_ime_composition", lambda self: True)
    monkeypatch.setattr(
        caret_text,
        "_char_before_caret",
        lambda: env.current().caret if env.current() is not None else None,
    )
    monkeypatch.setattr(ctypes, "windll", mock_windll, raising=False)
    monkeypatch.setattr(ctypes, "create_unicode_buffer", _make_unicode_buf)

    return {"user32": mock_user32, "kernel32": mock_kernel32}


def _make_gemini_http_response(text: str):
    payload = json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]}).encode("utf-8")

    class _Resp:
        status = 200
        fp = None

        def __init__(self) -> None:
            self._done = False

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, _size: int = -1) -> bytes:
            if self._done:
                return b""
            self._done = True
            return payload

    return _Resp()


def _build_configured_app(tmp_config_dir, monkeypatch: pytest.MonkeyPatch, env: _FakeDesktopEnv):
    app = make_voice_typer_app(tmp_config_dir, monkeypatch)
    (tmp_config_dir / "db").mkdir(parents=True, exist_ok=True)
    app.config.paste_on_stop = True
    app.config.clipboard_save_restore = False
    app.config.text_cleanup_enabled = False
    app.config.vocabulary_enabled = False
    app.config.auto_punctuation = False
    app.config.llm_polish = False
    app.config.ai_enhancement_enabled = False
    app.config.vocabulary_automation_enabled = False
    app.config.history_enabled = True
    app.config.crash_recovery_enabled = False
    app.config.auto_capitalize = True

    cm = make_clipboard_manager()
    cm._PASTE_RATE_LIMIT = 0.0
    cm._last_paste_time = 0.0
    app.clipboard = cm

    audio = make_sine(440.0, 0.8, sr=16000, amp=0.3)
    app.recorder = MagicMock()
    app.recorder.recording = True
    app.recorder._dropped_ring_chunks = 0
    app.recorder.last_rms = 0.2
    app.recorder._last_audio_stats = (0.2, 0.3, 0.0)

    def _stop_rec():
        app.recorder.recording = False
        return audio

    app.recorder.stop = MagicMock(side_effect=_stop_rec)
    app.tray = MagicMock()
    app._waveform_bubble = MagicMock()
    app._restore_volume = MagicMock()
    app._duck_volume = MagicMock()
    app._finalize_audio_quality_report = MagicMock()
    return app


def _close_app(app) -> None:
    with contextlib.suppress(Exception):
        if app.history_db is not None:
            app.history_db.close()
    with contextlib.suppress(Exception):
        app.tray._cancel_elapsed_timer()
    join_model_load_thread(app)


class TestStopTimeDestinationGeminiPath:
    """T5 + T6 over RecordingController -> RecordingLifecycle -> DictationPipeline -> Gemini CloudEngine."""

    def test_switch_a_to_b_to_c_pastes_into_stop_window_c_with_c_separator(
        self, tmp_config_dir, monkeypatch, accept_mock_http_peer
    ):
        windows = {
            0x1001: _FakeWindow(0x1001, 101, "app_a.exe", ""),
            0x2002: _FakeWindow(0x2002, 202, "app_b.exe", "trailing space "),
            0x3003: _FakeWindow(0x3003, 303, "notepad.exe", "existing sentence"),
        }
        env = _FakeDesktopEnv(windows, initial_hwnd=0x1001)
        _install_fake_desktop(monkeypatch, env)

        app = _build_configured_app(tmp_config_dir, monkeypatch, env)
        try:
            engine = CloudEngine(provider="gemini", api_key="test-key", consent_given=True)
            app.models.transcriber = engine
            app.models.active_transcriber = MagicMock(return_value=engine)

            def _fake_open(req, timeout=None):
                # Keep C focused; return raw text with whitespace around it.
                return _make_gemini_http_response("  Dictated text  ")

            monkeypatch.setattr("voice_typer.server.cloud_engines.assert_url_allowed", lambda *a, **kw: None)
            monkeypatch.setattr("voice_typer.server.cloud_engines._opener.open", _fake_open)

            # Dictation started while in A, then user moved A -> B -> C before pressing stop.
            env.switch_to(0x2002)
            env.switch_to(0x3003)

            app._stop_dictation()
            wait_for_busy_clear(app)

            assert env.clipboard["text"] == " dictated text"
            assert env.sendinputs == [(0x3003, 4)]
            assert env.set_foreground_calls == []
            assert app.history_db.get_latest_text() == "Dictated text"
        finally:
            _close_app(app)

    def test_switch_from_editor_to_terminal_before_stop_uses_stop_terminal_branch(
        self, tmp_config_dir, monkeypatch, accept_mock_http_peer
    ):
        windows = {
            0x1001: _FakeWindow(0x1001, 101, "notepad.exe", ""),
            0x4004: _FakeWindow(0x4004, 404, "cmd.exe", "git "),
        }
        env = _FakeDesktopEnv(windows, initial_hwnd=0x1001)
        _install_fake_desktop(monkeypatch, env)

        app = _build_configured_app(tmp_config_dir, monkeypatch, env)
        try:
            engine = CloudEngine(provider="gemini", api_key="test-key", consent_given=True)
            app.models.transcriber = engine
            app.models.active_transcriber = MagicMock(return_value=engine)

            monkeypatch.setattr("voice_typer.server.cloud_engines.assert_url_allowed", lambda *a, **kw: None)
            monkeypatch.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                lambda req, timeout=None: _make_gemini_http_response("Status"),
            )
            with patch.object(
                ClipboardManager,
                "_send_shift_insert_win32",
                side_effect=lambda *a, **kw: (env.shift_inserts.append(env.focus_hwnd), True)[1],
            ):
                # User switched to terminal before stopping.
                app.clipboard._keyboard = None
                env.switch_to(0x4004)
                app._stop_dictation()
                wait_for_busy_clear(app)

            assert env.clipboard["text"] == "status"
            assert env.shift_inserts == [0x4004]
            assert env.sendinputs == []
            assert env.set_foreground_calls == []
        finally:
            _close_app(app)

    def test_switch_after_stop_during_gemini_processing_aborts_paste_safely(
        self, tmp_config_dir, monkeypatch, accept_mock_http_peer
    ):
        from voice_typer.server.i18n import t as _i18n_t
        from voice_typer.server.tray_types import AppState

        windows = {
            0x1001: _FakeWindow(0x1001, 101, "app_a.exe", "prefix"),
            0x2002: _FakeWindow(0x2002, 202, "app_b.exe", ""),
        }
        env = _FakeDesktopEnv(windows, initial_hwnd=0x1001)
        _install_fake_desktop(monkeypatch, env)

        app = _build_configured_app(tmp_config_dir, monkeypatch, env)
        try:
            engine = CloudEngine(provider="gemini", api_key="test-key", consent_given=True)
            app.models.transcriber = engine
            app.models.active_transcriber = MagicMock(return_value=engine)

            def _slow_gemini(req, timeout=None):
                # User switches focus from A to B while Gemini is transcribing after stop!
                env.switch_to(0x2002)
                return _make_gemini_http_response("Dictated words")

            monkeypatch.setattr("voice_typer.server.cloud_engines.assert_url_allowed", lambda *a, **kw: None)
            monkeypatch.setattr("voice_typer.server.cloud_engines._opener.open", _slow_gemini)

            # Stop while focused in A (0x1001).
            app._stop_dictation()
            wait_for_busy_clear(app)

            # Paste must NOT go to B and must NOT refocus A; text remains on clipboard.
            assert env.sendinputs == []
            assert env.set_foreground_calls == []
            assert env.clipboard["text"] == " dictated words"
            assert app.history_db.get_latest_text() == "Dictated words"
            expected_status = _i18n_t("state.dictation_pipeline.done_in_clipboard", count=len("Dictated words"))
            assert any(
                call.args == (AppState.IDLE, expected_status)
                for call in app.tray.set_state.call_args_list
            )
        finally:
            _close_app(app)

    def test_switch_after_stop_with_save_restore_on_keeps_dictation_on_clipboard(
        self, tmp_config_dir, monkeypatch, accept_mock_http_peer
    ):
        from voice_typer.server.clipboard_snapshot import ClipboardSnapshot

        windows = {
            0x1001: _FakeWindow(0x1001, 101, "app_a.exe", "prefix"),
            0x2002: _FakeWindow(0x2002, 202, "app_b.exe", ""),
        }
        env = _FakeDesktopEnv(windows, initial_hwnd=0x1001)
        env.clipboard["text"] = "prior clipboard content"
        _install_fake_desktop(monkeypatch, env)

        deferred_events: list[dict] = []
        orig_publish = event_bus.publish
        def _record_publish(evt):
            if evt.get("type") == "paste_deferred":
                deferred_events.append(evt)
            return orig_publish(evt)

        monkeypatch.setattr(event_bus, "publish", _record_publish)

        saved_snap = ClipboardSnapshot(platform="win32", items=[], captured_at=0.0)
        monkeypatch.setattr(ClipboardSnapshot, "capture", classmethod(lambda cls: saved_snap))
        restored: list[bool] = []
        monkeypatch.setattr(saved_snap, "restore", lambda: restored.append(True))

        app = _build_configured_app(tmp_config_dir, monkeypatch, env)
        app.config.clipboard_save_restore = True
        app.clipboard.refresh_config(app.config)
        try:
            engine = CloudEngine(provider="gemini", api_key="test-key", consent_given=True)
            app.models.transcriber = engine
            app.models.active_transcriber = MagicMock(return_value=engine)

            def _slow_gemini(req, timeout=None):
                env.switch_to(0x2002)
                return _make_gemini_http_response("Dictated words")

            monkeypatch.setattr("voice_typer.server.cloud_engines.assert_url_allowed", lambda *a, **kw: None)
            monkeypatch.setattr("voice_typer.server.cloud_engines._opener.open", _slow_gemini)

            app._stop_dictation()
            wait_for_busy_clear(app)

            assert env.sendinputs == []
            assert env.set_foreground_calls == []
            assert restored == []
            assert env.clipboard["text"] == " dictated words"
            assert any(e.get("type") == "paste_deferred" for e in deferred_events)
        finally:
            _close_app(app)

    def test_back_to_back_sessions_across_windows_leave_no_stale_target_state(
        self, tmp_config_dir, monkeypatch, accept_mock_http_peer
    ):
        windows = {
            0x1001: _FakeWindow(0x1001, 101, "app_a.exe", "first"),
            0x2002: _FakeWindow(0x2002, 202, "app_b.exe", ""),
        }
        env = _FakeDesktopEnv(windows, initial_hwnd=0x1001)
        _install_fake_desktop(monkeypatch, env)

        app = _build_configured_app(tmp_config_dir, monkeypatch, env)
        try:
            responses = iter(["One", "two"])
            engine = CloudEngine(provider="gemini", api_key="test-key", consent_given=True)
            app.models.transcriber = engine
            app.models.active_transcriber = MagicMock(return_value=engine)

            monkeypatch.setattr("voice_typer.server.cloud_engines.assert_url_allowed", lambda *a, **kw: None)
            monkeypatch.setattr(
                "voice_typer.server.cloud_engines._opener.open",
                lambda req, timeout=None: _make_gemini_http_response(next(responses)),
            )

            # Session 1 stops & pastes into A ("first" -> " one").
            targets._set_focused_atspi_cache("stale-role-before-session-1")
            app._stop_dictation()
            wait_for_busy_clear(app)
            assert targets._LAST_FOCUSED_ROLE is None
            assert env.clipboard["text"] == " one"
            assert env.sendinputs == [(0x1001, 4)]

            # Immediate Session 2 in B (<50ms later, no restart) with an empty field -> "Two".
            app.recorder.recording = True
            targets._set_focused_atspi_cache("stale-role-from-app-a")
            env.switch_to(0x2002)
            app._stop_dictation()
            wait_for_busy_clear(app)

            assert targets._LAST_FOCUSED_ROLE is None
            assert env.clipboard["text"] == "Two"
            assert env.sendinputs == [(0x1001, 4), (0x2002, 4)]
            assert env.set_foreground_calls == []
        finally:
            _close_app(app)


class TestStopTimeDestinationAnthropicBridgePath:
    """T5 + T6 over Anthropic stt-bridge PluginSession -> deliver_transcription -> real ClipboardManager."""

    def _make_plugin_app(self):
        cm = make_clipboard_manager()
        cm._PASTE_RATE_LIMIT = 0.0
        cm._last_paste_time = 0.0
        app = SimpleNamespace(
            config=SimpleNamespace(device="cpu", language="en", auto_capitalize=True),
            clipboard=cm,
            history_db=MagicMock(),
            _last_transcription=None,
            _duck_volume=lambda: None,
            _restore_volume=lambda: None,
        )
        app.history_db.add_transcription.return_value = 1
        return app

    def test_switch_a_to_b_to_c_before_stop_delivers_to_c_with_c_context(self, monkeypatch):
        windows = {
            0x1001: _FakeWindow(0x1001, 101, "app_a.exe", ""),
            0x2002: _FakeWindow(0x2002, 202, "app_b.exe", "space "),
            0x3003: _FakeWindow(0x3003, 303, "notepad.exe", "previous text"),
        }
        env = _FakeDesktopEnv(windows, initial_hwnd=0x1001)
        _install_fake_desktop(monkeypatch, env)

        app = self._make_plugin_app()
        session = anthropic_plugin.PluginSession(app)
        session._active = True
        session._t0 = time.monotonic() - 1.0
        session._cycle = 1
        monkeypatch.setattr(session, "_stop_meter", lambda: None)
        monkeypatch.setattr(session, "_publish_state", lambda _s: None)
        monkeypatch.setattr(session, "_session_events", lambda *, start: None)
        monkeypatch.setattr(session, "_clear_prompt_box", lambda: None)
        monkeypatch.setattr(session, "_post", lambda path, timeout=0.0: {"text": "  Dictated  ", "duration_s": 1.0})

        # User starts in A, switches to B, switches to C, then stops in C.
        env.switch_to(0x2002)
        env.switch_to(0x3003)

        assert session.stop() is True

        assert env.clipboard["text"] == " dictated"
        assert env.sendinputs == [(0x3003, 4)]
        assert env.set_foreground_calls == []
        assert app.history_db.add_transcription.call_args.args[0] == "Dictated"

    def test_switch_after_stop_during_anthropic_bridge_wait_aborts_paste_safely(self, monkeypatch):
        windows = {
            0x1001: _FakeWindow(0x1001, 101, "app_a.exe", "already"),
            0x2002: _FakeWindow(0x2002, 202, "app_b.exe", ""),
        }
        env = _FakeDesktopEnv(windows, initial_hwnd=0x1001)
        _install_fake_desktop(monkeypatch, env)

        app = self._make_plugin_app()
        session = anthropic_plugin.PluginSession(app)
        session._active = True
        session._t0 = time.monotonic() - 1.0
        session._cycle = 2
        monkeypatch.setattr(session, "_stop_meter", lambda: None)
        monkeypatch.setattr(session, "_publish_state", lambda _s: None)
        monkeypatch.setattr(session, "_session_events", lambda *, start: None)
        monkeypatch.setattr(session, "_clear_prompt_box", lambda: None)

        def _slow_bridge_stop(path: str, timeout: float = 0.0) -> dict:
            assert path == "/stop"
            # User switches to App B while waiting for Claude web tab to finish transcribing.
            env.switch_to(0x2002)
            return {"text": "Dictated", "duration_s": 1.0}

        monkeypatch.setattr(session, "_post", _slow_bridge_stop)

        # User presses stop while focused in A (0x1001).
        assert session.stop() is True

        # Paste into B must be blocked, A must NOT be refocused, clipboard keeps formatted text.
        assert env.sendinputs == []
        assert env.set_foreground_calls == []
        assert env.clipboard["text"] == " dictated"
        assert app.history_db.add_transcription.call_args.args[0] == "Dictated"
