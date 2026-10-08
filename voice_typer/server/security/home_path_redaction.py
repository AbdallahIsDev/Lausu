"""Home-directory prefix redaction (privacy scrub for logs/exports).

Extracted verbatim from :mod:`voice_typer.server.security.redaction`
(callers import these names from that facade). Provides whole-string path
redaction plus the embedded-in-text variant used by the log filter and
the diagnostic-export pipeline.
"""

from __future__ import annotations

import os
import re


def _resolve_home_dirs() -> list[str]:
    """Return candidate home directories, most-specific first.

    Includes the explicit ``HOME`` env override (honoured on EVERY
    platform, :func:`ntpath.expanduser` ignores ``HOME`` on Windows,
    preferring ``USERPROFILE``, which silently defeats redaction when
    ``HOME`` is explicitly overridden) plus the platform-resolved home
    (``USERPROFILE`` on Windows). Redacting against BOTH candidates
    means an explicit override AND the platform default are both
    protected: e.g. under Git-Bash on Windows, ``HOME`` may be the
    POSIX-style ``/c/Users/alice`` while real log paths are
    ``C:\\Users\\alice\\…``; checking both covers that case.

    Deduplicated, non-empty values only. Returns ``[]`` when no home
    can be resolved (callers treat that as "home unknown" and return
    the input unchanged).
    """
    homes: list[str] = []
    env_home = os.environ.get("HOME")
    if env_home:
        homes.append(env_home)
    try:
        resolved = os.path.expanduser("~")
    except (KeyError, RuntimeError):
        resolved = ""
    if resolved and resolved not in homes:
        homes.append(resolved)
    return homes


def _redact_home_path(path: str | os.PathLike[str]) -> str:
    """Replace the user-home prefix in ``path`` with ``~``.

    filesystem paths embedded in the diagnostic bundle
        (``sentinel_path``, ``pid_file_path``, ``bundle_path``) leak the
        OS username via the home-directory prefix
        (e.g. ``/Users/alice/.lausu/…`` on macOS,
        ``C:\\Users\\alice\\…`` on Windows, ``/home/alice/…`` on Linux).
        Replacing the home prefix with ``~`` preserves the path structure
        (so support engineers can still see "this is under the config
        dir", "this is a relative path", "this is on a different drive")
        without leaking the username.

        The home directory is resolved at call time via
        :func:`_resolve_home_dirs` (explicit ``HOME`` override + the
        platform default). On platforms where no home can be determined,
        the path is returned unchanged (we never *introduce* a ``~``
        that wasn't a real prefix substitution).

        Comparison is case-insensitive on Windows (NTFS is case-
        insensitive; ``HOMEDRIVE`` / ``HOMEPATH`` / ``USERPROFILE`` can
        vary by case between processes) and case-sensitive on POSIX
        (where the home dir is stable per-user).

        Parameters
        ----------
        path : str or os.PathLike
            The filesystem path to redact. ``PathLike`` inputs are
            stringified via :func:`os.fspath`.

        Returns
        -------
        str
            ``path`` with the user-home prefix replaced by ``~``. If no
            home dir can be resolved, or ``path`` does not start with
            one, ``path`` is returned unchanged (stringified).
    """
    s = os.fspath(path) if not isinstance(path, str) else path
    s_norm = os.path.normpath(s)
    for home in _resolve_home_dirs():
        if not home or home == "~":
            continue
        home_norm = os.path.normpath(home)
        # ``os.path.normpath`` collapses ``//`` → ``/`` on POSIX and
        if os.name == "nt":
            if s_norm.lower().startswith(home_norm.lower()):
                return "~" + s_norm[len(home_norm) :]
        else:
            if s_norm.startswith(home_norm):
                return "~" + s_norm[len(home_norm) :]
    return s

# Cache for the home-path-substring regex, keyed by the resolved home
_HOME_PATH_RE_CACHE: tuple[tuple[str, ...], list[re.Pattern[str]]] | None = None

def _redact_home_path_in_text(text: str) -> str:
    """Replace home-directory path prefixes embedded anywhere in *text*.

    :func:`voice_typer.server._secrets._redact_home_path` only redacts
    when the *entire* input string is a single filesystem path under the
    home dir (it checks ``s.startswith(home)``).  Log messages, by
    contrast, embed paths inside larger sentences (e.g.
    ``"Opening log file: /home/alice/.lausu/foo.log"``), so the
    whole-string check returns the input unchanged and the OS username
    leaks to ``lausu.log``.

    This helper scans *text* for substrings that start with the home
    directory followed by a path separator and applies
    :func:`_redact_home_path` to each match -- replacing the home-dir
    prefix with ``~`` while preserving the rest of the path.  The regex
    is compiled once per unique home dir and cached.
    """
    global _HOME_PATH_RE_CACHE
    # Candidate homes: the explicit ``HOME`` override first (honoured on
    homes = _resolve_home_dirs()
    if not homes:
        return text
    key = tuple(homes)
    if _HOME_PATH_RE_CACHE is None or _HOME_PATH_RE_CACHE[0] != key:
        patterns: list[re.Pattern[str]] = []
        flags = re.IGNORECASE if os.name == "nt" else 0
        for home in homes:
            if not home or home == "~":
                continue
            # Match the home dir followed by a path separator and any
            patterns.append(re.compile(re.escape(home) + r"[/\\]\S*", flags))
        _HOME_PATH_RE_CACHE = (key, patterns)
    for pattern in _HOME_PATH_RE_CACHE[1]:
        text = pattern.sub(lambda m: _redact_home_path(m.group()), text)
    return text
