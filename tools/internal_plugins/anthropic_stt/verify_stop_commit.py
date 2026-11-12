"""Proves stopping a dictation COMMITS it instead of discarding it.

Claude's recording UI carries two sibling controls: "Finish dictation" (the
check mark, which turns the captured audio into text) and "Cancel dictation"
(the X, which throws the capture away). The old selector list matched only the
discard control, so every stop wiped the transcript and the whole dictation
disappeared -- no text, no clipboard, no history, no paste.

This verifier pins:
  1. the selector vocabulary (commit is the stop control, discard is separate),
  2. which aria-label each control matches,
  3. that the content script routes stop -> commit and cancel -> discard,
  4. the push-to-talk release that lands while the start is still in flight
     (deferred, not dropped).

Run: python verify_stop_commit.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
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


SELECTORS = json.loads((PLUGIN_DIR / "selectors.json").read_text(encoding="utf-8"))


def label_matchers(selector: str) -> list[str]:
    """The aria-label substrings a `button[aria-label*="X" i]` list accepts."""
    return [m.group(1).lower() for m in re.finditer(r'aria-label\*="([^"]+)"', selector)]


def matches(selector: str, label: str) -> bool:
    lowered = label.lower()
    return any(fragment in lowered for fragment in label_matchers(selector))


STOP = SELECTORS["stopSelector"]
CANCEL = SELECTORS["cancelSelector"]

check("a cancel selector exists", bool(CANCEL.strip()))
check("stop matches the commit control", matches(STOP, "Finish dictation"))
check("stop matches the legacy stop labels", matches(STOP, "Stop dictation"))
check("stop does NOT match the discard control", not matches(STOP, "Cancel dictation"))
check("cancel matches the discard control", matches(CANCEL, "Cancel dictation"))
check("cancel does NOT match the commit control", not matches(CANCEL, "Finish dictation"))
check(
    "the two selector lists share no label fragment",
    not (set(label_matchers(STOP)) & set(label_matchers(CANCEL))),
    str(sorted(set(label_matchers(STOP)) & set(label_matchers(CANCEL)))),
)
check(
    "the recording indicator documents both controls",
    "Finish dictation" in SELECTORS["recordingIndicator"]
    or "finish dictation" in SELECTORS["recordingIndicator"].lower(),
)

CONTENT = (PLUGIN_DIR / "extension" / "content.js").read_text(encoding="utf-8")
stop_body = CONTENT.split("async function stop(")[1].split("async function cancel(")[0]
cancel_body = CONTENT.split("async function cancel(")[1].split("async function clean(")[0]
check("stop() clicks the commit control", "stopButtons()" in stop_body and "cancelButtons" not in stop_body)
check("cancel() clicks the discard control", "cancelButtons()" in cancel_body)
check("stop() reports whether it actually committed", "committed: stopControl.length > 0" in stop_body)
check(
    "recordingState treats either control as recording",
    "stopButtons().length + cancelButtons().length" in CONTENT,
)

# Push-to-talk: the release can land mid-start (browser launch + handshake).
from tools.internal_plugins.anthropic_stt import plugin as plugin_session  # noqa: E402

calls: list[str] = []
plugin_session._post = lambda path, timeout=0.0: (
    calls.append(path),
    {"text": "hello world"} if path == "/stop" else {},
)[1]
plugin_session.ensure_daemon = lambda: True
plugin_session._ensure_browser = lambda timeout=15.0: True
plugin_session._mute_bubble_levels = lambda: None


class _Clipboard:
    _clipboard_seq = 1

    def copy(self, text: str) -> None:
        calls.append("clipboard.copy")

    def paste(self, **_kwargs) -> None:
        calls.append("paste")


class _History:
    def add_transcription(self, **_kwargs) -> int:
        calls.append("history")
        return 1


class _FakeApp:
    clipboard = _Clipboard()
    history_db = _History()
    config = types.SimpleNamespace(device="cpu", model_size="parakeet", language="en")


session = plugin_session.PluginSession(_FakeApp())
session._session_events = lambda start: calls.append(f"event:{start}")
session._notify = lambda message: calls.append(f"notify:{message}")

check("a fresh session does not own a cycle", not session.owns_cycle)
session._lock.acquire()
session._starting = True
session._lock.release()
check("a start in flight owns the cycle", session.owns_cycle)
accepted = session.stop()
check("release during the start is accepted", accepted is True)
check("nothing runs before the start lands", calls == [], str(calls))
session._lock.acquire()
session._starting = False
session._active = True
deferred = session._active and session._stop_requested
session._stop_requested = False
session._lock.release()
if deferred:
    session._stop_and_deliver()
check("the deferred release runs /stop", "/stop" in calls, str(calls))
check("the deferred release still delivers the text", "paste" in calls, str(calls))

calls.clear()
check("a stop with no cycle is refused", session.stop() is False)
session._active = False
check("an idle session does not own a cycle", not session.owns_cycle)

print(f"\n{'all checks passed' if _failed == 0 else f'{_failed} check(s) failed'}")
raise SystemExit(1 if _failed else 0)
