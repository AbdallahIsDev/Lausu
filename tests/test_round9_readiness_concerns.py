"""Round 9 readiness concerns: real-entry proof for fake local layouts.

Fakes live only at OS/process boundaries (filesystem, env, worker port, OS
permission probe, browser process). The decision path is production code:
``local_asr_problem``, the shared app start entry, the hotkey callback and the
one notice publisher.
"""

from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from voice_typer.server import (
    dictation_notices,
    dictation_origin,
    event_bus,
    hotkey_dispatch,
    internal_plugin_hook,
    local_asr_readiness,
    permissions,
    tray as tray_module,
)
from voice_typer.server.app_dictation import AppDictation
from voice_typer.server.asr_errors import MicrophonePermissionDeniedError
from voice_typer.server.branding import APP_NAME
from voice_typer.server.dictation_provider import for_config
from voice_typer.server.i18n import t
from voice_typer.server.recording_lifecycle import RecordingLifecycle

REPO_ROOT = Path(__file__).resolve().parent.parent

_NOTICE_KEY = "notify.model_manager.no_model_selected"


def _config(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "active_plugin": "",
        "asr_backend": "parakeet",
        "asr_provider": "",
        "cloud_provider": "",
        "cloud_model": "gpt-4o-transcribe",
        "model_size": "parakeet",
        "developer_mode": False,
        "model_idle_unload_minutes": 0,
        "hotkey": "<caps_lock>",
        "language": "",
        "recording_mode": "toggle",
        "tts_enabled": False,
        "translation_enabled": False,
        "voice_biometric_consent": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _real_config() -> object:
    from voice_typer.server.config import Config

    config = Config()
    config.model_size = "parakeet"
    config.asr_backend = "parakeet"
    config.asr_provider = ""
    config.active_plugin = ""
    config.voice_biometric_consent = True
    return config


def _runtime_file(tmp_path: Path, label: str = "runtime") -> Path:
    folder = tmp_path / label
    folder.mkdir(parents=True, exist_ok=True)
    dll = folder / local_asr_readiness.LIBRARY_BASENAME
    dll.write_bytes(b"fake native runtime")
    return dll


def _set_layout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    layout: str,
    runtime: Path,
    worker_port: int | None = None,
) -> None:
    from voice_typer.server import worker_client
    from voice_typer.server.media_ingest import ffmpeg_binaries
    from voice_typer.server.service import update_check

    present = layout in ("slim-pack", "pack-alt-runtime")
    monkeypatch.setattr(
        update_check,
        "_local_offline_pack_version",
        lambda root=None: "1.0.0" if present else None,
    )
    monkeypatch.setattr(ffmpeg_binaries, "is_frozen_build", lambda *a, **k: layout != "dev-source")
    monkeypatch.setattr(ffmpeg_binaries, "bundled_bin_dir", lambda *a, **k: tmp_path)
    if layout == "full-bundled":
        (tmp_path / "lausu-worker.exe").write_bytes(b"fake worker")
    monkeypatch.setattr(
        worker_client,
        "get_shared_client",
        lambda: SimpleNamespace(port=worker_port),
    )
    monkeypatch.setenv(local_asr_readiness.ENV_TRANSCRIBE_LIBRARY, str(runtime))


