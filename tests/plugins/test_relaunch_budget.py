"""Bounded relaunch: three recoveries, fourth closes the start cleanly."""

from __future__ import annotations

from tools.internal_plugins._common.bridge import session


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def run_with_deaths(deaths: int, *, stage: str = "browser"):
    clock = Clock()
    budget = session.RelaunchBudget(clock=clock, log=__import__("logging").getLogger("test"))
    launches: list[str] = []
    alive_calls = [0]

    def alive():
        alive_calls[0] += 1
        return alive_calls[0] <= deaths

    def launch(**kwargs):
        launches.append("force" if kwargs.get("force") else "normal")
        return True

    # Bridge becomes reachable only after every detected close was relaunched.
    def status():
        return {"connected": len(launches) > deaths}

    ok = session.ensure_browser(
        status_fn=lambda: {"browser": "connected"} if status()["connected"] else {"browser": "connecting"},
        launch_fn=launch,
        ready_fn=lambda snapshot: False,
        clock=clock,
        timeout=10.0,
        transport_fn=lambda snap: snap.get("browser") == "connected",
        alive_fn=alive,
        budget=budget,
        stage=stage,
    )
    return ok, budget.count, launches, clock


def test_one_or_two_closes_are_recovered():
    for deaths in (1, 2):
        ok, count, launches, _clock = run_with_deaths(deaths)
        assert ok is True
        assert count == deaths
        assert len(launches) >= deaths + 1


def test_three_closes_are_recovered():
    ok, count, launches, _clock = run_with_deaths(3)
    assert ok is True
    assert count == 3
    assert len(launches) >= 4


def test_fourth_close_exhausts_the_budget():
    ok, count, _launches, clock = run_with_deaths(4)
    assert ok is False
    assert count == 3
    assert clock.sleeps[-3:] == [0.5, 1.0, 1.5], "short bounded backoff between attempts"
