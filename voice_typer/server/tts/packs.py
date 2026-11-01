"""Pack manifests for the two TTS models.

This module exists so a TTS model is only used after its size and GGUF header
have been verified, mirroring the runtime-pack verify-before-use rule instead
of trusting whatever happens to sit in the models directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from voice_typer.server.tts.types import TtsError

#: GGUF files start with this magic; a truncated or HTML-error download is
#: caught here instead of surfacing as an opaque runtime load failure.
GGUF_MAGIC = b"GGUF"

_CHUNK = 1 << 20

#: Smallest file that can plausibly hold a TTS checkpoint. A partially
#: downloaded DualAR file still starts with ``GGUF`` (the header lands first),
#: so magic alone cannot catch a mid-transfer truncation; the runtime then fails
#: deep inside a tensor read (observed: "tensor data range is out of bounds").
MIN_PLAUSIBLE_GGUF_BYTES = 100 * 1024 * 1024


def verify_gguf(path: Path, *, expected_size: int | None = None) -> Path:
    """Verify a GGUF before a runtime is allowed to load it.

    ``expected_size`` is the publisher-pinned size and is checked when known;
    otherwise the magic and a plausibility floor are the checks. Returning the
    path keeps call sites fluent: ``model = verify_gguf(path)".
    """
    if not path.is_file():
        raise TtsError(f"artifact missing: {path}")
    actual = path.stat().st_size
    if expected_size is not None:
        if actual != expected_size:
            raise TtsError(
                f"artifact incomplete: {path.name} is {actual} bytes, expected {expected_size} "
                "(download finished?)"
            )
    elif actual < MIN_PLAUSIBLE_GGUF_BYTES:
        # No pinned size: fall back to a heuristic so an error page saved as a
        # .gguf is caught. An exact match is strictly stronger than the floor.
        raise TtsError(f"artifact too small to be a model: {path} ({actual} bytes)")
    with path.open("rb") as handle:
        magic = handle.read(4)
    if magic != GGUF_MAGIC:
        raise TtsError(f"artifact is not a GGUF file: {path} (magic={magic!r})")
    return path


def verify_model(path: Path, artifact: Artifact | None) -> Path:
    """Verify a configured model against its pinned artifact when it is ours.

    A user may point at a different quantization (``q8_0``), whose size differs
    legitimately, so the exact-size check applies only when the filename matches
    the pinned artifact; everything else still gets the magic/floor checks.
    """
    if artifact is not None and path.name == artifact.filename:
        return verify_gguf(path, expected_size=artifact.size_bytes)
    return verify_gguf(path)


@dataclass(frozen=True)
class Artifact:
    """One downloadable file with the exact size the publisher pinned."""

    filename: str
    url: str
    size_bytes: int

    def is_present(self, directory: Path) -> bool:
        """True when a complete file of the pinned size exists."""
        path = directory / self.filename
        return path.is_file() and path.stat().st_size == self.size_bytes

    def verify(self, directory: Path) -> Path:
        """Return the path, or raise if missing/short/not a GGUF."""
        return verify_gguf(directory / self.filename, expected_size=self.size_bytes)

    def download(self, directory: Path, *, progress: object | None = None) -> Path:
        """Fetch to ``.partial`` then atomically rename after a size check."""
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / self.filename
        if self.is_present(directory):
            return self.verify(directory)
        partial = target.with_suffix(target.suffix + ".partial")
        written = 0
        with urlopen(self.url) as response, partial.open("wb") as out:  # noqa: S310 - fixed https URLs
            while chunk := response.read(_CHUNK):
                out.write(chunk)
                written += len(chunk)
                if callable(progress):
                    progress(written, self.size_bytes)
        if written != self.size_bytes:
            partial.unlink(missing_ok=True)
            raise TtsError(f"download truncated for {self.filename}: {written} != {self.size_bytes}")
        partial.replace(target)
        return self.verify(directory)


#: Audio8-TTS-Realistic-0.6B, BF16 GGUF (model + codec + tokenizer bundled).
AUDIO8_REALISTIC_BF16 = Artifact(
    filename="audio8-tts-realistic-0.6b-bf16.gguf",
    url=(
        "https://huggingface.co/audio-cpp/Audio8-TTS-Realistic-0.6b-GGUF/resolve/main/"
        "audio8-tts-realistic-0.6b-bf16.gguf"
    ),
    size_bytes=1_890_480_128,
)

#: MagpieTTS multilingual 357M, v2607 F16 GGUF (the Arabic-capable profile).
#: The size is the runtime-pinned v2607 revision (commit 19806879…), not the
#: Hub's ``main`` listing: the API reports 568_663_392 for ``main``, while the
#: pinned revision — fetched twice independently and accepted by
#: ``nemo-speech pull``'s own size+SHA verification — is 568_663_328 bytes.
MAGPIE_V2607_F16 = Artifact(
    filename="magpie_tts_multilingual_357m.v2607.f16.gguf",
    url=(
        "https://huggingface.co/nvidia/magpie_tts_multilingual_357m/resolve/main/"
        "magpie_tts_multilingual_357m.v2607.f16.gguf"
    ),
    size_bytes=568_663_328,
)

#: NanoCodec decoder that turns Magpie's codec tokens into 22.05 kHz PCM.
NANO_CODEC_F16 = Artifact(
    filename="nemo_nano_codec_22khz_1.89kbps_21.5fps.decoder.f16.gguf",
    url=(
        "https://huggingface.co/nvidia/nemo-nano-codec-22khz-1.89kbps-21.5fps/resolve/main/"
        "nemo_nano_codec_22khz_1.89kbps_21.5fps.decoder.f16.gguf"
    ),
    size_bytes=78_823_104,
)

AUDIO8_ARTIFACTS: tuple[Artifact, ...] = (AUDIO8_REALISTIC_BF16,)
MAGPIE_ARTIFACTS: tuple[Artifact, ...] = (MAGPIE_V2607_F16, NANO_CODEC_F16)


def total_bytes(artifacts: tuple[Artifact, ...]) -> int:
    """Download footprint of a pack, for the settings/status surface."""
    return sum(a.size_bytes for a in artifacts)
