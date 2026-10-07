"""Screenshot capture tests (mocked grab, no real screen)."""

from pathlib import Path

import pytest
from PIL import Image
from voice_typer.server.screenshots import capture


def test_validate_rect_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        capture.validate_rect({"left": 0, "top": 0, "width": 0, "height": 10})
    with pytest.raises(ValueError):
        capture.validate_rect("nope")


def test_capture_unsupported_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(capture, "is_supported", lambda: False)
    with pytest.raises(RuntimeError, match="screenshot_unsupported"):
        capture.capture_rect({"left": 0, "top": 0, "width": 10, "height": 10}, Path("x.png"))


@pytest.mark.real_pil
def test_capture_saves_and_downscales(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(capture, "is_supported", lambda: True)
    from PIL import ImageGrab

    monkeypatch.setattr(ImageGrab, "grab", lambda bbox=None: Image.new("RGB", (3200, 100)))
    dest = tmp_path / "shot-1.png"
    out = capture.capture_rect({"left": 0, "top": 0, "width": 3200, "height": 100}, dest)
    assert out["width"] == 1600
    assert dest.exists()
    assert out["bytes"] > 0
