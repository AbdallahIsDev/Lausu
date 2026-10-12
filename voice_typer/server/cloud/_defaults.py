"""Per-provider endpoint/model defaults for the cloud ASR engines.

The `model` here is what the backend serves when ``config.cloud_model`` is
empty — i.e. when a provider was chosen without picking a model (the
onboarding flow does exactly that). It MUST be one of the models the
renderer's catalogue lists for the same provider, because the Cloud tab
marks `defaultModel` as the active row under the same condition; the two
tables are pinned against each other by
``tests/test_cloud_provider_catalogue_parity.py``.

Source of the model ids: the renderer catalogue
(``client/src/renderer/src/lib/utils/models.ts``), which cites each
provider's own live model list.
"""

from __future__ import annotations

_PROVIDER_DEFAULTS = {
    "openai": {
        "url": "https://api.openai.com/v1/audio/transcriptions",
        "model": "whisper-1",
    },
    "groq": {
        "url": "https://api.groq.com/openai/v1/audio/transcriptions",
        "model": "whisper-large-v3",
    },
    "deepgram": {
        # nova-3 is Deepgram's current general-purpose line (nova-2 stays
        # available in the catalogue for the languages nova-3 does not
        # cover yet, it is simply no longer the default).
        "url": "https://api.deepgram.com/v1/listen",
        "model": "nova-3",
    },
    "gemini": {
        # gemini-2.0-flash was the previous default and is now listed by
        # Google as SHUT DOWN, which is why this was rebuilt rather than
        # left alone: the URL template below substitutes {model}, so a
        # retired id produced a 404 on every request.
        "url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "model": "gemini-3.8-flash",
    },
}
