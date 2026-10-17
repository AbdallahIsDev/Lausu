# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**24 failing/errored tests** across 5 matrix legs.

### 1. `tests.test_ipc_server.TestCommandCostsContract.test_every_registered_command_has_explicit_cost@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_ipc_server.py:818`

```
assert not {'live_preview'}

AssertionError: Commands registered in _COMMAND_REGISTRY but missing from COMMAND_COSTS: ['live_preview']. Each registered command MUST have an explicit cost entry, add them to COMMAND_COSTS in voice_typer/server/ipc/rate_limiter.py. Cost tiers: 1=cheap read, 2=small write, 3=compute, 5=starts long-lived resource, 10=heavy I/O, 20=very heavy, 50=network-saturating download.
assert not {'live_preview'}
tests/test_ipc_server.py:818: in test_every_registered_command_has_explicit_cost
    assert not missing, (
E   AssertionError: Commands registered in _COMMAND_REGISTRY but missing from COMMAND_COSTS: ['live_preview']. Each registered command MUST have an explicit cost entry, add them to COMMAND_COSTS in voice_typer/server/ipc/rate_limiter.py. Cost tiers: 1=cheap read, 2=small write, 3=compute, 5=starts long-lived resource, 10=heavy I/O, 20=very heavy, 50=network-saturating download.
E   assert not {'live_preview'}
```

### 2. `tests.test_ipc_server.TestRegistryExtraction.test_registry_dict_same_keys_and_values_as_before@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_ipc_server.py:2055`

```
+    where {'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...} = <module 'voice_typer.server.ipc.registry' from '/Users/runner/work/Lausu/Lausu/voice_typer/server/ipc/registry.py'>._COMMAND_REGISTRY

AssertionError: registry._COMMAND_REGISTRY must contain 89 entries (85 forwarded in the Rust allowlist + shutdown + tray_click python-only + heartbeat + relaunch_ack host-dispatched); got 90. If the count drifted, update this test together with the registry + the TS/Rust allowlists.
assert 90 == 89
 +  where 90 = len({'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...})
 +    where {'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...} = <module 'voice_typer.server.ipc.registry' from '/Users/runner/work/Lausu/Lausu/voice_typer/server/ipc/registry.py'>._COMMAND_REGISTRY
tests/test_ipc_server.py:2055: in test_registry_dict_same_keys_and_values_as_before
    assert len(registry._COMMAND_REGISTRY) == 89, (
E   AssertionError: registry._COMMAND_REGISTRY must contain 89 entries (85 forwarded in the Rust allowlist + shutdown + tray_click python-only + heartbeat + relaunch_ack host-dispatched); got 90. If the count drifted, update this test together with the registry + the TS/Rust allowlists.
E   assert 90 == 89
E    +  where 90 = len({'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...})
E    +    where {'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...} = <module 'voice_typer.server.ipc.registry' from '/Users/runner/work/Lausu/Lausu/voice_typer/server/ipc/registry.py'>._COMMAND_REGISTRY
```

### 3. `tests.recording.test_recorder_split_pipelines.TestStopRecordingPrepareAudioPipelining.test_stats_overlap_with_prepare_audio`

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

### 4. `tests.tauri.mig19.test_phase4_validation.test_command_contract_is_frozen_no_untested_additions`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig19/test_phase4_validation.py:669`

```
Do NOT silently grow the wire contract.

Failed: ADR-0020 §16: _COMMAND_REGISTRY contains commands NOT in the frozen 68-command table AND NOT in the KNOWN_UNDOCUMENTED_COMMANDS allowlist:
  live_preview

To resolve, EITHER:
  (a) Remove the command from _COMMAND_REGISTRY (it was added without an ADR addendum), OR
  (b) Add it to EXPECTED_COMMANDS in this test + add an ADR-0020 addendum + add a _validate_dict_payload schema + add a test in tests/test_ipc_dispatch_errors.py, OR
  (c) Add it to KNOWN_UNDOCUMENTED_COMMANDS in this test with a comment naming the PR + reason (this is the explicit-gap path; the test_known_undocumented_commands_are_reported test below will then keep the entry in sync with reality).
Do NOT silently grow the wire contract.
tests/tauri/mig19/test_phase4_validation.py:669: in test_command_contract_is_frozen_no_untested_additions
    pytest.fail(
E   Failed: ADR-0020 §16: _COMMAND_REGISTRY contains commands NOT in the frozen 68-command table AND NOT in the KNOWN_UNDOCUMENTED_COMMANDS allowlist:
E     live_preview
E   
E   To resolve, EITHER:
E     (a) Remove the command from _COMMAND_REGISTRY (it was added without an ADR addendum), OR
E     (b) Add it to EXPECTED_COMMANDS in this test + add an ADR-0020 addendum + add a _validate_dict_payload schema + add a test in tests/test_ipc_dispatch_errors.py, OR
E     (c) Add it to KNOWN_UNDOCUMENTED_COMMANDS in this test with a comment naming the PR + reason (this is the explicit-gap path; the test_known_undocumented_commands_are_reported test below will then keep the entry in sync with reality).
E   Do NOT silently grow the wire contract.
```

