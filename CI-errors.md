# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**12 failing/errored tests** across 9 matrix legs.

### 1. `tests.hotkeys.test_caps_lock_suppressor.TestSendKeyboardEventHelper.test_input_struct_matches_win32_size`

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/hotkeys/test_caps_lock_suppressor.py:234`

```
+    where <built-in function sizeof> = ctypes.sizeof

assert 56 == 40
 +  where 56 = <built-in function sizeof>(INPUT)
 +    where <built-in function sizeof> = ctypes.sizeof
tests/hotkeys/test_caps_lock_suppressor.py:234: in test_input_struct_matches_win32_size
    assert ctypes.sizeof(INPUT) == expected
E   assert 56 == 40
E    +  where 56 = <built-in function sizeof>(INPUT)
E    +    where <built-in function sizeof> = ctypes.sizeof
```

### 2. `tests.test_architecture_doc_accuracy.test_main_rs_line_count_is_261`

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_architecture_doc_accuracy.py:231`

```
assert 266 == 261

AssertionError: src-tauri/src/main.rs must be 261 lines (actual: 266). Update the doc + this test together.
assert 266 == 261
tests/test_architecture_doc_accuracy.py:231: in test_main_rs_line_count_is_261
    assert actual == 261, (
E   AssertionError: src-tauri/src/main.rs must be 261 lines (actual: 266). Update the doc + this test together.
E   assert 266 == 261
```

### 3. `tests.test_hotkeys_win32.TestModifierOnlyHotkeys.test_alt_only_hotkey_starts_without_error`

- Legs: macos-14-3.12, ubuntu-22.04-3.13
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

### 4. `tests.test_ipc_reference_doc_accuracy.test_ipc_reference_doc_has_row_for_every_push_event_type`

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_ipc_reference_doc_accuracy.py:171`

```
assert not {'offline_pack_outdated'}

