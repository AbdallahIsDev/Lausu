"""Shared Node-daemon scaffolding for the bundled internal STT plugins.

Both plugins drive an external HTTP daemon (``run.js``) the same way: the same
error type, enable gate, POST plumbing, Node/executable resolution, dependency
root, environment backfill, spawn/liveness loop, and shutdown. Kept here so a
fix to spawning, NODE_PATH backfill or parent-PID forwarding cannot land in one
plugin and drift from the other.

The plugin modules keep thin no-argument wrappers around these helpers so their
existing module-level patch points keep working.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from voice_typer.server.parent_watch import PARENT_PID_ENV_VAR


class BridgeError(RuntimeError):
    """The daemon answered with an error; ``kind`` maps to a user-facing hint."""

    def __init__(self, reason: str, kind: str = "") -> None:
        super().__init__(reason)
        self.kind = kind


def plugins_enabled(plugins_dir: Path) -> bool:
    """The PLUGINS_ENABLED marker is the whole gate (developer mode writes it)."""
    return (plugins_dir / "PLUGINS_ENABLED").is_file()


def post(daemon_url: str, path: str, timeout: float, bridge_name: str) -> dict:
    """POST to the daemon and decode its JSON answer."""
    req = urllib.request.Request(daemon_url + path, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # The daemon puts the real reason in the body. urllib discards it, so
        # every failure surfaced as a bare "HTTP Error 500" traceback.
        try:
            raw = e.read().decode("utf-8", "replace")
        except Exception:
            raw = ""
        reason = ""
        kind = ""
        if raw:
            try:
                body = json.loads(raw)
                reason = str(body.get("error") or "")
                kind = str(body.get("kind") or "")
            except Exception:
                reason = raw[:200]
        raise BridgeError(reason or f"HTTP {e.code}", kind) from None
    except urllib.error.URLError as e:
        raise BridgeError(f"cannot reach the {bridge_name} ({e.reason})") from None


def daemon_alive(daemon_url: str, timeout: float = 1.5) -> bool:
    """Whether the daemon's status endpoint is answering."""
    try:
        with urllib.request.urlopen(daemon_url + "/status", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def node_exe() -> str:
    return shutil.which("node") or "node"


def node_deps_root() -> str:
    """Per-user directory the plugin's Node dependencies are installed into."""
    override = os.environ.get("PLUGINS_NODE_DEPS")
    if override:
        return override
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "voice-typer-internal-plugins", "node-deps")


def daemon_env() -> dict[str, str]:
    """NODE_PATH backfill plus the Windows paths Chrome resolution reads.

    Tauri trims the sidecar env; an unset PROGRAMFILES broke Chrome resolution,
    so the standard paths are filled in here for both plugins.
    """
    env = dict(os.environ)
    # Frozen builds must refuse dev diagnostics even if a dev flag leaked in.
    if getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", None):
        env["VOICE_TYPER_FROZEN"] = "1"
    # C-HOST-1: run.js watches this PID and shuts the bridge down when the
    # host dies, so a POSIX sidecar kill cannot leave it orphaned.
    parent_pid = os.environ.get(PARENT_PID_ENV_VAR)
    if parent_pid:
        env[PARENT_PID_ENV_VAR] = parent_pid
    env["NODE_PATH"] = node_deps_root() + os.pathsep + env.get("NODE_PATH", "")
    for key, fallback in (
        ("PROGRAMFILES", r"C://Program Files"),
        ("PROGRAMFILES(X86)", r"C://Program Files (x86)"),
        ("PROGRAMW6432", r"C://Program Files"),
        ("SYSTEMROOT", r"C://Windows"),
        ("LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local")),
    ):
        if not env.get(key):
            env[key] = fallback
    return env


def shutdown(post_fn: Callable[..., dict], log: logging.Logger, timeout: float = 3.0) -> None:
    """Close the daemon when the user selects another plugin."""
    try:
        post_fn("/shutdown", timeout=timeout)
    except Exception:
        log.debug("[PLUGIN] daemon shutdown request failed", exc_info=True)


def ensure_daemon(
    here: Path,
    alive_fn: Callable[[], bool],
    log: logging.Logger,
    *,
    attempts: int = 40,
    interval: float = 0.5,
    daemon_script: Path | None = None,
    daemon_args: tuple[str, ...] = (),
    cwd: Path | None = None,
    listening_fn: Callable[[], bool] | None = None,
) -> bool:
    """Spawn the shared Node control daemon if not already listening.

    ``here`` is the owning plugin dir (debug logs live there); ``daemon_script``
    and ``cwd`` point at the shared bridge so both plugins spawn the SAME daemon
    with a platform descriptor instead of maintaining two transports.
    """
    if alive_fn():
        return True
    if listening_fn is not None and listening_fn():
        # The port is already owned: a slow /status is a busy daemon, not a
        # dead one. Never spawn a second process onto an occupied port.
        for _ in range(3):
            time.sleep(interval)
            if alive_fn():
                return True
        log.error("[PLUGIN] the bridge is listening but not answering")
        return False
    env = daemon_env()
    # The daemon is the only place a browser/selector failure can surface, so
    # its output must be inspectable instead of DEVNULL: a dead daemon
    # otherwise fails as an opaque ConnectionRefusedError at stop time.
    debug = here / "debug"
    debug.mkdir(exist_ok=True)
    script = daemon_script or here / "run.js"
    workdir = cwd or script.parent
    try:
        with (
            open(debug / "daemon.out.log", "a", encoding="utf-8") as out,
            open(debug / "daemon.err.log", "a", encoding="utf-8") as err,
        ):
            subprocess.Popen(
                [node_exe(), str(script), *daemon_args],
                cwd=str(workdir),
                env=env,
                stdout=out,
                stderr=err,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    except Exception:
        log.exception("[PLUGIN] failed to spawn daemon")
        return False
    for _ in range(attempts):
        if alive_fn():
            return True
        time.sleep(interval)
    log.error("[PLUGIN] daemon did not come up")
    return False
