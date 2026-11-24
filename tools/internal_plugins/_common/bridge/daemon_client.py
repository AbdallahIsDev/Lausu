"""HTTP client for the SHARED bridge daemon.

One implementation, configured with the owning plugin's URL and bridge name.
The plugin's thin wrappers stay module attributes so existing monkeypatch seams
keep working.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.parse
import urllib.request

from tools.internal_plugins._common import daemon as _daemon_common

DEFAULT_PORT = 17875
BRIDGE_NAME = "STT bridge"


class DaemonClient:
    def __init__(
        self,
        env_var: str,
        bridge_name: str = BRIDGE_NAME,
        port: int = DEFAULT_PORT,
        *,
        config_dir: str | None = None,
        daemon_script: str | None = None,
        daemon_cwd: str | None = None,
        daemon_args: tuple[str, ...] = (),
    ) -> None:
        self.env_var = env_var
        self.bridge_name = bridge_name
        self.url = os.environ.get(env_var, f"http://127.0.0.1:{port}")
        self.config_dir = config_dir or ""
        self.daemon_script = daemon_script or ""
        self.daemon_cwd = daemon_cwd or ""
        self.daemon_args = daemon_args

    def post(self, path: str, timeout: float = 60.0) -> dict:
        return _daemon_common.post(self.url, path, timeout, self.bridge_name)

    def status(self, timeout: float = 1.5) -> dict | None:
        """The daemon's bridge snapshot, or None when it is not answering."""
        try:
            with urllib.request.urlopen(self.url + "/status", timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
                return data if isinstance(data, dict) else None
        except Exception:
            return None

    def alive(self, timeout: float = 6.0) -> bool:
        """A live daemon can be slow: /status waits on the browser tab.

        The old 1.5 s probe called a busy daemon dead and spawned a second one
        on the same port (EADDRINUSE), freezing the hotkey in ensure_daemon's
        retry loop after an extension reload broke the tab's content-script port.
        """
        return self.status(timeout=timeout) is not None

    def listening(self) -> bool:
        """Transport-only liveness: something owns our loopback port."""
        try:
            parsed = urllib.parse.urlparse(self.url)
            with socket.create_connection(
                (parsed.hostname or "127.0.0.1", parsed.port or DEFAULT_PORT),
                timeout=0.5,
            ):
                return True
        except OSError:
            return False

    def config(self) -> dict:
        """The daemon's browser knobs, or {} if unavailable."""
        try:
            with urllib.request.urlopen(self.url + "/config", timeout=2.0) as r:
                data = json.loads(r.read().decode("utf-8"))
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def browser_connected(snapshot: dict | None) -> bool:
        """Transport-only readiness: the extension is up, whatever the tab does.

        A connected browser resolves and recreates its own target tabs, so a
        missing tab must never be read as "launch Chrome again" (that opens a
        duplicate tab in the shared profile on every plugin switch).
        """
        return bool(snapshot) and snapshot.get("browser") == "connected"

    @staticmethod
    def bridge_ready(snapshot: dict | None) -> bool:
        """Connected AND the tab has answered once (a page state, not unknown)."""
        if not snapshot or snapshot.get("browser") != "connected":
            return False
        if snapshot.get("state") == "wrong-platform":
            return False
        page = snapshot.get("page")
        return isinstance(page, str) and page not in ("", "unknown")


def platform_url(status: dict | None, platform: str) -> bool:
    """A connected snapshot belongs to THIS plugin's platform."""
    if not DaemonClient.bridge_ready(status):
        return False
    actual = (status or {}).get("platform")
    return actual in (None, platform)


__all__ = ["DaemonClient", "DEFAULT_PORT", "BRIDGE_NAME", "platform_url"]
