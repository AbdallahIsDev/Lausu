"""Model-change outcome events published on the shared event bus."""

from __future__ import annotations

import logging

log = logging.getLogger("voice_typer.server.model_manager")


class ChangeEventsMixin:
    """Publishes the ``asr_backend_ready`` / ``asr_backend_load_failed`` events."""

    def _publish_backend_ready_event(self, backend: str, model_size: str) -> None:
        """Publish an ``asr_backend_ready`` event on the event_bus."""
        try:
            from voice_typer.server import event_bus

            event_bus.publish(
                {
                    "type": "asr_backend_ready",
                    "data": {
                        "backend": backend,
                        "model_size": model_size,
                    },
                }
            )
        except Exception:
            log.debug(
                "[MODEL] Failed to publish asr_backend_ready event",
                exc_info=True,
            )

    def _publish_backend_load_failed_event(
        self,
        backend: str,
        model_size: str,
        *,
        failure_reason: str,
    ) -> None:
        """Publish an ``asr_backend_load_failed`` event on the event_bus."""
        try:
            from voice_typer.server import event_bus

            event_bus.publish(
                {
                    "type": "asr_backend_load_failed",
                    "data": {
                        "backend": backend,
                        "model_size": model_size,
                        "failure_reason": failure_reason,
                    },
                }
            )
        except Exception:
            log.debug(
                "[MODEL] Failed to publish asr_backend_load_failed event",
                exc_info=True,
            )
