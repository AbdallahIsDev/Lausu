"""Route yt-dlp extractor output into the app log (ADR-0023 addendum).

yt-dlp writes progress and diagnostics straight to stdout/stderr unless it
is handed a ``logger`` object implementing ``debug``/``info``/``warning``/
``error``. A sidecar has no console, so that output was simply lost, and
when it did surface (an extractor printing an error) it carried raw URLs
with signed query strings and cookie/header dumps.

This adapter is the single place those messages enter our logging: one
formatted record per message, prefixed ``[YTDLP] ``, with URLs redacted and
secrets masked. Nothing is ever written to a stream.
"""

from __future__ import annotations

import logging
import re
from typing import Final

from voice_typer.server.security.secret_redaction import redact_secret, redact_url

log = logging.getLogger(__name__)

_PREFIX: Final[str] = "[YTDLP] "
_URL_RE = re.compile(r"https?://[^\s'\"<>()]+")


def redact_extractor_message(message: object) -> str:
    """Redact URLs and secrets in one extractor message.

    Signed CDN links carry their credential in the query string, so the
    whole URL goes through :func:`redact_url` (userinfo + query secrets)
    before the generic secret pass.
    """

    text = str(message)

    def _redact_match(match: re.Match[str]) -> str:
        return redact_url(match.group(0))

    redacted = _URL_RE.sub(_redact_match, text)
    return redact_secret(redacted)


# Extractor noise for THIS app: yt-dlp ffmpeg fixups for containers libav
# (PyAV) decodes natively, and we ship no ffmpeg on purpose. Matched on a
# stable substring, never by level — a blanket demotion would hide real ones.
_HARMLESS_MESSAGES: Final[tuple[tuple[str, str], ...]] = (
    ("writing DASH m4a", "DASH m4a"),
    ("Only some players support this container", "DASH m4a container"),
    ("Possible MPEG-TS in MP4 container or malformed AAC timestamps", "MPEG-TS in MP4"),
    ("Possible duplicate MOOV atoms", "duplicate MOOV"),
)


def harmless_reason(message: object) -> str | None:
    """Reason this extractor message is not actionable, or ``None``."""
    lowered = str(message).lower()
    for needle, reason in _HARMLESS_MESSAGES:
        if needle.lower() in lowered:
            return reason
    return None


class YtdlpLogAdapter:
    """yt-dlp's logger protocol, mapped onto the app logger.

    yt-dlp routes ordinary informational output (its ``[extractor] ...``
    lines) through ``debug``, so the mapping stays one-to-one for those.
    Two exceptions, both deliberate:

    * ``error`` is a WARNING: the app classifies extractor failures itself
      (``no_media_url``, ``login_required``, ...), and that verdict is the line
      that carries the real severity. An ERROR here meant two ERROR lines plus
      a traceback for what is really user input.
    * a short table of ffmpeg-fixup warnings goes to ``debug`` as one fixed
      classification (see ``_HARMLESS_MESSAGES``): libav decodes those
      containers natively, so no fixup and no ffmpeg is needed.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or log

    def debug(self, msg: object) -> None:
        self._logger.debug("%s%s", _PREFIX, redact_extractor_message(msg))

    def info(self, msg: object) -> None:
        self._logger.info("%s%s", _PREFIX, redact_extractor_message(msg))

    def warning(self, msg: object) -> None:
        text = redact_extractor_message(msg)
        reason = harmless_reason(text)
        if reason is not None:
            # One fixed short line per downgrade. Echoing yt-dlp's sentence
            # (and its "Install ffmpeg" tail) read as action the user must take.
            self._logger.debug("%scontainer note: %s (harmless, no ffmpeg needed)", _PREFIX, reason)
            return
        self._logger.warning("%s%s", _PREFIX, text)

    def error(self, msg: object) -> None:
        self.warning(msg)


def extractor_options(logger: logging.Logger | None = None) -> dict[str, object]:
    """Options every ``YoutubeDL`` in this package is constructed with.

    ``no_color`` keeps ANSI escapes out of the file log (the app's own
    colouring is a formatter concern, C-LOG-1) and ``noprogress`` stops the
    progress renderer from emitting non-log garbage.
    """

    return {
        "logger": YtdlpLogAdapter(logger),
        "no_color": True,
        "noprogress": True,
    }
