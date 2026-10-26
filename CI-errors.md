# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**4 failing/errored tests** across 3 matrix legs.

### 1. `tests.test_level_monitor_disconnect.TestDeviceLostEventEmitted.test_zero_chunk_detector_emits_device_lost_when_reopen_fails`

- Legs: macos-14-3.11
- Location: `tests/test_level_monitor_disconnect.py:300`

```
+  where 0 = len([])

AssertionError: starved stream with failing reopen must publish exactly one device_lost event; got [{'type': 'mic_level', 'data': {'level': 1.618566614070005e-09, 'peak': 1.334593879853685e-09, 'active': True}}]
assert 0 == 1
 +  where 0 = len([])
tests/test_level_monitor_disconnect.py:300: in test_zero_chunk_detector_emits_device_lost_when_reopen_fails
    assert len(device_lost_events) == 1, (
E   AssertionError: starved stream with failing reopen must publish exactly one device_lost event; got [{'type': 'mic_level', 'data': {'level': 1.618566614070005e-09, 'peak': 1.334593879853685e-09, 'active': True}}]
E   assert 0 == 1
E    +  where 0 = len([])
```

### 2. `tests.test_paste_cycle_zombie_guard.TestLiveCycleStillPastes.test_live_cycle_copies_and_dispatches`

- Legs: macos-14-3.11
- Location: `tests/test_paste_cycle_zombie_guard.py:191`

```
AssertionError: Expected '_dispatch_keystroke' to have been called once. Called 0 times.

AssertionError: Expected '_dispatch_keystroke' to have been called once. Called 0 times.
tests/test_paste_cycle_zombie_guard.py:191: in test_live_cycle_copies_and_dispatches
    dispatch.assert_called_once()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected '_dispatch_keystroke' to have been called once. Called 0 times.
```

### 3. `tests.test_level_monitor_rms_optimization.TestProcessLevelChunkEndToEnd.test_process_chunk_uses_optimized_path`

- Legs: ubuntu-22.04-3.11
- Location: `tests/test_level_monitor_rms_optimization.py:301`

```
+    where 3.662365779746324e-05 = <module 'voice_typer.server.level_monitor' from '/home/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'>._monitor_level

AssertionError: _monitor_level=3.662365779746324e-05 != expected 0.1 (NEW RMS path; chunk RMS=0.25)
assert 0.09996337634220254 < 1e-06
 +  where 0.09996337634220254 = abs((3.662365779746324e-05 - 0.1))
 +    where 3.662365779746324e-05 = <module 'voice_typer.server.level_monitor' from '/home/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'>._monitor_level
tests/test_level_monitor_rms_optimization.py:301: in test_process_chunk_uses_optimized_path
    assert abs(lm._monitor_level - expected_level) < 1e-6, (
E   AssertionError: _monitor_level=3.662365779746324e-05 != expected 0.1 (NEW RMS path; chunk RMS=0.25)
E   assert 0.09996337634220254 < 1e-06
E    +  where 0.09996337634220254 = abs((3.662365779746324e-05 - 0.1))
E    +    where 3.662365779746324e-05 = <module 'voice_typer.server.level_monitor' from '/home/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'>._monitor_level
```

### 4. `tests.recording.test_recorder_split_pipelines.TestStopRecordingPrepareAudioPipelining.test_stats_overlap_with_prepare_audio`

- Legs: windows-2022-3.13
- Location: `tests/recording/test_recorder_split_pipelines.py:426`

```
assert 1239.2766494 <= 1239.2765327

AssertionError:  regression: the stats computation started BEFORE the resample thread, _prepare_audio is NOT pipelined. The resample thread must be started BEFORE the stats computation.
assert 1239.2766494 <= 1239.2765327
tests\recording\test_recorder_split_pipelines.py:426: in test_stats_overlap_with_prepare_audio
    assert times["prepare_started"] <= times["stats_started"], (
E   AssertionError:  regression: the stats computation started BEFORE the resample thread, _prepare_audio is NOT pipelined. The resample thread must be started BEFORE the stats computation.
E   assert 1239.2766494 <= 1239.2765327
```
