"""Nuitka freeze jobs must reuse prior compilation work (build caching).

Fresh runners recompile ~800 C translation units from scratch (~2.5h).
Two mechanisms collapse repeat builds: Nuitka's inline clcache copy
(active unless CLCACHE_DISABLE is set, persisted by the ccache step)
and the scons build dir (up-to-date objects skipped by checksum).
"""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "tauri-windows-build.yml"

FREEZE_JOBS = ("build-sidecar-exe", "build-worker-exe")


def _jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _step_names(job: dict) -> list[str]:
    return [s.get("name", "") for s in job.get("steps", [])]


class TestCompilerCacheEnabled:
    """Neither freeze job may disable the compiler cache."""

    def test_no_clcache_disable_in_freeze_jobs(self):
        jobs = _jobs()
        for job_id in FREEZE_JOBS:
            env = jobs[job_id].get("env", {}) or {}
            assert "CLCACHE_DISABLE" not in env, (
                f"{job_id} sets CLCACHE_DISABLE: repeat builds recompile "
                "every TU from scratch (~2.5h). The old torch-compile hang "
                "that motivated the disable is gone with torch nofollowed."
            )

    def test_scons_build_dir_cached_in_freeze_jobs(self):
        jobs = _jobs()
        for job_id in FREEZE_JOBS:
            names = _step_names(jobs[job_id])
            assert any("scons build dir" in n for n in names), (
                f"{job_id} is missing the scons build-dir cache step; "
                "without the .build dir, scons cannot skip up-to-date objects"
            )
