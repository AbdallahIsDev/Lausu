# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**3 failing/errored tests** across 4 matrix legs.

### 1. `tests.recording.test_recorder_split_pipelines.TestStopRecordingPrepareAudioPipelining.test_stats_overlap_with_prepare_audio`

- Legs: ubuntu-22.04-3.10
- Location: `tests/recording/test_recorder_split_pipelines.py:412`

```
voice_typer.server.recording.exceptions.ResampleError: resample timed out after 2.0s

voice_typer.server.recording.exceptions.ResampleError: resample timed out after 2.0s
tests/recording/test_recorder_split_pipelines.py:412: in test_stats_overlap_with_prepare_audio
    stop_recording(rec)
voice_typer/server/recording/recording_lifecycle.py:335: in stop_recording
    raise ResampleError(
E   voice_typer.server.recording.exceptions.ResampleError: resample timed out after 2.0s
```

### 2. `tests.test_recording_lifecycle_threaded.TestRecordingStartFailureReason.test_permission_denied_surfaces_reason`

- Legs: ubuntu-22.04-3.10, windows-2022-3.10, windows-2022-3.12
- Location: `tests/test_recording_lifecycle_threaded.py:425`

```
AttributeError: 'NoneType' object has no attribute 'args'

AttributeError: 'NoneType' object has no attribute 'args'
tests/test_recording_lifecycle_threaded.py:425: in test_permission_denied_surfaces_reason
    notify_msg = str(notify_mock.call_args.args[1])
E   AttributeError: 'NoneType' object has no attribute 'args'
```

### 3. `tests.test_recording_lifecycle_threaded.TestDispatchThreadReturnsDuringModelReload.test_f2_returns_before_load_completes_when_model_reload_in_flight`

- Legs: windows-2022-3.11
- Location: `tests/test_recording_lifecycle_threaded.py:115`

```
+    where is_set = <threading.Event at 0x1cb84bb5890: unset>.is_set

AssertionError: ensure_active_engine_loaded() must have been called by the worker
assert False
 +  where False = is_set()
 +    where is_set = <threading.Event at 0x1cb84bb5890: unset>.is_set
tests\test_recording_lifecycle_threaded.py:115: in test_f2_returns_before_load_completes_when_model_reload_in_flight
    assert load_started.is_set(), "ensure_active_engine_loaded() must have been called by the worker"
E   AssertionError: ensure_active_engine_loaded() must have been called by the worker
E   assert False
E    +  where False = is_set()
E    +    where is_set = <threading.Event at 0x1cb84bb5890: unset>.is_set
```
