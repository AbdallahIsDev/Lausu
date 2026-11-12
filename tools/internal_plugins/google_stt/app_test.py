# Internal plugin in-app test harness: boots the app with the plugin gate open,
# toggles the dictation entry point (the same one the hotkey calls), and
# logs to a file so detached runs are inspectable. Not part of the product.
import os
import sys
import time
from pathlib import Path

os.environ["VOICE_TYPER_INTERNAL_PLUGINS"] = "1"
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG = Path(__file__).with_name("debug") / "app_test.log"
STOP_MARKER = Path(__file__).with_name("STOP")


def say(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def main() -> int:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        LOG.write_text("", encoding="utf-8")
        STOP_MARKER.unlink(missing_ok=True)
        say("log reset")
        return 0
    from voice_typer.server import internal_plugin_hook
    from voice_typer.server.app import LausuApp

    say(f"gate={internal_plugin_hook.plugins_enabled()}")
    app = LausuApp()
    say(f"installed={internal_plugin_hook.install(app)} toggle={app.toggle_dictation}")
    if len(sys.argv) > 1 and sys.argv[1] == "boot":
        say("boot ok")
        return 0
    say("START")
    app.toggle_dictation()
    STOP_MARKER.unlink(missing_ok=True)
    for _ in range(120):
        if STOP_MARKER.exists():
            break
        time.sleep(0.5)
    say("STOP")
    app.toggle_dictation()
    time.sleep(3.0)
    say("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
