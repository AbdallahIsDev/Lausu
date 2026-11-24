"""Offline tests for scripts/sync_ci_errors.py.

Everything runs against a throwaway git clone with a local bare repo acting as
``origin`` -- no network, no credential use, and never the real checkout's
origin.  pytest + stdlib only.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "sync_ci_errors.py"
HOOK_NAMES = ("pre-commit", "pre-push", "post-merge", "post-checkout")

REMOTE_V1 = "# CI errors\n\n- first report\n"
REMOTE_V2 = "# CI errors\n\n- second report\n"
REMOTE_V3 = "# CI errors\n\n- third report\n"

# Must stay byte-for-byte identical to the block appended to each .husky hook.
SYNC_SNIPPET = """(
  _sync_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$_sync_root" || exit 0
  if [ -x .venv/Scripts/python.exe ]; then
    _sync_py=.venv/Scripts/python.exe
  elif [ -x .venv/bin/python ]; then
    _sync_py=.venv/bin/python
  elif command -v python3 >/dev/null 2>&1; then
    _sync_py=python3
  else
    _sync_py=python
  fi
  "$_sync_py" scripts/sync_ci_errors.py --timeout 3 >/dev/null 2>&1 || :
) >/dev/null 2>&1 &"""


@pytest.fixture(scope="module")
def sync_mod():
    spec = importlib.util.spec_from_file_location("sync_ci_errors_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", GCM_INTERACTIVE="never")
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        pytest.fail(f"git {args} failed ({result.returncode}): {result.stderr}")
    return result


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _run_sync(repo: Path, *flags: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *flags],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


@pytest.fixture
def fake_repo(tmp_path: Path) -> SimpleNamespace:
    """A work clone whose origin has a ci-reports branch containing CI-errors.md."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "--quiet", str(origin))
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "--quiet", "-b", "main")
    _git(work, "config", "user.name", "Test User")
    _git(work, "config", "user.email", "test@example.invalid")
    _write(work / "seed.txt", "seed\n")
    _git(work, "add", "seed.txt")
    _git(work, "commit", "--quiet", "-m", "init")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "--quiet", "origin", "main")
    _git(origin, "symbolic-ref", "HEAD", "refs/heads/main")

    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "--quiet", str(origin), str(seed))
    _git(seed, "config", "user.name", "Test User")
    _git(seed, "config", "user.email", "test@example.invalid")
    _git(seed, "checkout", "--quiet", "--orphan", "ci-reports")
    (seed / "seed.txt").unlink()
    _write(seed / "CI-errors.md", REMOTE_V1)
    _git(seed, "add", "-A")
    _git(seed, "commit", "--quiet", "-m", "ci report")
    _git(seed, "push", "--quiet", "-u", "origin", "ci-reports")
    return SimpleNamespace(origin=origin, work=work, seed=seed)


def test_sync_fetches_only_ref_and_leaves_git_state_untouched(fake_repo) -> None:
    work = fake_repo.work
    head_before = _git(work, "rev-parse", "HEAD").stdout
    index_before = (work / ".git" / "index").read_bytes()
    cached_before = _git(work, "diff", "--cached", "--name-only").stdout
    seed_before = (work / "seed.txt").read_bytes()
    refs_before = set(_git(work, "for-each-ref", "--format=%(refname)", "refs/remotes/origin").stdout.split())

    result = _run_sync(work, "--verbose")
    assert result.returncode == 0, result.stderr
    assert "refs/heads/ci-reports:refs/remotes/origin/ci-reports" in result.stderr
    assert (work / "CI-errors.md").read_text(encoding="utf-8") == REMOTE_V1

    refs_after = set(_git(work, "for-each-ref", "--format=%(refname)", "refs/remotes/origin").stdout.split())
    assert refs_after - refs_before == {"refs/remotes/origin/ci-reports"}
    assert refs_before - refs_after == set()
    assert _git(work, "tag").stdout.strip() == ""
    assert _git(work, "rev-parse", "HEAD").stdout == head_before
    assert (work / ".git" / "index").read_bytes() == index_before
    assert _git(work, "diff", "--cached", "--name-only").stdout == cached_before
    assert (work / "seed.txt").read_bytes() == seed_before

    status_lines = [
        line
        for line in _git(work, "status", "--porcelain").stdout.splitlines()
        if line.strip() and not line.endswith("CI-errors.md")
    ]
    assert status_lines == []
    assert list(work.glob(".CI-errors-*.tmp")) == []


