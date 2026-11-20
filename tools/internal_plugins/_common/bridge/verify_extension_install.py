"""Read-only check of the shared extension install.

Prints the stable install path, whether its synced files and generated config
are current, where Chrome's registration points, and the exact next step.
Never writes to the Chrome profile or the extension install path.

Run: .venv/Scripts/python.exe tools/internal_plugins/_common/bridge/verify_extension_install.py
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parents[3]) not in sys.path:
    sys.path.insert(0, str(HERE.parents[3]))

paths = importlib.import_module("tools.internal_plugins._common.bridge.install_paths")

REQUIRED = (
    "manifest.json",
    "content.js",
    "service_worker.js",
    "popup.html",
    "popup.js",
    "icons/icon-16.png",
    "icons/icon-32.png",
    "icons/icon-48.png",
    "icons/icon-128.png",
    "generated/config.js",
)


def _live_bridge_connected() -> bool:
    """True when the running Chrome's extension answers the daemon right now.

    Chrome flushes ``Secure Preferences`` lazily, so a freshly loaded unpacked
    extension is invisible to the file check until Chrome exits or rotates its
    prefs. A live ``/status`` answer is the authoritative "it is installed and
    loaded" signal and is what the user actually cares about.
    """
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{paths.PORT}/status", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except (OSError, ValueError):
        return False
    return payload.get("browser") == "connected"


def main() -> int:
    failed = 0

    def report(label: str, ok: bool, detail: str = "") -> None:
        nonlocal failed
        if not ok:
            failed += 1
        print(f"{'PASS' if ok else 'FAIL'}  {label}{'  -- ' + detail if detail else ''}")

    target = paths.stable_extension_dir()
    print(f"stable extension path (from {paths.AUTHORITY.name}): {target}")
    print(f"dictation profile: {paths.profile_dir()}")

    missing = [rel for rel in REQUIRED if not (target / rel).is_file()]
    report("all synced files are present", not missing, f"missing: {missing}" if missing else "")

    checker = HERE / "tools" / "build-extension.js"
    try:
        result = subprocess.run(["node", str(checker), "--check"], capture_output=True, text=True, timeout=30)
        ok = result.returncode == 0
        detail = (result.stdout or result.stderr).strip().splitlines()[-1] if (result.stdout or result.stderr) else ""
    except (OSError, subprocess.SubprocessError) as exc:
        ok, detail = False, str(exc)
    report("source generated config matches token/wsUrl/platform maps", ok, detail)

    source_config = HERE / "extension" / "generated" / "config.js"
    installed_config = target / "generated" / "config.js"
    if source_config.is_file() and installed_config.is_file():
        same = source_config.read_bytes() == installed_config.read_bytes()
    else:
        same = False
    report("installed generated config matches the source", same)

    registered = paths.registered_extension_path()
    live = _live_bridge_connected()
    registered_here = registered is not None and Path(registered).resolve() == target.resolve()
    if registered_here:
        report("Chrome registration", True, str(registered))
    elif live:
        report(
            "Chrome registration",
            True,
            "loaded in the running Chrome (Chrome has not flushed Secure Preferences yet)",
        )
    elif registered is None:
        report("Chrome registration", False, "not registered")
    else:
        report("Chrome registration", False, f"points at {registered}")

    if paths.points_into_repo(registered):
        report(
            "registration is outside the repo",
            False,
            f"{registered} points into {paths.repo_root()}; load unpacked from {target}",
        )

    print()
    duplicates = paths.duplicate_registration_count(
        paths.profile_dir() / paths.PROFILE_DIRECTORY / "Secure Preferences", target
    )
    if duplicates > 1:
        print(
            f"NOTE: {duplicates} entries point at this folder; Chrome keeps the id it was "
            "loaded with, so remove the extra entry in chrome://extensions."
        )

    if live and not registered_here:
        print("NEXT: nothing to load -- the extension is installed and answering.")
    elif not live and not registered:
        print("NEXT: open chrome://extensions in the dictation profile -> Developer mode ->")
        print(f"      Load unpacked -> {target}")
    elif not live and registered and Path(registered).resolve() != target.resolve():
        print("NEXT: remove the old extension entry in chrome://extensions, then Load unpacked ->")
        print(f"      {target}")
    elif failed:
        print("NEXT: start the app once so the daemon re-syncs the extension, then reload it in")
        print("      chrome://extensions. Re-run this verifier.")
    else:
        print("NEXT: reload the extension in chrome://extensions after any extension change, then")
        print("      restart the dictation Chrome window so the multi-site manifest takes effect.")

    print(f"\n{'install is healthy' if failed == 0 else f'{failed} check(s) failed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
