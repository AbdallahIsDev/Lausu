# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**13 failing/errored tests** across 8 matrix legs.

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

### 2. `tests.test_audio_filter_reset_zero_buffers.test_streaming_resampler_chunk_cost_within_budget`

- Legs: ubuntu-22.04-3.10
- Location: `tests/test_audio_filter_reset_zero_buffers.py:147`

```
assert 17.858444199998758 < 10.0

AssertionError: resampler too slow: 17.9 ms/chunk
assert 17.858444199998758 < 10.0
tests/test_audio_filter_reset_zero_buffers.py:147: in test_streaming_resampler_chunk_cost_within_budget
    assert mean_ms < 10.0, f"resampler too slow: {mean_ms:.1f} ms/chunk"
E   AssertionError: resampler too slow: 17.9 ms/chunk
E   assert 17.858444199998758 < 10.0
```

### 3. `tests.test_level_monitor_rms_optimization.TestProcessLevelChunkEndToEnd.test_process_chunk_with_processor_uses_optimized_path`

- Legs: ubuntu-22.04-3.10
- Location: `tests/test_level_monitor_rms_optimization.py:297`

```
TypeError: 'NoneType' object is not callable

TypeError: 'NoneType' object is not callable
tests/test_level_monitor_rms_optimization.py:297: in test_process_chunk_with_processor_uses_optimized_path
    holder["callback"](chunk, 512, None, None)
E   TypeError: 'NoneType' object is not callable
```

### 4. `tests.test_noise_suppressor_gtcrn.TestGtcrnSharedSession.test_preload_second_call_noop_log`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.12
- Location: `tests/test_noise_suppressor_gtcrn.py:672`

```
+ ]

AssertionError: second preload must not re-emit the warmed INFO line
assert [<LogRecord: ... + warmed%s">] == []
  
  Left contains one more item: <LogRecord: voice_typer.server.audio_filters.gtcrn_backend, 20, /home/runner/work/Lausu/Lausu/voice_typer/server/audio_filters/gtcrn_backend.py, 128, "[GTCRN] GTCRN model loaded from bundled ONNX, preloaded + warmed%s">
  
  Full diff:
  - []
  + [
  +     <LogRecord: voice_typer.server.audio_filters.gtcrn_backend, 20, /home/runner/work/Lausu/Lausu/voice_typer/server/audio_filters/gtcrn_backend.py, 128, "[GTCRN] GTCRN model loaded from bundled ONNX, preloaded + warmed%s">,
  + ]
tests/test_noise_suppressor_gtcrn.py:672: in test_preload_second_call_noop_log
    assert warmed == [], "second preload must not re-emit the warmed INFO line"
E   AssertionError: second preload must not re-emit the warmed INFO line
E   assert [<LogRecord: ... + warmed%s">] == []
E     
E     Left contains one more item: <LogRecord: voice_typer.server.audio_filters.gtcrn_backend, 20, /home/runner/work/Lausu/Lausu/voice_typer/server/audio_filters/gtcrn_backend.py, 128, "[GTCRN] GTCRN model loaded from bundled ONNX, preloaded + warmed%s">
E     
E     Full diff:
E     - []
E     + [
E     +     <LogRecord: voice_typer.server.audio_filters.gtcrn_backend, 20, /home/runner/work/Lausu/Lausu/voice_typer/server/audio_filters/gtcrn_backend.py, 128, "[GTCRN] GTCRN model loaded from bundled ONNX, preloaded + warmed%s">,
E     + ]
```

### 5. `tests.test_paste_cycle_zombie_guard.TestFingerprintGate.test_matching_clipboard_dispatches_once`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_paste_cycle_zombie_guard.py:270`

```
assert False is True

assert False is True
tests/test_paste_cycle_zombie_guard.py:270: in test_matching_clipboard_dispatches_once
    assert pasted is True
E   assert False is True
```

### 6. `tests.test_paste_cycle_zombie_guard.TestFingerprintGate.test_unreadable_clipboard_fails_open`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_paste_cycle_zombie_guard.py:291`

```
assert False is True

assert False is True
tests/test_paste_cycle_zombie_guard.py:291: in test_unreadable_clipboard_fails_open
    assert pasted is True
E   assert False is True
```

### 7. `tests.test_startup_log_quality.TestCudaDllLine.test_line_names_process_purpose_and_duration`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_startup_log_quality.py:74`

```
assert []

AssertionError: expected a [CUDA-DLL] INFO line
assert []
tests/test_startup_log_quality.py:74: in test_line_names_process_purpose_and_duration
    assert lines, "expected a [CUDA-DLL] INFO line"
E   AssertionError: expected a [CUDA-DLL] INFO line
E   assert []
```

### 8. `tests.test_level_monitor_rms_optimization.TestProcessLevelChunkEndToEnd.test_process_chunk_uses_optimized_path`

- Legs: ubuntu-22.04-3.12
- Location: `tests/test_level_monitor_rms_optimization.py:247`

