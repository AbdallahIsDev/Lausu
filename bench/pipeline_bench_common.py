"""Shared asset guards and real-runtime wrappers for the pipeline benchmark.

Everything in this module is bench-only. It resolves models through the app's own
resolvers and refuses to run when an asset is absent; it never downloads.
"""

from __future__ import annotations

import statistics
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BENCH_DIR))

from bench_translation import join_chunk_outputs  # noqa: E402
from voice_typer.server.gguf_download import resolve_gguf_model_path  # noqa: E402
from voice_typer.server.translation import service as translation_service  # noqa: E402
from voice_typer.server.translation.chunking import bounded_chunks  # noqa: E402
from voice_typer.worker.asr_runner.runner import GgufRunner  # noqa: E402

SAMPLE_RATE = 16000
DEFAULT_WAV = Path(r"C:\Users\11\gguf-spike\audio\test16k.wav")
DEFAULT_LIBRARY = Path(
    r"C:\Users\11\gguf-spike\bin\cpu-vulkan\out\transcribe-native-windows-x86_64-cpu-vulkan\transcribe.dll"
)
DEFAULT_TRANSLATION_MODEL = Path(
    r"C:\Users\11\.cache\huggingface\hub\models--IndexTeam--Index-Translate-2B-GGUF\snapshots"
    r"\3a0eca6ce931d88d00614d427ab3ed8ff0743902\Index-Translate-2B.Q4_K_M.gguf"
)
DEFAULT_TRANSLATION_RUNTIME = Path(r"C:\Users\11\AppData\Roaming\lausu\translation\llama-server.exe")
DEFAULT_TRANSCRIBE_PACKAGE = Path(r"C:\Users\11\gguf-spike\venv\Lib\site-packages")


def require_existing(path: Path, label: str) -> Path:
    """Fail loudly for a missing on-disk asset; no fetch path exists here."""
    if not path.is_file():
        raise SystemExit(
            f"Missing {label}: {path}. This benchmark never downloads; "
            "install the asset yourself and pass its absolute path."
        )
    return path


def resolve_assets(args: Any) -> dict[str, str]:
    """Resolve every asset locally; use the app's resolvers where they exist."""
    asr_model = resolve_gguf_model_path("parakeet")
    if asr_model is None:
        raise SystemExit(
            "Missing local ASR GGUF (parakeet-ultra-Q8_0.gguf in the HuggingFace cache). "
            "This benchmark never downloads. Pass an already-installed file via the app's cache."
        )
    config = translation_config(args, gpu=True)
    try:
        model = translation_service.resolve_model_path(config)
        runtime = translation_service.resolve_runtime_path(config)
    except Exception as exc:
        raise SystemExit(f"Missing translation asset: {exc}. This benchmark never downloads.") from exc
    paths = {
        "asr_model": str(require_existing(Path(asr_model), "ASR GGUF")),
        "transcribe_library": str(require_existing(Path(args.library), "transcribe.dll")),
        "wav": str(require_existing(Path(args.audio), "recorded WAV")),
        "translation_model": str(require_existing(Path(model), "translation GGUF")),
        "translation_runtime": str(require_existing(Path(runtime), "llama-server.exe")),
        "transcribe_package": str(
            require_existing(Path(args.package) / "transcribe_cpp" / "__init__.py", "transcribe_cpp package")
        ),
    }
    for key, path in list(paths.items()):
        paths[key + "_bytes"] = str(Path(path).stat().st_size)
    return paths


def translation_config(args: Any, *, gpu: bool) -> SimpleNamespace:
    """Build the same config shape the bench_translation harness uses."""
    return SimpleNamespace(
        translation_enabled=True,
        translation_model="index-translate-2b-q4-k-m",
        translation_model_path=str(getattr(args, "translation_model", "") or ""),
        translation_runtime_path=str(getattr(args, "translation_runtime", "") or ""),
        translation_gpu_enabled=gpu,
        translation_glossary="",
        language=str(getattr(args, "spoken_language", "") or ""),
    )


def load_wav_slice(path: Path, seconds: float) -> tuple[Any, float]:
    """Load a real 16 kHz mono 16-bit WAV slice; never synthesise audio."""
    import numpy as np

    with wave.open(str(path), "rb") as handle:
        if handle.getframerate() != SAMPLE_RATE or handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise SystemExit(f"Unsupported WAV format in {path}: expected 16 kHz mono 16-bit")
        frames = min(handle.getnframes(), round(seconds * SAMPLE_RATE))
        pcm16 = np.frombuffer(handle.readframes(frames), dtype="<i2")
    audio = pcm16.astype(np.float32) / 32768.0
    return audio, len(audio) / SAMPLE_RATE


def summary(values: list[float]) -> dict[str, float | None]:
    """Summary of real measurements; empty input stays honestly empty."""
    if not values:
        return {"median": None, "p90": None, "min": None, "max": None, "count": 0}
    ordered = sorted(values)
    return {
        "median": round(statistics.median(ordered), 3),
        "p90": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))], 3),
        "min": round(ordered[0], 3),
        "max": round(ordered[-1], 3),
        "count": len(ordered),
    }