### 5. `tests.tauri.mig19.test_phase4_validation.test_known_undocumented_commands_are_reported`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig19/test_phase4_validation.py:711`

```
live_preview

Failed: Commands in _COMMAND_REGISTRY but NOT in EXPECTED_COMMANDS and NOT in KNOWN_UNDOCUMENTED_COMMANDS (add to KNOWN_UNDOCUMENTED_COMMANDS with a comment, OR close the gap by adding to EXPECTED_COMMANDS + ADR addendum):
  live_preview
tests/tauri/mig19/test_phase4_validation.py:711: in test_known_undocumented_commands_are_reported
    pytest.fail("\n\n".join(msg_parts))
E   Failed: Commands in _COMMAND_REGISTRY but NOT in EXPECTED_COMMANDS and NOT in KNOWN_UNDOCUMENTED_COMMANDS (add to KNOWN_UNDOCUMENTED_COMMANDS with a comment, OR close the gap by adding to EXPECTED_COMMANDS + ADR addendum):
E     live_preview
```

### 6. `tests.test_architecture_doc_accuracy.test_event_bus_count_matches_doc_and_code`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_architecture_doc_accuracy.py:40`

```
+  where 53 = len(frozenset({'asr_backend_disabled', 'asr_backend_load_failed', 'asr_backend_ready', 'asr_last_resort_unloaded', 'audio_clip', 'bubble_config', ...}))

AssertionError: EVENT_TYPES in voice_typer/server/event_bus.py must have 52 entries (actual: 53). Update doc + test together.
assert 53 == 52
 +  where 53 = len(frozenset({'asr_backend_disabled', 'asr_backend_load_failed', 'asr_backend_ready', 'asr_last_resort_unloaded', 'audio_clip', 'bubble_config', ...}))
tests/test_architecture_doc_accuracy.py:40: in test_event_bus_count_matches_doc_and_code
    assert len(EVENT_TYPES) == 52, (
E   AssertionError: EVENT_TYPES in voice_typer/server/event_bus.py must have 52 entries (actual: 53). Update doc + test together.
E   assert 53 == 52
E    +  where 53 = len(frozenset({'asr_backend_disabled', 'asr_backend_load_failed', 'asr_backend_ready', 'asr_last_resort_unloaded', 'audio_clip', 'bubble_config', ...}))
```

### 7. `tests.test_architecture_doc_accuracy.test_module_paths_use_package_form`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_architecture_doc_accuracy.py:281`

```
+  where 10 = len([PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/worker.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/test_recording_files.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/mic_level_push.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring_queries.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'), ...])

AssertionError: level_monitor/ must be a 9-file package (actual: 10).
assert 10 == 9
 +  where 10 = len([PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/worker.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/test_recording_files.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/mic_level_push.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring_queries.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'), ...])
tests/test_architecture_doc_accuracy.py:281: in test_module_paths_use_package_form
    assert len(level_files) == 9, f"level_monitor/ must be a 9-file package (actual: {len(level_files)})."
E   AssertionError: level_monitor/ must be a 9-file package (actual: 10).
E   assert 10 == 9
E    +  where 10 = len([PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/worker.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/test_recording_files.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/mic_level_push.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring_queries.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'), ...])
```

### 8. `tests.test_audio_filter_reset_zero_buffers.test_streaming_resampler_chunked_matches_oneshot`

- Legs: macos-14-3.10
- Location: `tests/test_audio_filter_reset_zero_buffers.py:129`

