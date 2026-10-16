"""Wiring tests for the mic guard: lazy build, event publish, teardown.

The guard's own behaviour is pinned by ``tests/test_mic_volume_guard.py``;
this file covers the three glue points that a unit test on the guard alone
would miss: the ``_mic_guard`` lazy property, the ``microphone_volume_lowered``
push payload, and the shutdown teardown.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from voice_typer.server import app_lazy_hub


class TestLazyProperty:
    def test_build_mic_guard_wires_the_live_enabled_flag(self):
        app = SimpleNamespace(config=SimpleNamespace(mic_guard_enabled=False))
        guard = app_lazy_hub._build_mic_guard(app)

        assert guard._enabled is not None
        assert guard._enabled() is False

        # Read live, so set_config takes effect without an app restart.
        app.config.mic_guard_enabled = True
        assert guard._enabled() is True

    def test_build_mic_guard_defaults_to_enabled_when_the_key_is_absent(self):
        app = SimpleNamespace(config=SimpleNamespace())
        guard = app_lazy_hub._build_mic_guard(app)
        assert guard._enabled() is True

    def test_build_mic_guard_wires_the_publish_callback(self, monkeypatch):
        """The wired callback publishes with the guard's LIVE ``supports_set``.

        ``can_set`` must ride the event or the renderer renders a button it
        cannot honour (and the macOS no-gain path loses its button-less
        variant).
        """
        published: list[dict] = []
        monkeypatch.setattr(
            "voice_typer.server.event_bus.publish",
            lambda event: published.append(event),
        )
        app = SimpleNamespace(config=SimpleNamespace(mic_guard_enabled=True))
        guard = app_lazy_hub._build_mic_guard(app)

        # A guard with no backend resolved yet cannot set: can_set False.
        guard._on_lowered(0.5, False)

        assert published == [
            {
                "type": "microphone_volume_lowered",
                "data": {"level": 0.5, "restored": False, "can_set": False},
            }
        ]

    def test_mic_guard_is_registered_as_a_lazy_property(self):
        descriptor = app_lazy_hub.AppLazyHub.__dict__["_mic_guard"]
        assert isinstance(descriptor, app_lazy_hub.LazyProperty)
        assert descriptor._backing_attr == "_mic_guard_backing"
        assert descriptor._log_label == "MicVolumeGuard"
        assert descriptor._factory is app_lazy_hub._build_mic_guard

    def test_backing_attribute_is_declared_on_the_app(self):
        """The descriptor writes to this attr, so it must pre-exist."""
        import inspect

        from voice_typer.server import app_construction

        src = inspect.getsource(app_construction)
        assert "_mic_guard_backing" in src
        assert "_mic_guard_failed_at" in src


class TestPublishPayload:
    def test_event_shape_matches_the_ts_union(self, monkeypatch):
        published: list[dict] = []
        monkeypatch.setattr(
            "voice_typer.server.event_bus.publish",
            lambda event: published.append(event),
        )

        app_lazy_hub._publish_mic_volume_lowered(0.92345678, True, False)

        assert published == [
            {
                "type": "microphone_volume_lowered",
                "data": {"level": 0.9235, "restored": True, "can_set": False},
            }
        ]

    def test_event_type_is_registered_in_the_python_registry(self):
        from voice_typer.server.event_bus import EVENT_TYPES

        assert "microphone_volume_lowered" in EVENT_TYPES

    def test_restored_flag_survives_the_publish(self, monkeypatch):
        published: list[dict] = []
        monkeypatch.setattr(
            "voice_typer.server.event_bus.publish",
            lambda event: published.append(event),
        )

        app_lazy_hub._publish_mic_volume_lowered(0.5, False, True)

        assert published[0]["data"]["restored"] is False
        assert published[0]["data"]["can_set"] is True


class TestShutdownTeardown:
    def test_teardown_stops_the_guard(self, monkeypatch):
        from voice_typer.server.shutdown.teardowns import mic_guard as teardown_mod

        guard = MagicMock()
        controller = SimpleNamespace(_app=SimpleNamespace(_mic_guard=guard))
        calls: list[tuple[str, float]] = []

        def fake_run_with_timeout(label, fn, timeout=0.0, **_kw):
            calls.append((label, timeout))
            return fn()

        monkeypatch.setattr(teardown_mod, "_run_with_timeout", fake_run_with_timeout)

        teardown_mod.teardown_mic_guard(controller)

        guard.stop.assert_called_once()
        assert calls and calls[0][0] == "mic_guard_stop"

    def test_teardown_is_a_no_op_without_a_guard(self, monkeypatch):
        from voice_typer.server.shutdown.teardowns import mic_guard as teardown_mod

        controller = SimpleNamespace(_app=SimpleNamespace())
        monkeypatch.setattr(
            teardown_mod,
            "_run_with_timeout",
            lambda *_a, **_kw: pytest.fail("teardown must not run without a guard"),
        )

        teardown_mod.teardown_mic_guard(controller)

    def test_teardown_is_registered_in_the_shutdown_plan(self):
        import inspect

        from voice_typer.server.shutdown import plan as plan_mod

        src = inspect.getsource(plan_mod)
        assert '"teardown_mic_guard"' in src, (
            "the mic guard's watcher thread must be stopped on shutdown, "
            "otherwise a 2s poll can outlive the app."
        )
