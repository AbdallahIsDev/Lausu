"""Terminal entry point: `lausu` starts the production desktop app.

Never falls back to the dev environment (``npm run tauri:dev``). That
path is explicit only via ``lausu --dev``. Production means the Tauri
host binary at an install path or a local ``src-tauri/target`` build.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

log = logging.getLogger("voice_typer.server.autostart_launcher")

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _host_binary_name() -> str:
    from voice_typer.server.platform_utils import is_macos, is_windows

    if is_macos():
        return "lausu-tauri"
    if is_windows():
        return "lausu-tauri.exe"
    return "lausu-tauri"


_LOCAL_TARGET_BINARIES = (
    _REPO_ROOT / "src-tauri" / "target" / "release" / _host_binary_name(),
    _REPO_ROOT / "src-tauri" / "target" / "debug" / _host_binary_name(),
)


def find_production_binary() -> str | None:
    """Locate the production Tauri host binary.

    Search order: installed paths (and ``VT_TAURI_BINARY``) first — those
    are the release/installed app — then a local ``src-tauri/target``
    build so a source checkout can run production without installing.
    """
    from voice_typer.server.autostart.tauri_spawn import _tauri_binary

    installed = _tauri_binary()
    if installed:
        return installed
    for cand in _LOCAL_TARGET_BINARIES:
        if cand.is_file():
            return str(cand)
    return None


def _is_local_build(binary: str) -> bool:
    try:
        resolved = Path(binary).resolve()
        target = (_REPO_ROOT / "src-tauri" / "target").resolve()
        resolved.relative_to(target)
        return True
    except (OSError, ValueError):
        return False


def launch_production(hidden: bool = False) -> int:
    """Spawn the production Tauri app. Returns a process exit code."""
    from voice_typer.server import autostart_launcher as launcher
    from voice_typer.server.autostart._spawn_env import (
        _launcher_child_env,
        _spawn_flags,
    )
    from voice_typer.server.autostart.tauri_spawn import (
        _spawn_login_child,
        _spawn_tauri_host,
    )

    binary = find_production_binary()
    if not binary:
        log.error(
            "[CLI] Production app binary not found. Install the app or build "
            "with `cargo tauri build`. Use `lausu --dev` only for the "
            "development environment."
        )
        print(
            "Production app binary not found.\n"
            "Install the app, or build the host (`cargo tauri build`).\n"
            "For the development environment use: lausu --dev",
            file=sys.stderr,
        )
        return 1

    if _is_local_build(binary):
        # Local target build: developer-owned artifact. Installed binaries
        # still go through the fail-closed manifest gate below.
        log.info("[CLI] launching local production build %s", binary)
        env = _launcher_child_env()
        if hidden:
            env["VT_START_HIDDEN"] = "1"
        flags: dict = {}
        flags.update(launcher._tauri_log_files())
        flags.update(_spawn_flags(hidden=hidden))
        child = _spawn_login_child(
            [binary],
            env=env,
            spawn_kwargs=flags,
            describe=f"local production tauri host {binary} (hidden={hidden})",
        )
        return 0 if child is not None else 1

    log.info("[CLI] launching installed production app %s", binary)
    child = _spawn_tauri_host(binary, hidden=hidden)
    return 0 if child is not None else 1


def launch_dev() -> int:
    """Explicit development environment (``npm run tauri:dev``)."""
    from voice_typer.server.autostart.dev_console import launch_dev_console

    log.info("[CLI] --dev: opening the development environment")
    return launch_dev_console("tauri:dev")

def _configure_launcher_logging() -> None:
    """Route the launcher's own records through the canonical terminal shape.

    ``logging.basicConfig`` cannot express C-LOG-1: ``%(levelname)s`` emits
    ``WARNING`` (7 chars) unpadded, so the message column shifts per level
    and the line does not match the app's own terminal output. Reuse the
    shared formatter instead of hand-rolling a format string (E7).

    Mirrors ``basicConfig``'s "do nothing if already configured" contract so
    a caller that configured logging first keeps its own handlers.
    """
    from voice_typer.server.log import _FlushingStreamHandler, _TerminalFormatter

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if root.handlers:
        return
    handler = _FlushingStreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(_TerminalFormatter())
    root.addHandler(handler)




def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lausu",
        description="Start the production desktop app (not the dev environment).",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="start the development environment (npm run tauri:dev) instead of production",
    )
    parser.add_argument(
        "--hidden",
        action="store_true",
        help="start with the main window hidden (tray only)",
    )
    args = parser.parse_args(argv)

    _configure_launcher_logging()

    if args.dev:
        return launch_dev()
    return launch_production(hidden=args.hidden)


if __name__ == "__main__":
    raise SystemExit(main())
