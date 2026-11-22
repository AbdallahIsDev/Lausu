# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.
> Source SHA: `47e021df7887ca07bafb09bfaa83c332830e3a64`

**15 failing/errored tests** across 6 matrix legs.

### 1. `tests.plugins.test_chrome_profile_pid_resolution.test_launch_records_pid_once_chrome_window_appears`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_chrome_profile_pid_resolution.py:74`

```
+  where 0 = len([])

AssertionError: the launch must retry until the window is painted
assert 0 >= 3
 +  where 0 = len([])
tests/plugins/test_chrome_profile_pid_resolution.py:74: in test_launch_records_pid_once_chrome_window_appears
    assert len(attempts) >= 3, "the launch must retry until the window is painted"
E   AssertionError: the launch must retry until the window is painted
E   assert 0 >= 3
E    +  where 0 = len([])
```

### 2. `tests.test_dictation_pipeline_history_gate.TestHistoryEnabledGate.test_calls_add_transcription_when_enabled`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_dictation_pipeline_history_gate.py:38`

```
Actual: add_transcription('hello world', duration=1.0, model='tiny.en', device='cpu', kind='dictation', processing_seconds=None, original_text=None)

AssertionError: expected call not found.
Expected: add_transcription('hello world', duration=1.0, model='tiny.en', device='cpu', kind='dictation', processing_seconds=None)
  Actual: add_transcription('hello world', duration=1.0, model='tiny.en', device='cpu', kind='dictation', processing_seconds=None, original_text=None)
tests/test_dictation_pipeline_history_gate.py:38: in test_calls_add_transcription_when_enabled
    app.history_db.add_transcription.assert_called_once_with(
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:951: in assert_called_once_with
    return self.assert_called_with(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:939: in assert_called_with
    raise AssertionError(_error_message()) from cause
E   AssertionError: expected call not found.
E   Expected: add_transcription('hello world', duration=1.0, model='tiny.en', device='cpu', kind='dictation', processing_seconds=None)
E     Actual: add_transcription('hello world', duration=1.0, model='tiny.en', device='cpu', kind='dictation', processing_seconds=None, original_text=None)
```

### 3. `tests.test_doc_command_counts.test_security_md_states_current_counts`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_doc_command_counts.py:34`

```
+      where <built-in method group of re.Match object at 0x10edcb2e0> = <re.Match object; span=(1866, 1888), match='registers 110 handlers'>.group

AssertionError: SECURITY.md documents 110 Python handlers but the actual registry count is 109.
assert 110 == 109
 +  where 110 = int('110')
 +    where '110' = <built-in method group of re.Match object at 0x10edcb2e0>(1)
 +      where <built-in method group of re.Match object at 0x10edcb2e0> = <re.Match object; span=(1866, 1888), match='registers 110 handlers'>.group
tests/test_doc_command_counts.py:34: in test_security_md_states_current_counts
    assert int(m_reg.group(1)) == actual_py, (
E   AssertionError: SECURITY.md documents 110 Python handlers but the actual registry count is 109.
E   assert 110 == 109
E    +  where 110 = int('110')
E    +    where '110' = <built-in method group of re.Match object at 0x10edcb2e0>(1)
E    +      where <built-in method group of re.Match object at 0x10edcb2e0> = <re.Match object; span=(1866, 1888), match='registers 110 handlers'>.group
```

### 4. `tests.test_doc_command_counts.test_features_md_states_command_counts`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_doc_command_counts.py:55`

```
+    where {'ack_cuda_activation', 'add_trusted_endpoint', 'bubble_host_hidden', 'cancel_cuda_download', 'cancel_model_download', 'chat_listen_start', ...} = _command_registry_entries()

AssertionError: FEATURES.md documents 110 commands total for _COMMAND_REGISTRY but the actual count is 109. Update FEATURES.md row #81.
assert 110 == 109
 +  where 110 = int('110')
 +    where '110' = <built-in method group of re.Match object at 0x143ba0d30>(1)
 +      where <built-in method group of re.Match object at 0x143ba0d30> = <re.Match object; span=(18181, 18228), match='_COMMAND_REGISTRY` registers 110 commands total'>.group
