#!/usr/bin/env python3
"""GitHub Releases publisher for runtime-pack assets (C-CI-13 / C-CI-11).

Uploads slim-core installer + runtime-pack zip + pack-manifest.json via
``gh`` (fallback: REST). Naming reference: scripts/build/artifact_names.py
(re-exported as ASSET_NAME_BUILDERS). Idempotent upload (--clobber).
Does NOT sign assets — signing stays in CI (C-CI-11). Exit 0/1/2.

This module is the stable entry point invoked by CI workflows by path and
by importers as ``release.publish_pack_release``. Implementation lives in
``result.py``, ``backends/{gh,api}.py``, ``publisher.py`` and ``cli.py``;
this file only bootstraps imports, owns the naming re-export and publishes
the public surface.
"""

from __future__ import annotations

import shutil  # noqa: F401  # patch seam: tests patch pub.shutil.which
import sys
from pathlib import Path

# Make ``scripts.build.artifact_names`` (the canonical §11.9 naming
# module) importable under every execution mode, direct script run
# (``python scripts/release/publish_pack_release.py`` puts
# ``scripts/release`` on sys.path), flat import from the tests
# (``release.publish_pack_release`` with ``scripts/`` on sys.path), and
# package import from the repo root. Same bootstrap pattern as
# ``scripts/diagnostics.py``. The scripts dir is also needed so the
# split modules can be imported under the stable ``release.*`` name
# when this file runs as a script.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
for _path in (_REPO_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

# ``APP_REPO`` is the ONE authoritative repo slug, so the publisher's upload
# target and the downloader's manifest URL
# (``update_check.DEFAULT_OFFLINE_PACK_MANIFEST_URL``, also derived from
# APP_REPO) stay on the same repo by construction.
from scripts.build import artifact_names  # noqa: E402

# ── Naming re-export ────────────────────────────────────────────────────

# Canonical release-asset naming (plan §11.9 / C-CI-13). The single
# source of truth is ``scripts/build/artifact_names.py``; these aliases
# re-export its builders so CI workflows and callers that already
# import this module can construct the expected asset names without a
# second copy of the naming scheme. The publisher does NOT enforce the
# names, it uploads whatever paths the caller passes.
ASSET_NAME_BUILDERS = {
    # (app_version, triple) -> "lausu-slim-core-<app_version>-<triple>[.exe]"
    "slim_core": artifact_names.slim_core_installer_name,
    # (pack_version, triple) -> "lausu-runtime-pack-<pack_version>-<triple>.zip"
    "runtime_pack": artifact_names.runtime_pack_name,
    # () -> "pack-manifest.json" (NOT versioned)
    "pack_manifest": artifact_names.pack_manifest_name,
    # (app_version, triple) -> "lausu-full-offline-<app_version>-<triple>[.exe]"
    "full_offline": artifact_names.full_offline_installer_name,
}

# ── Public surface re-exported from the split modules ──────────────────

from release.backends.api import (  # noqa: E402
    _api_request,  # noqa: F401
    _publish_via_api,  # noqa: F401
    api_create_release,
    api_upload_asset,
)
from release.backends.gh import (  # noqa: E402
    _publish_via_gh,  # noqa: F401
    build_gh_create_command,
    build_gh_upload_command,
    gh_release_exists,
    gh_release_url,
    run_gh,
)
from release.cli import _build_arg_parser, main  # noqa: E402,F401
from release.publisher import publish_release, validate_assets  # noqa: E402
from release.result import DEFAULT_GH_CLI, DEFAULT_REPO, PublishResult  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "ASSET_NAME_BUILDERS",
    "DEFAULT_GH_CLI",
    "DEFAULT_REPO",
    "PublishResult",
    "api_create_release",
    "api_upload_asset",
    "build_gh_create_command",
    "build_gh_upload_command",
    "gh_release_exists",
    "gh_release_url",
    "main",
    "publish_release",
    "run_gh",
    "validate_assets",
]
