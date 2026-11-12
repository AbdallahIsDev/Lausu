"""Chat service mixin: push-to-talk conversation (STT -> LLM -> TTS)."""

from __future__ import annotations

import logging
from typing import Any

from voice_typer.server.service._base import ServiceMixinBase

log = logging.getLogger(__name__)


class ChatMixin(ServiceMixinBase):
    """Mixin: voice conversation commands (lazy manager, mirrors TtsMixin)."""

    _chat_manager: Any = None

    def _get_chat_manager(self) -> Any:
        """Return the per-app manager, creating it on first use."""
        manager = getattr(self, "_chat_manager", None)
        if manager is None:
            from voice_typer.server import event_bus
            from voice_typer.server.conversation import ChatManager

            def _publish(data: dict) -> None:
                event_bus.publish({"type": "chat_turn", "data": data})

            manager = ChatManager(self._app, self._app.config, _publish, service=self)
            self._chat_manager = manager
        return manager

    def chat_listen_start(self) -> dict[str, object]:
        """Open chat capture (stops any playing TTS first)."""
        result: dict[str, object] = self._get_chat_manager().listen_start()
        return result

    def chat_listen_stop(self) -> dict[str, object]:
        """Stop capture; run the turn on a worker thread; return now."""
        result: dict[str, object] = self._get_chat_manager().listen_stop()
        return result

    def chat_state(self) -> dict[str, object]:
        """Snapshot for page mount / reattach."""
        result: dict[str, object] = self._get_chat_manager().state()
        return result

    def chat_reset(self) -> dict[str, object]:
        """Abort any in-flight turn and clear the conversation."""
        result: dict[str, object] = self._get_chat_manager().reset()
        return result
