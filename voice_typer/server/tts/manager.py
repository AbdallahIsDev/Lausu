"""App-facing TTS manager: status, pack preparation, speak, compare.

This module exists so the IPC/service layer never touches runtimes or paths:
it resolves the HF-folder layout into concrete engines, downloads a pack when
asked, and renders or compares the configured engine with playback.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from voice_typer.server.duration import format_duration
from voice_typer.server.tts import packs, runtimes
from voice_typer.server.tts.engines import Audio8Engine, MagpieEngine
from voice_typer.server.tts.paths import (
    audio8_binary,
    bin_dir,
    magpie_binary,
    model_dir,
    tts_root,
    work_dir,
)
from voice_typer.server.tts.playback import play_wav, shutdown_playback, start_playback
from voice_typer.server.tts.samples import (
    SAMPLE_TEXT,
    bundled_sample_path,
    sample_cache_path,
    sample_lock,
)
from voice_typer.server.tts.service import TtsService
from voice_typer.server.tts.types import TtsError, TtsRequest
from voice_typer.server.tts.voices import (
    AUDIO8_VOICES as _AUDIO8_VOICE_ENTRIES,
    MAGPIE_LANGUAGES,
    default_voice,
    languages_for,
    normalize_language,
    normalize_voice,
    voice_gender,
    voices_for,
)
from voice_typer.server.tts.wav import probe_wav

log = logging.getLogger(__name__)

ENGINES = ("audio8", "magpie")
#: Backwards-compatible id tuples (the catalogue itself lives in ``voices``).
AUDIO8_VOICES = tuple(voice.id for voice in _AUDIO8_VOICE_ENTRIES)


def _first(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


@dataclass
class TtsManager:
    """Owns the TTS runtime lifecycle for the running app."""

    config: Any
    _service: TtsService | None = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------ paths

    def _audio8_engine(self) -> Audio8Engine | None:
        model = model_dir("audio8") / packs.AUDIO8_REALISTIC_BF16.filename
        binary = audio8_binary()
        if not (model.is_file() and binary.is_file()):
            return None
        backend = os.environ.get("VOICE_TYPER_AUDIO8_BACKEND", "vulkan")
        return Audio8Engine(binary=binary, model=model, backend=backend)

    def _magpie_engine(self) -> MagpieEngine | None:
        binary = magpie_binary()
        root = model_dir("magpie")
        magpie = _first(sorted(root.glob("**/magpie_tts_multilingual_357m*.gguf")))
        codec = _first(sorted(root.glob("**/*nano*codec*.gguf")))
        tokenizer = _first([p for p in root.glob("**/model_config.yaml")]) if root.is_dir() else None
        if not (binary.is_file() and magpie and codec and tokenizer):
            return None
        return MagpieEngine(binary=binary, magpie_model=magpie, codec_model=codec, tokenizer_dir=tokenizer.parent)

    def _tts_service(self) -> TtsService:
        audio8 = self._audio8_engine()
        magpie = self._magpie_engine()
        service = self._service
        if service is not None:
            # A pack can land (or vanish) while the app is running: tts_prepare
            # writes into the HF folder, and without this check a service built
            # on the first attempt would keep reporting the engine as absent
            # until the whole app restarted.
            changed = (service.audio8 is None) != (audio8 is None) or (service.magpie is None) != (magpie is None)
            if changed:
                service.stop()
                self._service = service = None
        if service is None:
            service = TtsService(workdir=tts_root() / "work", audio8=audio8, magpie=magpie)
            self._service = service
            atexit.register(service.stop)
        return service

    def _installed(self, engine: str) -> bool:
        """True when both the runtime binary and the model pack are on disk."""
        if engine == "audio8":
            return self._audio8_engine() is not None
        return self._magpie_engine() is not None

    def _runtime_for(self, engine: str) -> Path:
        """Return the engine runtime, installing it when the app may.

        An explicit ``VOICE_TYPER_AUDIO8_BIN`` / ``VOICE_TYPER_NEMO_SPEECH_BIN``
        override stays authoritative: installing over a path the user chose
        would be surprising, so a missing override is reported, not replaced.
        """
        override = os.environ.get("VOICE_TYPER_AUDIO8_BIN" if engine == "audio8" else "VOICE_TYPER_NEMO_SPEECH_BIN")
        if override:
            path = Path(override)
            if not path.is_file():
                raise TtsError(f"{engine} runtime missing at {path}")
            return path
        return runtimes.install(engine)

    # ----------------------------------------------------------------- status

    def status(self) -> dict[str, object]:
        """Everything the Models page needs to render engines, voices and the toggle."""
        audio8 = self._audio8_engine()
        magpie = self._magpie_engine()
        active = str(getattr(self.config, "tts_engine", "off") or "off")
        # With no engine selected the top-level lists stay the full catalogue
        # (the pre-existing wire contract); per-engine lists below are always
        # exact.
        active_voices = voices_for(active) if active in ENGINES else ()
        active_languages = languages_for(active) if active in ENGINES else MAGPIE_LANGUAGES
        configured_language = str(getattr(self.config, "tts_language", "") or "")
        return {
            "engine": active,
            "enabled": bool(getattr(self.config, "tts_enabled", False)),
            "voice": normalize_voice(active, getattr(self.config, "tts_voice", None))
            if active in ENGINES
            else getattr(self.config, "tts_voice", "Aria"),
            "language": normalize_language(active, configured_language) if active in ENGINES else configured_language,
            "root": str(tts_root()),
            # Top-level lists describe the ACTIVE engine (what will speak).
            "voices": [voice.to_dict() for voice in active_voices],
            "languages": list(active_languages),
            # What the Test control branches on BEFORE the click: a cached clip
            # plays instantly, an uncached one has to render first.
            "sample_cached": self._sample_cached_map(),
            "engines": {
                "audio8": {
                    "available": audio8 is not None,
                    "label": "Audio8 TTS Realistic 0.6B",
                    "download_bytes": packs.total_bytes(packs.AUDIO8_ARTIFACTS),
                    "models_dir": str(model_dir("audio8")),
                    "binary": str(audio8_binary()),
                    "capabilities": ["tts", "clone"],
                    "voices": [voice.to_dict() for voice in voices_for("audio8")],
                    "languages": list(languages_for("audio8")),
                    "default_voice": default_voice("audio8"),
                },
                "magpie": {
                    "available": magpie is not None,
                    "label": "MagpieTTS Multilingual 357M",
                    "download_bytes": packs.total_bytes(packs.MAGPIE_ARTIFACTS),
                    "models_dir": str(model_dir("magpie")),
                    "binary": str(magpie_binary()),
                    "capabilities": ["tts", "arabic"],
                    "voices": [voice.to_dict() for voice in voices_for("magpie")],
                    "languages": list(MAGPIE_LANGUAGES),
                    "default_voice": default_voice("magpie"),
                },
            },
        }

    # -------------------------------------------------------------- preparing

    def prepare(self, engine: str) -> dict[str, object]:
        """Download one engine's pack into the HF folder."""
        if engine == "audio8":
            self._runtime_for("audio8")
            target = model_dir("audio8")
            for artifact in packs.AUDIO8_ARTIFACTS:
                artifact.download(target)
            return {"engine": engine, "downloaded": [a.filename for a in packs.AUDIO8_ARTIFACTS]}
        if engine == "magpie":
            # Magpie's tokenizer lives inside its .nemo archive; the runtime's
            # own `pull` is the documented, verified way to fetch all three.
            binary = self._runtime_for("magpie")
            target = model_dir("magpie")
            target.mkdir(parents=True, exist_ok=True)
            env = {**os.environ, "NEMO_SPEECH_MODEL_DIR": str(target)}
            completed = subprocess.run(  # noqa: S603 - fixed argv
                [str(binary), "pull", "magpie"],
                capture_output=True,
                text=True,
                env=env,
                timeout=1800,
                check=False,
            )
            if completed.returncode != 0:
                raise TtsError(f"magpie pull failed: {(completed.stderr or completed.stdout)[-500:]}")
            return {"engine": engine, "models_dir": str(target)}
        raise TtsError(f"unknown tts engine: {engine}")

    # ---------------------------------------------------------------- speaking

    def _request(self, text: str, engine: str) -> TtsRequest:
        """Build the request with a voice this engine actually advertises."""
        return TtsRequest(
            text=text,
            voice=normalize_voice(engine, getattr(self.config, "tts_voice", None)) or None,
            language=normalize_language(engine, getattr(self.config, "tts_language", None)) or None,
        )

    def _resolved_remote_tts(self) -> Any | None:
        """Return the resolved REMOTE TTS provider, or ``None`` for the local path.

        Resolution is at call time (a provider may come online after save).
        ``local`` keeps today's engine path untouched; a typed provider error
        propagates so the UI can render it instead of silently falling back.
        """
        from voice_typer.server.model_providers import resolve_tts

        resolved = resolve_tts(self.config)
        return None if resolved.provider.id == "local" else resolved

    def _speak_via_provider(self, text: str, resolved: Any, *, play: bool) -> dict[str, object]:
        """Synthesize through a remote provider and (optionally) play it."""
        from voice_typer.server.model_providers.contracts.tts import TtsRequest

        client = resolved.client()
        voice = str(getattr(self.config, "tts_voice_id", "") or "") or None
        language = str(getattr(self.config, "tts_language", "") or "") or None
        started = time.perf_counter()
        audio = client.synthesize(TtsRequest(text=text, voice=voice, language=language))
        wall_s = time.perf_counter() - started
        out = work_dir(resolved.provider.id) / "speak.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(audio.data)
        played = play_wav(out) if play else 0.0
        duration, sample_rate = probe_wav(out)
        log.info(
            "[TTS] speak provider=%s model=%s voice=%s %s",
            resolved.provider.id,
            resolved.model_id or "default",
            voice or "default",
            f"{wall_s:.1f}s",
        )
        return {
            "engine": resolved.provider.id,
            "wav_path": str(out),
            "duration_s": round(duration, 3),
            "wall_s": round(wall_s, 3),
            "realtime_factor": round(duration / wall_s, 2) if wall_s else 0.0,
            "sample_rate": sample_rate,
            "played_s": round(played, 3),
        }

    def speak(self, text: str, engine: str | None = None, *, play: bool = True) -> dict[str, object]:
        """Render with ``engine`` (default: the configured one), play it, report timings.

        ``play=False`` renders and returns the wav path without touching the
        speakers (the TTS domain contract consumes bytes, not playback).
        """
        if not text.strip():
            raise TtsError("tts: empty text")
        remote = self._resolved_remote_tts()
        if remote is not None:
            return self._speak_via_provider(text, remote, play=play)
        engine = engine or getattr(self.config, "tts_engine", "off")
        if engine not in ENGINES:
            raise TtsError("tts is turned off; pick Audio8 or Magpie first")
        if not self._installed(engine):
            raise TtsError(
                f"{engine} is not installed: no runtime in {bin_dir(engine)} or no model pack in {model_dir(engine)}"
            )
        service = self._tts_service()
        out = work_dir(engine) / "speak.wav"
        request = self._request(text, engine)
        result = service.synthesize(request, engine, out)
        played = self._start_playback(result.wav_path, engine, request.voice or "", cached=False) if play else 0.0
        return {
            "engine": engine,
            "voice": request.voice or "",
            "wav_path": str(result.wav_path),
            "duration_s": round(result.duration_s, 3),
            "wall_s": round(result.wall_s, 3),
            "realtime_factor": round(result.realtime_factor, 2),
            "sample_rate": result.sample_rate,
            "played_s": round(played, 3),
            "playing": bool(play),
        }

    def speak_sample(self, engine: str | None = None, voice: str | None = None) -> dict[str, object]:
        """Play a voice sample, rendering it only the first time.

        Resolution: bundled asset -> cached render -> render once into the
        cache. Selecting a voice never calls this; the Test button does.
        """
        engine = engine or getattr(self.config, "tts_engine", "off")
        if engine not in ENGINES:
            raise TtsError("tts is turned off; pick Audio8 or Magpie first")
        if not self._installed(engine):
            raise TtsError(
                f"{engine} is not installed: no runtime in {bin_dir(engine)} or no model pack in {model_dir(engine)}"
            )
        chosen = normalize_voice(engine, voice or getattr(self.config, "tts_voice", None))
        language = normalize_language(engine, getattr(self.config, "tts_language", ""))
        bundled = bundled_sample_path(engine, chosen)
        cached_path = sample_cache_path(engine, chosen, language)
        wall_s = 0.0
        if bundled is not None:
            wav_path, cached, from_bundle = bundled, True, True
        elif cached_path.is_file() and cached_path.stat().st_size > 0:
            wav_path, cached, from_bundle = cached_path, True, False
        else:
            with sample_lock():
                if cached_path.is_file() and cached_path.stat().st_size > 0:
                    wav_path, cached, from_bundle = cached_path, True, False
                else:
                    started = time.perf_counter()
                    result = self._tts_service().synthesize(
                        TtsRequest(text=SAMPLE_TEXT, voice=chosen, language=language or None),
                        engine,
                        cached_path,
                    )
                    wall_s = time.perf_counter() - started
                    wav_path, cached, from_bundle = result.wav_path, False, False
        kind = "bundled" if from_bundle else ("cached" if cached else "rendered")
        log.info(
            "[TTS] sample engine=%s voice=%s %s%s",
            engine,
            self._voice_label(engine, chosen),
            kind,
            f" {wall_s:.1f}s" if wall_s else "",
        )
        duration, sample_rate = probe_wav(wav_path)
        self._start_playback(wav_path, engine, chosen, cached=cached)
        return {
            "engine": engine,
            "voice": chosen,
            "language": language,
            "wav_path": str(wav_path),
            "duration_s": round(duration, 3),
            "wall_s": round(wall_s, 3),
            "realtime_factor": round(duration / wall_s, 2) if wall_s else 0.0,
            "sample_rate": sample_rate,
            "played_s": round(duration, 3),
            "cached": cached,
            "bundled": from_bundle,
            "playing": True,
        }

    # ------------------------------------------------------------- playback

    def _voice_label(self, engine: str, voice: str) -> str:
        """``Sofia(female)`` for logs, so a wrong voice is visible at a glance."""
        gender = voice_gender(engine, voice)
        return f"{voice}({gender})" if gender else voice

    def _publish_playback_state(self, engine: str, voice: str, state: str, cached: bool) -> None:
        """Push one playback transition (start / stop / natural end)."""
        try:
            from voice_typer.server import event_bus

            event_bus.publish(
                {
                    "type": "tts_playback_state",
                    "data": {
                        "engine": engine,
                        "voice": voice,
                        "state": state,
                        "cached": bool(cached),
                    },
                }
            )
        except Exception:
            log.debug("[TTS] playback-state publish failed", exc_info=True)

    def _start_playback(self, wav_path: Path, engine: str, voice: str, *, cached: bool) -> float:
        """Start playing ``wav_path`` and return immediately; report the duration."""
        self._publish_playback_state(engine, voice, "playing", cached)
        try:
            return start_playback(
                wav_path,
                on_finished=lambda interrupted, error: self._publish_playback_state(
                    engine, voice, "stopped" if interrupted else "finished", cached
                ),
            )
        except Exception:
            self._publish_playback_state(engine, voice, "stopped", cached)
            raise

    def stop_playback(self) -> bool:
        """Stop the current clip; True when one was playing."""
        from voice_typer.server.tts.playback import stop_playback as _stop

        return _stop()

    # --------------------------------------------------------------- prewarm

    def is_sample_cached(self, engine: str, voice: str | None, language: str | None) -> bool:
        """True when Test can play this clip without rendering it."""
        if engine not in ENGINES:
            return False
        chosen = normalize_voice(engine, voice)
        code = normalize_language(engine, language)
        if bundled_sample_path(engine, chosen) is not None:
            return True
        try:
            path = sample_cache_path(engine, chosen, code)
            return path.is_file() and path.stat().st_size > 0
        except OSError:
            return False

    def _sample_cached_map(self) -> dict[str, dict[str, dict[str, bool]]]:
        """engine → voice → language → cached, computed without rendering."""
        return {
            engine: {
                voice.id: {code: self.is_sample_cached(engine, voice.id, code) for code in languages_for(engine)}
                for voice in voices_for(engine)
            }
            for engine in ENGINES
        }

    def prewarm(self, engine: str) -> bool:
        """Start ``engine``'s runtime ahead of the first click (background)."""
        if engine not in ENGINES or not self._installed(engine):
            log.debug("[TTS] prewarm skipped engine=%s installed=False", engine)
            return False
        started = time.perf_counter()
        self._tts_service().ensure_started(engine)
        log.info("[TTS] prewarm engine=%s ready%s", engine, format_duration(time.perf_counter() - started))
        return True

    def shutdown(self) -> None:
        """Stop playback + every runtime (app shutdown)."""
        shutdown_playback()
        if self._service is not None:
            self._service.stop()
            self._service = None


def describe(manager: TtsManager) -> str:
    """Compact one-line status for logs and issue reports."""
    return json.dumps(manager.status(), sort_keys=True)
