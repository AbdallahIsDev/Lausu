"""Plugin activation must return in milliseconds (Item 2).

The daemon respawn used to block `activate()` for ~3 s on every plugin switch.
Boot/warm now happens on the background activation thread; the page-ready gate
for the first hotkey stays intact.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_PLUGIN_PATH = (
    __import__("pathlib").Path(__file__).resolve().parents[2]
    / "tools"
    / "internal_plugins"
    / "google_stt"
    / "plugin.py"
)


@pytest.fixture
def plugin(monkeypatch):
    name = "google_stt_fast_activation_under_test"
    if name in sys.modules:
        module = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, _PLUGIN_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    monkeypatch.setattr(module, "plugins_enabled", lambda: True)
    monkeypatch.setattr(module, "attach", lambda app: object())
    return module


def test_activate_returns_before_the_daemon_boot(plugin, monkeypatch):
    captured: dict[str, object] = {}

    class FakeThread:
        def __init__(self, *, target, name, daemon):
            captured["target"] = target
            captured["name"] = name

        def start(self):
            pass

    monkeypatch.setattr(plugin, "threading", SimpleNamespace(Thread=FakeThread))
    monkeypatch.setattr(
        plugin,
        "ensure_daemon",
        lambda: (time.sleep(0.35), True)[1],
    )
    monkeypatch.setattr(plugin, "_daemon_status", lambda: {"browser": "connected", "page": "ok"})

    t0 = time.monotonic()
    assert plugin.activate(MagicMock()) is True
    elapsed = time.monotonic() - t0

    assert elapsed < 0.3, elapsed
    assert captured["name"] == "plugin-activate-platform"
