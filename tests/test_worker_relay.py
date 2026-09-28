"""ADR-0024 Step 2 port-relay round-trip guards."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from voice_typer.server import event_bus, worker_relay
from voice_typer.server.sidecar_ws import _read_loop


@pytest.fixture(autouse=True)
def _isolated_port():
    """Reset BOTH port holders between tests.

    The relay is the single place that learns a worker port and it also
    feeds the shared `WorkerClient`, so resetting only
    `worker_relay._worker_port` would leak a live client port into the
    next test (and out into `test_transcribe_offline_forward`, where a
    set port flips `forwarded` from False to True).
    """
    from voice_typer.server import worker_client as wc

    def _reset() -> None:
        worker_relay.reset_worker_port()
        wc.get_shared_client().close()

    _reset()
    yield
    _reset()


def _host_frame(pid=1234, version="v1", port=54321, frame_id=7) -> dict:
    # Frozen wire shape (docs/code-notes/worker-port-relay.md#wire-shape).
    return {
        "type": "worker_started",
        "data": {"pid": pid, "version": version, "port": port},
        "id": frame_id,
    }


def _received_bus_events() -> tuple[list[dict], object]:
    received: list[dict] = []

    def _cb(event: dict) -> None:
        received.append(event)

    event_bus.subscribe(_cb)
    return received, _cb


def _drop_bus_events(subscriber: object) -> None:
    event_bus.unsubscribe(subscriber)  # type: ignore[arg-type]


def test_relay_feeds_the_shared_worker_client() -> None:
    """The relay must hand the port to the ONE shared WorkerClient.

    Regression guard found by the ADR-0024 Step 6 row-(b) host run: the
    relay stored the port but nothing ever called
    `WorkerClient.update_from_worker_started`, so in the real app the
    client kept `port is None`, every `send_transcribe` returned None and
    each request degraded to `worker_not_ready` even though a healthy
    worker was listening. The live test harness had wired the two by
    hand, which is exactly why the gap stayed hidden.
    """
    from voice_typer.server import worker_client as wc

    client = wc.get_shared_client()
    try:
        assert worker_relay.handle_host_frame(_host_frame(port=42424)) is True
        assert client.port == 42424, (
            "the shared client must learn the relayed port; otherwise the worker hop is unreachable in the real app"
        )
    finally:
        client.close()


def test_relay_survives_an_unusable_client() -> None:
    """A client that blows up must NOT fail an otherwise-valid relay."""
    from voice_typer.server import worker_client as wc

    original = wc.get_shared_client

    def _boom():
        raise RuntimeError("no ws dependency")

    wc.get_shared_client = _boom  # type: ignore[assignment]
    try:
        assert worker_relay.handle_host_frame(_host_frame(port=42425)) is True
        assert worker_relay.get_worker_port() == 42425
    finally:
        wc.get_shared_client = original  # type: ignore[assignment]


def test_round_trip_emit_parse_accessor_returns_port() -> None:
    """Host frame → handler → accessor returns the port, bus gets full shape."""
    received, subscriber = _received_bus_events()
    try:
        assert worker_relay.get_worker_port() is None
        assert worker_relay.handle_host_frame(_host_frame()) is True
        assert worker_relay.get_worker_port() == 54321
        assert received == [
            {
                "type": "worker_started",
                "data": {"pid": 1234, "version": "v1", "port": 54321},
            }
        ]
    finally:
        _drop_bus_events(subscriber)


@pytest.mark.parametrize(
    "port",
    [0, -1, 65536, 70000, "54321", 54321.5, True, False, None],
)
def test_malformed_ports_keep_prior_port(port) -> None:
    """Bad ports log + keep the prior valid port, never overwrite, no publish."""
    received, subscriber = _received_bus_events()
    try:
        assert worker_relay.handle_host_frame(_host_frame(port=11111)) is True
        frame = _host_frame()
        if port is None:
            del frame["data"]["port"]
        else:
            frame["data"]["port"] = port
        assert worker_relay.handle_host_frame(frame) is False
        assert worker_relay.get_worker_port() == 11111
        assert len(received) == 1, "malformed frame must not publish"
    finally:
        _drop_bus_events(subscriber)


def test_missing_port_on_first_frame_stays_unknown() -> None:
    frame = _host_frame()
    del frame["data"]["port"]
    assert worker_relay.handle_host_frame(frame) is False
    assert worker_relay.get_worker_port() is None


@pytest.mark.parametrize("pid", [-1, "1234", 12.5, True, None])
def test_malformed_pid_rejected(pid) -> None:
    assert worker_relay.handle_host_frame(_host_frame(port=11111)) is True
    assert worker_relay.handle_host_frame(_host_frame(pid=pid)) is False
    assert worker_relay.get_worker_port() == 11111


@pytest.mark.parametrize("version", [123, None, True, ["v1"]])
def test_malformed_version_rejected(version) -> None:
    assert worker_relay.handle_host_frame(_host_frame(port=11111)) is True
    assert worker_relay.handle_host_frame(_host_frame(version=version)) is False
    assert worker_relay.get_worker_port() == 11111


@pytest.mark.parametrize(
    "msg",
    [
        None,
        "worker_started",
        [],
        {"type": "worker_started"},
        {"type": "worker_started", "data": None},
        {"type": "worker_started", "data": "54321"},
        {"type": "worker_started", "data": []},
    ],
)
def test_non_dict_frames_rejected_without_crash(msg) -> None:
    assert worker_relay.handle_host_frame(msg) is False  # type: ignore[arg-type]
    assert worker_relay.get_worker_port() is None


class _FrameIterableWebsocket:
    def __init__(self, *frames: dict) -> None:
        self._frames = [json.dumps(f) for f in frames]
        self.sent: list[object] = []

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for raw in self._frames:
            yield raw

    async def send(self, data: object) -> None:
        self.sent.append(data)


@pytest.mark.asyncio
async def test_read_loop_routes_relay_around_dispatch() -> None:
    """The WS reader must intercept the relay (not a registry command)."""
    server = SimpleNamespace()
    dispatch_calls: list[dict] = []

    async def dispatch(msg, websocket):
        dispatch_calls.append(msg)
        return None  # pragma: no cover, must NOT run

    ws = _FrameIterableWebsocket(_host_frame())
    await asyncio.wait_for(_read_loop(ws, server, dispatch), timeout=3.0)

    assert worker_relay.get_worker_port() == 54321
    assert dispatch_calls == [], "relay must not reach the dispatch closure"
    assert ws.sent == [], "relay is fire-and-forget, no response frame"
