"""Proves the plugin session drives the app like the local model does.

Covers the behaviours the owner asked for after the first working dictation:
  * the pill shows RECORDING while the platform captures (it used to sit on
    "Ready" because only `bubble_show` was published),
  * the system volume is ducked for the capture and restored afterwards,
  * a stop that the PLATFORM performs (focus loss, its own 10-minute cap) still
    delivers what it captured instead of losing the cycle,
  * the user's stop and the platform watchdog cannot both run the stop path,
  * the prompt box is cleared once the text has been delivered.

Run: python verify_session_events.py
"""

from __future__ import annotations

import pathlib
import sys
import threading
import time
import types

PLUGIN_DIR = pathlib.Path(__file__).resolve().parent
ROOT = PLUGIN_DIR.parents[2]
sys.path.insert(0, str(ROOT))

_failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _failed
    if not ok:
        _failed += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -- ' + detail if detail else ''}")


from tools.internal_plugins.anthropic_stt import plugin as plugin_session  # noqa: E402

events: list[dict] = []
posts: list[str] = []
duck_calls: list[str] = []


class _Bus:
    @staticmethod
    def publish(event: dict) -> None:
        events.append(event)


sys.modules.setdefault("voice_typer.server.event_bus", _Bus)
import voice_typer.server  # noqa: E402

voice_typer.server.event_bus = _Bus  # type: ignore[attr-defined]


def fake_post(path: str, timeout: float = 0.0) -> dict:
    posts.append(path)
    if path == "/stop":
        return {"text": "delivered text", "duration_s": 3.0, "auto_stopped": False}
    if path == "/clear":
        return {"cleared": True}
    return {"ok": True}


plugin_session._post = fake_post
plugin_session.ensure_daemon = lambda: True
plugin_session._ensure_browser = lambda timeout=15.0: True
plugin_session._mute_bubble_levels = lambda: None


class _Clipboard:
    _clipboard_seq = 1

    def copy(self, text: str) -> None:
        pass

    def paste(self, **_kwargs) -> None:
        pass


class _History:
    def add_transcription(self, text: str, **_kwargs) -> int:
        return 1


class _App:
    clipboard = _Clipboard()
    history_db = _History()
    config = types.SimpleNamespace(device="cpu", language="en")

    def _duck_volume(self) -> None:
        duck_calls.append("duck")

    def _restore_volume(self, fade_ms=None) -> None:
        duck_calls.append("restore")


def new_session() -> plugin_session.PluginSession:
    session = plugin_session.PluginSession(_App())
    session._notify = lambda message: None
    return session


def states() -> list[str]:
    return [e["data"]["state"] for e in events if e.get("type") == "bubble_set_state"]


# --- start publishes the recording state and ducks the volume ---------------
events.clear()
posts.clear()
duck_calls.clear()
session = new_session()
session.start()
check("start publishes the recording pill state", states() == ["recording"], str(states()))
check("start ducks the system volume", duck_calls == ["duck"], str(duck_calls))
check("start hits /start", posts == ["/start"], str(posts))

# --- stop publishes transcribing -> idle, restores volume, clears the box ---
events.clear()
posts.clear()
duck_calls.clear()
session.stop()
check("stop publishes transcribing then idle", states() == ["transcribing", "idle"], str(states()))
check("stop restores the volume", duck_calls == ["restore"], str(duck_calls))
check("stop hits /stop then /clear", posts == ["/stop", "/clear"], str(posts))
check("stop delivers the text", "delivered text" in str(events), str(events)[:120])

# --- the platform stopping on its own still delivers the capture ------------
events.clear()
posts.clear()
duck_calls.clear()
session = new_session()
session.start()
posts.clear()
# The page reports idle twice: the platform ended the dictation by itself.
plugin_session._daemon_status = lambda: {"state": "idle", "browser": "connected"}
plugin_session._PLATFORM_WATCH_GRACE_S = 0.0
plugin_session._PLATFORM_WATCH_POLL_S = 0.01
watch = threading.Thread(target=session._watch_platform, daemon=True)
watch.start()
watch.join(timeout=5.0)
check("the platform-stop watchdog delivers the capture", "/stop" in posts, str(posts))
check("the watchdog clears the prompt box too", "/clear" in posts, str(posts))
check("the watchdog ends the session", session.active is False)

# --- a single idle blip must NOT cut a live capture -------------------------
events.clear()
posts.clear()
session = new_session()
session.start()
posts.clear()
reads = {"n": 0}


def flaky_status() -> dict:
    reads["n"] += 1
    # recording, one idle blip, then recording again
    return {"state": "idle" if reads["n"] == 2 else "recording", "browser": "connected"}


plugin_session._daemon_status = flaky_status
watch = threading.Thread(target=session._watch_platform, daemon=True)
watch.start()
time.sleep(0.2)
check("one idle blip does not stop the capture", "/stop" not in posts, str(posts))
session._active = False  # end the session so the watchdog thread exits
watch.join(timeout=2.0)

# --- the user's stop and the watchdog cannot both run ----------------------
events.clear()
posts.clear()
session = new_session()
session.start()
posts.clear()
session._stopping = True  # the watchdog's stop is already in flight
session._stop_and_deliver()
check("a concurrent stop is refused", posts == [], str(posts))
session._stopping = False

print(f"\n{'all checks passed' if _failed == 0 else f'{_failed} check(s) failed'}")
raise SystemExit(1 if _failed else 0)
