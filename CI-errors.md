# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**5 failing/errored tests** across 6 matrix legs.

### 1. `tests.recording.test_recorder_split_pipelines.TestStopRecordingPrepareAudioPipelining.test_stats_overlap_with_prepare_audio`

- Legs: macos-14-3.10, ubuntu-22.04-3.10
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

### 2. `tests.test_handlers_log_single_source.test_no_inline_get_logger[screenshot_handlers.py]`

- Legs: macos-14-3.10, macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_handlers_log_single_source.py:49`

```
assert not ['logging.getLogger(']

AssertionError: screenshot_handlers.py must import `log` from `voice_typer.server.handlers._log` instead of calling `logging.getLogger(...)` inline. Found 1 inline calls.
assert not ['logging.getLogger(']
tests/test_handlers_log_single_source.py:49: in test_no_inline_get_logger
    assert not matches, (
E   AssertionError: screenshot_handlers.py must import `log` from `voice_typer.server.handlers._log` instead of calling `logging.getLogger(...)` inline. Found 1 inline calls.
E   assert not ['logging.getLogger(']
```

### 3. `tests.test_handlers_log_single_source.test_no_handler_module_uses_import_logging_only_for_logger`

- Legs: macos-14-3.10, macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_handlers_log_single_source.py:66`

```
assert []

AssertionError: screenshot_handlers.py imports `logging` but does not use it for anything other than getLogger (which is banned). Remove the unused import.
assert []
tests/test_handlers_log_single_source.py:66: in test_no_handler_module_uses_import_logging_only_for_logger
    assert non_getlogger_usages, (
E   AssertionError: screenshot_handlers.py imports `logging` but does not use it for anything other than getLogger (which is banned). Remove the unused import.
E   assert []
```

### 4. `tests.test_hotkeys_win32.TestModifierOnlyHotkeys.test_alt_only_hotkey_starts_without_error`

- Legs: macos-14-3.10, macos-14-3.12, ubuntu-22.04-3.11, ubuntu-22.04-3.13
- Location: `tests/test_hotkeys_win32.py:285`

```
AssertionError: LL hook handle never installed for modifier-only spec (waited 15.0s)

AssertionError: LL hook handle never installed for modifier-only spec (waited 15.0s)
tests/test_hotkeys_win32.py:285: in test_alt_only_hotkey_starts_without_error
    _wait_until(
tests/test_hotkeys_win32.py:28: in _wait_until
    raise AssertionError(f"{msg} (waited {timeout}s)")
E   AssertionError: LL hook handle never installed for modifier-only spec (waited 15.0s)
```

### 5. `tests.test_recording_lifecycle_threaded.TestRecordingStartFailureReason.test_permission_denied_surfaces_reason`

- Legs: macos-14-3.10, ubuntu-22.04-3.11
- Location: `tests/test_recording_lifecycle_threaded.py:425`

```
AttributeError: 'NoneType' object has no attribute 'args'

AttributeError: 'NoneType' object has no attribute 'args'
tests/test_recording_lifecycle_threaded.py:425: in test_permission_denied_surfaces_reason
    notify_msg = str(notify_mock.call_args.args[1])
E   AttributeError: 'NoneType' object has no attribute 'args'
```