AssertionError: push_events.ts declares 1 event types with no row in docs/ipc-reference.md: ['offline_pack_outdated']. Add a row in the '## Push events' table.
assert not {'offline_pack_outdated'}
tests/test_ipc_reference_doc_accuracy.py:171: in test_ipc_reference_doc_has_row_for_every_push_event_type
    assert not missing_from_doc, (
E   AssertionError: push_events.ts declares 1 event types with no row in docs/ipc-reference.md: ['offline_pack_outdated']. Add a row in the '## Push events' table.
E   assert not {'offline_pack_outdated'}
```

### 5. `tests.test_ipc_reference_doc_accuracy.test_ipc_reference_doc_push_events_header_count_matches_source`

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_ipc_reference_doc_accuracy.py:159`

```
assert 62 == 63

AssertionError: docs/ipc-reference.md documents 62 typed push events but the renderer's types/ipc/push_events.ts declares 63 (via `type: "<name>"` literals). Update the header.
assert 62 == 63
tests/test_ipc_reference_doc_accuracy.py:159: in test_ipc_reference_doc_push_events_header_count_matches_source
    assert documented == actual, (
E   AssertionError: docs/ipc-reference.md documents 62 typed push events but the renderer's types/ipc/push_events.ts declares 63 (via `type: "<name>"` literals). Update the header.
E   assert 62 == 63
```

### 6. `tests.test_pii_redaction_blind_spots.TestNoRawTranscriptionInLogs.test_no_raw_transcription_variable_interpolated_in_log_calls`

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_pii_redaction_blind_spots.py:127`

```
assert not ["voice_typer/server/system_whisper.py: log.debug('[MODEL] worker whisper load refused: %r', result), interpolates raw transcription variable"]

AssertionError: XZ-LOG-12 regression: found log calls that interpolate a raw transcription variable directly. The PIIRedactionFilter only catches four structured PII patterns, free-form medical / financial / address / name content would leak into the log file. Either (a) apply ``redact_pii()`` / log a hash before the call, OR (b) add the format string to ``_SAFE_LOG_CALL_SITES`` in this test with a justification comment. Unsafe calls:
    voice_typer/server/system_whisper.py: log.debug('[MODEL] worker whisper load refused: %r', result), interpolates raw transcription variable
assert not ["voice_typer/server/system_whisper.py: log.debug('[MODEL] worker whisper load refused: %r', result), interpolates raw transcription variable"]
tests/test_pii_redaction_blind_spots.py:127: in test_no_raw_transcription_variable_interpolated_in_log_calls
    assert not all_unsafe, (
E   AssertionError: XZ-LOG-12 regression: found log calls that interpolate a raw transcription variable directly. The PIIRedactionFilter only catches four structured PII patterns, free-form medical / financial / address / name content would leak into the log file. Either (a) apply ``redact_pii()`` / log a hash before the call, OR (b) add the format string to ``_SAFE_LOG_CALL_SITES`` in this test with a justification comment. Unsafe calls:
E       voice_typer/server/system_whisper.py: log.debug('[MODEL] worker whisper load refused: %r', result), interpolates raw transcription variable
E   assert not ["voice_typer/server/system_whisper.py: log.debug('[MODEL] worker whisper load refused: %r', result), interpolates raw transcription variable"]
```

### 7. `tests.test_recording_lifecycle_threaded.TestRecordingStartFailureReason.test_permission_denied_surfaces_reason`

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.12
- Location: `tests/test_recording_lifecycle_threaded.py:425`

```
AttributeError: 'NoneType' object has no attribute 'args'

AttributeError: 'NoneType' object has no attribute 'args'
tests/test_recording_lifecycle_threaded.py:425: in test_permission_denied_surfaces_reason
    notify_msg = str(notify_mock.call_args.args[1])
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: 'NoneType' object has no attribute 'args'
```

### 8. `tests.test_requirements_lock_completeness.test_lockfile_pinned_versions_satisfy_pyproject_constraints`

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_requirements_lock_completeness.py:185`

```
assert not ['  cryptography: lockfile pins 50.0.0 but pyproject.toml requires >=48.0.1,<49']

AssertionError: Lockfile drift detected, the lockfile pin violates the version specifier declared in pyproject.toml. CI (which resolves from pyproject.toml) and the documented `pip install --require-hashes -r requirements-lock.txt` path now install DIFFERENT versions. Regenerate the lockfile with:
    uv pip compile --generate-hashes --universal --python-version 3.12 pyproject.toml -o requirements-lock.txt
  
  Violations:
    cryptography: lockfile pins 50.0.0 but pyproject.toml requires >=48.0.1,<49
assert not ['  cryptography: lockfile pins 50.0.0 but pyproject.toml requires >=48.0.1,<49']
tests/test_requirements_lock_completeness.py:185: in test_lockfile_pinned_versions_satisfy_pyproject_constraints
    assert not violations, (
E   AssertionError: Lockfile drift detected, the lockfile pin violates the version specifier declared in pyproject.toml. CI (which resolves from pyproject.toml) and the documented `pip install --require-hashes -r requirements-lock.txt` path now install DIFFERENT versions. Regenerate the lockfile with:
E       uv pip compile --generate-hashes --universal --python-version 3.12 pyproject.toml -o requirements-lock.txt
E     
E     Violations:
E       cryptography: lockfile pins 50.0.0 but pyproject.toml requires >=48.0.1,<49
E   assert not ['  cryptography: lockfile pins 50.0.0 but pyproject.toml requires >=48.0.1,<49']
```

### 9. `tests.test_runtime_pack_publish_workflow.TestActionPinContract.test_actions_match_pin_map`

- Legs: macos-14-3.12, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_runtime_pack_publish_workflow.py:133`

```
assert not ['unpinned/unknown action: dtolnay/rust-toolchain@v1']

AssertionError: C-CI-5 pin violations:
  unpinned/unknown action: dtolnay/rust-toolchain@v1
assert not ['unpinned/unknown action: dtolnay/rust-toolchain@v1']
tests/test_runtime_pack_publish_workflow.py:133: in test_actions_match_pin_map
    assert not violations, "C-CI-5 pin violations:\n" + "\n".join(violations)
E   AssertionError: C-CI-5 pin violations:
E     unpinned/unknown action: dtolnay/rust-toolchain@v1
E   assert not ['unpinned/unknown action: dtolnay/rust-toolchain@v1']
```

### 10. `tests.test_audio_callback.TestSilentInputThreadStorm.test_guard_does_not_suppress_redisconnect_after_restart`

- Legs: ubuntu-22.04-3.10
- Location: `tests/test_audio_callback.py:162`

```
assert 0 == 1

AssertionError: first zero-filled chunk should spawn 1 handler, got 0
assert 0 == 1
tests/test_audio_callback.py:162: in test_guard_does_not_suppress_redisconnect_after_restart
    assert spawn_count["n"] == 1, f"first zero-filled chunk should spawn 1 handler, got {spawn_count['n']}"
E   AssertionError: first zero-filled chunk should spawn 1 handler, got 0
E   assert 0 == 1
```

### 11. `tests.test_worker_relay.test_round_trip_emit_parse_accessor_returns_port`

- Legs: ubuntu-22.04-3.13, windows-2022-3.11
- Location: `tests/test_worker_relay.py:105`

```
]

AssertionError: assert [{'type': 'wo..._pid': 1234}}] == [{'type': 'wo...ort': 54321}}]
  
  Left contains one more item: {'type': 'offline_pack_ready', 'data': {'version': 'v1', 'worker_pid': 1234}}
  
  Full diff:
    [
        {
            'type': 'worker_started',
            'data': {
                'pid': 1234,
                'version': 'v1',
                'port': 54321,
            },
        },
  +     {
  +         'type': 'offline_pack_ready',
  +         'data': {
  +             'version': 'v1',
  +             'worker_pid': 1234,
  +         },
  +     },
    ]
tests/test_worker_relay.py:105: in test_round_trip_emit_parse_accessor_returns_port
    assert received == [
E   AssertionError: assert [{'type': 'wo..._pid': 1234}}] == [{'type': 'wo...ort': 54321}}]
E     
E     Left contains one more item: {'type': 'offline_pack_ready', 'data': {'version': 'v1', 'worker_pid': 1234}}
E     
E     Full diff:
E       [
E           {
E               'type': 'worker_started',
E               'data': {
E                   'pid': 1234,
E                   'version': 'v1',
E                   'port': 54321,
E               },
E           },
```

### 12. `tests.test_crash_recovery_del_extraction.TestCleanupFlushPendingResilience.test_swallows_keyboard_interrupt_from_save_sync`

- Legs: windows-2022-3.10
- Location: `tests/conftest.py:606`

```
KeyError: 1148

failed on setup with "KeyError: 1148"
C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pytest_asyncio\plugin.py:926: in pytest_fixture_setup
    return (yield)
tests\conftest.py:606: in clear_binary_path_cache
    clear_caches()
tests\fixtures\cache_resets.py:40: in clear_caches
    module = importlib.import_module(module_path)
C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
E   KeyError: 1148
```