```
+    where 0.0001765562454238534 = <module 'voice_typer.server.level_monitor' from '/home/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'>._monitor_level

AssertionError: _monitor_level=0.0001765562454238534 != expected 0.1 (NEW RMS path; chunk RMS=0.25)
assert 0.09982344375457615 < 1e-06
 +  where 0.09982344375457615 = abs((0.0001765562454238534 - 0.1))
 +    where 0.0001765562454238534 = <module 'voice_typer.server.level_monitor' from '/home/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'>._monitor_level
tests/test_level_monitor_rms_optimization.py:247: in test_process_chunk_uses_optimized_path
    assert abs(lm._monitor_level - expected_level) < 1e-6, (
E   AssertionError: _monitor_level=0.0001765562454238534 != expected 0.1 (NEW RMS path; chunk RMS=0.25)
E   assert 0.09982344375457615 < 1e-06
E    +  where 0.09982344375457615 = abs((0.0001765562454238534 - 0.1))
E    +    where 0.0001765562454238534 = <module 'voice_typer.server.level_monitor' from '/home/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'>._monitor_level
```

### 9. `tests.app.test_config_wiring.TestTextCleanupConfig.test_cleanup_skipped_when_disabled`

- Legs: windows-2022-3.10, windows-2022-3.11
- Location: `(unknown location)`

```
(no error line)

failed on setup with "worker 'gw0' crashed while running 'tests/app/test_config_wiring.py::TestTextCleanupConfig::test_cleanup_skipped_when_disabled'"
worker 'gw0' crashed while running 'tests/app/test_config_wiring.py::TestTextCleanupConfig::test_cleanup_skipped_when_disabled'
```

### 10. `tests.app.test_lifecycle.TestAppStartupIntegration.test_tray_icon_created_on_start`

- Legs: windows-2022-3.10
- Location: `(unknown location)`

```
(no error line)

failed on setup with "worker 'gw1' crashed while running 'tests/app/test_lifecycle.py::TestAppStartupIntegration::test_tray_icon_created_on_start'"
worker 'gw1' crashed while running 'tests/app/test_lifecycle.py::TestAppStartupIntegration::test_tray_icon_created_on_start'
```

### 11. `pytest.internal`

- Legs: windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `(pytest internal error, no test location)`

```
internal error

internal error
Traceback (most recent call last):
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\_pytest\main.py", line 330, in wrap_session
    session.exitstatus = doit(config, session) or 0
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\_pytest\main.py", line 384, in _main
    config.hook.pytest_runtestloop(session=session)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_caller.py", line 197, in __call__
    return self._hookexec(
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_manager.py", line 183, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_execution.py", line 195, in _multicall
    raise exception
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_execution.py", line 167, in _multicall
    teardown.throw(exception)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\_pytest\logging.py", line 816, in pytest_runtestloop
    return (yield)  # Run all the tests.
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_execution.py", line 167, in _multicall
    teardown.throw(exception)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\_pytest\terminal.py", line 708, in pytest_runtestloop
    result = yield
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_execution.py", line 167, in _multicall
    teardown.throw(exception)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pytest_cov\plugin.py", line 348, in pytest_runtestloop
    result = yield
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_execution.py", line 147, in _multicall
    res = hook_impl.function(*args)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\dsession.py", line 138, in pytest_runtestloop
    self.loop_once()
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\dsession.py", line 163, in loop_once
    call(**kwargs)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\dsession.py", line 306, in worker_collectionfinish
    self.sched.schedule()
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\scheduler\loadscope.py", line 354, in schedule
    self._reschedule(node)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\scheduler\loadscope.py", line 336, in _reschedule
    self._assign_work_unit(node)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\scheduler\loadscope.py", line 275, in _assign_work_unit
    worker_collection = self.registered_collections[node]
```

### 12. `tests.app.test_config_wiring.TestSettingsWindowIntegration.test_model_change_uses_config_device`

- Legs: windows-2022-3.11, windows-2022-3.12
- Location: `(unknown location)`

```
(no error line)

failed on setup with "worker 'gw2' crashed while running 'tests/app/test_config_wiring.py::TestSettingsWindowIntegration::test_model_change_uses_config_device'"
worker 'gw2' crashed while running 'tests/app/test_config_wiring.py::TestSettingsWindowIntegration::test_model_change_uses_config_device'
```

### 13. `tests.app.test_config_wiring.TestConfigWiring.test_autostart_disabled_when_config_false`

- Legs: windows-2022-3.12, windows-2022-3.13
- Location: `(unknown location)`

```
(no error line)

failed on setup with "worker 'gw0' crashed while running 'tests/app/test_config_wiring.py::TestConfigWiring::test_autostart_disabled_when_config_false'"
worker 'gw0' crashed while running 'tests/app/test_config_wiring.py::TestConfigWiring::test_autostart_disabled_when_config_false'
```
