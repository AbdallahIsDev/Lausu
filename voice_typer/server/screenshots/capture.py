"""Rect screen grab for the screenshot beta (Windows-only)."""

from __future__ import annotations

from pathlib import Path

MAX_WIDTH_DEFAULT = 1600


def is_supported() -> bool:
    from voice_typer.server.platform_utils import is_windows

    return is_windows()


def validate_rect(rect: object) -> tuple[int, int, int, int]:
    if not isinstance(rect, dict):
        raise ValueError("rect must be an object")
    try:
        left = int(rect["left"])
        top = int(rect["top"])
        width = int(rect["width"])
        height = int(rect["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("rect needs int left/top/width/height") from exc
    # Non-positive or absurd sizes are caller bugs, reject before grabbing.
    if width <= 0 or height <= 0 or width > 7680 or height > 4320:
        raise ValueError("rect width/height out of range")
    return left, top, width, height


def capture_rect(rect: dict, dest_path: Path, *, max_width: int = MAX_WIDTH_DEFAULT) -> dict:
    if not is_supported():
        raise RuntimeError("screenshot_unsupported")
    # Lazy import keeps Pillow out of cold startup on other platforms.
    from PIL import ImageGrab

    left, top, width, height = validate_rect(rect)
    img = ImageGrab.grab(bbox=(left, top, left + width, height))
    if img.width > max_width:
        # Downscale wide grabs so PNGs stay small enough to paste.
        ratio = max_width / img.width
        img = img.resize((max_width, max(1, int(img.height * ratio))))
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest_path, format="PNG", optimize=True)
    size = dest_path.stat().st_size
    return {"path": str(dest_path), "width": img.width, "height": img.height, "bytes": size}
