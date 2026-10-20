# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**2 failing/errored tests** across 2 matrix legs.

### 1. `tests.test_logging_setup.TestStartupBanner.test_banner_includes_session_id_once`

- Legs: windows-2022-3.11
- Location: `tests/test_logging_setup.py:431`

```
assert 'session=f9fc54c1' in '2026-10-19  21:40:40  INFO  [MIC-WATCHER] Stopped device-change watcher'

AssertionError: GT-B1-15: first log line must carry session=<id>; got: '2026-10-19  21:40:40  INFO  [MIC-WATCHER] Stopped device-change watcher'
assert 'session=f9fc54c1' in '2026-10-19  21:40:40  INFO  [MIC-WATCHER] Stopped device-change watcher'
tests\test_logging_setup.py:431: in test_banner_includes_session_id_once
    assert f"session={session_id}" in lines[0], (
E   AssertionError: GT-B1-15: first log line must carry session=<id>; got: '2026-10-19  21:40:40  INFO  [MIC-WATCHER] Stopped device-change watcher'
E   assert 'session=f9fc54c1' in '2026-10-19  21:40:40  INFO  [MIC-WATCHER] Stopped device-change watcher'
```

### 2. `tests.test_shutdown_deadline.TestOverallDeadline.test_deadline_skips_non_critical_parallel_teardowns`

- Legs: windows-2022-3.13
- Location: `tests/test_shutdown_deadline.py:159`

```
assert 'teardown_asr_models' not in ['teardown_timers_and_recording', 'teardown_recorder', 'teardown_history_db', 'teardown_crash_recovery', 'teardown_asr_models', 'teardown_restore_volume', ...]

AssertionError: non-critical teardown 'teardown_asr_models' MUST be skipped when the 20s deadline is near (< 5s remaining). Called: ['teardown_timers_and_recording', 'teardown_recorder', 'teardown_history_db', 'teardown_crash_recovery', 'teardown_asr_models', 'teardown_restore_volume', 'teardown_waveform_wiring', 'teardown_sounddevice', 'teardown_mutex_handle', 'teardown_pid_file', 'teardown_devnull_files', 'teardown_hotkeys', 'teardown_level_monitor', 'teardown_host_child', 'teardown_event_bus']
assert 'teardown_asr_models' not in ['teardown_timers_and_recording', 'teardown_recorder', 'teardown_history_db', 'teardown_crash_recovery', 'teardown_asr_models', 'teardown_restore_volume', ...]
tests\test_shutdown_deadline.py:159: in test_deadline_skips_non_critical_parallel_teardowns
    assert name not in called, (
E   AssertionError: non-critical teardown 'teardown_asr_models' MUST be skipped when the 20s deadline is near (< 5s remaining). Called: ['teardown_timers_and_recording', 'teardown_recorder', 'teardown_history_db', 'teardown_crash_recovery', 'teardown_asr_models', 'teardown_restore_volume', 'teardown_waveform_wiring', 'teardown_sounddevice', 'teardown_mutex_handle', 'teardown_pid_file', 'teardown_devnull_files', 'teardown_hotkeys', 'teardown_level_monitor', 'teardown_host_child', 'teardown_event_bus']
E   assert 'teardown_asr_models' not in ['teardown_timers_and_recording', 'teardown_recorder', 'teardown_history_db', 'teardown_crash_recovery', 'teardown_asr_models', 'teardown_restore_volume', ...]
```
