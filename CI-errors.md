# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.
> Source SHA: `5ec0af0547d105a5691fc55e04eabcaade09ec75`

**19 failing/errored tests** across 6 matrix legs.

### 1. `tests.test_tts_local_client`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13
- Location: `tests/test_tts_local_client.py:14`

```
ModuleNotFoundError: No module named 'soundfile'

collection failure
ImportError while importing test module '/Users/runner/work/Lausu/Lausu/tests/test_tts_local_client.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_tts_local_client.py:14: in <module>
    import soundfile as sf
E   ModuleNotFoundError: No module named 'soundfile'
```

### 2. `tests.test_tts_voice_identity`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13
- Location: `tests/test_tts_voice_identity.py:33`

```
ModuleNotFoundError: No module named 'soundfile'

collection failure
ImportError while importing test module '/Users/runner/work/Lausu/Lausu/tests/test_tts_voice_identity.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_tts_voice_identity.py:33: in <module>
    import soundfile as sf
E   ModuleNotFoundError: No module named 'soundfile'
```

### 3. `tests.model_providers.test_domain_wiring.test_remote_tts_provider_is_used_when_configured`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13
- Location: `voice_typer/server/tts/wav.py:28`

```
voice_typer.server.tts.types.TtsError: unreadable WAV at /private/var/folders/9d/l02zfgrs7c16twd3wbpdmhkc0000gn/T/pytest-of-runner/pytest-1/popen-gw2/test_remote_tts_provider_is_us0/tts/work/custom/speak.wav: soundfile unavailable: No module named 'soundfile'

voice_typer.server.tts.types.TtsError: unreadable WAV at /private/var/folders/9d/l02zfgrs7c16twd3wbpdmhkc0000gn/T/pytest-of-runner/pytest-1/popen-gw2/test_remote_tts_provider_is_us0/tts/work/custom/speak.wav: soundfile unavailable: No module named 'soundfile'
voice_typer/server/tts/wav.py:28: in probe_wav
    import soundfile as sf  # type: ignore[import-untyped]
    ^^^^^^^^^^^^^^^^^^^^^^
E   ModuleNotFoundError: No module named 'soundfile'

The above exception was the direct cause of the following exception:
tests/model_providers/test_domain_wiring.py:56: in test_remote_tts_provider_is_used_when_configured
    result = manager.speak("hello", play=False)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
voice_typer/server/tts/manager.py:280: in speak
    return self._speak_via_provider(text, remote, play=play)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
voice_typer/server/tts/manager.py:252: in _speak_via_provider
    duration, sample_rate = probe_wav(out)
                            ^^^^^^^^^^^^^^
voice_typer/server/tts/wav.py:30: in probe_wav
    raise TtsError(f"unreadable WAV at {path}: soundfile unavailable: {exc}") from exc
E   voice_typer.server.tts.types.TtsError: unreadable WAV at /private/var/folders/9d/l02zfgrs7c16twd3wbpdmhkc0000gn/T/pytest-of-runner/pytest-1/popen-gw2/test_remote_tts_provider_is_us0/tts/work/custom/speak.wav: soundfile unavailable: No module named 'soundfile'
```

### 4. `tests.test_media_selfcheck.test_frozen_resolver_ignores_path_and_uses_original_exe_dir`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_media_selfcheck.py:87`

```
assert None is not None

assert None is not None
tests/test_media_selfcheck.py:87: in test_frozen_resolver_ignores_path_and_uses_original_exe_dir
    assert pair is not None
E   assert None is not None
```

### 5. `tests.test_module_split_reexports_wave3.TestConfigApplierFacadeReexports.test_handlers_take_side_effect_context_no_facade_global`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_module_split_reexports_wave3.py:344`

```
AttributeError: module 'voice_typer.server.config_applier_handlers' has no attribute '_TrayLeftClickHandler'

AttributeError: module 'voice_typer.server.config_applier_handlers' has no attribute '_TrayLeftClickHandler'
tests/test_module_split_reexports_wave3.py:344: in test_handlers_take_side_effect_context_no_facade_global
    apply = getattr(handlers, name).apply
            ^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: module 'voice_typer.server.config_applier_handlers' has no attribute '_TrayLeftClickHandler'
```

### 6. `tests.test_module_split_reexports_wave3.TestConfigApplierFacadeReexports.test_moved_symbols_resolve_to_the_sibling_modules`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_module_split_reexports_wave3.py:308`

```
AttributeError: module 'voice_typer.server.config_applier' has no attribute '_TrayLeftClickHandler'

AttributeError: module 'voice_typer.server.config_applier' has no attribute '_TrayLeftClickHandler'
tests/test_module_split_reexports_wave3.py:308: in test_moved_symbols_resolve_to_the_sibling_modules
    config_applier._TrayLeftClickHandler
E   AttributeError: module 'voice_typer.server.config_applier' has no attribute '_TrayLeftClickHandler'
```

### 7. `tests.test_module_split_reexports_wave9.TestRecordingLifecycleStageOrderParity.test_pipeline_stage_order_matches_the_contract`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_module_split_reexports_wave9.py:659`

