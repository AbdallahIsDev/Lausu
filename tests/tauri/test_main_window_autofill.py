"""The main WebView must not offer browser-level general autofill.

WebView2 "Saved info" suggestions ignore `autocomplete="off"` on input
elements. Tauri 2.12+ exposes `generalAutofillEnabled` per window; the main
window turns it off so the Media link field never gets an OS-styled dropdown.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_main_window_disables_general_autofill() -> None:
    config = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    main = next(window for window in config["app"]["windows"] if window.get("label") == "main")
    assert main.get("generalAutofillEnabled") is False
