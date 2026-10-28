# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**2 failing/errored tests** across 2 matrix legs.

### 1. `tests.test_hotkey_watchdog.TestPynputWatchdog.test_watchdog_resets_failure_count_on_recovery`

- Legs: macos-14-3.11
- Location: `tests/test_hotkey_watchdog.py:154`

```
+  where 3 = <voice_typer.server.hotkeys.pynput_backend.PynputHotkey object at 0x167a73210>._watchdog_failure_count

AssertionError: Watchdog should reset failure count to 0 when listener is healthy
assert 3 == 0
 +  where 3 = <voice_typer.server.hotkeys.pynput_backend.PynputHotkey object at 0x167a73210>._watchdog_failure_count
tests/test_hotkey_watchdog.py:154: in test_watchdog_resets_failure_count_on_recovery
    assert backend._watchdog_failure_count == 0, (
E   AssertionError: Watchdog should reset failure count to 0 when listener is healthy
E   assert 3 == 0
E    +  where 3 = <voice_typer.server.hotkeys.pynput_backend.PynputHotkey object at 0x167a73210>._watchdog_failure_count
```

### 2. `tests.test_retry_regressions.TestPreRollFiltered.test_preroll_chunks_passed_through_audio_processor`

- Legs: windows-2022-3.13
- Location: `tests/test_retry_regressions.py:297`

```
+      where <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x00000271BB6D1DE0> = <voice_typer.server.recording.recorder.Recorder object at 0x00000271BB6E8410>._audio_pipeline

AssertionError: pre-roll chunks not captured, preroll_buffer has 0, buffer has 5
assert (0 >= 5 or 3 >= 5)
 +  where 0 = len(deque([]))
 +    where deque([]) = <voice_typer.server.recording.recorder.Recorder object at 0x00000271BB6E8410>._preroll_buffer
 +  and   3 = len(<voice_typer.server.recording.recording_buffer.GrowableRecordingBuffer object at 0x00000271BB6762C0>)
[+2 more lines; full report in element text]
tests\test_retry_regressions.py:297: in test_preroll_chunks_passed_through_audio_processor
    assert len(r._preroll_buffer) >= n_preroll_chunks or len(r._audio_pipeline._buffer) >= n_preroll_chunks, (
E   AssertionError: pre-roll chunks not captured, preroll_buffer has 0, buffer has 5
E   assert (0 >= 5 or 3 >= 5)
E    +  where 0 = len(deque([]))
E    +    where deque([]) = <voice_typer.server.recording.recorder.Recorder object at 0x00000271BB6E8410>._preroll_buffer
E    +  and   3 = len(<voice_typer.server.recording.recording_buffer.GrowableRecordingBuffer object at 0x00000271BB6762C0>)
E    +    where <voice_typer.server.recording.recording_buffer.GrowableRecordingBuffer object at 0x00000271BB6762C0> = <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x00000271BB6D1DE0>._buffer
E    +      where <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x00000271BB6D1DE0> = <voice_typer.server.recording.recorder.Recorder object at 0x00000271BB6E8410>._audio_pipeline
```
