"""Launch-time browser pid resolution must outlast a not-yet-ready Chrome.

Chrome returns from ``CreateProcess`` before its top-level browser window
exists. Recording a pid from a single probe left the per-plugin pid file stale
on a cold start. The retry lives in ``resolve_browser_pid_after_launch`` and is
reached through ``launch()``; its platform-neutral seam is
``resolve_browser_pid`` (on Windows that waits for a painted browser window,
elsewhere it resolves the process directly). Stubbing that seam keeps the
retry contract testable on every CI leg.
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


def test_launch_records_pid_once_chrome_window_appears(tmp_path: Path, monkeypatch) -> None:
    profile = "C:/Users/11/AppData/Local/voice-typer-internal-plugins/google-stt-profile"
    fake_time = _FakeTime()
    attempts: list[int] = []

    monkeypatch.setattr(chrome_profile, "find_chrome", lambda: "chrome.exe")
    monkeypatch.setattr(
        chrome_profile,
        "_popen",
        lambda *args, **kwargs: SimpleNamespace(pid=4242),
    )

    def resolvable_pid(_profile_dir: str) -> int | None:
        attempts.append(1)
        return 4242 if len(attempts) >= 3 else None

    monkeypatch.setattr(chrome_profile, "resolve_browser_pid", resolvable_pid)
    monkeypatch.setattr(chrome_profile, "time", fake_time)

    assert chrome_profile.launch(profile, "https://claude.ai/new", plugin_dir=str(tmp_path))
    recorded = json.loads((tmp_path / chrome_profile.PID_FILE).read_text(encoding="utf-8"))
    assert recorded == {"pid": 4242}
    assert len(attempts) >= 3, "the launch must retry until the pid resolves"
