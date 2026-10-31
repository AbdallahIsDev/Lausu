"""Tier-1/2 fallback: temp audio-only download via yt-dlp (ADR-0023 E9).

When direct streaming stalls (STREAM_STALLED) or the signed URL expires
(URL_EXPIRED) past one inline re-resolve, the audio is downloaded to a
temp file instead. Cleanup is guaranteed by the caller's context manager.
"""

from __future__ import annotations

import contextlib
import logging
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from voice_typer.server.media_ingest.errors import DOWNLOAD_FAILED, MediaIngestError
from voice_typer.server.media_ingest.ytdlp_log import extractor_options

log = logging.getLogger(__name__)

#: Fixed on-disk name. The title is attacker/author-controlled text (path
#: separators, 200-char unicode, a trailing dot on Windows) and naming the
#: temp file after it made the download itself a filesystem hazard.
DOWNLOAD_TEMPLATE = "media.%(ext)s"
#: Floor for a stuck CDN socket; the extractor default is unlimited.
SOCKET_TIMEOUT_SECONDS = 20


def _download_with_verdict(downloader: Any, url: str) -> dict[str, Any] | None:
    """Run the download and return the extractor's own verdict.

    ``extract_info(..., download=True)`` hands back the post-download info,
    whose ``requested_downloads[0]`` names the format actually written. A
    double that only exposes ``download()`` still works (verdict unknown).
    """
    extract = getattr(downloader, "extract_info", None)
    if callable(extract):
        info = extract(url, download=True)
        return info if isinstance(info, dict) else None
    downloader.download([url])
    return None


def _requested_download(info: dict[str, Any] | None) -> dict[str, Any]:
    """The format entry the extractor says it wrote (empty when unknown)."""
    if not isinstance(info, dict):
        return {}
    requested = info.get("requested_downloads")
    if isinstance(requested, list) and requested and isinstance(requested[0], dict):
        return requested[0]
    return info


def _download_bytes(entry: dict[str, Any], target: Path) -> int:
    """Size the info reports, else the file on disk."""
    for key in ("filesize", "filesize_approx"):
        value = entry.get(key)
        if isinstance(value, int) and value > 0:
            return value
    try:
        return target.stat().st_size
    except OSError:
        return 0


@contextlib.contextmanager
def temp_audio_download(
    url: str,
    *,
    factory: Callable[..., Any] | None = None,
    on_progress: Callable[[float], None] | None = None,
    js_runtimes: dict[str, dict[str, str]] | None = None,
) -> Iterator[Path]:
    """Download audio-only to a temp file; delete it on exit.

    Yields the downloaded file path. ``on_progress`` receives the
    download fraction (0-1) so the job can publish a download phase.
    """
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise MediaIngestError(DOWNLOAD_FAILED, "media downloader unavailable") from exc

    def _hook(status: dict[str, Any]) -> None:
        if on_progress is None or status.get("status") != "downloading":
            return
        total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
        done = status.get("downloaded_bytes") or 0
        if total and done:
            on_progress(min(1.0, float(done) / float(total)))

    options: dict[str, Any] = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "extractor_retries": 2,
        "socket_timeout": SOCKET_TIMEOUT_SECONDS,
        "continuedl": True,
        "windowsfilenames": True,
        "restrictfilenames": False,
        "progress_hooks": [_hook],
    }
    options.update(extractor_options(log))
    if js_runtimes:
        options["js_runtimes"] = js_runtimes

    maker = factory or (lambda opts: YoutubeDL(opts))
    with tempfile.TemporaryDirectory(prefix="lausu_media_") as tmp:
        out_dir = Path(tmp)
        options["outtmpl"] = str(out_dir / DOWNLOAD_TEMPLATE)
        before = set(out_dir.iterdir())
        info: dict[str, Any] | None = None
        try:
            downloader = maker(options)
            if hasattr(downloader, "__enter__"):
                with downloader as active:
                    info = _download_with_verdict(active, url)
            else:
                info = _download_with_verdict(downloader, url)
        except MediaIngestError:
            raise
        except Exception as exc:
            raise MediaIngestError(DOWNLOAD_FAILED, f"audio download failed: {exc}") from exc
        produced = [p for p in set(out_dir.iterdir()) - before if p.is_file()]
        if not produced:
            raise MediaIngestError(DOWNLOAD_FAILED, "audio download produced no file")
        target = max(produced, key=lambda p: p.stat().st_size)
        # One auditable line: ``vcodec=none`` is the extractor's own proof that
        # no video was fetched (the ``.mp4`` name is a forced HLS label).
        entry = _requested_download(info)
        log.info(
            "[MEDIA] download: format=%s ext=%s vcodec=%s acodec=%s bytes=%d",
            str(entry.get("format_id") or "-"),
            str(entry.get("ext") or target.suffix.lstrip(".") or "-"),
            str(entry.get("vcodec") or "-"),
            str(entry.get("acodec") or "-"),
            _download_bytes(entry, target),
        )
        yield target