[+2 more lines; full report in element text]
tests/test_doc_command_counts.py:55: in test_features_md_states_command_counts
    assert int(m_reg.group(1)) == len(_command_registry_entries()), (
E   AssertionError: FEATURES.md documents 110 commands total for _COMMAND_REGISTRY but the actual count is 109. Update FEATURES.md row #81.
E   assert 110 == 109
E    +  where 110 = int('110')
E    +    where '110' = <built-in method group of re.Match object at 0x143ba0d30>(1)
E    +      where <built-in method group of re.Match object at 0x143ba0d30> = <re.Match object; span=(18181, 18228), match='_COMMAND_REGISTRY` registers 110 commands total'>.group
E    +  and   109 = len({'ack_cuda_activation', 'add_trusted_endpoint', 'bubble_host_hidden', 'cancel_cuda_download', 'cancel_model_download', 'chat_listen_start', ...})
E    +    where {'ack_cuda_activation', 'add_trusted_endpoint', 'bubble_host_hidden', 'cancel_cuda_download', 'cancel_model_download', 'chat_listen_start', ...} = _command_registry_entries()
```

### 5. `tests.test_doc_command_counts.test_contributing_md_states_registry_count`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_doc_command_counts.py:100`

```
+      where <built-in method group of re.Match object at 0x10edcaef0> = <re.Match object; span=(23942, 23973), match='reuses the 110-command registry'>.group

AssertionError: CONTRIBUTING.md documents 110-command registry but the actual _COMMAND_REGISTRY count is 109. Update the sidecar_ws.py row in CONTRIBUTING.md.
assert 110 == 109
 +  where 110 = int('110')
 +    where '110' = <built-in method group of re.Match object at 0x10edcaef0>(1)
 +      where <built-in method group of re.Match object at 0x10edcaef0> = <re.Match object; span=(23942, 23973), match='reuses the 110-command registry'>.group
tests/test_doc_command_counts.py:100: in test_contributing_md_states_registry_count
    assert int(m.group(1)) == actual, (
E   AssertionError: CONTRIBUTING.md documents 110-command registry but the actual _COMMAND_REGISTRY count is 109. Update the sidecar_ws.py row in CONTRIBUTING.md.
E   assert 110 == 109
E    +  where 110 = int('110')
E    +    where '110' = <built-in method group of re.Match object at 0x10edcaef0>(1)
E    +      where <built-in method group of re.Match object at 0x10edcaef0> = <re.Match object; span=(23942, 23973), match='reuses the 110-command registry'>.group
```

### 6. `tests.test_history_db_batch_insert.test_single_row_insert_uses_batch_path`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_history_db_batch_insert.py:119`

```
assert 0 == 1

AssertionError: expected 1 placeholder tuple for N=1 batch; got 0
assert 0 == 1
tests/test_history_db_batch_insert.py:119: in test_single_row_insert_uses_batch_path
    assert placeholder_tuples == 1, f"expected 1 placeholder tuple for N=1 batch; got {placeholder_tuples}"
E   AssertionError: expected 1 placeholder tuple for N=1 batch; got 0
E   assert 0 == 1
```

### 7. `tests.test_history_db_batch_insert.TestInsertSqlSingleSource.test_single_row_sql_shape`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_history_db_batch_insert.py:191`

```
?                                                                                                                                                                                                                                         +++++++++++++++                                                         +++

AssertionError: assert 'INSERT INTO ..., ?, ?, ?, ?)' == 'INSERT INTO ..., ?, ?, ?, ?)'

  - INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
[+2 more lines; full report in element text]
tests/test_history_db_batch_insert.py:191: in test_single_row_sql_shape
    assert _build_insert_sql(1) == (
E   AssertionError: assert 'INSERT INTO ..., ?, ?, ?, ?)' == 'INSERT INTO ..., ?, ?, ?, ?)'
E
E     - INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
E     + INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method, original_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
E     ?                                                                                                                                                                                                                                         +++++++++++++++                                                         +++
```

### 8. `tests.test_history_db_batch_insert.TestInsertSqlSingleSource.test_multi_row_sql_shape`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_history_db_batch_insert.py:202`

```
?                                                                                                                                                                                                                                         +++++++++++++++                                                         +++                                                    +++                                                    +++

AssertionError: assert 'INSERT INTO ..., ?, ?, ?, ?)' == 'INSERT INTO ..., ?, ?, ?, ?)'

  - INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
[+2 more lines; full report in element text]
tests/test_history_db_batch_insert.py:202: in test_multi_row_sql_shape
    assert _build_insert_sql(3) == (
E   AssertionError: assert 'INSERT INTO ..., ?, ?, ?, ?)' == 'INSERT INTO ..., ?, ?, ?, ?)'
E
E     - INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
E     + INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method, original_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
E     ?                                                                                                                                                                                                                                         +++++++++++++++                                                         +++                                                    +++                                                    +++
```

### 9. `tests.test_ipc_server.TestRegistryExtraction.test_registry_dict_same_keys_and_values_as_before`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_ipc_server.py:2062`

```
+    where {'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...} = <module 'voice_typer.server.ipc.registry' from '/Users/runner/work/Lausu/Lausu/voice_typer/server/ipc/registry.py'>._COMMAND_REGISTRY

AssertionError: registry._COMMAND_REGISTRY must contain 110 entries (105 forwarded in the Rust allowlist + shutdown + tray_click + bubble_host_hidden host-dispatched + heartbeat + relaunch_ack host-dispatched); got 109. If the count drifted, update this test together with the registry + the TS/Rust allowlists.
assert 109 == 110
[+2 more lines; full report in element text]
tests/test_ipc_server.py:2062: in test_registry_dict_same_keys_and_values_as_before
    assert len(registry._COMMAND_REGISTRY) == 110, (
E   AssertionError: registry._COMMAND_REGISTRY must contain 110 entries (105 forwarded in the Rust allowlist + shutdown + tray_click + bubble_host_hidden host-dispatched + heartbeat + relaunch_ack host-dispatched); got 109. If the count drifted, update this test together with the registry + the TS/Rust allowlists.
E   assert 109 == 110
E    +  where 109 = len({'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...})
E    +    where {'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...} = <module 'voice_typer.server.ipc.registry' from '/Users/runner/work/Lausu/Lausu/voice_typer/server/ipc/registry.py'>._COMMAND_REGISTRY
```

### 10. `tests.test_module_split_reexports_wave9.TestDownloadsComposite.test_surface_matches_the_presplit_mixin`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_module_split_reexports_wave9.py:305`

```
}

AssertionError: missing: []; unexpected: ['_download_translation']
assert {'_download_p...d_model', ...} == {'_download_p...sitions', ...}

  Extra items in the left set:
  '_download_translation'

  Full diff: (-: missing in left side, +: extra in left side)
    {
        '_download_parakeet',
        '_download_qwen',
  +     '_download_translation',
        '_download_whisper_family',
        '_enqueue_download',
        '_is_active_download_model',
        '_push_queue_positions',
[+11 more lines; full report in element text]
tests/test_module_split_reexports_wave9.py:305: in test_surface_matches_the_presplit_mixin
    assert surface == EXPECTED_DOWNLOAD_SURFACE, (
E   AssertionError: missing: []; unexpected: ['_download_translation']
E   assert {'_download_p...d_model', ...} == {'_download_p...sitions', ...}
E
E     Extra items in the left set:
E     '_download_translation'
E
E     Full diff: (-: missing in left side, +: extra in left side)
E       {
E           '_download_parakeet',
E           '_download_qwen',
E     +     '_download_translation',
E           '_download_whisper_family',
E           '_enqueue_download',
E           '_is_active_download_model',
E           '_push_queue_positions',
E           '_queued_download_runner',
E           '_remove_queued_download',
E           '_require_huggingface_consent',
E           '_start_next_queued_download',
E           'cancel_model_download',
```

### 11. `tests.test_no_literal_tray_strings.test_no_literal_user_facing_string_in_gui_calls[_download_translation.py]`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_no_literal_tray_strings.py:100`

```
assert not [(55, 'Translation model downloaded successfully')]

AssertionError: _download_translation.py: user-facing string passed as a literal to a UI call (C-I18N-1). Use i18n.t('<key>') and register the key in voice_typer/server/i18n.py, map it in i18n/push.ts, and add it to all 8 renderer locales:
    line 55: 'Translation model downloaded successfully'
assert not [(55, 'Translation model downloaded successfully')]
tests/test_no_literal_tray_strings.py:100: in test_no_literal_user_facing_string_in_gui_calls
    assert not offenders, (
E   AssertionError: _download_translation.py: user-facing string passed as a literal to a UI call (C-I18N-1). Use i18n.t('<key>') and register the key in voice_typer/server/i18n.py, map it in i18n/push.ts, and add it to all 8 renderer locales:
E       line 55: 'Translation model downloaded successfully'
E   assert not [(55, 'Translation model downloaded successfully')]
```

### 12. `tests.test_perf_data_store_save_write.TestHistoryDBMultiRowInsertBatching.test_three_pending_inserts_are_batched_into_one_multi_row_insert`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_perf_data_store_save_write.py:330`

```
assert 0 == 3

AssertionError: ER-78: expected total of 3 placeholder tuples across batches, got 0. SQL: ['INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method, original_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,...
[+1 more line; full report in element text]
tests/test_perf_data_store_save_write.py:330: in test_three_pending_inserts_are_batched_into_one_multi_row_insert
    assert total_tuples == 3, (
E   AssertionError: ER-78: expected total of 3 placeholder tuples across batches, got 0. SQL: ['INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method, original_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)']
E   assert 0 == 3
```

### 13. `tests.test_perf_data_store_save_write.TestHistoryDBMultiRowInsertBatching.test_single_insert_below_threshold_is_not_batched`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_perf_data_store_save_write.py:356`

```
+    where <built-in method count of str object at 0x1478a0bb0> = 'INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method, original_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'.count

AssertionError: single-row INSERT should have 1 placeholder tuple, got 0. SQL: INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method, original_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
assert 0 == 1
[+2 more lines; full report in element text]
tests/test_perf_data_store_save_write.py:356: in test_single_insert_below_threshold_is_not_batched
    assert sql.count(placeholder_tuple) == 1, (
E   AssertionError: single-row INSERT should have 1 placeholder tuple, got 0. SQL: INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method, original_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
E   assert 0 == 1
E    +  where 0 = <built-in method count of str object at 0x1478a0bb0>('(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
E    +    where <built-in method count of str object at 0x1478a0bb0> = 'INSERT INTO transcriptions (text, duration, model, device, word_count, char_count, language, kind, source_type, source_title, source_url, file_name, thumbnail_url, media_duration_seconds, processing_seconds, download_seconds, method, original_text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'.count
```

### 14. `tests.test_store_cycle_guard.TestStoreGuardBlocksCancelledCycle.test_live_cycle_reaches_the_wrapped_store_stage`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_store_cycle_guard.py:121`

```
Actual: mock('live text', original_text=None)

AssertionError: expected call not found.
Expected: mock('live text')
  Actual: mock('live text', original_text=None)
tests/test_store_cycle_guard.py:121: in test_live_cycle_reaches_the_wrapped_store_stage
    pipeline._store_result.assert_called_once_with("live text")
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:951: in assert_called_once_with
    return self.assert_called_with(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:939: in assert_called_with
    raise AssertionError(_error_message()) from cause
E   AssertionError: expected call not found.
E   Expected: mock('live text')
E     Actual: mock('live text', original_text=None)
```

### 15. `tests.hotkeys.test_polling_strategy.TestPressHoldReleaseNoRepeat.test_two_press_cycles_fire_exactly_twice`

- Legs: macos-15-3.13
- Location: `tests/hotkeys/test_polling_strategy.py:249`

```
AssertionError: Callback did not fire on press (cycle 2) (waited 2.0s)

AssertionError: Callback did not fire on press (cycle 2) (waited 2.0s)
tests/hotkeys/test_polling_strategy.py:249: in test_two_press_cycles_fire_exactly_twice
    _wait_until(
tests/hotkeys/test_polling_strategy.py:89: in _wait_until
    raise AssertionError(f"{msg} (waited {timeout}s)")
E   AssertionError: Callback did not fire on press (cycle 2) (waited 2.0s)
```
