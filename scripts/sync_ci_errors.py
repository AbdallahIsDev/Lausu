#!/usr/bin/env python3
"""Best-effort, offline-safe sync of the local CI-errors.md from origin/ci-reports.

Design contract
---------------
* Fetch ONLY ``+refs/heads/ci-reports:refs/remotes/origin/ci-reports`` (no tags,
  no prune, no index/HEAD/other-ref writes, no working-tree writes other than
  the single local ``CI-errors.md``).  ``GIT_OPTIONAL_LOCKS=0`` keeps git from
  even taking optional index locks.
* Read the file with ``git show origin/ci-reports:CI-errors.md`` and install it
  atomically (temp file in the same directory + ``os.replace``).  An identical
  file is never rewritten (mtime untouched).
* Everything that can legitimately go wrong away from a developer machine --
  offline, unauthenticated, missing branch, missing file, git not installed,
  timeout -- is a silent no-op with exit code 0.  ``--verbose`` turns those
  no-ops into one-line diagnostics on stderr; normal operation is silent.
* ``--check`` never writes.  It prints ``CI-errors.md: MATCH`` or
  ``CI-errors.md: MISMATCH`` and exits 1 only on a real mismatch.  If the
  remote could not be read (offline / auth / missing branch / missing file),
  ``--check`` also exits 0 and prints NOTHING -- "no data" is not a mismatch,
  so hooks and lightweight CI gates never fail just because the network is
  down.  A missing *local* file with a readable remote IS a mismatch.

Stdlib only, cross-platform (Windows / macOS / Linux).
"""

from __future__ import annotations

import argparse
import contextlib
import os
import stat
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

FETCH_REFSPEC = "+refs/heads/ci-reports:refs/remotes/origin/ci-reports"
REMOTE_FILESPEC = "origin/ci-reports:CI-errors.md"
LOCAL_FILENAME = "CI-errors.md"
DEFAULT_FETCH_TIMEOUT = 20.0
HOOK_FETCH_TIMEOUT = 3.0
PROBE_TIMEOUT = 5.0
MATCH_LINE = "CI-errors.md: MATCH"
MISMATCH_LINE = "CI-errors.md: MISMATCH"


class SyncError(Exception):
    """Internal failure while running git or writing the local file."""


def _log(verbose: bool, message: str) -> None:
    if verbose:
        print(f"[sync_ci_errors] {message}", file=sys.stderr)


