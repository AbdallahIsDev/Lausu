"""Open a visible console running the Tauri/Vite dev server.

Used by the Dev shortcut and as a fallback when no installed
``lausu-tauri`` binary is found (source checkout without an install).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys  # noqa: F401  # re-exported for tests (dev_console.sys)
from pathlib import Path

log = logging.getLogger("voice_typer.server.autostart_launcher")


def client_dir() -> Path:
    """Repo ``voice_typer/client`` (dev checkout)."""
    return Path(__file__).resolve().parent.parent.parent.parent / "voice_typer" / "client"


def launch_dev_console(npm_script: str = "dev") -> int:
    """Spawn a visible console running ``npm run <npm_script>`` in the client dir.

    Returns 0 when the console was spawned, 1 on failure.
    """
    cwd = client_dir()
    if not (cwd / "package.json").is_file():
        log.error("[DEV] client dir missing package.json: %s", cwd)
        return 1

    from voice_typer.server.platform_utils import is_windows

    if is_windows():
        # CREATE_NEW_CONSOLE: pythonw has no console, the user needs one
        # to see vite/tauri output and Ctrl+C the dev server.
        try:
            subprocess.Popen(
                ["cmd.exe", "/k", "npm", "run", npm_script],
                cwd=str(cwd),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            log.info("[DEV] spawned console: npm run %s in %s", npm_script, cwd)
            return 0
        except OSError:
            log.exception("[DEV] failed to spawn dev console")
            return 1

    # POSIX: prefer the user's terminal emulator when available.
    term = os.environ.get("TERMINAL") or "x-terminal-emulator"
    try:
        subprocess.Popen(
            [term, "-e", "npm", "run", npm_script],
            cwd=str(cwd),
            start_new_session=True,
        )
        log.info("[DEV] spawned %s: npm run %s in %s", term, npm_script, cwd)
        return 0
    except OSError:
        log.exception("[DEV] failed to spawn terminal %s", term)
        return 1
