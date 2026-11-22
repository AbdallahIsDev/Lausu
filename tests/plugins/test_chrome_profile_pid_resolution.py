"""Launch-time browser pid resolution must outlast Chrome's window creation.

Chrome returns from ``CreateProcess`` before its top-level browser window
exists. Recording a pid only when a painted window is already visible left the
per-plugin pid file stale and produced a spurious warning on every cold start.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tools.internal_plugins._common.bridge import chrome_profile


class _FakeTime:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _browser_info() -> dict:
    return {
        "hwnd": 1,
        "class": chrome_profile.BROWSER_CLASS,
        "title": "Claude - Google Chrome",
        "rect": (100, 100, 900, 700),
        "visible": True,
    }


def test_launch_records_pid_once_chrome_window_appears(
    tmp_path: Path, monkeypatch
) -> None:
    profile = "C:/Users/11/AppData/Local/voice-typer-internal-plugins/google-stt-profile"
    fake_time = _FakeTime()
    attempts: list[int] = []

    monkeypatch.setattr(chrome_profile, "find_chrome", lambda: "chrome.exe")
    monkeypatch.setattr(
        chrome_profile,
        "_popen",
        lambda *args, **kwargs: SimpleNamespace(pid=4242),
    )
    monkeypatch.setattr(
        chrome_profile,
        "_process_rows",
        lambda: [
            {
                "pid": "4242",
                "image": "chrome.exe",
                "cmdline": f'"chrome.exe" --user-data-dir={profile} https://claude.ai/new',
            }
        ],
    )

    def windows(_pid: int) -> list[int]:
        attempts.append(1)
        return [1] if len(attempts) >= 3 else []

    monkeypatch.setattr(chrome_profile, "_windows_for_pid", windows)
    monkeypatch.setattr(chrome_profile, "_window_info", lambda _hwnd: _browser_info())
    monkeypatch.setattr(chrome_profile, "time", fake_time)

    assert chrome_profile.launch(profile, "https://claude.ai/new", plugin_dir=str(tmp_path))
    recorded = json.loads((tmp_path / chrome_profile.PID_FILE).read_text(encoding="utf-8"))
    assert recorded == {"pid": 4242}
    assert len(attempts) >= 3, "the launch must retry until the window is painted"