def test_atomic_write_uses_replace_then_skips_identical(tmp_path: Path, sync_mod, monkeypatch) -> None:
    target = tmp_path / "CI-errors.md"
    _write(target, "old\n")
    calls: list[tuple[str, str]] = []
    real_replace = os.replace

    def spy_replace(src, dst, *args, **kwargs):
        calls.append((str(src), str(dst)))
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(sync_mod.os, "replace", spy_replace)
    assert sync_mod.atomic_write(target, b"new\n") is True
    assert len(calls) == 1
    assert calls[0][1] == str(target)
    assert Path(calls[0][0]).parent == target.parent  # temp file in the SAME dir
    assert target.read_bytes() == b"new\n"
    assert list(tmp_path.glob(".CI-errors-*.tmp")) == []

    after_mtime = target.stat().st_mtime_ns
    assert sync_mod.atomic_write(target, b"new\n") is False
    assert len(calls) == 1  # no second replace -> no rewrite
    assert target.stat().st_mtime_ns == after_mtime
    assert target.read_bytes() == b"new\n"

    missing = tmp_path / "nested" / "CI-errors.md"
    missing.parent.mkdir()
    assert sync_mod.atomic_write(missing, b"fresh") is True
    assert missing.read_bytes() == b"fresh"


def test_idempotent_second_run_does_not_rewrite(fake_repo) -> None:
    work = fake_repo.work
    assert _run_sync(work).returncode == 0
    local = work / "CI-errors.md"
    first_mtime = local.stat().st_mtime_ns
    first_bytes = local.read_bytes()

    second = _run_sync(work, "--verbose")
    assert second.returncode == 0
    assert "already up to date" in second.stderr
    assert local.stat().st_mtime_ns == first_mtime
    assert local.read_bytes() == first_bytes


def test_offline_is_silent_and_leaves_local_file_alone(fake_repo) -> None:
    work = fake_repo.work
    assert _run_sync(work).returncode == 0
    local = work / "CI-errors.md"
    local.write_bytes(b"SENTINEL: must not change\n")

    _git(work, "remote", "set-url", "origin", str(fake_repo.origin.parent / "does-not-exist.git"))
    result = _run_sync(work)
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""
    assert local.read_bytes() == b"SENTINEL: must not change\n"

    verbose = _run_sync(work, "--verbose")
    assert verbose.returncode == 0
    assert "silent no-op" in verbose.stderr


def test_offline_check_is_also_silent_zero(fake_repo) -> None:
    work = fake_repo.work
    assert _run_sync(work).returncode == 0
    _git(work, "remote", "set-url", "origin", str(fake_repo.origin.parent / "does-not-exist.git"))
    result = _run_sync(work, "--check")
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""


