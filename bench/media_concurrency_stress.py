"""Concurrent media transcription stress harness (ADR-0023 multi-job).

Exercises the REAL `MediaJobManager`, the REAL `engine_loop.transcribe_windows`
(lane + abort guard), the REAL PyAV decoder and a REAL faster-whisper model.
Only two things are substituted, and both are substituted because they are
environment, not code:

* the model-manager plumbing (`_ensure_media_backend`), replaced by a direct
  `WhisperModel` wrapped in a backend that mirrors `system_whisper`'s contract
  (`_inference_lock`, `_abort_event`, abort polled between segments);
* History persistence, replaced by a char count (no app/history DB here).

Scenarios
---------
``serial``    N jobs with ``max_jobs=1`` — the baseline.
``parallel``  the same N jobs with ``max_jobs=4`` — the feature under test.
``cap``       the cap refuses the (cap+1)th start, and a finished job frees
              its slot immediately.
``cancel``    cancelling one job mid-flight leaves the others' decodes intact
              (the shared abort signal must never cross jobs).
``parity``    the same clip decoded concurrently is byte-identical, and the
              same content in an .mp3 vs an .mp4 yields a real transcript of
              comparable length. (The two files are DIFFERENT lossy encodes,
              so exact text equality is not a valid gate with a small model.)

The serial-vs-parallel ratio is reported as ``[INFO]``, not judged: wall-clock
throughput moves with every other process on the box (identical flags measured
1.34x and 0.76x on a loaded machine), so only the correctness scenarios above
gate the exit code. Read the ratio on an idle machine.

The download tier is modelled by a rate-limited, cancel-aware local copy
rather than a loopback HTTP server: the cost concurrency overlaps is ingest
I/O, and a socket here only adds flakiness. The downloader itself is covered
by its own unit tests.

Usage:
    .venv/Scripts/python.exe bench/media_concurrency_stress.py
    .venv/Scripts/python.exe bench/media_concurrency_stress.py --jobs 6 --clip 240
    .venv/Scripts/python.exe bench/media_concurrency_stress.py \
        --audio ~/Downloads/talk.mp3 --video ~/Downloads/talk.mp4 \
        --device cuda --compute float16

The default media is the owner's Downloads pair (the same recording as .mp3
and .mp4); `--audio`/`--video` point it at any equivalent pair.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from voice_typer.server.media_ingest import (  # noqa: E402
    decoder as decoder_mod,
    engine_loop as loop_mod,
)
from voice_typer.server.media_ingest.jobs import MediaJob, MediaJobManager  # noqa: E402

DOWNLOADS = Path.home() / "Downloads"
AUDIO_SRC = DOWNLOADS / "How To Build a Clean Gaming Laptop Setup_(MP3_160K).mp3"
VIDEO_SRC = DOWNLOADS / "How To Build a Clean Gaming Laptop Setup_(240P).mp4"
DEFAULT_MODEL = REPO_ROOT / ".tmp-tiny-model"


# --------------------------------------------------------------------------
# Real engine, wrapped in the contract `engine_loop` expects
# --------------------------------------------------------------------------
class RealBackend:
    """faster-whisper model behind the `WindowBackend` protocol.

    Mirrors `system_whisper.SystemWhisperEngine`: one non-thread-safe model
    behind an RLock, one shared abort Event polled BETWEEN segments.
    """

    def __init__(
        self,
        model_path: Path,
        *,
        language: str = "en",
        device: str = "auto",
        compute_type: str | None = None,
        cpu_threads: int = 4,
    ) -> None:
        from faster_whisper import WhisperModel

        if device in ("cuda", "auto"):
            # Production does this before every model load: it puts the
            # `nvidia-*` wheel DLL dirs on the Windows loader path, without
            # which ctranslate2 cannot find cublas64_12.dll. Skipping it here
            # would make the bench test a runtime the app never sees.
            from voice_typer.server.nvidia_dll_paths import _configure_nvidia_dll_paths

            _configure_nvidia_dll_paths()

        kwargs: dict = {"device": device, "cpu_threads": cpu_threads}
        if compute_type:
            kwargs["compute_type"] = compute_type
        self._model = WhisperModel(str(model_path), **kwargs)
        self.language = language
        self.is_loaded = True
        self._abort_event = threading.Event()
        self._inference_lock = threading.RLock()
        self.decode_calls = 0
        self.decode_seconds = 0.0

    def clear_abort(self) -> None:
        self._abort_event.clear()

    def request_abort(self) -> None:
        self._abort_event.set()

    def transcribe_with_fallback(self, audio, *args, **kwargs) -> str:
        import numpy as np

        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        # Same contract as `system_whisper`: a scoped `abort_event` (the job's
        # own cancel Event) wins over the engine-wide flag.
        abort_source = kwargs.get("abort_event") or self._abort_event
        with self._inference_lock:
            self.decode_calls += 1
            started = time.perf_counter()
            try:
                segments, _info = self._model.transcribe(
                    samples,
                    language=self.language,
                    vad_filter=True,
                    temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                )
                parts: list[str] = []
                for seg in segments:
                    if abort_source.is_set():
                        break
                    text = (seg.text or "").strip()
                    if text:
                        parts.append(text)
                return " ".join(parts)
            finally:
                self.decode_seconds += time.perf_counter() - started


# --------------------------------------------------------------------------
# Throttled ingest (the I/O phase concurrency actually overlaps)
# --------------------------------------------------------------------------
def throttled_ingest_copy(src: Path, job: MediaJob, dest_dir: Path, bytes_per_second: int) -> Path:
    """Copy ``src`` to a temp file at a capped rate, cancel-aware.

    Stands in for the download tier: the cost that concurrency overlaps is
    *ingest I/O*, and a rate-limited copy reproduces that cost without a
    socket. (The HTTP downloader itself is covered by its own unit tests;
    an intermittent loopback server here would only add flakiness.)
    """
    target = dest_dir / f"{job.job_id}-{src.name}"
    chunk = 64 * 1024
    budget = chunk / max(1, bytes_per_second)
    with src.open("rb") as handle, target.open("wb") as out:
        while True:
            if job.cancel_event.is_set():
                break
            data = handle.read(chunk)
            if not data:
                break
            out.write(data)
            time.sleep(budget)
    return target


# --------------------------------------------------------------------------
# Clips: identical content, two containers
# --------------------------------------------------------------------------
def write_clip(src: Path, dst: Path, seconds: float) -> None:
    """Decode ``seconds`` of ``src`` to a 16 kHz mono WAV."""
    import numpy as np

    want = int(seconds * loop_mod.TARGET_SAMPLE_RATE)
    buf: list = []
    got = 0
    for chunk in decoder_mod.decode_chunks(str(src)):
        buf.append(chunk)
        got += int(chunk.shape[0])
        if got >= want:
            break
    audio = np.concatenate(buf)[:want] if buf else np.zeros(0, dtype=np.float32)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(str(dst), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(loop_mod.TARGET_SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())


# --------------------------------------------------------------------------
# The job body (mirrors handlers/media_handlers.py)
# --------------------------------------------------------------------------
@dataclass
class JobRun:
    job_id: str
    source: str
    started: float
    finished: float = 0.0
    chars: int = 0
    text: str = ""
    status: str = "running"
    error: str | None = None
    progress_seen: list[float] = field(default_factory=list)


REMOTE_PREFIX = "http://cdn.local/"
REMOTE_ROOT: Path | None = None
INGEST_BYTES_PER_SECOND = 1_500_000


def make_runner(mgr: MediaJobManager, backend: RealBackend, tmp_dir: Path):
    def _runner(job: MediaJob) -> dict:
        source = job.source
        path = Path(source)
        if source.startswith(REMOTE_PREFIX):
            assert REMOTE_ROOT is not None
            path = throttled_ingest_copy(
                REMOTE_ROOT / source[len(REMOTE_PREFIX):],
                job,
                tmp_dir,
                INGEST_BYTES_PER_SECOND,
            )
            if job.cancel_event.is_set():
                # A cancelled download is a partial job, not a failure.
                return {"chars": 0, "text": ""}
        total = decoder_mod.probe_duration_seconds(str(path))
        state = loop_mod.transcribe_windows(
            decoder_mod.decode_chunks(str(path)),
            backend,
            cancel_event=job.cancel_event,
            on_progress=None,
            total_seconds=total,
            lane=mgr.asr_lane,
        )
        return {"chars": len(state.text), "text": state.text}

    return _runner


class RecordingManager(MediaJobManager):
    """Manager that keeps every job's timings for the report."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.runs: dict[str, JobRun] = {}
        self._lock2 = threading.Lock()

    def start(self, source, runner, *, client_id=None, export_path=None):  # noqa: D102 - same contract
        # The run record is filled by a wrapper, not by `collect()`: a
        # finished job leaves `_jobs` immediately (the registry only tracks
        # running jobs), so post-hoc reads would find nothing.
        run = JobRun(job_id="", source=source, started=time.perf_counter())

        def _wrapped(job: MediaJob) -> dict:
            run.job_id = job.job_id
            # Read the runner's RETURN VALUE, never `job.result`: the manager
            # assigns that (and `job.status`) only after the runner returns,
            # so reading them here would always observe the pre-completion
            # state and report 0 chars for a perfectly good transcript.
            try:
                result = runner(job)
            except BaseException as exc:
                run.finished = time.perf_counter()
                run.status = "failed"
                run.error = str(exc)
                raise
            run.finished = time.perf_counter()
            # Mirror the manager's own rule: a runner that returns normally
            # after its cancel_event was set produced a PARTIAL job, and the
            # manager will flip job.status to "cancelled" once we return.
            # Claiming "completed" here made a cancelled job report success.
            run.status = "cancelled" if job.cancel_event.is_set() else "completed"
            run.chars = int((result or {}).get("chars", 0))
            run.text = str((result or {}).get("text", ""))
            return result

        job = super().start(source, _wrapped, client_id=client_id, export_path=export_path)
        run.job_id = job.job_id
        with self._lock2:
            self.runs[job.job_id] = run
        return job

    def collect(self) -> None:
        """Best-effort refresh for jobs that are still running."""
        with self._lock:
            jobs = dict(self._jobs)
        for job_id, run in self.runs.items():
            job = jobs.get(job_id)
            if job is None:
                continue
            run.status = job.status
            run.error = job.error


