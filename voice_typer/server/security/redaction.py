"""Secret + PII redaction facade (public import surface).

Every name this module used to define now lives in a focused sibling and
is re-exported here so historical imports keep resolving:

* :mod:`voice_typer.server.security.secret_patterns` (regex tables +
  public-vocabulary exemptions),
* :mod:`voice_typer.server.security.secret_redaction`
  (``redact_secret`` / ``redact_api_keys`` / ``redact_url``),
* :mod:`voice_typer.server.security.home_path_redaction`
  (home-directory prefix scrub),
* :mod:`voice_typer.server.security.pii_redaction`
  (``_redact_text`` / ``PIIRedactionFilter`` / ``redact_pii`` /
  ``install_lastresort_pii_filter``),
* :mod:`voice_typer.server.security.export_redaction`
  (``redact_for_export``).

Historical note: hosts the redaction half of the former
``voice_typer.server._secrets`` module (API-key / bearer-token /
flag-form / URL-userinfo / home-path redaction) merged with the PII
redaction filter from the former ``voice_typer.server.security`` module
(``PIIRedactionFilter``, ``redact_pii``, ``install_lastresort_pii_filter``).
The URL-allowlist half of the former ``_secrets.py`` lives in
:mod:`voice_typer.server.security.url_allowlist`; the model-integrity
half of the former ``security.py`` lives in
:mod:`voice_typer.server.security.model_integrity`.

Importing this module installs the last-resort PII filter.
"""

from __future__ import annotations

import logging

from voice_typer.server.security.export_redaction import redact_for_export  # noqa: F401  # facade re-export
from voice_typer.server.security.home_path_redaction import (  # noqa: F401  # facade re-export
    _HOME_PATH_RE_CACHE,
    _redact_home_path,
    _redact_home_path_in_text,
    _resolve_home_dirs,
)
from voice_typer.server.security.pii_redaction import (  # noqa: F401  # facade re-export
    _CONTROL_CHAR_RE,
    _FAST_TRIGGER,
    PIIRedactionFilter,
    _escape_control_chars,
    _redact_text,
    install_lastresort_pii_filter,
    redact_pii,
)
from voice_typer.server.security.secret_patterns import (  # noqa: F401  # facade re-export
    _BARE_KEY_VALUE_PATTERN,
    _BINARY_LABEL_RE,
    _DASH_JOINED_FULL_RE,
    _FLAG_KEY_PATTERNS,
    _FLAG_VALUE_PATTERN,
    _HASH_LABEL_RE,
    _KEY_PATTERNS,
    _KEYWORD_ALT,
    _MIN_REDACT_LEN,
    _PROPSET_LABEL_RE,
    _PUBLIC_CONFIG_FIELD_NAMES_CACHE,
    _PUBLIC_ENV_VAR_NAMES,
    _PUBLIC_IPC_COMMAND_NAMES_CACHE,
    _SECRET_KEYWORDS,
    _TEARDOWN_LABEL_RE,
    _THREAD_LABEL_RE,
    _flag_sub,
    _public_config_field_names,
    _public_ipc_command_names,
)
from voice_typer.server.security.secret_redaction import (  # noqa: F401  # facade re-export
    redact_api_keys,
    redact_secret,
    redact_url,
)

log = logging.getLogger(__name__)


# Install at import time so the protection is in place as soon as the
install_lastresort_pii_filter()
