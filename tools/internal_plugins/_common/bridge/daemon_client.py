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
        platform: str = "",
    ) -> None:
        self.platform = platform
        self.env_var = env_var
        self.bridge_name = bridge_name
        self.url = os.environ.get(env_var, f"http://127.0.0.1:{port}")
        self.config_dir = config_dir or ""
        self.daemon_script = daemon_script or ""
        self.daemon_cwd = daemon_cwd or ""
        self.daemon_args = daemon_args

    def _url_for(self, path: str) -> str:
        """Scope each request to the owning plugin's platform.

        One shared daemon serves all three plugins; its process-wide config
        descriptor belongs to whichever plugin spawned it first, so the
        platform MUST travel with the request (C-PARITY-1).
        """
        url = self.url + path
        if self.platform:
            separator = "&" if "?" in url else "?"
            url += f"{separator}platform={urllib.parse.quote(self.platform)}"
        return url

    def post(self, path: str, timeout: float = 60.0) -> dict:
        return _daemon_common.post(self.url, path, timeout, self.bridge_name, platform=self.platform)

    def status(self, timeout: float = 1.5) -> dict | None:
        """The daemon's bridge snapshot, or None when it is not answering."""
        try:
            with urllib.request.urlopen(self._url_for("/status"), timeout=timeout) as r:
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
            with urllib.request.urlopen(self._url_for("/config"), timeout=2.0) as r:
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
    def page_ready(snapshot: dict | None) -> bool:
        """The target tab is loaded AND its dictation control is clickable.

        A live WebSocket only proves the extension exists; the content script
        re-injects at document_idle and the page hydrates later. Clicking a
        mic that is not there yet starts nothing (P2).
        """
        if not DaemonClient.bridge_ready(snapshot):
            return False
        snapshot = snapshot or {}
        return (
            snapshot.get("page") == "ok"
            and int(snapshot.get("micCount") or 0) > 0
            and snapshot.get("selectorsReady") is True
        )

    @staticmethod
    def readiness_state(snapshot: dict | None) -> dict:
        """One truthful readiness tuple from the extension's single probe.

        Only used for logging and user-facing recovery hints; the mic gate
        itself stays ``page_ready`` (P2).
        """
        snapshot = snapshot or {}
        readiness = snapshot.get("readiness")
        if not isinstance(readiness, dict):
            readiness = {
                "browser": "up" if DaemonClient.browser_connected(snapshot) else "down",
                "tab": "ready" if snapshot.get("hasTab") else "missing",
                "content_script": "present" if DaemonClient.bridge_ready(snapshot) else "absent",
                "control": "present" if int(snapshot.get("micCount") or 0) > 0 else "missing",
                "signed_in": "no" if snapshot.get("page") == "signed_out" else "unknown",
                "reason": "ready" if DaemonClient.page_ready(snapshot) else "page-not-ready",
            }
        return {
            "browser": str(readiness.get("browser") or "down"),
            "tab": str(readiness.get("tab") or "missing"),
            "content_script": str(readiness.get("content_script") or "absent"),
            "control": str(readiness.get("control") or "missing"),
            "signed_in": str(readiness.get("signed_in") or "unknown"),
            "reason": str(readiness.get("reason") or "unknown"),
        }

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
