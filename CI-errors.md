# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**2 failing/errored tests** across 2 matrix legs.

### 1. `tests.test_retry_regressions.TestPreRollFiltered.test_preroll_chunks_passed_through_audio_processor`

- Legs: ubuntu-22.04-3.12
- Location: `tests/test_retry_regressions.py:319`

```
+      where <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x7f63d5cae390> = <voice_typer.server.recording.recorder.Recorder object at 0x7f63d5bae2a0>._audio_pipeline

AssertionError: pre-roll chunks must be prepended to the buffer, expected >= 5, got 4
assert 4 >= 5
 +  where 4 = len(<voice_typer.server.recording.recording_buffer.GrowableRecordingBuffer object at 0x7f63c8e26cc0>)
 +    where <voice_typer.server.recording.recording_buffer.GrowableRecordingBuffer object at 0x7f63c8e26cc0> = <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x7f63d5cae390>._buffer
 +      where <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x7f63d5cae390> = <voice_typer.server.recording.recorder.Recorder object at 0x7f63d5bae2a0>._audio_pipeline
tests/test_retry_regressions.py:319: in test_preroll_chunks_passed_through_audio_processor
    assert len(r._audio_pipeline._buffer) >= n_preroll_chunks, (
E   AssertionError: pre-roll chunks must be prepended to the buffer, expected >= 5, got 4
E   assert 4 >= 5
E    +  where 4 = len(<voice_typer.server.recording.recording_buffer.GrowableRecordingBuffer object at 0x7f63c8e26cc0>)
E    +    where <voice_typer.server.recording.recording_buffer.GrowableRecordingBuffer object at 0x7f63c8e26cc0> = <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x7f63d5cae390>._buffer
E    +      where <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x7f63d5cae390> = <voice_typer.server.recording.recorder.Recorder object at 0x7f63d5bae2a0>._audio_pipeline
```

### 2. `tests.test_capture_worker_lifecycle.TestStopEventWorkerBody.test_drain_true_drains_remaining_events_before_exit`

- Legs: windows-2022-3.13
- Location: `tests/test_capture_worker_lifecycle.py:430`

```
+      where <queue.Queue object at 0x0000021A2C1174A0> = <tests.test_capture_worker_lifecycle._FakeRecorder object at 0x0000021A0E0BAFD0>._event_queue

assert 1 == 0
 +  where 1 = qsize()
 +    where qsize = <queue.Queue object at 0x0000021A2C1174A0>.qsize
 +      where <queue.Queue object at 0x0000021A2C1174A0> = <tests.test_capture_worker_lifecycle._FakeRecorder object at 0x0000021A0E0BAFD0>._event_queue
tests\test_capture_worker_lifecycle.py:430: in test_drain_true_drains_remaining_events_before_exit
    assert fake._event_queue.qsize() == 0
E   assert 1 == 0
E    +  where 1 = qsize()
E    +    where qsize = <queue.Queue object at 0x0000021A2C1174A0>.qsize
E    +      where <queue.Queue object at 0x0000021A2C1174A0> = <tests.test_capture_worker_lifecycle._FakeRecorder object at 0x0000021A0E0BAFD0>._event_queue
```
