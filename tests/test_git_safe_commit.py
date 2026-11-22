"""Offline tests for scripts/git_safe_commit.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.git_safe_commit import commit_lock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "git_safe_commit.py"


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stdout}{result.stderr}")
    return result


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Safe Commit Test")
    git(path, "config", "user.email", "safe@example.com")
    return path


def seed(path: Path) -> None:
    (path / "base.txt").write_text("base\n", encoding="utf-8")
    git(path, "add", "base.txt")
    git(path, "commit", "-qm", "init")


def run_safe(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_refuses_foreign_staged_path(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    seed(repo)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    git(repo, "add", "b.txt")

    result = run_safe(repo, "-m", "add a", "--", "a.txt")

    assert result.returncode != 0
    assert "b.txt" in result.stderr
    assert git(repo, "diff", "--cached", "--name-only").stdout.strip() == "b.txt"
    assert git(repo, "log", "-1", "--format=%s").stdout.strip() == "init"


def test_commits_only_given_path(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    seed(repo)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")

    result = run_safe(repo, "-m", "add a", "--", "a.txt")

    assert result.returncode == 0, result.stderr
    stat = git(repo, "show", "--stat", "--format=", "HEAD").stdout
    assert "a.txt" in stat
    assert "b.txt" not in stat
    assert git(repo, "status", "--short").stdout.strip() == "?? b.txt"


def test_stages_deletion_of_missing_file(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    seed(repo)
    (repo / "gone.txt").write_text("gone\n", encoding="utf-8")
    git(repo, "add", "gone.txt")
    git(repo, "commit", "-qm", "add gone")
    (repo / "gone.txt").unlink()

    result = run_safe(repo, "-m", "remove gone", "--", "gone.txt")

    assert result.returncode == 0, result.stderr
    stat = git(repo, "show", "--stat", "--format=", "HEAD").stdout
    assert "gone.txt" in stat and "1 deletion" in stat
    assert git(repo, "ls-files", "gone.txt").stdout == ""


def test_untrack_mode_leaves_file_on_disk(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    seed(repo)
    (repo / "CI-errors.md").write_text("generated\n", encoding="utf-8")
    git(repo, "add", "CI-errors.md")
    git(repo, "commit", "-qm", "add generated")

    result = run_safe(repo, "-m", "untrack generated", "--untrack", "--", "CI-errors.md")

    assert result.returncode == 0, result.stderr
    assert (repo / "CI-errors.md").read_text(encoding="utf-8") == "generated\n"
    assert git(repo, "ls-files", "CI-errors.md").stdout == ""
    stat = git(repo, "show", "--stat", "--format=", "HEAD").stdout
    assert "CI-errors.md" in stat and "1 deletion" in stat
    assert git(repo, "diff", "--cached", "--name-only").stdout == ""


def test_lock_contention_fails_fast(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    seed(repo)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")

    with commit_lock(repo, 60):
        result = run_safe(repo, "-m", "add a", "--lock-timeout", "1", "--", "a.txt")

    assert result.returncode != 0
    assert "could not acquire" in result.stderr
    assert git(repo, "log", "-1", "--format=%s").stdout.strip() == "init"


def test_pre_commit_hook_is_not_bypassed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    seed(repo)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nprintf 'ran' > hook-ran.txt\n", encoding="utf-8")
    hook.chmod(0o755)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")

    result = run_safe(repo, "-m", "add a", "--", "a.txt")

    assert result.returncode == 0, result.stderr
    assert (repo / "hook-ran.txt").read_text(encoding="utf-8") == "ran"


def test_push_refused_when_origin_has_non_bot_commit(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", "-q", "-b", "main", str(remote))
    work = init_repo(tmp_path / "work")
    seed(work)
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "-q", "-u", "origin", "main")

    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(remote), str(other))
    git(other, "config", "user.name", "Other Agent")
    git(other, "config", "user.email", "other@example.com")
    (other / "other.txt").write_text("other\n", encoding="utf-8")
    git(other, "add", "other.txt")
    git(other, "commit", "-qm", "other agent commit")
    git(other, "push", "-q", "origin", "main")

    (work / "local.txt").write_text("local\n", encoding="utf-8")
    result = run_safe(work, "-m", "local commit", "--push", "--", "local.txt")

    assert result.returncode != 0
    assert "refusing to push" in result.stderr
    assert git(work, "rev-list", "HEAD..origin/main").stdout.strip()
