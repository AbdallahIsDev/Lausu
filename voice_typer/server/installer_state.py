"""Read the slim-core installer's ``installer-state.json`` (pack split §4.8).

Written by ``scripts/windows/installer-hooks.nsh`` (checkbox) and
``scripts/windows/full-offline-installer.nsi`` (``pack_bundled: true``).
Schema::

    {
      "include_offline_engine_pack": bool,
      "installer_version": str,
      "pack_bundled": bool
    }

Used at launch to decide whether the silent pack download may start.
"""

from __future__ import annotations

import json
import logging
import os
import sys  # noqa: F401  # re-exported for tests (installer_state.sys)
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class InstallerState:
    """Parsed ``installer-state.json``. Missing file → defaults."""

    include_offline_engine_pack: bool = True
    pack_bundled: bool = False
    installer_version: str | None = None
    source: str | None = None


def _as_bool(value: Any, default: bool) -> bool:
    """Strict bool parse. ``bool("false")`` is True in Python — reject that."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return default


def installer_state_path() -> Path:
    """Canonical path of the installer-written state file.

    Windows honours ``LOCALAPPDATA`` (folder redirection / roaming setups)
    instead of assuming ``%USERPROFILE%\\AppData\\Local``.
    """
    from voice_typer.server.platform_utils import is_windows

    if is_windows():
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else (Path.home() / "AppData" / "Local")
        base = base / "lausu"
    else:
        # Non-Windows installs have no NSIS Components page; the path is
        # still the documented location so tests and tooling can write it.
        base = Path.home() / ".local" / "share" / "lausu"
    return base / "installer-state.json"


def load_installer_state(path: Path | None = None) -> InstallerState:
    """Load installer state. Corrupt/missing file → safe defaults (download allowed)."""
    target = path if path is not None else installer_state_path()
    try:
        raw = target.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return InstallerState(source=str(target))
    except OSError as exc:
        log.warning("[INSTALLER] installer-state.json unreadable (%s); using defaults", exc)
        return InstallerState(source=str(target))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("[INSTALLER] installer-state.json not JSON (%s); using defaults", exc)
        return InstallerState(source=str(target))
    if not isinstance(data, dict):
        log.warning("[INSTALLER] installer-state.json is not an object; using defaults")
        return InstallerState(source=str(target))
    version = data.get("installer_version")
    return InstallerState(
        include_offline_engine_pack=_as_bool(data.get("include_offline_engine_pack"), True),
        pack_bundled=_as_bool(data.get("pack_bundled"), False),
        installer_version=version if isinstance(version, str) else None,
        source=str(target),
    )


def pack_download_allowed(
    state: InstallerState | None = None,
    *,
    pack_present: bool | None = None,
) -> bool:
    """True when the silent pack download may run.

    - ``include_offline_engine_pack=False`` (user unticked the checkbox):
      skip — explicit opt-out wins even if the pack vanished later.
    - ``pack_bundled=True`` AND pack already on disk: skip (full-offline
      extract succeeded; nothing to fetch).
    - ``pack_bundled=True`` AND pack NOT on disk: ALLOW — the wrapper's
      extract failed or a cleaner deleted the pack; do not strand the user.
    - Otherwise: allowed (always-on product decision).
    """
    st = state if state is not None else load_installer_state()
    if not st.include_offline_engine_pack:
        return False
    if st.pack_bundled:
        if pack_present is None:
            # Unknown: assume the bundled pack is there (historical
            # behaviour) so a present full-offline install never re-downloads.
            return False
        return not pack_present
    return True