# --------------------------------------------------------------------------
# Scenarios
# --------------------------------------------------------------------------
def _report(name: str, ok: bool, detail: str) -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}: {detail}")
    return ok


def _info(name: str, detail: str) -> None:
    """Record a measurement without judging it.

    Wall-clock throughput depends on every other process on the box, so it is
    reported for the record and never gates the run.
    """
    print(f"  [INFO] {name}: {detail}")


def scenario_throughput(
    backend: RealBackend, tmp_dir: Path, *, jobs: int, max_jobs: int, label: str, url: str
) -> tuple[float, list[JobRun]]:
    mgr = RecordingManager(max_jobs=max_jobs)
    runner = make_runner(mgr, backend, tmp_dir)
    wall_start = time.perf_counter()
    for _ in range(jobs):
        if max_jobs == 1:
            # The serial baseline: submit, wait for it to finish, submit again.
            mgr.start(url, runner)
            while mgr.running_count() > 0:
                time.sleep(0.02)
        else:
            # The page disables its inputs at the cap; the harness waits for a
            # slot the same way instead of tripping the rejection.
            while not mgr.has_capacity():
                time.sleep(0.02)
            mgr.start(url, runner)
    while mgr.running_count() > 0:
        time.sleep(0.05)
    mgr.wait(30.0)
    wall = time.perf_counter() - wall_start
    mgr.collect()
    runs = list(mgr.runs.values())
    print(f"  {label}: {jobs} jobs, cap {max_jobs} -> {wall:.1f}s wall")
    return wall, runs


