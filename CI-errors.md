# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**3 failing/errored tests** across 3 matrix legs.

### 1. `tests.test_retry_regressions.TestPreRollFiltered.test_preroll_chunks_passed_through_audio_processor`

- Legs: ubuntu-22.04-3.11
- Location: `tests/test_retry_regressions.py:297`

```
+      where <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x7f935e99a0d0> = <voice_typer.server.recording.recorder.Recorder object at 0x7f935f0fb190>._audio_pipeline

AssertionError: pre-roll chunks not captured, preroll_buffer has 0, buffer has 5
assert (0 >= 5 or 4 >= 5)
 +  where 0 = len(deque([]))
 +    where deque([]) = <voice_typer.server.recording.recorder.Recorder object at 0x7f935f0fb190>._preroll_buffer
 +  and   4 = len(<voice_typer.server.recording.recording_buffer.GrowableRecordingBuffer object at 0x7f935ce10440>)
 +    where <voice_typer.server.recording.recording_buffer.GrowableRecordingBuffer object at 0x7f935ce10440> = <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x7f935e99a0d0>._buffer
 +      where <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x7f935e99a0d0> = <voice_typer.server.recording.recorder.Recorder object at 0x7f935f0fb190>._audio_pipeline
tests/test_retry_regressions.py:297: in test_preroll_chunks_passed_through_audio_processor
    assert len(r._preroll_buffer) >= n_preroll_chunks or len(r._audio_pipeline._buffer) >= n_preroll_chunks, (
E   AssertionError: pre-roll chunks not captured, preroll_buffer has 0, buffer has 5
E   assert (0 >= 5 or 4 >= 5)
E    +  where 0 = len(deque([]))
E    +    where deque([]) = <voice_typer.server.recording.recorder.Recorder object at 0x7f935f0fb190>._preroll_buffer
E    +  and   4 = len(<voice_typer.server.recording.recording_buffer.GrowableRecordingBuffer object at 0x7f935ce10440>)
E    +    where <voice_typer.server.recording.recording_buffer.GrowableRecordingBuffer object at 0x7f935ce10440> = <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x7f935e99a0d0>._buffer
E    +      where <voice_typer.server.recording.audio_pipeline.AudioPipeline object at 0x7f935e99a0d0> = <voice_typer.server.recording.recorder.Recorder object at 0x7f935f0fb190>._audio_pipeline
```

### 2. `tests.test_dictation_pipeline_stage_timer.TestTimedStageContextManager.test_records_positive_duration_in_dict`

- Legs: windows-2022-3.10
- Location: `tests/test_dictation_pipeline_stage_timer.py:24`

```
assert 1.0 < 0.13920000014877587

assert 1.0 < 0.13920000014877587
tests\test_dictation_pipeline_stage_timer.py:24: in test_records_positive_duration_in_dict
    assert 1.0 < timings["transcribe"] < 1000.0
E   assert 1.0 < 0.13920000014877587
```

### 3. `tests.hotkeys.test_polling_strategy.TestPressHoldReleaseNoRepeat.test_two_press_cycles_fire_exactly_twice`

- Legs: windows-2022-3.12
- Location: `tests/hotkeys/test_polling_strategy.py:249`

```
AssertionError: Callback did not fire on press (cycle 1) (waited 2.0s)

AssertionError: Callback did not fire on press (cycle 1) (waited 2.0s)
tests\hotkeys\test_polling_strategy.py:249: in test_two_press_cycles_fire_exactly_twice
    _wait_until(
tests\hotkeys\test_polling_strategy.py:89: in _wait_until
    raise AssertionError(f"{msg} (waited {timeout}s)")
E   AssertionError: Callback did not fire on press (cycle 1) (waited 2.0s)
```
