"""Screenshot IPC handler tests (faked server, tmp profile, no real grab)."""

from pathlib import Path

from voice_typer.server.screenshots import capture as _cap, paths as _paths

from tests.fixtures.ipc_test_helpers import make_ipc_server_with_fakes

_RECT = {"left": 0, "top": 0, "width": 10, "height": 10}


def _enable(server, beta=True, consent=True) -> None:
    server.app.config.screenshot_beta_enabled = beta
    server.app.config.screenshot_consent = consent


def _code(server, payload) -> str:
    return server._handle_screenshot_capture(payload, {})["data"]["code"]


def test_capture_gates_in_order(monkeypatch, tmp_path: Path) -> None:
    import voice_typer.server.platform_utils as _plat

    monkeypatch.setattr(_paths, "_config_dir", lambda: tmp_path)
    server, _, _ = make_ipc_server_with_fakes()
    monkeypatch.setattr(_plat, "is_windows", lambda: False)
    _enable(server)
    assert _code(server, {"cycle_id": "c1", "rect": _RECT}) == "screenshot_unsupported"
    monkeypatch.setattr(_plat, "is_windows", lambda: True)
    _enable(server, beta=False)
    assert _code(server, {"cycle_id": "c1", "rect": _RECT}) == "screenshot_disabled"
    _enable(server, beta=True, consent=False)
    assert _code(server, {"cycle_id": "c1", "rect": _RECT}) == "screenshot_no_consent"


def test_capture_success_then_already_captured(monkeypatch, tmp_path: Path) -> None:
    import voice_typer.server.platform_utils as _plat

    monkeypatch.setattr(_plat, "is_windows", lambda: True)
    monkeypatch.setattr(_paths, "_config_dir", lambda: tmp_path)
    dest = _paths.shot_path("2026-10-07_X")
    fake = {"path": str(dest), "width": 10, "height": 10, "bytes": 8}
    monkeypatch.setattr(_cap, "capture_rect", lambda rect, p, **kw: fake)
    server, _, _ = make_ipc_server_with_fakes()
    _enable(server)
    payload = {"cycle_id": "2026-10-07_X", "rect": dict(_RECT)}
    assert server._handle_screenshot_capture(payload, {})["type"] == "screenshot_captured"
    dest.write_bytes(b"\x89PNG" + b"0" * 16)
    assert _code(server, payload) == "screenshot_already_captured"


def test_status_clear_and_consent(monkeypatch, tmp_path: Path) -> None:
    import voice_typer.server.platform_utils as _plat

    monkeypatch.setattr(_plat, "is_windows", lambda: True)
    monkeypatch.setattr(_paths, "_config_dir", lambda: tmp_path)
    server, _, service = make_ipc_server_with_fakes()
    _enable(server)
    status = server._handle_screenshot_get_status({}, {})
    assert status["type"] == "screenshot_status"
    assert status["data"]["supported"] is True
    out = server._handle_screenshot_set_consent({"consented": True}, {})
    assert out["type"] == "ack"
    service.apply_config.assert_called_once_with({"screenshot_consent": True})
    assert server._handle_screenshot_clear_cycle({"cycle_id": "nope"}, {})["type"] == "ack"