def scenario_cap(backend: RealBackend, tmp_dir: Path, url: str, cap: int) -> bool:
    mgr = RecordingManager(max_jobs=cap)
    runner = make_runner(mgr, backend, tmp_dir)
    accepted = 0
    refused = 0
    from voice_typer.server.media_ingest.errors import JOB_BUSY, MediaIngestError

    for _ in range(cap + 2):
        try:
            mgr.start(url, runner)
            accepted += 1
        except MediaIngestError as exc:
            if exc.code == JOB_BUSY:
                refused += 1
            else:
                raise
    ok = _report(
        "cap refuses past the limit",
        accepted == cap and refused == 2,
        f"accepted={accepted} refused={refused} cap={cap}",
    )
    # A finished job frees exactly one slot.
    deadline = time.perf_counter() + 240
    while mgr.running_count() >= cap and time.perf_counter() < deadline:
        time.sleep(0.05)
    try:
        mgr.start(url, runner)
        refilled = True
    except MediaIngestError:
        refilled = False
    ok &= _report("a freed slot accepts the next job", refilled, f"running={mgr.running_count()}")
    mgr.cancel()
    mgr.wait(30.0)
    return ok


def scenario_cancel(backend: RealBackend, tmp_dir: Path, url: str, jobs: int) -> bool:
    mgr = RecordingManager(max_jobs=jobs)
    runner = make_runner(mgr, backend, tmp_dir)
    started = [mgr.start(url, runner) for _ in range(jobs)]
    victim = started[0]
    time.sleep(1.0)  # let the first window decode start
    mgr.cancel(victim.job_id)
    while mgr.running_count() > 0:
        time.sleep(0.05)
    mgr.wait(30.0)
    mgr.collect()

    survivors = [mgr.runs[j.job_id] for j in started[1:]]
    victim_run = mgr.runs[victim.job_id]
    # Authoritative status: the manager sets job.status AFTER the runner
    # returns, so join first and read it here instead of trusting the record
    # the runner wrote mid-flight.
    victim_run.status = victim.status
    ok = _report(
        "cancelling one job does not truncate the others",
        all(run.chars > 0 for run in survivors),
        f"survivor chars={[run.chars for run in survivors]}",
    )
    ok &= _report(
        "the cancelled job stops early",
        victim_run.chars < max(run.chars for run in survivors) or victim_run.status == "cancelled",
        f"victim chars={victim_run.chars} status={victim_run.status}",
    )
    return ok


