"""Secure file I/O facade (public import surface).

Every name this module used to define now lives in a focused sibling and
is re-exported here so historical imports keep resolving:

* :mod:`voice_typer.server.security.atomic_write`
  (``_secure_atomic_write`` / ``_windows_fsync_directory`` /
  ``_chmod_owner_only`` + the Windows replace-retry constants),
* :mod:`voice_typer.server.security.secure_read` (``_secure_read_text`` /
  ``_read_with_byte_limit`` / ``_DEFAULT_MAX_READ_BYTES``),
* :mod:`voice_typer.server.security.persisted_json`
  (``PersistedJSON`` + ``_QUARANTINE_SUFFIX_SEQ``).

Existing patch seams keep working: ``config`` /
``voice_typer.server.secure_file_io`` re-export these names, and
``_secure_atomic_write`` resolves ``_chmod_owner_only`` through this
facade at call time (tests monkeypatch it here).
"""

from __future__ import annotations

import logging

from voice_typer.server.security.atomic_write import (  # noqa: F401  # facade re-export
    _OS_REPLACE_MAX_ATTEMPTS,
    _OS_REPLACE_RETRY_DELAY_S,
    _chmod_owner_only,
    _secure_atomic_write,
    _windows_fsync_directory,
)
from voice_typer.server.security.persisted_json import (  # noqa: F401  # facade re-export
    _QUARANTINE_SUFFIX_SEQ,
    PersistedJSON,
    T,
)
from voice_typer.server.security.secure_read import (  # noqa: F401  # facade re-export
    _DEFAULT_MAX_READ_BYTES,
    _read_with_byte_limit,
    _secure_read_text,
)

log = logging.getLogger("voice_typer.server.config")