class Translator:
    """Owns the production translation service for one GPU/CPU configuration."""

    def __init__(self, args: Any, target_language: str) -> None:
        self._args = args
        self.target = target_language
        self.service: Any = None
        self.config: Any = None
        self._gpu: bool | None = None

    def start(self, *, gpu: bool) -> float:
        """Start (or switch) the runtime; return cold-start seconds (0 when reused)."""
        if self.service is not None and self._gpu == gpu:
            return 0.0
        self.stop()
        self.config = translation_config(self._args, gpu=gpu)
        started = time.perf_counter()
        self.service = translation_service.get_service(self.config)
        self.service.ensure_runtime()
        self._gpu = gpu
        elapsed = time.perf_counter() - started
        return round(elapsed, 3)

    def translate(self, text: str) -> str:
        if self.service is None:
            raise RuntimeError("translator was not started")
        return self.service.translate(text, self.target)

    def stop(self) -> None:
        if self.service is None:
            return
        translation_service.shutdown()
        self.service = None
        self._gpu = None


def translate_bounded(translator: Translator, text: str, max_chars: int = 1600) -> tuple[str, float, int]:
    """Translate long text through bounded chunks; return (text, seconds, chunk_count)."""
    chunks = bounded_chunks(text, max_chars)
    started = time.perf_counter()
    outputs = [translator.translate(chunk) for chunk in chunks]
    elapsed = time.perf_counter() - started
    return join_chunk_outputs(chunks, outputs), round(elapsed, 3), len(chunks)


class Sampler:
    """Sample process RSS and GPU memory while a run is in flight."""

    def __init__(self, interval: float = 0.25) -> None:
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.rss_mb: list[int] = []
        self.child_rss_mb: list[int] = []
        self.vram_mb: list[int] = []
        self.nvidia_smi = False

    def __enter__(self) -> Sampler:
        import shutil

        import psutil

        self._proc = psutil.Process()
        self.nvidia_smi = shutil.which("nvidia-smi") is not None

        def loop() -> None:
            while not self._stop.is_set():
                try:
                    self.rss_mb.append(int(self._proc.memory_info().rss / (1024 * 1024)))
                    children = [
                        int(child.memory_info().rss / (1024 * 1024))
                        for child in self._proc.children(recursive=True)
                        if "llama" in child.name().lower() or "transcribe" in child.name().lower()
                    ]
                    if children:
                        self.child_rss_mb.append(max(children))
                except Exception:
                    pass
                if self.nvidia_smi:
                    try:
                        out = subprocess.run(
                            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                            capture_output=True,
                            text=True,
                            timeout=2,
                            check=False,
                        )
                        if out.returncode == 0:
                            self.vram_mb.append(int(out.stdout.strip().splitlines()[0].strip()))
                    except Exception:
                        pass
                self._stop.wait(self._interval)

        self._thread = threading.Thread(target=loop, name="bench-memory-sample", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None

    def report(self) -> dict[str, Any]:
        return {
            "rss_mb_sampled": summary([float(value) for value in self.rss_mb]),
            "child_rss_mb_sampled": summary([float(value) for value in self.child_rss_mb]),
            "vram_mb_sampled": summary([float(value) for value in self.vram_mb]),
            "note": "sampled every 0.25 s, NOT peak; VRAM is whole-GPU via nvidia-smi",
            "nvidia_smi_available": self.nvidia_smi,
        }


class AsrRunner:
    """Wrap the app's real GGUF ctypes runner with one wrapper per backend."""

    def __init__(self, model_path: str, library: str) -> None:
        import os

        os.environ["TRANSCRIBE_LIBRARY"] = library
        self.model_path = model_path
        self._runners: dict[str, GgufRunner] = {}
        self.load_seconds: dict[str, float] = {}

    def transcribe(self, audio: Any, backend: str, language: str = "en") -> Any:
        runner = self._runners.get(backend)
        if runner is None:
            started = time.perf_counter()
            runner = GgufRunner(self.model_path)
            runner._loader()
            self.load_seconds[backend] = round(time.perf_counter() - started, 3)
            self._runners[backend] = runner
        return runner.transcribe(audio, language=language, backend=backend)


class NativeAsrRunner:
    """Same DLL via its Python binding, with real word timestamps and a persistent model."""

    def __init__(self, model_path: str, library: str, package: str) -> None:
        import os

        os.environ["TRANSCRIBE_LIBRARY"] = library
        package_dir = str(Path(package).resolve().parent.parent)
        if package_dir not in sys.path:
            sys.path.insert(0, package_dir)
        import transcribe_cpp

        self._cpp = transcribe_cpp
        self.model_path = model_path
        self._models: dict[str, Any] = {}
        self.load_seconds: dict[str, float] = {}

    def _model(self, backend: str) -> Any:
        model = self._models.get(backend)
        if model is None:
            started = time.perf_counter()
            model = self._cpp.Model(self.model_path, backend=backend)
            self.load_seconds[backend] = round(time.perf_counter() - started, 3)
            self._models[backend] = model
        return model

    def transcribe(self, audio: Any, backend: str, language: str = "en") -> Any:
        model = self._model(backend)
        with model.session(n_threads=8) as session:
            result = session.run(audio, language=language, timestamps="word")
        return result
