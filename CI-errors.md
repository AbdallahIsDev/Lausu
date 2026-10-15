# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**8 failing/errored tests** across 5 matrix legs.

### 1. `tests.test_branding_scan_coverage.test_real_project_branding_scan_passes`

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_branding_scan_coverage.py:126`

```
+  where 1 = CompletedProcess(args=['/Library/Frameworks/Python.framework/Versions/3.12/bin/python', '/Users/runner/work/Lausu/Lausu/scripts/check_branding.py'], returncode=1, stdout='ERROR: Found 10 hardcoded references to \'Lausu\' that should use the branding constant.\n\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:9:  Some("Lausu"),\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:11:  "Lausu",\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:21:  "Lausu",\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:29:  Some("Lausu"),\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:31:  "Lausu",\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:41:  "Lausu",\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:45:  Some("Lausu"),\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:47:  "Lausu",\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:53:  "Lausu",\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:63:  "Lausu",\n\nFix: Replace the hardcoded string with the APP_NAME constant from:\n  - Python: from voice_typer.server.branding import APP_NAME\n  - TypeScript (main): import { APP_NAME } from \'./branding\'  (src/main/branding.ts)\n  - TypeScript (renderer): import { APP_NAME } from \'../branding\'  (src/renderer/src/branding.ts)\n  - Rust: use crate::branding::APP_NAME;  (src-tauri/src/branding.rs)\n', stderr='').returncode

AssertionError: real-project branding scan should exit 0; got rc=1.
  stdout:
  ERROR: Found 10 hardcoded references to 'Lausu' that should use the branding constant.
  
    /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:9:  Some("Lausu"),
    /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:11:  "Lausu",
    /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:21:  "Lausu",
    /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:29:  Some("Lausu"),
    /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:31:  "Lausu",
    /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:41:  "Lausu",
    /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:45:  Some("Lausu"),
    /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:47:  "Lausu",
    /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:53:  "Lausu",
    /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:63:  "Lausu",
  
  Fix: Replace the hardcoded string with the APP_NAME constant from:
    - Python: from voice_typer.server.branding import APP_NAME
    - TypeScript (main): import { APP_NAME } from './branding'  (src/main/branding.ts)
    - TypeScript (renderer): import { APP_NAME } from '../branding'  (src/renderer/src/branding.ts)
    - Rust: use crate::branding::APP_NAME;  (src-tauri/src/branding.rs)
  
  stderr:
  
assert 1 == 0
 +  where 1 = CompletedProcess(args=['/Library/Frameworks/Python.framework/Versions/3.12/bin/python', '/Users/runner/work/Lausu/Lausu/scripts/check_branding.py'], returncode=1, stdout='ERROR: Found 10 hardcoded references to \'Lausu\' that should use the branding constant.\n\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:9:  Some("Lausu"),\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:11:  "Lausu",\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:21:  "Lausu",\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:29:  Some("Lausu"),\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:31:  "Lausu",\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:41:  "Lausu",\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:45:  Some("Lausu"),\n  /Users/runner/work/Lausu/Lausu/src-tauri/src/notify_aumid_tests.rs:47:  "Lausu",\n  /Users/runner/work/L
… (truncated)
```

### 2. `tests.test_handlers_log_single_source.test_no_inline_get_logger[screenshot_handlers.py]`

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
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

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
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

- Legs: macos-14-3.12
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

- Legs: macos-14-3.12
- Location: `tests/test_recording_lifecycle_threaded.py:425`

```
AttributeError: 'NoneType' object has no attribute 'args'

AttributeError: 'NoneType' object has no attribute 'args'
tests/test_recording_lifecycle_threaded.py:425: in test_permission_denied_surfaces_reason
    notify_msg = str(notify_mock.call_args.args[1])
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: 'NoneType' object has no attribute 'args'
```

### 6. `tests.test_startup_log_quality.TestCudaDllLine.test_line_names_process_purpose_and_duration`

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
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

### 7. `tests.recording.test_recorder_split_pipelines.TestStopRecordingPrepareAudioPipelining.test_stats_overlap_with_prepare_audio`

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

### 8. `tests.test_crash_recovery_deque.TestEntriesIsBoundedDeque.test_entries_maxlen_matches_constant`

- Legs: ubuntu-22.04-3.10
- Location: `tests/test_crash_recovery_deque.py:14`

```
KeyError: 140469344709504

failed on setup with "KeyError: 140469344709504"
tests/test_crash_recovery_deque.py:14: in _mock_recovery_owner_acl
    monkeypatch.setattr(
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/site-packages/_pytest/monkeypatch.py:70: in resolve
    found: object = importlib.import_module(used)
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
<frozen importlib._bootstrap>:1050: in _gcd_import
    ???
<frozen importlib._bootstrap>:1024: in _find_and_load
    ???
<frozen importlib._bootstrap>:171: in __enter__
    ???
<frozen importlib._bootstrap>:123: in acquire
    ???
E   KeyError: 140469344709504
```