class TestA1NoFalseRefusal:
    @pytest.mark.parametrize("layout", ["dev-source", "slim-pack", "full-bundled", "pack-alt-runtime"])
    def test_working_local_layout_is_never_refused(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, layout: str
    ) -> None:
        from voice_typer.server import tray_models

        monkeypatch.setattr(tray_models, "is_active_model_downloaded", lambda _config: True)
        runtime = _runtime_file(tmp_path, "alt-runtime" if layout == "pack-alt-runtime" else "runtime")
        _set_layout(
            monkeypatch,
            tmp_path,
            layout=layout,
            runtime=runtime,
            worker_port=9231 if layout == "dev-source" else None,
        )

        assert local_asr_readiness.readiness_probe is local_asr_readiness.local_asr_problem
        problem = local_asr_readiness.local_asr_problem(_real_config())
        assert problem is None, f"{layout} must not be refused ({problem})"
        # Loader and probe resolve the same directory through the one resolver.
        from voice_typer.worker.asr_runner import runner

        assert local_asr_readiness.resolve_native_runtime_dir() == runtime.parent
        assert runner.library_dir() == runtime.parent

    def test_genuine_missing_pack_and_runtime_are_still_refused(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from voice_typer.server import tray_models

        monkeypatch.setattr(tray_models, "is_active_model_downloaded", lambda _config: True)
        runtime = _runtime_file(tmp_path)
        _set_layout(monkeypatch, tmp_path, layout="slim-pack", runtime=runtime)
        monkeypatch.setattr(
            "voice_typer.server.service.update_check._local_offline_pack_version", lambda root=None: None
        )
        assert local_asr_readiness.local_asr_problem(_real_config()) == "offline_pack_missing"

        _set_layout(monkeypatch, tmp_path, layout="slim-pack", runtime=runtime)
        monkeypatch.setenv(local_asr_readiness.ENV_TRANSCRIBE_LIBRARY, str(tmp_path / "absent.dll"))
        assert local_asr_readiness.local_asr_problem(_real_config()) == "local_runtime_missing"

    def test_probe_errors_fail_open(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from voice_typer.server import tray_models

        monkeypatch.setattr(tray_models, "is_active_model_downloaded", lambda _config: True)
        runtime = _runtime_file(tmp_path)

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("pack root unreadable")

        monkeypatch.setattr("voice_typer.server.service.update_check._local_offline_pack_version", _boom)
        monkeypatch.setenv(local_asr_readiness.ENV_TRANSCRIBE_LIBRARY, str(runtime))
        assert local_asr_readiness.local_asr_problem(_real_config()) is None

    def test_sidecar_never_imports_worker_runner_and_import_loads_no_dll(self) -> None:
        script = (
            "import ctypes, sys\n"
            "def _no_dll(*a, **k):\n"
            "    raise AssertionError('import loaded a DLL')\n"
            "ctypes.CDLL = _no_dll\n"
            "import voice_typer.server.local_asr_readiness as m\n"
            "assert m.resolve_native_runtime_dir is not None\n"
            "assert not [k for k in sys.modules if k.startswith('voice_typer.worker.asr_runner')]\n"
            "print('OK')\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "OK"

    def test_no_slim_core_ratchet_import_added(self) -> None:
        scripts = REPO_ROOT / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            import slim_core_ml_ratchet_check as ratchet
        finally:
            sys.path.pop(0)
        hits = ratchet.scan()
        assert not [h for h in hits if h["file"] == "voice_typer/server/local_asr_readiness.py"]

    def test_frozen_sidecar_include_lists_do_not_expose_the_worker_runner(self) -> None:
        nuitka = list((REPO_ROOT / "scripts" / "build").glob("build_sidecar_*.sh"))
        assert nuitka
        for script in nuitka:
            body = script.read_text(encoding="utf-8")
            assert "--include-package=voice_typer" in body
            assert "asr_runner.runner" not in body
        spec = (REPO_ROOT / "scripts" / "build" / "lausu.spec").read_text(encoding="utf-8")
        assert "voice_typer.worker.asr_runner.runner" not in spec

    def test_module_level_imports_stay_light(self) -> None:
        source = (REPO_ROOT / "voice_typer" / "server" / "local_asr_readiness.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module}
        assert "voice_typer.worker.asr_runner.runner" not in imported
        assert not any(isinstance(node, ast.ImportFrom) and node.module == "ctypes" for node in tree.body)


class _FakeTray:
    """Real ``TrayIcon.notify(title, message)`` shape, no GUI."""

    def __init__(self) -> None:
        self.notifications: list[tuple[str, str]] = []

    def notify(self, title: str, message: str) -> None:
        self.notifications.append((title, message))

    def set_state(self, *_args: object, **_kwargs: object) -> None:
        pass

    def notify_safety(self, title: str, message: str) -> None:
        self.notifications.append((title, message))


def _published(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(event_bus, "publish", lambda payload: captured.append(payload) or True)
    return captured


def _wired_app(config: SimpleNamespace) -> tuple[SimpleNamespace, SimpleNamespace, RecordingLifecycle]:
    app = SimpleNamespace(
        config=config,
        tray=_FakeTray(),
        _shutting_down=False,
        _cycle_counter=0,
        _cycle_id="",
        models=MagicMock(),
        recorder=MagicMock(),
        _busy_event=SimpleNamespace(is_set=lambda: True),
        _waveform_bubble=MagicMock(),
        _schedule_timer=MagicMock(),
        _cancel_pending_timers=MagicMock(),
    )
    from tests.fixtures.bubble_policy_fixture import attach_policy

    attach_policy(app._waveform_bubble, "show_on_record")
    app.recorder.recording = False
    app.models.active_transcriber.return_value = None
    app.models._model_load_thread = None
    lifecycle = RecordingLifecycle()
    controller = SimpleNamespace(_app=app, _toggle_lock=threading.RLock())
    app.recording = SimpleNamespace(toggle=lambda: lifecycle.toggle(controller))
    app.toggle_dictation = AppDictation.toggle_dictation.__get__(app, type(app))
    app._start_dictation = lambda: lifecycle.start(controller)
    return app, controller, lifecycle


class TestA3UnifiedNoticePath:
    def test_tray_notify_signature_is_two_args(self) -> None:
        signature = inspect.signature(tray_module.TrayIcon.notify)
        assert list(signature.parameters) == ["self", "title", "message"]

    def test_publish_notice_delivers_to_tray_and_event(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _published(monkeypatch)
        app = SimpleNamespace(tray=_FakeTray())

        dictation_notices.publish_notice(app, "plain message")

        assert app.tray.notifications == [(APP_NAME, "plain message")]
        assert captured[-1]["type"] == "notification"
        assert captured[-1]["data"]["message"] == "plain message"

    def test_hotkey_no_engine_path_delivers_the_same_notice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _published(monkeypatch)
        app = SimpleNamespace(config=_config(model_size="", asr_backend="", active_plugin=""), tray=_FakeTray())
        dispatcher = hotkey_dispatch.HotkeyDispatchMixin()
        dispatcher._app = app

        assert dispatcher._no_active_engine() is True

        assert app.tray.notifications == [(APP_NAME, t(_NOTICE_KEY))]
        assert captured[-1]["data"]["message"] == t(_NOTICE_KEY)

    def test_start_entry_no_engine_path_delivers_the_same_notice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _published(monkeypatch)
        app, _controller, _lifecycle = _wired_app(_config(model_size="", asr_backend=""))

        with dictation_origin.user_action("button"):
            app.toggle_dictation()

        assert app.tray.notifications == [(APP_NAME, t(_NOTICE_KEY))]
        assert captured[-1]["data"]["message"] == t(_NOTICE_KEY)
        assert app.recorder.start.called is False


class TestA2PermissionForNonLocalProviders:
    def test_cloud_denied_permission_refuses_at_the_real_start_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _published(monkeypatch)
        config = _config(asr_backend="cloud", cloud_provider="openai", model_size="")
        assert for_config(config).kind == "cloud"
        app, _controller, _lifecycle = _wired_app(config)

        def _denied() -> None:
            raise MicrophonePermissionDeniedError("denied by OS", state="denied")

        monkeypatch.setattr(permissions, "verify_microphone_accessible", _denied)
        with dictation_origin.user_action("hotkey"):
            app.toggle_dictation()

        assert app.recorder.start.called is False, "cloud must not open the mic when OS permission is denied"
        assert app.models.start_background_load.called is False, "no local model load for cloud"
        assert any(p.get("type") == "microphone_permission_revoked" for p in captured) or app.tray.notifications
        assert app._waveform_bubble.apply_visibility.call_args_list[-1].args[0] == "permission_revoked"

    def test_plugin_never_runs_the_local_permission_gate_or_mic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _published(monkeypatch)
        monkeypatch.setattr(internal_plugin_hook, "internal_surface_enabled", lambda _cfg: True)
        monkeypatch.setattr(internal_plugin_hook, "plugin_display_name", lambda app=None: "ChatGPT STT")
        config = _config(active_plugin="chatgpt_stt", developer_mode=True)
        assert for_config(config).kind == "plugin"
        app, _controller, _lifecycle = _wired_app(config)

        def _must_not_be_called() -> None:
            raise AssertionError("local mic permission gate is not the plugin's permission authority")

        monkeypatch.setattr(permissions, "verify_microphone_accessible", _must_not_be_called)
        with dictation_origin.user_action("hotkey"):
            app.toggle_dictation()

        assert app.recorder.start.called is False
        assert app.models.start_background_load.called is False
        assert any(p.get("type") == "notification" for p in captured)
        # The browser owns plugin dictation: its mic permission is handled by
        # the dedicated Chrome profile pre-grant and the extension's
        # micPermission readiness fact, not by the sidecar's local mic probe.


class TestA4ReadinessSeamCannotHideARealFailure:
    def test_no_production_module_rebinds_readiness_probe(self) -> None:
        offenders: list[str] = []
        for path in (REPO_ROOT / "voice_typer").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id == "readiness_probe":
                        if path.name == "local_asr_readiness.py" and node.lineno > 50:
                            continue
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
        assert offenders == []

    def test_real_path_refusal_guards_against_a_leaked_stub(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from voice_typer.server import tray_models

        captured = _published(monkeypatch)
        monkeypatch.setattr(tray_models, "is_active_model_downloaded", lambda _config: True)
        runtime = _runtime_file(tmp_path)
        _set_layout(monkeypatch, tmp_path, layout="slim-pack", runtime=runtime)
        monkeypatch.setattr(
            "voice_typer.server.service.update_check._local_offline_pack_version", lambda root=None: None
        )
        app, _controller, _lifecycle = _wired_app(_real_config())

        # A test that exercises the real path must see the real probe.
        assert local_asr_readiness.readiness_probe is local_asr_readiness.local_asr_problem
        with dictation_origin.user_action("button"):
            app.toggle_dictation()
        assert app._start_dictation is not None and app.recorder.start.called is False
        assert any(p.get("type") == "notification" and "Offline pack" in str(p["data"]["message"]) for p in captured)

        # Proof the identity guard matters: a leaked stub hides this failure.
        with monkeypatch.context() as ctx:
            ctx.setattr(local_asr_readiness, "readiness_probe", lambda _config: None)
            assert local_asr_readiness.readiness_probe is not local_asr_readiness.local_asr_problem
            assert local_asr_readiness.readiness_probe(_real_config()) is None
            assert local_asr_readiness.local_asr_problem(_real_config()) == "offline_pack_missing"