```
+      where <ufunc 'absolute'> = np.abs

AssertionError: assert np.float32(9.313226e-10) == 0.0
 +  where np.float32(9.313226e-10) = <function max at 0x105c7a1b0>(array([0.000000e+00, 0.000000e+00, 0.000000e+00, ..., 4.656613e-10,\n       5.820766e-11, 0.000000e+00], shape=(1024,), dtype=float32))
 +    where <function max at 0x105c7a1b0> = np.max
 +    and   array([0.000000e+00, 0.000000e+00, 0.000000e+00, ..., 4.656613e-10,\n       5.820766e-11, 0.000000e+00], shape=(1024,), dtype=float32) = <ufunc 'absolute'>((array([ 9.2539922e-09,  2.2526635e-06, -3.3697943e-05, ...,\n        4.0074368e-03, -4.0152267e-04,  2.5318800e-03],\n      shape=(1024,), dtype=float32) - array([ 9.2539922e-09,  2.2526635e-06, -3.3697943e-05, ...,\n        4.0074373e-03, -4.0152261e-04,  2.5318800e-03],\n      shape=(1024,), dtype=float32)))
 +      where <ufunc 'absolute'> = np.abs
tests/test_audio_filter_reset_zero_buffers.py:129: in test_streaming_resampler_chunked_matches_oneshot
    assert np.max(np.abs(ref - streamed)) == 0.0
E   AssertionError: assert np.float32(9.313226e-10) == 0.0
E    +  where np.float32(9.313226e-10) = <function max at 0x105c7a1b0>(array([0.000000e+00, 0.000000e+00, 0.000000e+00, ..., 4.656613e-10,\n       5.820766e-11, 0.000000e+00], shape=(1024,), dtype=float32))
E    +    where <function max at 0x105c7a1b0> = np.max
E    +    and   array([0.000000e+00, 0.000000e+00, 0.000000e+00, ..., 4.656613e-10,\n       5.820766e-11, 0.000000e+00], shape=(1024,), dtype=float32) = <ufunc 'absolute'>((array([ 9.2539922e-09,  2.2526635e-06, -3.3697943e-05, ...,\n        4.0074368e-03, -4.0152267e-04,  2.5318800e-03],\n      shape=(1024,), dtype=float32) - array([ 9.2539922e-09,  2.2526635e-06, -3.3697943e-05, ...,\n        4.0074373e-03, -4.0152261e-04,  2.5318800e-03],\n      shape=(1024,), dtype=float32)))
E    +      where <ufunc 'absolute'> = np.abs
```

### 9. `tests.test_doc_command_counts.test_features_md_states_command_counts`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_doc_command_counts.py:55`

```
+    where {'add_trusted_endpoint', 'cancel_model_download', 'check_accessibility', 'check_offline_pack_update', 'clear_history', 'delete_history', ...} = _command_registry_entries()

AssertionError: FEATURES.md documents 89 commands total for _COMMAND_REGISTRY but the actual count is 90. Update FEATURES.md row #81.
assert 89 == 90
 +  where 89 = int('89')
 +    where '89' = <built-in method group of re.Match object at 0x13fca4a60>(1)
 +      where <built-in method group of re.Match object at 0x13fca4a60> = <re.Match object; span=(18128, 18174), match='_COMMAND_REGISTRY` registers 89 commands total'>.group
 +  and   90 = len({'add_trusted_endpoint', 'cancel_model_download', 'check_accessibility', 'check_offline_pack_update', 'clear_history', 'delete_history', ...})
 +    where {'add_trusted_endpoint', 'cancel_model_download', 'check_accessibility', 'check_offline_pack_update', 'clear_history', 'delete_history', ...} = _command_registry_entries()
