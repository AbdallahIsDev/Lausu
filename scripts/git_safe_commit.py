#!/usr/bin/env python3
"""Serialize shared-checkout commits behind an exclusive lock.

Usage:
    python scripts/git_safe_commit.py -m "msg" -- <path>...
    python scripts/git_safe_commit.py -m "msg" --push -- <path>...
    python scripts/git_safe_commit.py -m "msg" --untrack -- <path>...

Rules:
* One exclusive lock per git dir (60 s default wait, ``--lock-timeout N`` for tests).
* Refuse when the index holds staged paths outside the explicit set.
* Added/modified files commit with an explicit pathspec.
* ``--untrack`` stages ``git rm --cached`` deletions and commits WITHOUT a
  pathspec (a pathspec commit would re-add the working-tree bytes).
* ``--push`` fetches first and refuses non-bot commits on origin/main.
* Never runs reset/stash/clean/checkout/rebase/amend/force or --no-verify.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import sys
import time
from collections.abc import Iterator, Sequence
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl

BOT_NAME = "github-actions[bot]"
BOT_FILE_ALLOWLIST = frozenset({"CI-errors.md"})
DEFAULT_LOCK_TIMEOUT = 60.0


class SafeCommitError(Exception):
    """A precondition failed; no git write should be attempted."""


def split_argv(argv: Sequence[str]) -> tuple[list[str], list[str]]:
    """Split before ``--`` so paths with dashes are unambiguous."""
    items = list(argv)
    if "--" in items:
        index = items.index("--")
        return items[:index], items[index + 1 :]
    return items, []


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    opts, paths = split_argv(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-m", "--message", required=True, help="commit message")
    parser.add_argument("--push", action="store_true", help="fetch, check bot rule, push main")
    parser.add_argument("--untrack", action="store_true", help="git rm --cached then commit with no pathspec")
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=DEFAULT_LOCK_TIMEOUT,
        help=f"seconds to wait for the lock (default {DEFAULT_LOCK_TIMEOUT:g})",
    )
    parser.add_argument("paths", nargs="*", help=argparse.SUPPRESS)
    parsed = parser.parse_args(opts)
    parsed.paths = [*parsed.paths, *paths]
    if not parsed.paths:
        parser.error("at least one path is required (use -- before paths)")
    return parsed


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise SafeCommitError(
            f"git {' '.join(args)} failed ({result.returncode}):\n{result.stdout}{result.stderr}".rstrip()
        )
    return result


def git_root() -> Path:
    found = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    if found.returncode != 0:
        raise SafeCommitError("not inside a git work tree")
    return Path(found.stdout.strip())


def lock_file(repo: Path) -> Path:
    git_dir = _git(repo, "rev-parse", "--absolute-git-dir").stdout.strip()
    return Path(git_dir) / "lausu-commit.lock"


@contextlib.contextmanager
def commit_lock(repo: Path, timeout: float = DEFAULT_LOCK_TIMEOUT) -> Iterator[None]:
    """Hold the per-repo commit lock; never unlink it (stable inode matters)."""
    path = lock_file(repo)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    deadline = time.monotonic() + timeout
    try:
        while not acquired:
            try:
                if os.name == "nt":
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise SafeCommitError(
                        f"could not acquire {path} within {timeout:g}s; another commit is running"
                    ) from None
                time.sleep(0.1)
        yield
    finally:
        if acquired:
            if os.name == "nt":
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def staged_paths(repo: Path) -> list[str]:
    output = _git(repo, "diff", "--cached", "--name-only").stdout
    return [line for line in output.splitlines() if line.strip()]


def refuse_foreign_stage(repo: Path, allowed: set[str]) -> None:
    foreign = [path for path in staged_paths(repo) if path not in allowed]
    if foreign:
        raise SafeCommitError("refusing to commit: staged paths outside the requested set:\n  " + "\n  ".join(foreign))


def assert_push_allowed(repo: Path) -> None:
    """Standing rule: only bot commits touching CI-errors.md may be integrated."""
    incoming = _git(repo, "rev-list", "HEAD..origin/main").stdout.split()
    for sha in incoming:
        identity = _git(repo, "show", "-s", "--format=%an <%ae>", sha).stdout.strip()
        files = [
            line
            for line in _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", sha).stdout.splitlines()
            if line.strip()
        ]
        if not (identity.startswith(f"{BOT_NAME} <") and set(files) <= BOT_FILE_ALLOWLIST):
            raise SafeCommitError(
                f"refusing to push: origin/main has non-bot commit {sha[:9]} ({identity}) touching {files}"
            )


def show_head(repo: Path) -> None:
    print(_git(repo, "show", "--stat", "--format=%h %an %s", "HEAD").stdout.rstrip())


def commit_paths(repo: Path, message: str, paths: Sequence[str], push: bool) -> None:
    refuse_foreign_stage(repo, set(paths))
    add = _git(repo, "add", "--", *paths)
    if add.stdout.strip():
        print(add.stdout.rstrip())
    commit = _git(repo, "commit", "-m", message, "--", *paths)
    print(commit.stdout.rstrip(), file=sys.stderr)
    show_head(repo)
    if push:
        _git(repo, "fetch", "origin")
        assert_push_allowed(repo)
        push_result = _git(repo, "push", "origin", "main")
        print(push_result.stderr.rstrip(), file=sys.stderr)


def untrack_paths(repo: Path, message: str, paths: Sequence[str], push: bool) -> None:
    existing = staged_paths(repo)
    if existing:
        raise SafeCommitError("refusing to untrack with a dirty index:\n  " + "\n  ".join(existing))
    rm = _git(repo, "rm", "--cached", "-q", "--", *paths)
    if rm.stdout.strip():
        print(rm.stdout.rstrip())
    status = _git(repo, "diff", "--cached", "--name-status").stdout.splitlines()
    expected = [f"D\t{path}" for path in paths]
    if sorted(status) != sorted(expected):
        raise SafeCommitError(f"staged deletions do not match request:\nexpected {expected}\nactual   {status}")
    commit = _git(repo, "commit", "-m", message)
    print(commit.stdout.rstrip(), file=sys.stderr)
    show_head(repo)
    if push:
        _git(repo, "fetch", "origin")
        assert_push_allowed(repo)
        push_result = _git(repo, "push", "origin", "main")
        print(push_result.stderr.rstrip(), file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        repo = git_root()
        with commit_lock(repo, args.lock_timeout):
            if args.untrack:
                untrack_paths(repo, args.message, args.paths, args.push)
            else:
                commit_paths(repo, args.message, args.paths, args.push)
    except SafeCommitError as exc:
        print(f"git_safe_commit: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