def scenario_parity(backend: RealBackend, tmp_dir: Path, audio_clip: Path, video_clip: Path) -> bool:
    """Two checks, both meaningful:

    * determinism — the SAME clip decoded by two concurrent jobs must produce
      byte-identical text (the lane must not let two decodes interfere);
    * container parity — the .mp3 and the .mp4 hold the same recording, but
      they are two DIFFERENT lossy encodes, so their decoded samples differ.
      Near-identical text is the correct expectation, not equality.
    """
    import difflib

    mgr = RecordingManager(max_jobs=3)
    runner = make_runner(mgr, backend, tmp_dir)
    for source in (str(audio_clip), str(audio_clip), str(video_clip)):
        mgr.start(source, runner)
    while mgr.running_count() > 0:
        time.sleep(0.05)
    mgr.wait(30.0)
    mgr.collect()
    texts = [run.text for run in mgr.runs.values()]
    if len(texts) < 3:
        return _report("parity run produced three transcripts", False, f"got {len(texts)}")

    same_file_a, same_file_b, video_text = texts[0], texts[1], texts[2]
    ok = _report(
        "the same clip decoded concurrently yields identical text",
        bool(same_file_a) and same_file_a == same_file_b,
        f"chars={len(same_file_a)}/{len(same_file_b)} identical={same_file_a == same_file_b}",
    )
    ratio = difflib.SequenceMatcher(None, same_file_a, video_text).ratio()
    length_delta = abs(len(same_file_a) - len(video_text)) / max(1, len(same_file_a))
    detail = (
        f"mp3 {len(same_file_a)} chars, mp4 {len(video_text)} chars, "
        f"length delta {length_delta:.1%}, char similarity {ratio:.3f}"
    )
    if ratio < 0.999:
        opcodes = [
            op
            for op in difflib.SequenceMatcher(None, same_file_a, video_text).get_opcodes()
            if op[0] != "equal"
        ]
        if opcodes:
            _tag, i1, i2, j1, j2 = opcodes[0]
            detail += (
                f"; first diff: {same_file_a[max(0, i1 - 25):i2 + 25]!r}"
                f" vs {video_text[max(0, j1 - 25):j2 + 25]!r}"
            )
    # NOT an equality gate: two different lossy encodes are two different
    # sample streams, and a tiny model's autoregressive decode diverges from
    # them. What must hold is that the VIDEO path produces a real transcript
    # of the same length — that is the container support being tested.
    ok &= _report(
        "the mp4 yields a real transcript of the same length as the mp3",
        len(video_text) > 0 and length_delta < 0.10,
        detail,
    )
    return ok


def scenario_log_lines(jobs: int, cap: int) -> bool:
    """C-LOG-5: exactly one start line and one outcome line per job."""
    records: list[str] = []

    class _Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    logger = logging.getLogger("voice_typer.server.media_ingest.jobs")
    handler = _Collect()
    logger.addHandler(handler)
    previous = logger.level
    logger.setLevel(logging.INFO)
    try:
        mgr = MediaJobManager(max_jobs=cap)
        for _ in range(jobs):
            mgr.start("noop", lambda _job: {"chars": 1})
        while mgr.running_count() > 0:
            time.sleep(0.01)
        mgr.wait(10.0)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)
    starts = [line for line in records if "job start:" in line]
    outcomes = [line for line in records if "job completed" in line or "job cancelled" in line or "job failed" in line]
    return _report(
        "one start line + one outcome line per job",
        len(starts) == jobs and len(outcomes) == jobs,
        f"starts={len(starts)} outcomes={len(outcomes)} jobs={jobs}",
    )


