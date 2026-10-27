# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**4 failing/errored tests** across 9 matrix legs.

### 1. `tests.tauri.mig19.test_final_glue.test_main_rs_does_not_register_unknown_commands`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/mig19/test_final_glue.py:425`

```
assert not ['pick_media_file_command']

AssertionError: main.rs: generate_handler! list contains identifiers not in the frozen v1 command contract (ADR-0020 §16). New commands must go through the §16 process. Unknown identifiers: ['pick_media_file_command']
assert not ['pick_media_file_command']
tests/tauri/mig19/test_final_glue.py:425: in test_main_rs_does_not_register_unknown_commands
    assert not unknown, (
E   AssertionError: main.rs: generate_handler! list contains identifiers not in the frozen v1 command contract (ADR-0020 §16). New commands must go through the §16 process. Unknown identifiers: ['pick_media_file_command']
E   assert not ['pick_media_file_command']
```

### 2. `tests.test_architecture_doc_accuracy.test_tauri_command_count_in_doc_matches_code`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_architecture_doc_accuracy.py:186`

```
+  where 27 = len(['dispatch', 'shutdown_sidecar', 'restart_sidecar', 'export_history', 'export_vocabulary', 'bubble_show', ...])

AssertionError: generate_handler! in main.rs must register 26 commands (actual: 27: ['dispatch', 'shutdown_sidecar', 'restart_sidecar', 'export_history', 'export_vocabulary', 'bubble_show', 'bubble_signal_ready', 'bubble_set_position', 'bubble_set_draggable', 'bubble_move_by', 'bubble_hide_complete', 'bubble_dismiss', 'bubble_resize', 'bubble_request_screenshot_capture', 'bubble_toggle_dictation', 'open_logs', 'open_external_url_command', 'reveal_path_command', 'open_model_import_dialog', 'pick_media_file_command', 'export_templates', 'export_config', 'save_stats_image', 'send_bug_report', 'renderer_log_error', 'set_host_locale', 'renderer_heartbeat'])
assert 27 == 26
 +  where 27 = len(['dispatch', 'shutdown_sidecar', 'restart_sidecar', 'export_history', 'export_vocabulary', 'bubble_show', ...])
tests/test_architecture_doc_accuracy.py:186: in test_tauri_command_count_in_doc_matches_code
    assert len(cmds) == 26, f"generate_handler! in main.rs must register 26 commands (actual: {len(cmds)}: {cmds})"
E   AssertionError: generate_handler! in main.rs must register 26 commands (actual: 27: ['dispatch', 'shutdown_sidecar', 'restart_sidecar', 'export_history', 'export_vocabulary', 'bubble_show', 'bubble_signal_ready', 'bubble_set_position', 'bubble_set_draggable', 'bubble_move_by', 'bubble_hide_complete', 'bubble_dismiss', 'bubble_resize', 'bubble_request_screenshot_capture', 'bubble_toggle_dictation', 'open_logs', 'open_external_url_command', 'reveal_path_command', 'open_model_import_dialog', 'pick_media_file_command', 'export_templates', 'export_config', 'save_stats_image', 'send_bug_report', 'renderer_log_error', 'set_host_locale', 'renderer_heartbeat'])
E   assert 27 == 26
E    +  where 27 = len(['dispatch', 'shutdown_sidecar', 'restart_sidecar', 'export_history', 'export_vocabulary', 'bubble_show', ...])
```

### 3. `tests.test_architecture_doc_accuracy.test_main_rs_line_count_is_268`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_architecture_doc_accuracy.py:234`

```
assert 269 == 268

AssertionError: src-tauri/src/main.rs must be 268 lines (actual: 269). Update the doc + this test together.
assert 269 == 268
tests/test_architecture_doc_accuracy.py:234: in test_main_rs_line_count_is_268
    assert actual == 268, (
E   AssertionError: src-tauri/src/main.rs must be 268 lines (actual: 269). Update the doc + this test together.
E   assert 269 == 268
```

### 4. `tests.test_recording_lifecycle_threaded.TestDispatchThreadReturnsDuringModelReload.test_f2_returns_before_load_completes_when_model_reload_in_flight`

- Legs: windows-2022-3.11
- Location: `tests/test_recording_lifecycle_threaded.py:137`

```
+    where is_set = <threading.Event at 0x1f1dd689b90: unset>.is_set

AssertionError: ensure_active_engine_loaded() must have been called by the worker
assert False
 +  where False = is_set()
 +    where is_set = <threading.Event at 0x1f1dd689b90: unset>.is_set
tests\test_recording_lifecycle_threaded.py:137: in test_f2_returns_before_load_completes_when_model_reload_in_flight
    assert load_started.is_set(), "ensure_active_engine_loaded() must have been called by the worker"
E   AssertionError: ensure_active_engine_loaded() must have been called by the worker
E   assert False
E    +  where False = is_set()
E    +    where is_set = <threading.Event at 0x1f1dd689b90: unset>.is_set
```
