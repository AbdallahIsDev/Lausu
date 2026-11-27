"""Keep plugin unit tests away from the real profile and real WMI.

The browser layer is faked here; the code under test (session/config/bridge)
is real. Live behavior is verified separately in the running app.
"""

from __future__ import annotations

import pytest
from tools.internal_plugins._common.bridge import chrome_profile, profile_state


def control_posts(posts):
    """Read-only draft snapshots are not control commands."""
    return [p for p in posts if p != "/draft-snapshot"]


def ready_snapshot(**changes):
    """A fully hydrated extension snapshot for fake-layer tests."""
    status = {
        "browser": "connected",
        "page": "ok",
        "micCount": 1,
        "selectorsReady": True,
        "readiness": {
            "browser": "up",
            "tab": "ready",
            "content_script": "present",
            "control": "present",
            "signed_in": "unknown",
            "document_ready": True,
            "control_stable": True,
            "tab_quiet_ms": 500,
            "reason": "ready",
        },
    }
    status.update(changes)
    return status


@pytest.fixture(autouse=True)
def fake_browser_layer(monkeypatch):
    monkeypatch.setattr(chrome_profile, "browser_liveness", lambda *_a, **_k: True)
    monkeypatch.setattr(profile_state, "apply_before_launch", lambda *_a, **_k: None)
    # Never let a unit test read the live plugin daemon over HTTP.
    from tools.internal_plugins._common.bridge.daemon_client import DaemonClient

    monkeypatch.setattr(DaemonClient, "config", lambda self: {})
