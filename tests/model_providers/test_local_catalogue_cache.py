"""Local provider catalogues: opt-in gating, single-flight and the short cache.

A machine with neither Ollama nor LM Studio installed used to pay a full connect
timeout for each of them on every ``provider_list`` (page mount, every key and
domain write), twice at once in development because React StrictMode invokes the
mount effect twice. These tests pin the two halves of the fix: a server nobody
configured is never dialled, and a server that is wanted is probed once per
window.
"""

from __future__ import annotations

import logging
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest
from voice_typer.server.model_providers import builtin
from voice_typer.server.model_providers.local_catalogue import (
    cached_local_catalogue,
    clear_local_catalogue,
    force_local_catalogue,
)

LOGGER = "voice_typer.server.model_providers.builtin"


@pytest.fixture(autouse=True)
def _clean_catalogue_state():
    clear_local_catalogue()
    yield
    clear_local_catalogue()


@pytest.fixture
def config(monkeypatch: pytest.MonkeyPatch):
    """Bind a fake Config for the provider layer; returns the setter."""
    previous = builtin._config_getter  # noqa: SLF001 - module-level binding under test

    def install(**fields: Any) -> None:
        base = {
            "ollama_base_url": "",
            "lmstudio_base_url": "",
            "local_onnx_model_dir": "",
            "openrouter_base_url": "",
            "language": "en",
            "asr_provider": "",
            "tts_provider": "",
            "llm_provider": "",
        }
        base.update(fields)
        builtin.install_config_getter(lambda: SimpleNamespace(**base))

    try:
        yield install
    finally:
        builtin.install_config_getter(previous)


# ── the opt-in gate (builtin) ────────────────────────────────────────────────


def test_unconfigured_local_server_is_never_dialled(monkeypatch: pytest.MonkeyPatch, config) -> None:
    calls: list[Any] = []

    def explode(*args: Any, **kwargs: Any) -> list[Any]:
        calls.append(args)
        raise AssertionError("a local server nobody configured must not be dialled")

    monkeypatch.setattr("voice_typer.server.model_providers.ollama.list_local_models", explode)
    monkeypatch.setattr("voice_typer.server.model_providers.lmstudio.list_models", explode)
    config()

    assert builtin._ollama_models() == []  # noqa: SLF001 - the unit under test
    assert builtin._lmstudio_models() == []  # noqa: SLF001
    assert calls == []


def test_a_selected_local_provider_is_dialled(monkeypatch: pytest.MonkeyPatch, config) -> None:
    calls: list[Any] = []

    def probe(*args: Any, **kwargs: Any) -> list[Any]:
        calls.append(kwargs)
        return []

    monkeypatch.setattr("voice_typer.server.model_providers.ollama.list_local_models", probe)
    config(llm_provider="ollama")

    assert builtin._ollama_models() == []  # noqa: SLF001
    assert len(calls) == 1
    # The probe is bounded: an unreachable server cannot block for the default.
    assert calls[0]["timeout_s"] == 2.0


def test_a_custom_base_url_opts_in(monkeypatch: pytest.MonkeyPatch, config) -> None:
    calls: list[Any] = []

    def probe(*args: Any, **kwargs: Any) -> list[Any]:
        calls.append(args)
        return []

    monkeypatch.setattr("voice_typer.server.model_providers.lmstudio.list_models", probe)
    config(lmstudio_base_url="http://127.0.0.1:9999/v1")

    builtin._lmstudio_models()  # noqa: SLF001
    assert len(calls) == 1
    assert calls[0][0] == "http://127.0.0.1:9999/v1"


def test_force_bypasses_the_gate(monkeypatch: pytest.MonkeyPatch, config) -> None:
    calls: list[Any] = []

    def probe(*args: Any, **kwargs: Any) -> list[Any]:
        calls.append(args)
        return []

    monkeypatch.setattr("voice_typer.server.model_providers.lmstudio.list_models", probe)
    config()

    with force_local_catalogue():
        builtin._lmstudio_models()  # noqa: SLF001
    assert len(calls) == 1


def test_a_dead_server_logs_once_per_window(
    monkeypatch: pytest.MonkeyPatch, config, caplog: pytest.LogCaptureFixture
) -> None:
    def boom(*args: Any, **kwargs: Any) -> list[Any]:
        raise TimeoutError("timed out")

    monkeypatch.setattr("voice_typer.server.model_providers.ollama.list_local_models", boom)
    config(llm_provider="ollama")

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        assert builtin._ollama_models() == []  # noqa: SLF001
        assert builtin._ollama_models() == []  # noqa: SLF001

    messages = [r.getMessage() for r in caplog.records if "ollama catalogue unavailable" in r.getMessage()]
    assert len(messages) == 1, messages
    assert "timed out" in messages[0]


# ── the cache itself ─────────────────────────────────────────────────────────


def test_probe_runs_once_within_the_window() -> None:
    calls: list[int] = []

    def probe() -> list[str]:
        calls.append(1)
        return ["a", "b"]

    first, first_error = cached_local_catalogue("demo", probe)
    second, second_error = cached_local_catalogue("demo", probe)

    assert (first, second) == (["a", "b"], ["a", "b"])
    assert (first_error, second_error) == (None, None)
    assert len(calls) == 1


def test_failure_is_cached_and_reported_to_the_leader_only() -> None:
    calls: list[int] = []

    def probe() -> list[str]:
        calls.append(1)
        raise RuntimeError("refused")

    models, error = cached_local_catalogue("demo", probe)
    again, again_error = cached_local_catalogue("demo", probe)

    assert (models, again) == ([], [])
    assert isinstance(error, RuntimeError)
    assert again_error is None, "only the probe that ran reports the failure"
    assert len(calls) == 1


def test_clear_forces_a_fresh_probe() -> None:
    calls: list[int] = []

    def probe() -> list[str]:
        calls.append(1)
        return []

    cached_local_catalogue("demo", probe)
    clear_local_catalogue("demo")
    cached_local_catalogue("demo", probe)

    assert len(calls) == 2


def test_ttl_expiry_reprobes() -> None:
    calls: list[int] = []

    def probe() -> list[str]:
        calls.append(1)
        return []

    cached_local_catalogue("demo", probe, ttl=0.0)
    cached_local_catalogue("demo", probe, ttl=0.0)

    assert len(calls) == 2


def test_concurrent_callers_share_one_probe() -> None:
    calls: list[int] = []
    results: list[list[str]] = []
    gate = threading.Barrier(8)

    def probe() -> list[str]:
        calls.append(1)
        time.sleep(0.05)  # long enough for every waiter to arrive
        return ["shared"]

    def worker() -> None:
        gate.wait(timeout=5.0)
        models, _ = cached_local_catalogue("demo", probe)
        results.append(models)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5.0)

    assert len(calls) == 1, f"expected one probe, got {len(calls)}"
    assert results == [["shared"]] * 8
