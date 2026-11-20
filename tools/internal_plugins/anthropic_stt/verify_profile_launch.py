"""Proves the profile launcher can only ever start plain Chrome.

The old Playwright setup died on automation flags. This guard fails if any
switch other than --user-data-dir / --profile-directory ever reaches the
command line, and it pins the PowerShell launchers to the same rule.

Run: python verify_profile_launch.py
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import pathlib
import sys
import tempfile
import types

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent
ROOT = PLUGIN_DIR.parents[2]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("anthropic_stt_plugin", PLUGIN_DIR / "plugin.py")
plugin = importlib.util.module_from_spec(_spec)
# plugin.py calls session.bind_entry(sys.modules[__name__]) at import time,
# so the module must be registered before exec_module (C-ARCH-2).
sys.modules[_spec.name] = plugin
_spec.loader.exec_module(plugin)
chrome = importlib.import_module("tools.internal_plugins._common.bridge.chrome_profile")

_failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _failed
    if not ok:
        _failed += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -- ' + detail if detail else ''}")


URL = "https://claude.ai/new"
PROFILE = r"C:\Users\11\AppData\Local\voice-typer-internal-plugins\google-stt-profile"
EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ARGS = [f"--user-data-dir={PROFILE}", "--profile-directory=Default", URL]

check("profile_args is exactly three arguments", chrome.profile_args(PROFILE, URL) == ARGS)
try:
    chrome._assert_plain(ARGS)
    check("the plain launch is accepted", True)
except ValueError as exc:  # noqa: BLE001 - the failure is the assertion
    check("the plain launch is accepted", False, str(exc))

FORBIDDEN = (
    "--remote-debugging-port=9222",
    "--remote-debugging-pipe",
    "--enable-automation",
    "--headless=new",
    "--user-agent=Mozilla/5.0",
    "--proxy-server=http://127.0.0.1:8080",
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--window-position=-32000,-32000",
    "--window-size=1280,720",
    "--start-minimized",
    "--kiosk",
    "--app=https://claude.ai/new",
)
for switch in FORBIDDEN:
    try:
        chrome._assert_plain(ARGS + [switch])
        check(f"rejects {switch}", False, "accepted")
    except ValueError:
        check(f"rejects {switch}", True)

captured: list[tuple[list[str], dict]] = []


def fake_popen(command, **kwargs):
    captured.append((command, kwargs))
    return types.SimpleNamespace(pid=4242)


original_popen = chrome._popen
chrome._popen = fake_popen
try:
    spawned = chrome.launch(PROFILE, URL, chrome_path=EXE)
finally:
    chrome._popen = original_popen

check("launch spawns Chrome", spawned)
check("command line is the exe plus the three arguments", bool(captured) and captured[0][0] == [EXE, *ARGS])
check(
    "the child gets the browser environment without a shell",
    bool(captured) and captured[0][1].get("shell") is None and bool(captured[0][1].get("env")),
)

# Hidden mode changes NO launch argument (no automation fingerprint) and only
# toggles the window via the injected Win32 seam.
visibility_calls = []
original_visibility = chrome._set_window_visible_fn
chrome._set_window_visible_fn = lambda pid, visible, wait: visibility_calls.append((pid, visible, wait)) or True
# The launcher records the WMI-resolved chrome pid, not Popen's pid.
original_resolver = chrome.resolve_browser_pid
chrome.resolve_browser_pid = lambda _profile: 4242
workspace = pathlib.Path(tempfile.mkdtemp(prefix="anthropic-stt-visibility-"))
chromium_stub = chrome._popen
chrome._popen = fake_popen
try:
    hidden = chrome.launch(PROFILE, URL, chrome_path=EXE, visible=False, plugin_dir=str(workspace))
finally:
    chrome._set_window_visible_fn = original_visibility
    chrome.resolve_browser_pid = original_resolver
    chrome._popen = chromium_stub
check("a hidden launch still spawns Chrome", hidden)
check("hidden mode hides without extra flags", visibility_calls == [(4242, False, 5.0)], str(visibility_calls))
check("the launched pid is recorded for live toggling", chrome._read_pid(str(workspace)) == 4242)
check("no automation switch reached the command line", captured[-1][0] == [EXE, *ARGS])

original_find = chrome.find_chrome
chrome.find_chrome = lambda: None
try:
    missing = chrome.launch(PROFILE, URL)
finally:
    chrome.find_chrome = original_find
check("a machine without Chrome fails closed", missing is False)
check("an empty profileDir fails closed", chrome.launch("", URL, chrome_path=EXE) is False)

real = chrome.find_chrome()
check("finds the installed branded Chrome", bool(real) and pathlib.Path(real).is_file(), str(real))

# The sidecar runs with a trimmed environment (.env_clear() + allowlist), so the
# lookup must backfill the Windows paths itself or the launch never happens.
trimmed = {}
for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "LOCALAPPDATA", "LUASU_CHROME_PATH"):
    trimmed[key] = os.environ.pop(key, None)
try:
    from_trimmed = chrome.find_chrome()
finally:
    for key, value in trimmed.items():
        if value is not None:
            os.environ[key] = value
check(
    "finds Chrome with the sidecar's trimmed environment",
    bool(from_trimmed) and pathlib.Path(from_trimmed).is_file(),
    str(from_trimmed),
)
check("the trimmed lookup returns the same browser", from_trimmed == real)

check("bridge: no daemon answer is not ready", not plugin._bridge_ready(None))
check(
    "bridge: disconnected is not ready",
    not plugin._bridge_ready({"browser": "disconnected", "page": "unknown"}),
)
check(
    "bridge: connected before the tab answered is not ready",
    not plugin._bridge_ready({"browser": "connected", "page": "unknown"}),
)
check(
    "bridge: connected on a signed-out page is ready",
    plugin._bridge_ready({"browser": "connected", "page": "signed_out"}),
)
check("bridge: connected on a ready page is ready", plugin._bridge_ready({"browser": "connected", "page": "ok"}))

# The hotkey path may open the profile, but a dead extension must not spawn a new
# tab on every press: one launch per cooldown window, and never while ready.
launches: list[tuple[str, str]] = []


def fake_launch(profile_dir: str, url: str) -> bool:
    launches.append((profile_dir, url))
    return True


original = {
    "launch_profile": plugin.launch_profile,
    "daemon_status": plugin._daemon_status,
    "daemon_config": plugin._daemon_config,
    "time": plugin.time,
}
plugin.launch_profile = fake_launch
plugin._daemon_config = lambda: {"profileDir": PROFILE, "claudeUrl": URL}
plugin._daemon_status = lambda: {"browser": "disconnected", "page": "unknown"}
plugin._last_launch_ts = 0.0
plugin.time = types.SimpleNamespace(monotonic=lambda: 1000.0)
try:
    plugin._ensure_browser(timeout=0.0)
    first = len(launches)
    plugin._ensure_browser(timeout=0.0)
    second = len(launches)
    plugin.time = types.SimpleNamespace(monotonic=lambda: 1000.0 + plugin._LAUNCH_COOLDOWN_S + 1.0)
    plugin._ensure_browser(timeout=0.0)
    third = len(launches)
finally:
    plugin.launch_profile = original["launch_profile"]
    plugin._daemon_status = original["daemon_status"]
    plugin._daemon_config = original["daemon_config"]
    plugin.time = original["time"]

check("the hotkey path opens the profile when the bridge is down", first == 1)
check("a second press inside the cooldown does not spawn another window", second == 1)
check("the cooldown expires and allows one more launch", third == 2)
check("the launch carries the configured profile and url", launches[0] == (PROFILE, URL))

ready_launches = len(launches)
plugin.launch_profile = fake_launch
plugin._daemon_status = lambda: {"browser": "connected", "page": "ok"}
plugin._last_launch_ts = 0.0
try:
    ready = plugin._ensure_browser(timeout=0.0)
finally:
    plugin.launch_profile = original["launch_profile"]
    plugin._daemon_status = original["daemon_status"]
check("a ready bridge is used as-is with no launch", ready and len(launches) == ready_launches)

PS_FORBIDDEN = (
    "--remote-debugging",
    "--enable-automation",
    "--disable-blink-features",
    "--headless",
    "--user-agent",
    "--proxy-server",
    "--window-position",
    "--start-minimized",
    "--kiosk",
)
for name in ("launch-claude-profile.ps1", "install-shortcut.ps1"):
    script = PLUGIN_DIR / "setup" / name
    text = script.read_text(encoding="utf-8").lower() if script.is_file() else ""
    hits = [marker for marker in PS_FORBIDDEN if marker in text]
    check(f"setup/{name} carries no automation switch", bool(text) and not hits, str(hits))
    check(
        f"setup/{name} keeps the profile argument shape",
        "--user-data-dir" in text and "--profile-directory=default" in text,
    )

print(f"\n{'all checks passed' if _failed == 0 else f'{_failed} check(s) failed'}")
raise SystemExit(1 if _failed else 0)
