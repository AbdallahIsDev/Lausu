"""Supervision of one local speech runtime process.

This module exists so both engines are started, health-checked, and stopped the
same way: one runtime process per engine, serving its documented HTTP API on a
loopback port the app picked, never a per-utterance subprocess that would reload
a multi-GB model for every sentence.
"""

from __future__ import annotations

import logging
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from voice_typer.server.tts.types import TtsError

log = logging.getLogger(__name__)

#: Cold load of a 0.6B DualAR model or the Magpie stack, plus the first
#: tokenizer warmup. Measured on this project's reference machine: ~40s Vulkan,
#: ~15s CUDA; 180s leaves headroom for a first-run pack on a cold disk.
STARTUP_TIMEOUT_S = 180.0
_HEALTH_POLL_S = 0.5


def free_port() -> int:
    """Ask the OS for an unused loopback port.

    Binding to port 0 and closing is racy in principle; in practice the window
    is microseconds and the alternative (hardcoding 8080) collides with the
    app's own sidecar and any other audio.cpp instance.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass(frozen=True)
class RuntimeSpec:
    """Everything needed to launch one runtime binary."""

    name: str
    argv: list[str]
    log_path: Path
    #: Runtime health route; audio.cpp and NeMo-Speech.cpp both expose /health.
    health_path: str = "/health"


@dataclass
class RuntimeServer:
    """A started runtime process, addressable at ``base_url``.

    Use as a context manager: ``with RuntimeServer.start(spec) as runtime:``.
    """

    spec: RuntimeSpec
    port: int
    process: subprocess.Popen[bytes] | None = field(default=None, repr=False)
    startup_s: float = 0.0

    @property
    def base_url(self) -> str:
        """Loopback base URL the runtime is listening on."""
        return f"http://127.0.0.1:{self.port}"

    @classmethod
    def start(cls, spec: RuntimeSpec, *, timeout_s: float = STARTUP_TIMEOUT_S) -> RuntimeServer:
        """Spawn the runtime and block until its health route answers."""
        spec.log_path.parent.mkdir(parents=True, exist_ok=True)
        port = free_port()
        started = time.perf_counter()
        log_handle = spec.log_path.open("wb")
        try:
            process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
                [part.format(port=port) for part in spec.argv],
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            log_handle.close()
            raise TtsError(f"{spec.name}: runtime binary not found: {spec.argv[0]}") from exc
        server = cls(spec=spec, port=port, process=process)
        try:
            server._wait_healthy(timeout_s)
        except Exception:
            server.stop()
            raise
        server.startup_s = time.perf_counter() - started
        log.info("[TTS] %s ready on %s in %.1fs", spec.name, server.base_url, server.startup_s)
        return server

    def _wait_healthy(self, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        url = f"{self.base_url}{self.spec.health_path}"
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise TtsError(
                    f"{self.spec.name}: runtime exited {self.process.returncode} during startup\n{self._log_tail()}"
                )
            try:
                with urlopen(url, timeout=2.0) as response:  # noqa: S310 - loopback
                    if response.status == 200:
                        return
            except (URLError, OSError):
                time.sleep(_HEALTH_POLL_S)
        raise TtsError(f"{self.spec.name}: not healthy after {timeout_s:.0f}s\n{self._log_tail()}")

    def _log_tail(self, limit: int = 1200) -> str:
        """Last lines of the runtime log, for the failure that named the runtime."""
        try:
            text = self.spec.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text.strip()[-limit:]

    @property
    def running(self) -> bool:
        """True while the runtime process is alive."""
        return self.process is not None and self.process.poll() is None

    def stop(self, *, grace_s: float = 10.0) -> None:
        """Ask the runtime to exit, then terminate, then kill."""
        process = self.process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=grace_s)
        except subprocess.TimeoutExpired:
            log.warning("[TTS] %s ignored terminate, killing", self.spec.name)
            process.kill()
            process.wait(timeout=grace_s)

    def __enter__(self) -> RuntimeServer:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()
