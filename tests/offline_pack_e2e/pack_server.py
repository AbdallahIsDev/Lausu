"""Loopback static server for the runtime-pack end-to-end harness.

Test-only: serves manifest/zip bytes over 127.0.0.1 with Range support and
optional mid-body disconnect. Never imported by production code.
"""

from __future__ import annotations

import re
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

_RANGE_RE = re.compile(r"bytes=(\d+)-")


class LoopbackPackServer:
    """Small HTTP server that records Range requests for the E2E tests."""

    def __init__(
        self,
        files: dict[str, bytes],
        *,
        drop_path: str | None = None,
        drop_after: int = 0,
        chunk_delay_s: float = 0.0,
    ) -> None:
        self._files = dict(files)
        self._drop_path = drop_path
        self._drop_after = drop_after
        self._chunk_delay_s = chunk_delay_s
        self.range_requests: list[int] = []
        self.path_hits: Counter[str] = Counter()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
                name = self.path.lstrip("/").split("?", 1)[0]
                outer.path_hits[name] += 1
                payload = outer._files.get(name)
                if payload is None:
                    self.send_error(404, "not found")
                    return
                offset = 0
                range_header = self.headers.get("Range")
                if range_header:
                    match = _RANGE_RE.fullmatch(range_header.strip())
                    if match is None:
                        self.send_error(400, "bad range")
                        return
                    offset = int(match.group(1))
                    outer.range_requests.append(offset)
                    if offset >= len(payload):
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{len(payload)}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                body = payload[offset:]
                self.send_response(206 if range_header else 200)
                self.send_header("Content-Length", str(len(body)))
                if offset:
                    self.send_header("Content-Range", f"bytes {offset}-{len(payload) - 1}/{len(payload)}")
                self.end_headers()
                if name == outer._drop_path and not range_header:
                    truncated = body[: outer._drop_after]
                    if truncated:
                        self.wfile.write(truncated)
                    self.close_connection = True
                    return
                step = max(1, 1 << 20)
                for start in range(0, len(body), step):
                    self.wfile.write(body[start : start + step])
                    if outer._chunk_delay_s:
                        time.sleep(outer._chunk_delay_s)

            def log_message(self, *_args: Any) -> None:
                return

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="pack-fixture-http", daemon=True)

    @property
    def port(self) -> int:
        return int(self._httpd.server_address[1])

    def url(self, name: str) -> str:
        return f"http://127.0.0.1:{self.port}/{name}"

    def start(self) -> LoopbackPackServer:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)
