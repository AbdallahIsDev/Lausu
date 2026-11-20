"""Attach the real bubble visibility policy to a MagicMock bubble.

This keeps existing call-site tests asserting real show/hide behavior while
the decision itself moved into the single ``WaveformBubble`` policy.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from voice_typer.server.waveform import WaveformBubble


def attach_policy(bubble: MagicMock, behavior: str) -> None:
    real = WaveformBubble()
    real.set_behavior_provider(lambda: behavior)
    real.on_show = bubble.show
    real.on_hide = bubble.hide
    real.on_set_state = bubble.set_state
    bubble.apply_visibility.side_effect = real.apply_visibility
