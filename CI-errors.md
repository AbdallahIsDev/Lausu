# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**2 failing/errored tests** across 8 matrix legs.

### 1. `tests.test_module_split_reexports_wave9.TestRecordingLifecycleSplitFacade.test_surface_matches_the_presplit_class`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_module_split_reexports_wave9.py:565`

```
}

AssertionError: missing: []; unexpected: ['_hide_instant_start_feedback', '_publish_instant_start_feedback']
assert {'_cancel_imp...eedback', ...} == {'_cancel_imp...d_event', ...}

  Extra items in the left set:
  '_publish_instant_start_feedback'
  '_hide_instant_start_feedback'

  Full diff:
    {
        '_cancel_impl',
        '_claim_keyboard_ownership_for_recording',
        '_gate_voice_biometric_consent',
  +     '_hide_instant_start_feedback',
        '_notify_mic_watcher_of_active_device',
  +     '_publish_instant_start_feedback',
        '_publish_permission_denied_refusal',
        '_publish_recording_started_event',
        '_publish_start_failure_notification',
        '_rearm_esc_cancel_if_enabled',
        '_run_public_entry',
        '_run_stop_and_transcribe',
        '_schedule_permission_revoked_bubble_reset',
        '_spawn_dictation_start_worker',
        '_start_dictation_worker_entry',
        '_start_impl',
        '_stop_and_transcribe_worker_entry',
        '_stop_impl',
        '_surface_busy_refusal',
        '_teardown_failed_recorder_start',
        '_toggle_impl',
        '_wire_recorder_start_callbacks',
        'cancel',
        'start',
        'stop',
        'toggle',
    }
tests/test_module_split_reexports_wave9.py:565: in test_surface_matches_the_presplit_class
    assert surface == EXPECTED_RECORDING_LIFECYCLE_SURFACE, (
```

### 2. `tests.test_module_split_reexports_wave9.TestRecordingLifecycleStageOrderParity.test_pipeline_stage_order_matches_pre_split`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_module_split_reexports_wave9.py:657`

```
assert not ['AppState.RECORDING', '_publish_recording_started_event', '_waveform_bubble.show()', 'set_state("recording")']

AssertionError: missing stage markers: ['AppState.RECORDING', '_publish_recording_started_event', '_waveform_bubble.show()', 'set_state("recording")']
assert not ['AppState.RECORDING', '_publish_recording_started_event', '_waveform_bubble.show()', 'set_state("recording")']
tests/test_module_split_reexports_wave9.py:657: in test_pipeline_stage_order_matches_pre_split
    self._ordered_markers(start_src, self.START_STAGE_ORDER) == self.START_STAGE_ORDER
tests/test_module_split_reexports_wave9.py:645: in _ordered_markers
    assert not missing, f"missing stage markers: {missing}"
E   AssertionError: missing stage markers: ['AppState.RECORDING', '_publish_recording_started_event', '_waveform_bubble.show()', 'set_state("recording")']
E   assert not ['AppState.RECORDING', '_publish_recording_started_event', '_waveform_bubble.show()', 'set_state("recording")']
```