```
assert not ['app._waveform_bubble.show()', 'set_state("recording")']

AssertionError: missing stage markers: ['app._waveform_bubble.show()', 'set_state("recording")']
assert not ['app._waveform_bubble.show()', 'set_state("recording")']
tests/test_module_split_reexports_wave9.py:659: in test_pipeline_stage_order_matches_the_contract
    self._ordered_markers(feedback_src, self.INSTANT_START_FEEDBACK_ORDER) == self.INSTANT_START_FEEDBACK_ORDER
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_module_split_reexports_wave9.py:642: in _ordered_markers
    assert not missing, f"missing stage markers: {missing}"
E   AssertionError: missing stage markers: ['app._waveform_bubble.show()', 'set_state("recording")']
E   assert not ['app._waveform_bubble.show()', 'set_state("recording")']
```

### 8. `tests.test_paste_failure_toast.TestPasteFailureBubbleState.test_bubble_shows_paste_failed_with_timed_exit`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_paste_failure_toast.py:280`

```
AssertionError: Expected 'show' to be called once. Called 0 times.

AssertionError: Expected 'show' to be called once. Called 0 times.
tests/test_paste_failure_toast.py:280: in test_bubble_shows_paste_failed_with_timed_exit
    app._waveform_bubble.show.assert_called_once_with()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:950: in assert_called_once_with
    raise AssertionError(msg)
E   AssertionError: Expected 'show' to be called once. Called 0 times.
```

### 9. `tests.test_short_audio_energy_gate.test_boundary_matrix_is_stable[1]`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:161`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:161: in test_boundary_matrix_is_stable
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 10. `tests.test_short_audio_energy_gate.test_boundary_matrix_is_stable[0]`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:161`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:161: in test_boundary_matrix_is_stable
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 11. `tests.test_short_audio_energy_gate.test_boundary_matrix_is_stable[2]`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:161`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:161: in test_boundary_matrix_is_stable
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 12. `tests.test_short_audio_energy_gate.test_loud_word_survives_and_loud_click_is_rejected`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:177`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:177: in test_loud_word_survives_and_loud_click_is_rejected
    _assert_discarded(_drive_gate(click))
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 13. `tests.test_short_audio_energy_gate.test_quiet_tap_and_long_silence_are_rejected`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:184`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:184: in test_quiet_tap_and_long_silence_are_rejected
    _assert_discarded(_drive_gate(_shape_audio(kind, duration_s, rng)))
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 14. `tests.test_short_audio_energy_gate.TestUnusableRmsIsDiscarded.test_garbage_last_rms_discards_without_crashing[none]`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:313`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:313: in test_garbage_last_rms_discards_without_crashing
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 15. `tests.test_short_audio_energy_gate.TestUnusableRmsIsDiscarded.test_garbage_last_rms_discards_without_crashing[string]`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:313`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:313: in test_garbage_last_rms_discards_without_crashing
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 16. `tests.test_short_audio_energy_gate.TestUnusableRmsIsDiscarded.test_garbage_last_rms_discards_without_crashing[nan]`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:313`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:313: in test_garbage_last_rms_discards_without_crashing
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 17. `tests.test_short_audio_energy_gate.TestUnusableRmsIsDiscarded.test_garbage_last_rms_discards_without_crashing[magic_mock]`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:313`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:313: in test_garbage_last_rms_discards_without_crashing
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 18. `tests.test_slice3_log_hygiene.TestNoiseSuppressorOncePerProcess.test_second_init_drops_to_debug`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11
- Location: `tests/test_slice3_log_hygiene.py:102`

```
+  where 0 = len([])

AssertionError: first init logs INFO once per process
assert 0 == 1
 +  where 0 = len([])
tests/test_slice3_log_hygiene.py:102: in test_second_init_drops_to_debug
    assert len(infos) == 1, "first init logs INFO once per process"
E   AssertionError: first init logs INFO once per process
E   assert 0 == 1
E    +  where 0 = len([])
```

### 19. `tests.test_recording.TestStopCallbackBackoff.test_zero_ms_common_case_when_flag_already_clear`

- Legs: ubuntu-22.04-3.13
- Location: `tests/test_recording.py:453`

```
+  where 12288 = len([0.01, 0.01, 0.01, 0.01, 0.01, 0.01, ...])

AssertionError: Expected 0 sleep calls (flag clear), got 12288
assert 12288 == 0
 +  where 12288 = len([0.01, 0.01, 0.01, 0.01, 0.01, 0.01, ...])
tests/test_recording.py:453: in test_zero_ms_common_case_when_flag_already_clear
    assert len(sleep_calls) == 0, f"Expected 0 sleep calls (flag clear), got {len(sleep_calls)}"
E   AssertionError: Expected 0 sleep calls (flag clear), got 12288
E   assert 12288 == 0
E    +  where 12288 = len([0.01, 0.01, 0.01, 0.01, 0.01, 0.01, ...])
```