def test_missing_branch_and_missing_remote_file_are_silent(tmp_path: Path) -> None:
    origin = tmp_path / "empty-origin.git"
    _git(tmp_path, "init", "--bare", "--quiet", str(origin))
    work = tmp_path / "no-branch"
    work.mkdir()
    _git(work, "init", "--quiet", "-b", "main")
    _git(work, "config", "user.name", "Test User")
    _git(work, "config", "user.email", "test@example.invalid")
    _write(work / "seed.txt", "seed\n")
    _git(work, "add", "seed.txt")
    _git(work, "commit", "--quiet", "-m", "init")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "--quiet", "origin", "main")
    _git(origin, "symbolic-ref", "HEAD", "refs/heads/main")

    result = _run_sync(work)
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""
    assert not (work / "CI-errors.md").exists()

    # Now the branch exists but the file does not.
    seed = tmp_path / "empty-seed"
    _git(tmp_path, "clone", "--quiet", str(origin), str(seed))
    _git(seed, "config", "user.name", "Test User")
    _git(seed, "config", "user.email", "test@example.invalid")
    _git(seed, "checkout", "--quiet", "--orphan", "ci-reports")
    (seed / "seed.txt").unlink()
    _write(seed / "README.md", "no digest here\n")
    _git(seed, "add", "-A")
    _git(seed, "commit", "--quiet", "-m", "no file")
    _git(seed, "push", "--quiet", "-u", "origin", "ci-reports")

    result = _run_sync(work)
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""
    assert not (work / "CI-errors.md").exists()


def test_check_reports_match_and_mismatch_without_writing(fake_repo) -> None:
    work = fake_repo.work
    local = work / "CI-errors.md"

    first = _run_sync(work, "--check")
    assert first.returncode == 1
    assert first.stdout.strip() == "CI-errors.md: MISMATCH"
    assert not local.exists()  # --check never writes

    assert _run_sync(work).returncode == 0
    matched = _run_sync(work, "--check")
    assert matched.returncode == 0
    assert matched.stdout.strip() == "CI-errors.md: MATCH"

    # Advance remote only; --check must detect the drift and not download it.
    _write(fake_repo.seed / "CI-errors.md", REMOTE_V2)
    _git(fake_repo.seed, "add", "CI-errors.md")
    _git(fake_repo.seed, "commit", "--quiet", "-m", "v2")
    _git(fake_repo.seed, "push", "--quiet", "origin", "ci-reports")
    drifted = _run_sync(work, "--check")
    assert drifted.returncode == 1
    assert drifted.stdout.strip() == "CI-errors.md: MISMATCH"
    assert local.read_text(encoding="utf-8") == REMOTE_V1

    assert _run_sync(work).returncode == 0
    assert local.read_text(encoding="utf-8") == REMOTE_V2
    assert _run_sync(work, "--check").returncode == 0


def test_every_hook_has_nonblocking_invocation_and_bounded_latency(fake_repo, tmp_path: Path) -> None:
    if shutil.which("sh") is None:
        pytest.skip("the hook snippet is a POSIX shell script and sh is not on PATH")
    hook_dir = REPO_ROOT / ".husky"
    for name in HOOK_NAMES:
        hook = hook_dir / name
        assert hook.exists(), f"missing hook: {name}"
        text = hook.read_text(encoding="utf-8")
        assert SYNC_SNIPPET in text, f"{name} does not carry the exact bounded sync block"
        assert text.count("scripts/sync_ci_errors.py") == 1

    # Execute the exact snippet from a temp script in the throwaway repo so the
    # real checkout's origin/refs are never touched.
    work = fake_repo.work
    scripts_dir = work / "scripts"
    scripts_dir.mkdir()
    shutil.copyfile(SCRIPT, scripts_dir / "sync_ci_errors.py")
    measure = work / "_measure_hook_sync.sh"
    measure.write_text("#!/usr/bin/env sh\n" + SYNC_SNIPPET + "\n", encoding="utf-8")

    started = time.perf_counter()
    proc = subprocess.run(
        ["sh", str(measure)],
        cwd=str(work),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    elapsed = time.perf_counter() - started
    print(f"\n[hook latency] backgrounded sync returned in {elapsed * 1000:.1f} ms")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "" and proc.stderr == ""
    assert elapsed < 3.0, f"hook added {elapsed:.2f}s; budget is ~3s"

    # Let the detached child finish, then confirm it did its job atomically.
    deadline = time.monotonic() + 5
    while not (work / "CI-errors.md").exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert (work / "CI-errors.md").read_text(encoding="utf-8") == REMOTE_V1
    assert list(work.glob(".CI-errors-*.tmp")) == []
