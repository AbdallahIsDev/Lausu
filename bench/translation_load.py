"""Simulated ASR-like background load for the translation benchmark.

This is a benchmark-only stressor. It does not load an ASR model and is not a
dictation path; it just keeps CPU or CUDA busy while translation requests run.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Any

_STOP_WAIT_S = 5.0


class CpuLoad:
    """Keep a fixed number of worker threads doing deterministic CPU math."""

    def __init__(self, workers: int = 2) -> None:
        if workers < 1:
            raise ValueError("workers must be positive")
        self.workers = workers
        self.iterations = 0
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if self._threads:
            return
        self._stop.clear()
        for index in range(self.workers):
            thread = threading.Thread(
                target=self._run,
                args=(index + 1,),
                name=f"translation-load-{index + 1}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._stop.set()
        deadline = time.monotonic() + _STOP_WAIT_S
        for thread in self._threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        self._threads.clear()

    def _run(self, seed: int) -> None:
        accumulator = float(seed)
        while not self._stop.is_set():
            for step in range(256):
                accumulator += math.sin(accumulator + seed + step * 0.01) * 0.5
            if accumulator > 1e9:
                accumulator -= 1e9
            self.iterations += 1
            time.sleep(0)


class GpuLoad:
    """Keep one CUDA device busy with small matrix multiplies.

    Requires an already-installed CUDA build of torch. This benchmark never
    installs anything; when CUDA is unavailable it says so instead of falling
    back to a different load shape.
    """

    def __init__(self) -> None:
        self.iterations = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._torch: Any = None

    def start(self) -> None:
        if self._thread is not None:
            return
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("GPU load needs an already-installed torch CUDA build; use --load-kind cpu") from exc
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available in this Python environment; use --load-kind cpu")
        self._torch = torch
        self._thread = threading.Thread(target=self._run, name="translation-gpu-load", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=_STOP_WAIT_S)
            self._thread = None

    def _run(self) -> None:
        torch = self._torch
        size = 512
        left = torch.randn((size, size), device="cuda")
        right = torch.randn((size, size), device="cuda")
        while not self._stop.is_set():
            result = left @ right
            left = result * 0.5
            self.iterations += 1


def make_load(kind: str, workers: int) -> Any:
    """Return an idle load object; call start()/stop() around the measured work."""
    if kind == "cpu":
        return CpuLoad(workers)
    if kind == "gpu":
        return GpuLoad()
    return None