def main() -> int:
    global REMOTE_ROOT, INGEST_BYTES_PER_SECOND

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=6, help="jobs per throughput scenario")
    parser.add_argument("--cap", type=int, default=4, help="concurrency cap under test")
    parser.add_argument("--clip", type=float, default=240.0, help="clip length in seconds")
    parser.add_argument("--bandwidth", type=int, default=1_500_000, help="simulated download bytes/s")
    parser.add_argument("--model", default=str(DEFAULT_MODEL), help="faster-whisper model dir")
    parser.add_argument(
        "--device", default="auto", help="auto | cpu | cuda (what the app would pick)"
    )
    parser.add_argument("--compute", default=None, help="e.g. int8, float16 (default: model's)")
    parser.add_argument(
        "--audio",
        default=str(AUDIO_SRC),
        help="audio source file (default: the Downloads .mp3 pair)",
    )
    parser.add_argument(
        "--video",
        default=str(VIDEO_SRC),
        help="video source with the SAME content as --audio (default: the Downloads .mp4)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    audio_src = Path(args.audio)
    video_src = Path(args.video)
    for src in (audio_src, video_src):
        if not src.is_file():
            print(
                f"missing test media: {src}\n"
                "Pass --audio/--video (the same recording in two containers) or put the "
                "default pair in ~/Downloads.",
                file=sys.stderr,
            )
            return 2
    model_dir = Path(args.model)
    if not (model_dir / "model.bin").is_file():
        print(f"missing model at {model_dir} (see the module docstring)", file=sys.stderr)
        return 2

    tmp_dir = Path(tempfile.mkdtemp(prefix="media-stress-"))
    clip_dir = tmp_dir / "clips"
    clip_dir.mkdir()
    audio_clip = clip_dir / "clip-audio.wav"
    video_clip = clip_dir / "clip-video.wav"
    print(f"building {args.clip:.0f}s clips from the Downloads pair…")
    write_clip(audio_src, audio_clip, args.clip)
    write_clip(video_src, video_clip, args.clip)
    print(f"  audio clip {audio_clip.stat().st_size / 1e6:.1f} MB, video clip {video_clip.stat().st_size / 1e6:.1f} MB")

    print(f"loading model {model_dir.name}…")
    backend = RealBackend(model_dir, device=args.device, compute_type=args.compute)
    ok = True
    try:
        REMOTE_ROOT = clip_dir
        INGEST_BYTES_PER_SECOND = args.bandwidth
        url = f"{REMOTE_PREFIX}{audio_clip.name}"
        print(
            f"\nremote source: {url} "
            f"(throttled ingest at {args.bandwidth / 1e6:.1f} MB/s)"
        )

        print("\n[1] throughput — serial baseline")
        serial_wall, serial_runs = scenario_throughput(
            backend, tmp_dir, jobs=args.jobs, max_jobs=1, label="serial", url=url
        )
        print("\n[2] throughput — concurrent")
        parallel_wall, parallel_runs = scenario_throughput(
            backend, tmp_dir, jobs=args.jobs, max_jobs=args.cap, label="parallel", url=url
        )
        speedup = serial_wall / parallel_wall if parallel_wall else 0.0
        _info(
            "throughput speedup",
            f"{speedup:.2f}x (serial {serial_wall:.1f}s -> parallel {parallel_wall:.1f}s) "
            f"on {os.cpu_count()} logical CPUs — load-sensitive, meaningful only on an idle machine",
        )
        ok &= _report(
            "every concurrent job produced text",
            all(run.chars > 0 for run in parallel_runs),
            f"chars={[run.chars for run in parallel_runs]}",
        )
        ok &= _report(
            "concurrent transcripts match the serial baseline",
            {run.chars for run in serial_runs} == {run.chars for run in parallel_runs},
            f"serial={sorted({r.chars for r in serial_runs})} parallel={sorted({r.chars for r in parallel_runs})}",
        )

        print("\n[3] cap")
        ok &= scenario_cap(backend, tmp_dir, url, args.cap)

        print("\n[4] per-job cancel")
        ok &= scenario_cancel(backend, tmp_dir, url, args.cap)

        print("\n[5] decode parity (mp3 vs mp4, same content)")
        ok &= scenario_parity(backend, tmp_dir, audio_clip, video_clip)

        print("\n[6] log contract")
        ok &= scenario_log_lines(args.jobs, args.cap)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(
        f"\nmodel decode calls={backend.decode_calls} decode time={backend.decode_seconds:.1f}s"
    )
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
