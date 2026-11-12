"""Proves the plugin surfaces the daemon's real reason instead of a bare
"HTTP Error 500", and that every daemon failure kind has a user-facing hint.

No browser and no network: ``urlopen`` is stubbed with the exact 500 body the
daemon sends. Regression guard for the failure path that produced a 20-line
urllib traceback and no explanation.

Run: python verify_bridge_error.py
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import urllib.error

PLUGIN_PATH = pathlib.Path(__file__).with_name("plugin.py")
_spec = importlib.util.spec_from_file_location("google_stt_plugin", PLUGIN_PATH)
plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin)

_failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _failed
    if not ok:
        _failed += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -- ' + detail if detail else ''}")


def _http_500(body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://127.0.0.1:17874/start", 500, "Internal Server Error", {}, io.BytesIO(body))


def _raise(exc: BaseException):
    raise exc


def _stub_urlopen(exc: BaseException) -> None:
    plugin.urllib.request.urlopen = lambda *a, **k: _raise(exc)


# 1. The exact body the daemon sends when the browser died.
_stub_urlopen(_http_500(json.dumps({"error": "browser-closed", "kind": "browser-closed"}).encode()))
try:
    plugin._post("/start")
    check("daemon 500 raises BridgeError", False, "no exception raised")
except Exception as e:  # noqa: BLE001 - the test asserts on any failure mode
    check("daemon 500 raises BridgeError", isinstance(e, plugin.BridgeError), type(e).__name__)
    check("daemon reason survives", str(e) == "browser-closed", f'reason="{e}"')
    check("daemon kind survives", getattr(e, "kind", "") == "browser-closed", f'kind="{getattr(e, "kind", "")}"')
    check(
        "hint exists for that kind",
        bool(plugin._START_HINTS.get(getattr(e, "kind", ""))),
        plugin._START_HINTS.get(getattr(e, "kind", "")) or "MISSING",
    )

# 2. A non-JSON body must still produce a readable reason, not a raw traceback.
_stub_urlopen(_http_500(b"not json at all"))
try:
    plugin._post("/start")
    check("non-JSON body degrades gracefully", False, "no exception raised")
except Exception as e:  # noqa: BLE001
    check("non-JSON body degrades gracefully", str(e) == "not json at all", f'reason="{e}"')

# 3. Daemon not listening at all.
plugin.urllib.request.urlopen = lambda *a, **k: _raise(urllib.error.URLError("connection refused"))
try:
    plugin._post("/start")
    check("unreachable daemon is readable", False, "no exception raised")
except Exception as e:  # noqa: BLE001
    check(
        "unreachable daemon is readable",
        "cannot reach the Google STT bridge" in str(e),
        f'reason="{e}"',
    )

# 4. No daemon failure kind may reach the user as a bare slug.
KINDS = (
    "browser-closed",
    "mic-missing",
    "no-recording-indicator",
    "platform-not-recording",
    "composer-dirty",
    "signed-out",
)
missing = [k for k in KINDS if not plugin._START_HINTS.get(k)]
check(
    "every daemon kind has a user hint",
    not missing,
    f"missing: {missing}" if missing else f"{len(KINDS)} kinds covered",
)

print(f"\n{'all checks passed' if _failed == 0 else f'{_failed} check(s) failed'}")
raise SystemExit(1 if _failed else 0)