tests/test_doc_command_counts.py:55: in test_features_md_states_command_counts
    assert int(m_reg.group(1)) == len(_command_registry_entries()), (
E   AssertionError: FEATURES.md documents 89 commands total for _COMMAND_REGISTRY but the actual count is 90. Update FEATURES.md row #81.
E   assert 89 == 90
E    +  where 89 = int('89')
E    +    where '89' = <built-in method group of re.Match object at 0x13fca4a60>(1)
E    +      where <built-in method group of re.Match object at 0x13fca4a60> = <re.Match object; span=(18128, 18174), match='_COMMAND_REGISTRY` registers 89 commands total'>.group
E    +  and   90 = len({'add_trusted_endpoint', 'cancel_model_download', 'check_accessibility', 'check_offline_pack_update', 'clear_history', 'delete_history', ...})
E    +    where {'add_trusted_endpoint', 'cancel_model_download', 'check_accessibility', 'check_offline_pack_update', 'clear_history', 'delete_history', ...} = _command_registry_entries()
```

### 10. `tests.test_doc_command_counts.test_contributing_md_states_registry_count`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_doc_command_counts.py:100`

```
+      where <built-in method group of re.Match object at 0x13fca5480> = <re.Match object; span=(23931, 23961), match='reuses the 85-command registry'>.group

AssertionError: CONTRIBUTING.md documents 85-command registry but the actual _COMMAND_REGISTRY count is 90. Update the sidecar_ws.py row in CONTRIBUTING.md.
assert 85 == 90
 +  where 85 = int('85')
 +    where '85' = <built-in method group of re.Match object at 0x13fca5480>(1)
 +      where <built-in method group of re.Match object at 0x13fca5480> = <re.Match object; span=(23931, 23961), match='reuses the 85-command registry'>.group
tests/test_doc_command_counts.py:100: in test_contributing_md_states_registry_count
    assert int(m.group(1)) == actual, (
E   AssertionError: CONTRIBUTING.md documents 85-command registry but the actual _COMMAND_REGISTRY count is 90. Update the sidecar_ws.py row in CONTRIBUTING.md.
E   assert 85 == 90
E    +  where 85 = int('85')
E    +    where '85' = <built-in method group of re.Match object at 0x13fca5480>(1)
E    +      where <built-in method group of re.Match object at 0x13fca5480> = <re.Match object; span=(23931, 23961), match='reuses the 85-command registry'>.group
```

### 11. `tests.test_handlers_log_single_source.test_no_inline_get_logger[screenshot_handlers.py]`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
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

### 12. `tests.test_handlers_log_single_source.test_no_handler_module_uses_import_logging_only_for_logger`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
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

### 13. `tests.test_hotkeys_win32.TestModifierOnlyHotkeys.test_alt_only_hotkey_starts_without_error`

- Legs: macos-14-3.10
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

### 14. `tests.test_ipc_reference_doc_accuracy.test_ipc_reference_doc_commands_header_count_matches_registry`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_ipc_reference_doc_accuracy.py:146`

```
assert 89 == 90

AssertionError: docs/ipc-reference.md documents 89 total commands but _COMMAND_REGISTRY has 90. Update the header.
assert 89 == 90
tests/test_ipc_reference_doc_accuracy.py:146: in test_ipc_reference_doc_commands_header_count_matches_registry
    assert documented == actual, (
E   AssertionError: docs/ipc-reference.md documents 89 total commands but _COMMAND_REGISTRY has 90. Update the header.
E   assert 89 == 90
```

### 15. `tests.test_ipc_reference_doc_accuracy.test_ipc_reference_doc_push_events_header_count_matches_source`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_ipc_reference_doc_accuracy.py:159`

```
assert 64 == 65

AssertionError: docs/ipc-reference.md documents 64 typed push events but the renderer's types/ipc/push_events.ts declares 65 (via `type: "<name>"` literals). Update the header.
assert 64 == 65
tests/test_ipc_reference_doc_accuracy.py:159: in test_ipc_reference_doc_push_events_header_count_matches_source
    assert documented == actual, (
E   AssertionError: docs/ipc-reference.md documents 64 typed push events but the renderer's types/ipc/push_events.ts declares 65 (via `type: "<name>"` literals). Update the header.
E   assert 64 == 65
```

### 16. `tests.test_ipc_reference_doc_accuracy.test_ipc_reference_doc_has_row_for_every_push_event_type`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_ipc_reference_doc_accuracy.py:171`

```
assert not {'live_preview_audio'}

AssertionError: push_events.ts declares 1 event types with no row in docs/ipc-reference.md: ['live_preview_audio']. Add a row in the '## Push events' table.
assert not {'live_preview_audio'}
tests/test_ipc_reference_doc_accuracy.py:171: in test_ipc_reference_doc_has_row_for_every_push_event_type
    assert not missing_from_doc, (
E   AssertionError: push_events.ts declares 1 event types with no row in docs/ipc-reference.md: ['live_preview_audio']. Add a row in the '## Push events' table.
E   assert not {'live_preview_audio'}
```

### 17. `tests.test_mic_page_selection_and_test_transport.TestFinishedCallbackIdentityGuard.test_genuine_finish_of_current_stream_still_emits`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_mic_page_selection_and_test_transport.py:167`

```
+  where 0 = len([])

assert 0 == 1
 +  where 0 = len([])
tests/test_mic_page_selection_and_test_transport.py:167: in test_genuine_finish_of_current_stream_still_emits
    assert len(events) == 1
E   assert 0 == 1
E    +  where 0 = len([])
```

### 18. `tests.test_mic_page_selection_and_test_transport.TestFinishedCallbackIdentityGuard.test_guard_is_idempotent_per_episode`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_mic_page_selection_and_test_transport.py:180`

```
+    where [] = _device_lost([])

assert 0 == 1
 +  where 0 = len([])
 +    where [] = _device_lost([])
tests/test_mic_page_selection_and_test_transport.py:180: in test_guard_is_idempotent_per_episode
    assert len(_device_lost(captured)) == 1
E   assert 0 == 1
E    +  where 0 = len([])
E    +    where [] = _device_lost([])
```

### 19. `tests.test_recording_lifecycle_threaded.TestRecordingStartFailureReason.test_permission_denied_surfaces_reason`

- Legs: macos-14-3.10, ubuntu-22.04-3.11
- Location: `tests/test_recording_lifecycle_threaded.py:425`

```
AttributeError: 'NoneType' object has no attribute 'args'

AttributeError: 'NoneType' object has no attribute 'args'
tests/test_recording_lifecycle_threaded.py:425: in test_permission_denied_surfaces_reason
    notify_msg = str(notify_mock.call_args.args[1])
E   AttributeError: 'NoneType' object has no attribute 'args'
```

### 20. `tests.test_recording_lifecycle_threaded.TestRecordingStartFailureReason.test_unknown_error_keeps_generic_label`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_recording_lifecycle_threaded.py:469`

```
+    where <built-in method lower of str object at 0x105845590> = 'Could not start recording. Please try again.'.lower

AssertionError: unknown failure notification should point at the log, got: 'Could not start recording. Please try again.'
assert 'check logs/lausu.log' in 'could not start recording. please try again.'
 +  where 'could not start recording. please try again.' = <built-in method lower of str object at 0x105845590>()
 +    where <built-in method lower of str object at 0x105845590> = 'Could not start recording. Please try again.'.lower
tests/test_recording_lifecycle_threaded.py:469: in test_unknown_error_keeps_generic_label
    assert "check logs/lausu.log" in notify_msg.lower(), (
E   AssertionError: unknown failure notification should point at the log, got: 'Could not start recording. Please try again.'
E   assert 'check logs/lausu.log' in 'could not start recording. please try again.'
E    +  where 'could not start recording. please try again.' = <built-in method lower of str object at 0x105845590>()
E    +    where <built-in method lower of str object at 0x105845590> = 'Could not start recording. Please try again.'.lower
```

### 21. `tests.test_startup_log_quality.TestCudaDllLine.test_line_names_process_purpose_and_duration`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
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

### 22. `tests.test_audio_filter_reset_zero_buffers.test_streaming_resampler_chunk_cost_within_budget`

- Legs: ubuntu-22.04-3.10
- Location: `tests/test_audio_filter_reset_zero_buffers.py:147`

```
assert 24.20524059999707 < 10.0

AssertionError: resampler too slow: 24.2 ms/chunk
assert 24.20524059999707 < 10.0
tests/test_audio_filter_reset_zero_buffers.py:147: in test_streaming_resampler_chunk_cost_within_budget
    assert mean_ms < 10.0, f"resampler too slow: {mean_ms:.1f} ms/chunk"
E   AssertionError: resampler too slow: 24.2 ms/chunk
E   assert 24.20524059999707 < 10.0
```

### 23. `tests.test_noise_suppressor_gtcrn.TestGtcrnSharedSession.test_preload_second_call_noop_log`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12
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

### 24. `tests.test_tauri_sign_cmd_safe.TestAuthenticodeSigningHelper.test_helper_retries_timestamp_servers_and_verifies`

- Legs: ubuntu-22.04-3.10
- Location: `tests/conftest.py:149`

```
KeyError: 140364910664576

failed on setup with "KeyError: 140364910664576"
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/site-packages/pytest_asyncio/plugin.py:926: in pytest_fixture_setup
    return (yield)
tests/conftest.py:149: in default_text_field_focus
    monkeypatch.setattr(
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
E   KeyError: 140364910664576
```
