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


class YtdlpLogAdapter:
    """yt-dlp's logger protocol, mapped onto the app logger.

    yt-dlp routes ordinary informational output (its ``[extractor] ...``
    lines) through ``debug`` and only warnings/errors through the matching
    levels, so the mapping is deliberately one-to-one rather than
    "demote everything".
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or log

    def debug(self, msg: object) -> None:
        self._logger.debug("%s%s", _PREFIX, redact_extractor_message(msg))

    def info(self, msg: object) -> None:
        self._logger.info("%s%s", _PREFIX, redact_extractor_message(msg))

    def warning(self, msg: object) -> None:
        self._logger.warning("%s%s", _PREFIX, redact_extractor_message(msg))

    def error(self, msg: object) -> None:
        self._logger.error("%s%s", _PREFIX, redact_extractor_message(msg))


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
