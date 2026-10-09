"""Onboarding wizard selections mixin: microphone, hotkey presets,
model/backend choices, and the model catalog.

Split from ``voice_typer/server/onboarding.py`` (create-first);
``OnboardingController`` composes it so the historical import path
keeps resolving.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from voice_typer.server.config import DEFAULT_HOTKEY

log = logging.getLogger(__name__)


class _OnboardingSelectionsMixin:
    """Wizard step input surface (selections + catalogs)."""

    # Host state owned by OnboardingController.__init__ (composed class).
    selected_microphone: str | None
    selected_hotkey: str
    selected_model: str
    selected_backend: str

    if TYPE_CHECKING:
        # Provided by the composing OnboardingController (progress
        # persistence lives on the facade, see _load_progress).
        def _persist_progress(self) -> None: ...

    def get_microphones(self) -> list[dict]:
        """Get available microphones for Step 2."""
        try:
            from voice_typer.server.server_platform.microphone_list import list_microphones

            return list_microphones()
        except Exception:
            return []

    def set_microphone(self, mic_id: str | None) -> None:
        """Store the selected microphone."""
        self.selected_microphone = mic_id
        # Persist progress so a mid-wizard app
        self._persist_progress()

    HOTKEY_PRESETS = [
        # Caps Lock is the recommended default, universally present,
        DEFAULT_HOTKEY,
        # F-keys remain available as alternatives for users with
        "<f2>",
        "<f3>",
        "<f4>",
        "<f5>",
        "<f6>",
        "<f7>",
        "<f8>",
        "<f9>",
        "<f10>",
        "<f11>",
        "<f12>",
    ]

    def set_hotkey(self, hotkey: str) -> None:
        """Store the selected hotkey."""
        self.selected_hotkey = hotkey
        # Persist progress so a mid-wizard app
        self._persist_progress()

    # The Model step's local-vs-cloud choice. The app NEVER downloads
    BACKEND_CHOICES: tuple[str, ...] = ("local", "cloud")

    # each entry now carries ``vram_gb`` (estimated VRAM for
    MODEL_OPTIONS = [
        {
            "name": "tiny",
            "size": "~75MB",
            "speed": "Fastest",
            "description": "Multilingual, best for quick notes",
            "vram_gb": 0.5,
            "languages": None,
        },
        {
            "name": "large-v3",
            "size": "~3GB",
            "speed": "Slow",
            "description": "Multilingual, highest accuracy, GPU recommended",
            "vram_gb": 3.0,
            "languages": None,
        },
        {
            "name": "large-v3-turbo",
            "size": "~809MB",
            "speed": "Fast",
            "description": "Multilingual, near-large-v3 accuracy at 8x speed",
            "vram_gb": 2.0,
            "languages": None,
        },
        # NVIDIA Parakeet RNN-T model, fast, accurate, multilingual.
        {
            "name": "parakeet",
            "size": "~1.2GB",
            "speed": "Fast",
            "description": "NVIDIA Parakeet, fast & accurate, multilingual",
            "vram_gb": 2.0,
            "languages": None,
        },
    ]

    def set_model(self, model_name: str) -> None:
        """Store the selected model."""
        self.selected_model = model_name
        # Persist progress so a mid-wizard app
        self._persist_progress()

    def set_backend(self, backend: str) -> None:
        """Store the local-vs-cloud backend choice (Model step).

        ``"local"`` runs a local AI model (downloaded explicitly by the
        user); ``"cloud"`` connects a cloud transcription API. Invalid
        choices raise ``ValueError`` so the IPC layer surfaces an error
        envelope instead of silently persisting garbage.
        """
        if backend not in self.BACKEND_CHOICES:
            raise ValueError(f"unknown onboarding backend choice: {backend!r}")
        self.selected_backend = backend
        # Persist progress so a mid-wizard app
        self._persist_progress()

    @classmethod
    def get_model_catalog(cls) -> list[dict]:
        """Return the full rich-metadata model catalog.

        the static :attr:`MODEL_OPTIONS` list is intentionally
        short, it's the curated subset shown on the wizard's Model
        step. The *full* catalog (every Whisper variant, distilled
        variants, turbo, Parakeet, with VRAM / language / speed /
        accuracy / repo_id metadata) lives in
        :mod:`voice_typer.server.model_registry` and is exposed via
        :func:`get_all_models`.

        The renderer's Models page already consumes this catalog via
        the ``get_model_catalog`` IPC; the onboarding wizard can use
        the same catalog (via this method, exposed as the new
        ``onboarding_get_model_catalog`` IPC) when it wants to show
        the full set instead of the curated subset.

        Each entry is a dict with the fields defined on
        :class:`voice_typer.server.model_registry.ModelMetadata`:
        ``name``, ``download_size_mb``, ``required_vram_mb``,
        ``backend``, ``multilingual``, ``supported_languages``,
        ``description``, ``repo_id``, ``is_distilled``,
        ``speed_rating``, ``accuracy_rating``.

        Returns an empty list if the registry can't be imported
        (defensive, the registry module is side-effect-free at
        import time so this should never trigger in practice).
        """
        try:
            from voice_typer.server.model_registry import get_all_models

            return [m.to_dict() for m in get_all_models()]
        except Exception:
            log.exception("[ONBOARDING] get_model_catalog failed")
            return []
