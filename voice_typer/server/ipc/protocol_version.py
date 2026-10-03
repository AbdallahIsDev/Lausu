"""Shared IPC transport constants.

Frame caps and protocol constants must agree across every transport and
both process sides (the slim-core sidecar and the separate worker binary).
Duplicating them per-module risks a silent mismatch, where a sender
serialises an envelope the receiver refuses to read.

- ``PROTOCOL_VERSION`` is bumped when a wire-format change requires it;
  ``_COMMAND_REGISTRY`` (in ``voice_typer/server/ipc_server.py``) must gain
  the matching command in the same change.
"""

PROTOCOL_VERSION: int = 1

# ADR-0020 §10: 1 MiB WebSocket frame cap. The sidecar's outbound sender
# and the worker's WS server must agree on this value. Kept in a
# dependency-free module so the slim-core sidecar can import it without
# pulling in ``voice_typer.worker`` (mirrors the PROTOCOL_VERSION split).
MAX_WS_FRAME_BYTES: int = 1 * 1024 * 1024
