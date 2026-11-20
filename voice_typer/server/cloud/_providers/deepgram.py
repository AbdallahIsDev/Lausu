"""SEC-005: query parameters (model, language) are URL-encoded to prevent
Deepgram ``/v1/listen`` URL building.
Extracted from the ``cloud_engines.py`` monolith. Pure shaping, no
query parameters or path segments via ``config.cloud_model`` (e.g.
``"&punctuate=false&smart_format=true"``).
"""

from __future__ import annotations

import re
from urllib.parse import urlencode

# A model/language value may only contain URL-safe token characters.
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._\-]+$")


def build_listen_url(api_url: str, model_name: str, language: str | None) -> str:
    """Build the Deepgram listen URL with encoded query parameters.

    ``language=None`` means Auto. Deepgram's own ``language`` default is
    ``en``, so omitting the parameter is NOT neutral: Auto asks for
    ``detect_language=true`` instead, which lets Deepgram identify the
    spoken language and transcribe in it.
    """
    if not _SAFE_TOKEN_RE.match(model_name or ""):
        raise RuntimeError(f"Deepgram model name {model_name!r} contains invalid characters")
    params: dict[str, str] = {"model": model_name}
    if language:
        if not _SAFE_TOKEN_RE.match(language):
            raise RuntimeError(f"Deepgram language {language!r} contains invalid characters")
        params["language"] = language
    else:
        params["detect_language"] = "true"
    # Trailing, so the query keeps its historical ``model&language&punctuate``
    # shape when a language is pinned.
    params["punctuate"] = "true"
    return f"{api_url}?{urlencode(params)}"
