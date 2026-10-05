"""Cross-layer pin: the backend default must be a value the UI actually offers.

The idle-unload window is written by the renderer (Settings -> General) and
read by the scheduler in ``model_manager._lifecycle``. Nothing in either
process forces the two to agree, so a default of, say, 45 would ship a
blank-looking dropdown (no SelectItem matches) with no error anywhere.
This test reads the renderer's option list as source text and asserts the
Python default is a member of it.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OPTIONS_TS = REPO_ROOT / "voice_typer" / "client" / "src" / "renderer" / "src" / "lib" / "utils" / "modelIdleUnload.ts"


def _offered_values() -> list[int]:
    text = OPTIONS_TS.read_text(encoding="utf-8")
    return [int(v) for v in re.findall(r"value:\s*(\d+)", text)]


class TestIdleUnloadDefaultIsOffered:
    def test_backend_default_is_one_of_the_ui_options(self):
        from voice_typer.server.config import Config

        default = Config().model_idle_unload_minutes
        offered = _offered_values()
        assert default in offered, (
            f"backend default model_idle_unload_minutes={default} is not one of the "
            f"dropdown options {offered}; the Select would render an empty trigger"
        )

    def test_dropdown_order_is_exactly_as_specified(self):
        # 15/30/60/90/120 ascending, then Never (0) last. 5 is deliberately
        # absent: it evicts the model during an ordinary pause.
        assert _offered_values() == [15, 30, 60, 90, 120, 0]

    def test_floor_and_ceiling_are_respected(self):
        numeric = [v for v in _offered_values() if v > 0]
        assert min(numeric) == 15, "5 minutes is not a real choice; floor is 15"
        assert max(numeric) == 120, "ceiling is 120"
