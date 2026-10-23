"""Canonical spec delivery, duplicate-hotkey policy, effective config publish."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher


def _make_app(hotkey: str = "<f2>", mode: str = "toggle", repaste: str | None = None) -> SimpleNamespace:
    app = SimpleNamespace()
    app.config = SimpleNamespace(
        hotkey=hotkey,
        recording_mode=mode,
        esc_cancel_enabled=False,
        repaste_hotkey=repaste,
        save=MagicMock(return_value=True),
    )
    app.tray = MagicMock()
    app._stop_dictation = MagicMock()
    app.toggle_dictation = MagicMock()
    app._cancel_dictation = MagicMock()
    app.repaste_last = MagicMock()
    return app


@pytest.fixture
def factory(monkeypatch):
    """Patch the factory and return the mock so tests can inspect args."""
    backends: dict[str, MagicMock] = {}

    def _create(spec: str, role: str | None = None) -> MagicMock:
        backend = MagicMock()
        backend.is_alive.return_value = True
        backends.setdefault(spec, backend)
        return backend

    mock = MagicMock(side_effect=_create)
    monkeypatch.setattr("voice_typer.server.hotkey_dispatcher.create_hotkey_backend", mock)
    return mock


class TestCanonicalSpecReachesBackend:
    """Alias spellings collapse to the canonical form before the factory."""

    @pytest.mark.parametrize(
        ("user_input", "expected_canonical"),
        [
            ("<ctrl_l>+<f9>", "<ctrl>+<f9>"),
            ("<alt_l>", "<alt>"),
            ("<option>+q", "<alt>+<q>"),
        ],
    )
    def test_factory_receives_canonical_spec(self, monkeypatch, user_input, expected_canonical):
        app = _make_app(hotkey=user_input)
        dispatcher = HotkeyDispatcher(app)

        received: list[tuple[str, str | None]] = []

        def _capture(spec: str, role: str | None = None) -> MagicMock:
            received.append((spec, role))
            backend = MagicMock()
            backend.is_alive.return_value = True
            return backend

        monkeypatch.setattr(
            "voice_typer.server.hotkey_dispatcher.create_hotkey_backend",
            MagicMock(side_effect=_capture),
        )
        dispatcher.register()
        assert received, "factory was never called"
        assert received[0][0] == expected_canonical

    def test_alias_equal_specs_share_one_pool_entry(self, monkeypatch):
        """``<ctrl>+<f9>`` and ``<ctrl_l>+<f9>`` must collapse to one pool key."""
        created: list[str] = []

        def _create(spec: str, role: str | None = None) -> MagicMock:
            created.append(spec)
            backend = MagicMock()
            backend.is_alive.return_value = True
            return backend

        monkeypatch.setattr(
            "voice_typer.server.hotkey_dispatcher.create_hotkey_backend",
            MagicMock(side_effect=_create),
        )

        app1 = _make_app(hotkey="<ctrl>+<f9>")
        d1 = HotkeyDispatcher(app1)
        d1.register()
        app2 = _make_app(hotkey="<ctrl_l>+<f9>")
        d2 = HotkeyDispatcher(app2)
        d2.register()

        # Both requests must produce the same canonical spec string.
        assert created == ["<ctrl>+<f9>", "<ctrl>+<f9>"]


class TestDuplicateHotkeys:
    """Alias-equivalent duplicates are rejected, not silently mutated."""

    def test_partial_update_with_dictation_spec_rejects_repaste(self):
        from voice_typer.server.config_validators.entry_points import validate_config_update

        current = SimpleNamespace(hotkey="<ctrl>+<alt>+v", repaste_hotkey="<ctrl>+<space>")
        validated, errors = validate_config_update({"repaste_hotkey": "<ctrl>+<alt>+v"}, current=current)
        assert errors, "alias-equivalent duplicate must be rejected"
        assert any("Hotkey conflict" in e for e in errors), f"unexpected errors: {errors!r}"
        # The whole payload is rejected by the caller, so nothing is applied.
        assert validated, "errors are what reject the payload, not an empty validated dict"

    def test_alias_equivalent_pair_rejects(self):
        from voice_typer.server.config_validators.entry_points import validate_config_update

        current = SimpleNamespace(hotkey="<ctrl>+<f9>", repaste_hotkey="<ctrl>+<space>")
        # ``<ctrl_l>+<f9>`` canonicalises to ``<ctrl>+<f9>``.
        _, errors = validate_config_update({"repaste_hotkey": "<ctrl_l>+<f9>"}, current=current)
        assert errors
        assert any("Hotkey conflict" in e for e in errors), f"unexpected errors: {errors!r}"

    def test_distinct_specs_do_not_conflict(self):
        from voice_typer.server.config_validators.entry_points import validate_config_update

        current = SimpleNamespace(hotkey="<ctrl>+<f9>", repaste_hotkey="<ctrl>+<space>")
        _, errors = validate_config_update({"repaste_hotkey": "<ctrl>+<alt>+r"}, current=current)
        assert not errors, f"distinct specs must not conflict, got: {errors!r}"

    def test_register_repaste_never_mutates_config(self, monkeypatch):
        """register_repaste must not silently rewrite ``config.repaste_hotkey``."""
        app = _make_app(hotkey="<ctrl>+<alt>+v", repaste="<ctrl>+<alt>+v")
        dispatcher = HotkeyDispatcher(app)
        original = app.config.repaste_hotkey
        dispatcher.register_repaste()
        assert app.config.repaste_hotkey == original, "register_repaste must not rewrite config"
        assert dispatcher._repaste_backend is None


class TestSetConfigPublishesEffectiveValue:
    """config_changed carries the value AFTER apply, not the request."""

    def test_publish_carries_effective_hotkey(self, monkeypatch):
        from voice_typer.server.handlers.config_handlers import ConfigHandlersMixin

        published: list[dict] = []
        monkeypatch.setattr(
            "voice_typer.server.event_bus.publish",
            lambda payload: published.append(payload["data"]),
        )

        handler = ConfigHandlersMixin.__new__(ConfigHandlersMixin)
        handler.app = MagicMock()
        # Simulate a failed re-registration that restored the old value.
        handler.app.config.hotkey = "<f2>"

        to_persist = {"hotkey": "<f3>"}
        handler._run_set_config_side_effects(to_persist, to_persist)

        assert published, "config_changed was never published"
        assert published[-1]["hotkey"] == "<f2>", (
            f"expected the OLD hotkey <f2> (restored by failed restart), got {published[-1]['hotkey']}"
        )