def _git_env() -> dict[str, str]:
    """Env that cannot prompt for credentials or grab an index lock."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    return env


def _creation_flags() -> int:
    if sys.platform == "win32":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def run_git(args: Sequence[str], cwd: Path, timeout: float, verbose: bool) -> subprocess.CompletedProcess[bytes]:
    """Run git with captured output.  Non-zero rc is returned, not raised."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            timeout=timeout,
            capture_output=True,
            env=_git_env(),
            creationflags=_creation_flags(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        _log(verbose, f"git {args[0]} timed out after {timeout:g}s")
        raise SyncError(f"git {args[0]} timed out") from exc
    except OSError as exc:
        _log(verbose, f"cannot run git: {exc}")
        raise SyncError("git unavailable") from exc


def find_repo_root(start: Path | None = None, verbose: bool = False) -> Path | None:
    """Resolve the repo root without changing directories or touching state."""
    probe_from = start if start is not None else Path.cwd()
    try:
        probe = run_git(["rev-parse", "--show-toplevel"], probe_from, PROBE_TIMEOUT, verbose)
    except SyncError:
        probe = None
    if probe is not None and probe.returncode == 0:
        return Path(os.fsdecode(probe.stdout).strip())
    # Fallback for a copied script running outside a worktree.
    fallback = Path(__file__).resolve().parent.parent
    if (fallback / ".git").exists():
        return fallback
    return None


def read_remote(repo_root: Path, timeout: float, verbose: bool) -> bytes | None:
    """Return raw blob bytes, or None when the ref/file is unavailable."""
    result = run_git(["show", REMOTE_FILESPEC], repo_root, timeout, verbose)
    if result.returncode != 0:
        detail = os.fsdecode(result.stderr).strip().splitlines()
        _log(verbose, f"git show unavailable: {detail[0] if detail else 'no detail'}")
        return None
    return result.stdout


def atomic_write(path: Path, data: bytes) -> bool:
    """Install ``data`` at ``path`` atomically.  True iff bytes were written."""
    try:
        existing = path.read_bytes()
    except FileNotFoundError:
        existing = None
    except OSError as exc:
        raise SyncError(f"cannot read {path.name}: {exc}") from exc
    if existing == data:
        return False

    parent = path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=".CI-errors-", suffix=".tmp", dir=str(parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if existing is not None:
            with contextlib.suppress(OSError):
                os.chmod(tmp_name, stat.S_IMODE(path.stat().st_mode))
        os.replace(tmp_name, path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise SyncError(f"cannot write {path.name}: {exc}") from exc
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync CI-errors.md from origin/ci-reports (silent, offline-safe).")
    parser.add_argument("-v", "--verbose", action="store_true", help="diagnostics on stderr")
    parser.add_argument(
        "--check",
        action="store_true",
        help="never write; MATCH/MISMATCH on stdout, exit 1 only on a real mismatch "
        "(offline/unavailable remote is a silent no-op with exit 0)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_FETCH_TIMEOUT,
        metavar="SECONDS",
        help=f"git fetch/show timeout in seconds (default: {DEFAULT_FETCH_TIMEOUT:g}, "
        f"hooks use {HOOK_FETCH_TIMEOUT:g})",
    )
    parser.add_argument(
        "--repo",
        metavar="DIR",
        help=argparse.SUPPRESS,  # test/integration escape hatch; not part of the public CLI.
    )
    args = parser.parse_args(argv)

    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    verbose = args.verbose
    timeout = args.timeout
    start = Path(args.repo) if args.repo else None

    try:
        repo_root = find_repo_root(start, verbose)
        if repo_root is None:
            _log(verbose, "not inside a git worktree - no-op")
            return 0
        _log(verbose, f"repo root: {repo_root}")

        fetch_args = ["fetch", "--quiet", "--no-tags", "origin", FETCH_REFSPEC]
        _log(verbose, "fetch command: " + " ".join(["git", *fetch_args]))
        try:
            fetch = run_git(
                fetch_args,
                repo_root,
                timeout,
                verbose,
            )
        except SyncError:
            _log(verbose, "fetch failed - silent no-op")
            return 0
        if fetch.returncode != 0:
            detail = os.fsdecode(fetch.stderr).strip().splitlines()
            _log(
                verbose,
                f"fetch rejected (rc={fetch.returncode}): {detail[0] if detail else 'no detail'} - silent no-op",
            )
            return 0
        _log(verbose, "fetched origin/ci-reports")

        remote = read_remote(repo_root, timeout, verbose)
        if remote is None:
            _log(verbose, "remote CI-errors.md unavailable - silent no-op")
            return 0
        _log(verbose, f"remote file: {len(remote)} bytes")

        local_path = repo_root / LOCAL_FILENAME
        try:
            local = local_path.read_bytes()
        except FileNotFoundError:
            local = None
        except OSError as exc:
            raise SyncError(f"cannot read {LOCAL_FILENAME}: {exc}") from exc

        in_sync = local == remote
        if args.check:
            if in_sync:
                print(MATCH_LINE)
            else:
                print(MISMATCH_LINE)
            _log(verbose, f"--check: {'MATCH' if in_sync else 'MISMATCH'}")
            return 0 if in_sync else 1

        if in_sync:
            _log(verbose, "local file already up to date")
            return 0
        if atomic_write(local_path, remote):
            _log(verbose, f"installed {LOCAL_FILENAME} ({len(remote)} bytes)")
        else:
            _log(verbose, f"{LOCAL_FILENAME} changed concurrently - left untouched")
        return 0
    except SyncError as exc:
        _log(verbose, f"error: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
