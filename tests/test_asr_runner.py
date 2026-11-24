"""Contract tests for the ctypes wrapper (fake shared-library layer, no DLL)."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from voice_typer.server.media_ingest import ffmpeg_binaries
from voice_typer.worker.asr_runner import GgufRunner, RunnerError
from voice_typer.worker.asr_runner.contract import check_contract
from voice_typer.worker.asr_runner.runner import library_dir

FIXED_TEXT = "hello from the fake library"
FIXED_SEGMENTS = [(0, 640, "hello from"), (640, 1210, "the fake library")]


class _FakeLibrary:
    def __init__(self, *, status: int = 0, fail_open: bool = False, crash: bool = False) -> None:
        self.status = status
        self.fail_open = fail_open
        self.crash = crash
        self.freed = False

    def transcribe_open(self, _path, _load, _session, out):
        if self.fail_open:
            return 4
        out._obj.value = 1
        return 0

    def transcribe_set_abort_callback(self, *_args):
        return None

    def transcribe_run(self, *_args):
        if self.crash:
            raise OSError("simulated native crash")
        return self.status

    def transcribe_full_text(self, _session):
        return FIXED_TEXT.encode("utf-8")

    def transcribe_n_segments(self, _session):
        return len(FIXED_SEGMENTS)

    def transcribe_get_segment(self, _session, index, out):
        t0, t1, text = FIXED_SEGMENTS[index]
        seg = out._obj
        seg.t0_ms = t0
        seg.t1_ms = t1
        seg.text = text.encode("utf-8")
        seg.speaker_id = 0
        return 0

    def transcribe_segment_init(self, *_args):
        return None

    def transcribe_detected_language(self, _session):
        return b"en"

    def transcribe_status_string(self, status):
        return f"status-{status}".encode()

    def transcribe_session_free(self, _session):
        self.freed = True


def _loader_for(fake: _FakeLibrary):
    return lambda: (fake, Path("."))


@pytest.fixture(autouse=True)
def _contract_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "contract.json").write_text('{"version":"0.4.2","backends":["cpu","vulkan"]}')
    monkeypatch.setattr("voice_typer.worker.asr_runner.runner.check_contract", lambda *_a, **_k: None)


def test_real_c_api_shape_is_mapped() -> None:
    """t0_ms/t1_ms/text come from upstream include/transcribe.h."""
    fake = _FakeLibrary()
    result = GgufRunner("model.gguf", loader=_loader_for(fake)).transcribe(np.zeros(1600, dtype=np.float32))
    assert result.text == FIXED_TEXT
    assert [s.start for s in result.segments] == [0.0, 0.64]
    assert [s.end for s in result.segments] == [0.64, 1.21]
    assert result.language == "en"
    assert fake.freed


def test_confidence_fields_are_not_fabricated() -> None:
    from voice_typer.worker.asr_runner.engine import _DecodedSegment

    seg = _DecodedSegment(0.0, 1.0, "text")
    assert seg.avg_logprob is None
    assert seg.no_speech_prob is None


def test_abort_and_load_failures_map_to_clear_errors() -> None:
    fake = _FakeLibrary(fail_open=True)
    with pytest.raises(RunnerError, match="could not be loaded"):
        GgufRunner("model.gguf", loader=_loader_for(fake)).transcribe(np.zeros(100, dtype=np.float32))
    abort = threading.Event()
    abort.set()
    fake = _FakeLibrary()
    with pytest.raises(RunnerError):
        GgufRunner("model.gguf", loader=_loader_for(fake)).transcribe(
            np.zeros(100, dtype=np.float32), abort_event=abort
        )


def test_native_crash_does_not_hang_or_silently_pass() -> None:
    fake = _FakeLibrary(crash=True)
    with pytest.raises(RunnerError):
        GgufRunner("model.gguf", loader=_loader_for(fake)).transcribe(np.zeros(100, dtype=np.float32))


def test_contract_version_is_checked(tmp_path: Path) -> None:
    (tmp_path / "contract.json").write_text('{"version":"0.0.1"}')
    with pytest.raises(RuntimeError, match="wrong version"):
        check_contract(tmp_path)


def test_frozen_library_resolution_ignores_path_and_sys_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = tmp_path / "install"
    extraction = tmp_path / "onefile-tmp"
    on_path = tmp_path / "path"
    original.mkdir()
    extraction.mkdir()
    on_path.mkdir()
    name = "transcribe.dll" if (__import__("os").name == "nt") else "libtranscribe.so"
    shipped = original / name
    shipped.write_bytes(b"real")
    decoy = on_path / name
    decoy.write_bytes(b"decoy")
    monkeypatch.setattr(
        ffmpeg_binaries,
        "__compiled__",
        SimpleNamespace(containing_dir=str(original)),
        raising=False,
    )
    monkeypatch.setattr(__import__("sys"), "executable", str(extraction / "python-sidecar.exe"))
    monkeypatch.setenv("PATH", str(on_path))
    monkeypatch.delenv("TRANSCRIBE_LIBRARY", raising=False)
    assert library_dir() == original


def test_dev_override_is_honoured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lib = tmp_path / "custom.dll"
    lib.write_bytes(b"")
    monkeypatch.setenv("TRANSCRIBE_LIBRARY", str(lib))
    assert library_dir() == tmp_path
