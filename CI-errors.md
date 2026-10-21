# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**134 failing/errored tests** across 4 matrix legs.

### 1. `tests.app.test_config_wiring.TestConfigWiring.test_paste_on_stop_preserves_user_value`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/app/test_config_wiring.py:28`

```
+    where Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95) = <voice_typer.server.app.LausuApp object at 0x7f9e1a51dc90>.config

AssertionError: assert True is False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_
… (truncated)
```

### 2. `tests.app.test_config_wiring.TestConfigWiring.test_streaming_preserves_user_value`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/app/test_config_wiring.py:45`

```
+    where Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95) = <voice_typer.server.app.LausuApp object at 0x7f9e1a48a3b0>.config

AssertionError: assert True is False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_
… (truncated)
```

### 3. `tests.app.test_config_wiring.TestConfigWiring.test_transcription_speed_settings_wired`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/app/test_config_wiring.py:85`

```
assert 1 == 2

assert 1 == 2
tests/app/test_config_wiring.py:85: in test_transcription_speed_settings_wired
    assert kwargs["beam_size"] == 2
E   assert 1 == 2
```

### 4. `tests.app.test_config_wiring.TestConfigWiring.test_autostart_disabled_when_config_false`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/app/test_config_wiring.py:129`

```
+  where 0 = len([])

assert 0 == 1
 +  where 0 = len([])
tests/app/test_config_wiring.py:129: in test_autostart_disabled_when_config_false
    assert len(called) == 1  # disable_autostart was called
E   assert 0 == 1
E    +  where 0 = len([])
```

### 5. `tests.config.test_config_load_save.TestConfigLoadSave.test_load_reads_existing_file`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:76`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f9>'

  - <f9>
  + <caps_lock>
tests/config/test_config_load_save.py:76: in test_load_reads_existing_file
    assert c.hotkey == "<f9>"
E   AssertionError: assert '<caps_lock>' == '<f9>'
E
E     - <f9>
E     + <caps_lock>
```

### 6. `tests.config.test_config_load_save.TestConfigLoadSave.test_load_preserves_user_device_and_paste_settings`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:98`

```
+  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).streaming_transcription

AssertionError: assert True is False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_c
… (truncated)
```

### 7. `tests.config.test_config_load_save.TestConfigLoadSave.test_load_keeps_supported_models_unchanged[tiny]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:137`

```
- tiny

AssertionError: assert '' == 'tiny'

  - tiny
tests/config/test_config_load_save.py:137: in test_load_keeps_supported_models_unchanged
    assert c.model_size == valid_model
E   AssertionError: assert '' == 'tiny'
E
E     - tiny
```

### 8. `tests.config.test_config_load_save.TestConfigLoadSave.test_load_keeps_supported_models_unchanged[large-v3-turbo]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:137`

```
- large-v3-turbo

AssertionError: assert '' == 'large-v3-turbo'

  - large-v3-turbo
tests/config/test_config_load_save.py:137: in test_load_keeps_supported_models_unchanged
    assert c.model_size == valid_model
E   AssertionError: assert '' == 'large-v3-turbo'
E
E     - large-v3-turbo
```

### 9. `tests.config.test_config_load_save.TestConfigLoadSave.test_load_keeps_large_v3_turbo_model`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:144`

```
- large-v3-turbo

AssertionError: assert '' == 'large-v3-turbo'

  - large-v3-turbo
tests/config/test_config_load_save.py:144: in test_load_keeps_large_v3_turbo_model
    assert c.model_size == "large-v3-turbo"
E   AssertionError: assert '' == 'large-v3-turbo'
E
E     - large-v3-turbo
```

### 10. `tests.config.test_config_load_save.TestConfigLoadSave.test_load_ignores_unknown_keys`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:158`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f5>'

  - <f5>
  + <caps_lock>
tests/config/test_config_load_save.py:158: in test_load_ignores_unknown_keys
    assert c.hotkey == "<f5>"
E   AssertionError: assert '<caps_lock>' == '<f5>'
E
E     - <f5>
E     + <caps_lock>
```

### 11. `tests.config.test_config_load_save.TestConfigLoadSave.test_round_trip`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:203`

```
+ <f7>

AssertionError: assert '<f7>' == '<caps_lock>'

  - <caps_lock>
  + <f7>
tests/config/test_config_load_save.py:203: in test_round_trip
    assert c1.hotkey == c2.hotkey
E   AssertionError: assert '<f7>' == '<caps_lock>'
E
E     - <caps_lock>
E     + <f7>
```

### 12. `tests.config.test_config_load_save.TestConfigPathValidation.test_qwen_model_path_valid_dir_preserved`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:272`

```
+  and   '/tmp/pytest-of-runner/pytest-1/popen-gw0/test_qwen_model_path_valid_dir0/qwen_model' = str(PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_qwen_model_path_valid_dir0/qwen_model'))

AssertionError: assert None == '/tmp/pytest-of-runner/pytest-1/popen-gw0/test_qwen_model_path_valid_dir0/qwen_model'
 +  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).qwen_model_path
 +  and   '/tmp/pytest-of-runner/pytest-1/popen-gw0/test_qwen_model_path_valid_dir0/qwen_model' = str(PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_qwen_model_path_valid_dir0/qwen_model'))
tests/config/test_config_load_save.py:272: in test_qwen_model_path_valid_dir_preserved
    assert c.qwen_model_path == str(model_dir)
E   AssertionError: assert None == '/tmp/pytest-of-runner/pytest-1/popen-gw0/test_qwen_model_path_valid_dir0/qwen_model'
E    +  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_mode
… (truncated)
```

### 13. `tests.config.test_config_load_save.TestConfigPathValidation.test_corrections_path_valid_file_preserved`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:318`

```
+  and   '/tmp/pytest-of-runner/pytest-1/popen-gw0/test_corrections_path_valid_fi0/corrections.json' = str(PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_corrections_path_valid_fi0/corrections.json'))

AssertionError: assert None == '/tmp/pytest-of-runner/pytest-1/popen-gw0/test_corrections_path_valid_fi0/corrections.json'
 +  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).corrections_path
 +  and   '/tmp/pytest-of-runner/pytest-1/popen-gw0/test_corrections_path_valid_fi0/corrections.json' = str(PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_corrections_path_valid_fi0/corrections.json'))
tests/config/test_config_load_save.py:318: in test_corrections_path_valid_file_preserved
    assert c.corrections_path == str(corrections_file)
E   AssertionError: assert None == '/tmp/pytest-of-runner/pytest-1/popen-gw0/test_corrections_path_valid_fi0/corrections.json'
E    +  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack
… (truncated)
```

### 14. `tests.config.test_config_load_save.TestConfigParametrized.test_config_field_roundtrip[hotkey-<f5>]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:481`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f5>'

  - <f5>
  + <caps_lock>
tests/config/test_config_load_save.py:481: in test_config_field_roundtrip
    assert getattr(loaded, field) == value
E   AssertionError: assert '<caps_lock>' == '<f5>'
E
E     - <f5>
E     + <caps_lock>
```

### 15. `tests.config.test_config_load_save.TestConfigParametrized.test_config_field_roundtrip[language-fr]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:481`

```
+ en

AssertionError: assert 'en' == 'fr'

  - fr
  + en
tests/config/test_config_load_save.py:481: in test_config_field_roundtrip
    assert getattr(loaded, field) == value
E   AssertionError: assert 'en' == 'fr'
E
E     - fr
E     + en
```

### 16. `tests.config.test_config_load_save.TestConfigParametrized.test_config_field_roundtrip[language-zh]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:481`

```
+ en

AssertionError: assert 'en' == 'zh'

  - zh
  + en
tests/config/test_config_load_save.py:481: in test_config_field_roundtrip
    assert getattr(loaded, field) == value
E   AssertionError: assert 'en' == 'zh'
E
E     - zh
E     + en
```

### 17. `tests.config.test_config_load_save.TestConfigParametrized.test_config_field_roundtrip[model_size-large-v3-turbo]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:481`

```
- large-v3-turbo

AssertionError: assert '' == 'large-v3-turbo'

  - large-v3-turbo
tests/config/test_config_load_save.py:481: in test_config_field_roundtrip
    assert getattr(loaded, field) == value
E   AssertionError: assert '' == 'large-v3-turbo'
E
E     - large-v3-turbo
```

### 18. `tests.config.test_config_load_save.TestConfigParametrized.test_config_field_roundtrip[device-cpu]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:481`

```
+ cuda

AssertionError: assert 'cuda' == 'cpu'

  - cpu
  + cuda
tests/config/test_config_load_save.py:481: in test_config_field_roundtrip
    assert getattr(loaded, field) == value
E   AssertionError: assert 'cuda' == 'cpu'
E
E     - cpu
E     + cuda
```

### 19. `tests.config.test_config_load_save.TestConfigParametrized.test_various_sample_rates[8000]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:489`

```
+  where 16000 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).sample_rate

AssertionError: assert 16000 == 8000
 +  where 16000 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_thres
… (truncated)
```

### 20. `tests.config.test_config_load_save.TestConfigParametrized.test_various_sample_rates[22050]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:489`

```
+  where 16000 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).sample_rate

AssertionError: assert 16000 == 22050
 +  where 16000 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_thre
… (truncated)
```

### 21. `tests.config.test_config_load_save.TestConfigParametrized.test_various_sample_rates[44100]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:489`

```
+  where 16000 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).sample_rate

AssertionError: assert 16000 == 44100
 +  where 16000 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_thre
… (truncated)
```

### 22. `tests.config.test_config_load_save.TestConfigParametrized.test_various_sample_rates[48000]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:489`

```
+  where 16000 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).sample_rate

AssertionError: assert 16000 == 48000
 +  where 16000 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_thre
… (truncated)
```

### 23. `tests.config.test_config_load_save.TestConfigParametrized.test_various_beam_sizes[2]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:497`

```
+  where 1 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).beam_size

AssertionError: assert 1 == 2
 +  where 1 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, no
… (truncated)
```

### 24. `tests.config.test_config_load_save.TestConfigParametrized.test_various_beam_sizes[3]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:497`

```
+  where 1 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).beam_size

AssertionError: assert 1 == 3
 +  where 1 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, no
… (truncated)
```

### 25. `tests.config.test_config_load_save.TestConfigParametrized.test_various_beam_sizes[5]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:497`

```
+  where 1 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).beam_size

AssertionError: assert 1 == 5
 +  where 1 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, no
… (truncated)
```

### 26. `tests.config.test_config_load_save.TestConfigParametrized.test_autostart_roundtrip[False]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:505`

```
+  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).autostart

AssertionError: assert True == False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold
… (truncated)
```

### 27. `tests.config.test_config_load_save.TestConfigParametrized.test_paste_on_stop_roundtrip[False]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:513`

```
+  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).paste_on_stop

AssertionError: assert True == False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_thres
… (truncated)
```

### 28. `tests.config.test_config_load_save.TestConfigParametrized.test_show_notifications_roundtrip[False]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:521`

```
+  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).show_notifications

AssertionError: assert True == False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_
… (truncated)
```

### 29. `tests.config.test_config_load_save.TestConfigParametrized.test_streaming_transcription_roundtrip[False]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:529`

```
+  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).streaming_transcription

AssertionError: assert True == False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_c
… (truncated)
```

### 30. `tests.config.test_config_load_save.TestDeprecatedFieldsScrubbedOnLoad.test_config_with_deprecated_fields_loads_without_error`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:577`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f9>'

  - <f9>
  + <caps_lock>
tests/config/test_config_load_save.py:577: in test_config_with_deprecated_fields_loads_without_error
    assert c.hotkey == "<f9>"
E   AssertionError: assert '<caps_lock>' == '<f9>'
E
E     - <f9>
E     + <caps_lock>
```

### 31. `tests.config.test_config_load_save.TestDeprecatedFieldsScrubbedOnLoad.test_config_with_deprecated_fields_at_schema_v3_loads`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_load_save.py:592`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f9>'

  - <f9>
  + <caps_lock>
tests/config/test_config_load_save.py:592: in test_config_with_deprecated_fields_at_schema_v3_loads
    assert c.hotkey == "<f9>"
E   AssertionError: assert '<caps_lock>' == '<f9>'
E
E     - <f9>
E     + <caps_lock>
```

### 32. `tests.config.test_config_schema_migration.TestConfigSchemaVersion.test_config_migration_from_version_0`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_schema_migration.py:34`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f3>'

  - <f3>
  + <caps_lock>
tests/config/test_config_schema_migration.py:34: in test_config_migration_from_version_0
    assert loaded.hotkey == "<f3>"
E   AssertionError: assert '<caps_lock>' == '<f3>'
E
E     - <f3>
E     + <caps_lock>
```

### 33. `tests.config.test_config_schema_migration.TestV5PushToTalkHotkeyPrune.test_load_prunes_push_to_talk_hotkey_from_v4_config`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_schema_migration.py:212`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f9>'

  - <f9>
  + <caps_lock>
tests/config/test_config_schema_migration.py:212: in test_load_prunes_push_to_talk_hotkey_from_v4_config
    assert loaded.hotkey == "<f9>"
E   AssertionError: assert '<caps_lock>' == '<f9>'
E
E     - <f9>
E     + <caps_lock>
```

### 34. `tests.config.test_config_validation.TestNonNumericFieldValidation.test_bool_field_coerces_zero`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_validation.py:26`

```
+  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).paste_on_stop

AssertionError: assert True is False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_thres
… (truncated)
```

### 35. `tests.config.test_config_validation.TestNonNumericFieldValidation.test_str_field_keeps_valid_string`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_validation.py:47`

```
+ en

AssertionError: assert 'en' == 'fr'

  - fr
  + en
tests/config/test_config_validation.py:47: in test_str_field_keeps_valid_string
    assert c.language == "fr"
E   AssertionError: assert 'en' == 'fr'
E
E     - fr
E     + en
```

### 36. `tests.config.test_config_validation.TestNonNumericFieldValidation.test_startup6_int_field_preserves_user_value`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/config/test_config_validation.py:77`

```
+  where 500 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).volume_duck_smart_poll_interval_ms

AssertionError: assert 500 == 1500
 +  where 500 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter
… (truncated)
```

### 37. `tests.test_allowed_user_models.TestAllowedUserModels.test_load_preserves_valid_model_choice[tiny]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_allowed_user_models.py:59`

```
- tiny

AssertionError: Config.load() reset model_size from 'tiny' to '', valid choices must be preserved.
assert '' == 'tiny'

  - tiny
tests/test_allowed_user_models.py:59: in test_load_preserves_valid_model_choice
    assert c.model_size == model_size, (
E   AssertionError: Config.load() reset model_size from 'tiny' to '', valid choices must be preserved.
E   assert '' == 'tiny'
E
E     - tiny
```

### 38. `tests.test_allowed_user_models.TestAllowedUserModels.test_load_preserves_valid_model_choice[large-v3]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_allowed_user_models.py:59`

```
- large-v3

AssertionError: Config.load() reset model_size from 'large-v3' to '', valid choices must be preserved.
assert '' == 'large-v3'

  - large-v3
tests/test_allowed_user_models.py:59: in test_load_preserves_valid_model_choice
    assert c.model_size == model_size, (
E   AssertionError: Config.load() reset model_size from 'large-v3' to '', valid choices must be preserved.
E   assert '' == 'large-v3'
E
E     - large-v3
```

### 39. `tests.test_allowed_user_models.TestAllowedUserModels.test_load_preserves_valid_model_choice[large-v3-turbo]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_allowed_user_models.py:59`

```
- large-v3-turbo

AssertionError: Config.load() reset model_size from 'large-v3-turbo' to '', valid choices must be preserved.
assert '' == 'large-v3-turbo'

  - large-v3-turbo
tests/test_allowed_user_models.py:59: in test_load_preserves_valid_model_choice
    assert c.model_size == model_size, (
E   AssertionError: Config.load() reset model_size from 'large-v3-turbo' to '', valid choices must be preserved.
E   assert '' == 'large-v3-turbo'
E
E     - large-v3-turbo
```

### 40. `tests.test_allowed_user_models.TestAllowedUserModels.test_load_preserves_valid_model_choice[parakeet]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_allowed_user_models.py:59`

```
- parakeet

AssertionError: Config.load() reset model_size from 'parakeet' to '', valid choices must be preserved.
assert '' == 'parakeet'

  - parakeet
tests/test_allowed_user_models.py:59: in test_load_preserves_valid_model_choice
    assert c.model_size == model_size, (
E   AssertionError: Config.load() reset model_size from 'parakeet' to '', valid choices must be preserved.
E   assert '' == 'parakeet'
E
E     - parakeet
```

### 41. `tests.test_allowed_user_models.TestAllowedUserModels.test_load_preserves_valid_model_choice[qwen]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_allowed_user_models.py:59`

```
- qwen

AssertionError: Config.load() reset model_size from 'qwen' to '', valid choices must be preserved.
assert '' == 'qwen'

  - qwen
tests/test_allowed_user_models.py:59: in test_load_preserves_valid_model_choice
    assert c.model_size == model_size, (
E   AssertionError: Config.load() reset model_size from 'qwen' to '', valid choices must be preserved.
E   assert '' == 'qwen'
E
E     - qwen
```

### 42. `tests.test_config_backup_secure.TestSaveUnlockedBackupSecure.test_save_does_not_poison_bak_via_symlinked_source`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_backup_secure.py:173`

```
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/pytest-of-runner/pytest-1/popen-gw1/test_save_does_not_poison_bak_0/config.json'

FileNotFoundError: [Errno 2] No such file or directory: '/tmp/pytest-of-runner/pytest-1/popen-gw1/test_save_does_not_poison_bak_0/config.json'
tests/test_config_backup_secure.py:173: in test_save_does_not_poison_bak_via_symlinked_source
    config_file.unlink()
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/pathlib.py:1206: in unlink
    self._accessor.unlink(self)
E   FileNotFoundError: [Errno 2] No such file or directory: '/tmp/pytest-of-runner/pytest-1/popen-gw1/test_save_does_not_poison_bak_0/config.json'
```

### 43. `tests.test_config_backup_secure.TestSaveUnlockedBackupSecure.test_save_backup_block_creates_bak_with_correct_content`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_backup_secure.py:237`

```
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/pytest-of-runner/pytest-1/popen-gw0/test_save_backup_block_creates0/config.json'

FileNotFoundError: [Errno 2] No such file or directory: '/tmp/pytest-of-runner/pytest-1/popen-gw0/test_save_backup_block_creates0/config.json'
tests/test_config_backup_secure.py:237: in test_save_backup_block_creates_bak_with_correct_content
    pre_save_on_disk = config_file.read_text()
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/pathlib.py:1134: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/pathlib.py:1119: in open
    return self._accessor.open(self, mode, buffering, encoding, errors,
E   FileNotFoundError: [Errno 2] No such file or directory: '/tmp/pytest-of-runner/pytest-1/popen-gw0/test_save_backup_block_creates0/config.json'
```

### 44. `tests.test_config_backup_secure.TestSaveUnlockedBackupSecure.test_save_backup_uses_secure_read`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_backup_secure.py:219`

```
+  where False = any(<generator object TestSaveUnlockedBackupSecure.test_save_backup_uses_secure_read.<locals>.<genexpr> at 0x7f8ae1d494d0>)

AssertionError: FR-24: Config.save() did not call _secure_read_text on config.json during the backup block. Calls observed: []. The backup READ must use _secure_read_text (not Path.read_bytes) to prevent symlink-following.
assert False
 +  where False = any(<generator object TestSaveUnlockedBackupSecure.test_save_backup_uses_secure_read.<locals>.<genexpr> at 0x7f8ae1d494d0>)
tests/test_config_backup_secure.py:219: in test_save_backup_uses_secure_read
    assert any(config_file_str in c for c in calls), (
E   AssertionError: FR-24: Config.save() did not call _secure_read_text on config.json during the backup block. Calls observed: []. The backup READ must use _secure_read_text (not Path.read_bytes) to prevent symlink-following.
E   assert False
E    +  where False = any(<generator object TestSaveUnlockedBackupSecure.test_save_backup_uses_secure_read.<locals>.<genexpr> at 0x7f8ae1d494d0>)
```

### 45. `tests.test_config_backup_secure.TestSaveUnlockedBackupSecure.test_save_bak_has_0600_perms`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_backup_secure.py:272`

```
+    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_save_bak_has_0600_perms0/config.json.bak').exists

AssertionError: assert False
 +  where False = exists()
 +    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_save_bak_has_0600_perms0/config.json.bak').exists
tests/test_config_backup_secure.py:272: in test_save_bak_has_0600_perms
    assert bak_path.exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_save_bak_has_0600_perms0/config.json.bak').exists
```

### 46. `tests.test_config_corruption_backup.TestCorruptConfigBackup.test_valid_config_not_moved`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_corruption_backup.py:127`

```
+    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_valid_config_not_moved0/config.json').exists

AssertionError: Valid config.json was moved aside, only corrupt configs should be moved.
assert False
 +  where False = exists()
 +    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_valid_config_not_moved0/config.json').exists
tests/test_config_corruption_backup.py:127: in test_valid_config_not_moved
    assert config_file.exists(), "Valid config.json was moved aside, only corrupt configs should be moved."
E   AssertionError: Valid config.json was moved aside, only corrupt configs should be moved.
E   assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_valid_config_not_moved0/config.json').exists
```

### 47. `tests.test_config_corruption_backup.TestSaveBackupBeforeOverwrite.test_save_bak_round_trip_recovery`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_corruption_backup.py:413`

```
+    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_save_bak_round_trip_recov0/config.json.bak').exists

AssertionError: assert False
 +  where False = exists()
 +    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_save_bak_round_trip_recov0/config.json.bak').exists
tests/test_config_corruption_backup.py:413: in test_save_bak_round_trip_recovery
    assert bak.exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_save_bak_round_trip_recov0/config.json.bak').exists
```

### 48. `tests.test_config_corruption_backup.TestSaveBackupBeforeOverwrite.test_save_bak_preserves_byte_for_byte_content`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_corruption_backup.py:379`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f3>'

  - <f3>
  + <caps_lock>
tests/test_config_corruption_backup.py:379: in test_save_bak_preserves_byte_for_byte_content
    assert cfg.hotkey == "<f3>"
E   AssertionError: assert '<caps_lock>' == '<f3>'
E
E     - <f3>
E     + <caps_lock>
```

### 49. `tests.test_config_corruption_backup.TestDeprecatedKeysSilentlyScrubbed.test_stale_v3_config_with_deprecated_keys_handled_gracefully`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_corruption_backup.py:486`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f9>'

  - <f9>
  + <caps_lock>
tests/test_config_corruption_backup.py:486: in test_stale_v3_config_with_deprecated_keys_handled_gracefully
    assert cfg.hotkey == "<f9>"
E   AssertionError: assert '<caps_lock>' == '<f9>'
E
E     - <f9>
E     + <caps_lock>
```

### 50. `tests.test_config_corruption_backup.TestDeprecatedKeysSilentlyScrubbed.test_stale_v2_config_with_deprecated_keys_loads_cleanly`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_corruption_backup.py:461`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f9>'

  - <f9>
  + <caps_lock>
tests/test_config_corruption_backup.py:461: in test_stale_v2_config_with_deprecated_keys_loads_cleanly
    assert cfg.hotkey == "<f9>"
E   AssertionError: assert '<caps_lock>' == '<f9>'
E
E     - <f9>
E     + <caps_lock>
```

### 51. `tests.test_config_custom_theme_null.TestConfigRoundTripWithNone.test_save_load_round_trip_with_none`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_custom_theme_null.py:140`

```
+  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).custom_theme

AssertionError: assert None == {'light': {'--background': '#ffffff', '--foreground': '#000000', '--primary': '#0000ff', '--bg-subtle': '#f0f0f0', ...}, 'dark': {'--background': '#000000', '--foreground': '#ffffff', '--primary': '#0000ff', '--bg-subtle': '#1a1a1a', ...}}
 +  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_
… (truncated)
```

### 52. `tests.test_config_editor_lock.TestReloadAfterEditor.test_config_reloaded_after_editor_closes[windows]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_editor_lock.py:186`

```
+    where Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95) = <voice_typer.server.app.LausuApp object at 0x7f8af0c893c0>.config

AssertionError: B-4: windows branch: after the editor closes, the in-memory config must reflect the user's saved edits on disk.
assert True is False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_
… (truncated)
```

### 53. `tests.test_config_editor_lock.TestReloadAfterEditor.test_config_reloaded_after_editor_closes[linux]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_editor_lock.py:186`

```
+    where Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95) = <voice_typer.server.app.LausuApp object at 0x7f9e08f37670>.config

AssertionError: B-4: linux branch: after the editor closes, the in-memory config must reflect the user's saved edits on disk.
assert True is False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_fi
… (truncated)
```

### 54. `tests.test_config_editor_lock.TestReloadAfterEditor.test_config_reloaded_after_editor_closes[macos]`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_editor_lock.py:186`

```
+    where Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95) = <voice_typer.server.app.LausuApp object at 0x7f8af8a2e1d0>.config

AssertionError: B-4: macos branch: after the editor closes, the in-memory config must reflect the user's saved edits on disk.
assert True is False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_fi
… (truncated)
```

### 55. `tests.test_config_group_fixes.TestMigratorFailureDoesNotBumpSchemaVersion.test_migrator_failure_leaves_schema_version_at_loaded_version`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_group_fixes.py:52`

```
+  where 5 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).schema_version

AssertionError: DE-3 regression: schema_version was bumped to 5 even though the v2 migrator raised, the config is now bricked in a half-migrated state and the next launch will skip the failed migrator.
assert 5 == 0
 +  where 5 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=
… (truncated)
```

### 56. `tests.test_config_group_fixes.TestLoadAcquiresConfigLock.test_load_calls_acquire_config_lock`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_group_fixes.py:161`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f5>'

  - <f5>
  + <caps_lock>
tests/test_config_group_fixes.py:161: in test_load_calls_acquire_config_lock
    assert loaded.hotkey == "<f5>"
E   AssertionError: assert '<caps_lock>' == '<f5>'
E
E     - <f5>
E     + <caps_lock>
```

### 57. `tests.test_config_group_fixes.TestLoadAcquiresConfigLock.test_load_still_works_when_lock_is_noop`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_group_fixes.py:180`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f9>'

  - <f9>
  + <caps_lock>
tests/test_config_group_fixes.py:180: in test_load_still_works_when_lock_is_noop
    assert loaded.hotkey == "<f9>"
E   AssertionError: assert '<caps_lock>' == '<f9>'
E
E     - <f9>
E     + <caps_lock>
```

### 58. `tests.test_config_group_fixes.TestCustomThemeValidatedOnLoad.test_valid_custom_theme_is_preserved`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_group_fixes.py:350`

```
+  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).custom_theme

AssertionError: DE-29 over-correction: a VALID custom_theme must be preserved on load, not reset.  Got: None
assert None == {'light': {'--background': '#ffffff', '--foreground': '#000000', '--primary': '#0066cc', '--bg-subtle': '#f0f0f0', ...}, 'dark': {'--background': '#000000', '--foreground': '#ffffff', '--primary': '#3399ff', '--bg-subtle': '#1a1a1a', ...}}
 +  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cl
… (truncated)
```

### 59. `tests.test_config_group_fixes.TestCustomThemeValidatedOnLoad.test_malformed_custom_theme_records_load_warning`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_group_fixes.py:370`

```
+  where False = any(<generator object TestCustomThemeValidatedOnLoad.test_malformed_custom_theme_records_load_warning.<locals>.<genexpr> at 0x7f9e2e105d20>)

AssertionError: DE-29: custom_theme validation failure not surfaced in last_load_warnings: []
assert False
 +  where False = any(<generator object TestCustomThemeValidatedOnLoad.test_malformed_custom_theme_records_load_warning.<locals>.<genexpr> at 0x7f9e2e105d20>)
tests/test_config_group_fixes.py:370: in test_malformed_custom_theme_records_load_warning
    assert any("custom_theme" in w and "validation" in w.lower() for w in warnings), (
E   AssertionError: DE-29: custom_theme validation failure not surfaced in last_load_warnings: []
E   assert False
E    +  where False = any(<generator object TestCustomThemeValidatedOnLoad.test_malformed_custom_theme_records_load_warning.<locals>.<genexpr> at 0x7f9e2e105d20>)
```

### 60. `tests.test_config_load_corruption.TestConfigLoadCaughtFailureModes.test_field_with_uncoercible_string_returns_defaults_and_logs_warning`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_load_corruption.py:97`

```
+  where 2 = len([<LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/coercion.py, 108, "[CONFIG] invalid streaming_chunk_seconds value %r; resetting to default 12.0">, <LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/loader.py, 442, "[CONFIG] %s loading config %s: %s. Using defaults.">])

assert 2 == 1
 +  where 2 = len([<LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/coercion.py, 108, "[CONFIG] invalid streaming_chunk_seconds value %r; resetting to default 12.0">, <LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/loader.py, 442, "[CONFIG] %s loading config %s: %s. Using defaults.">])
tests/test_config_load_corruption.py:97: in test_field_with_uncoercible_string_returns_defaults_and_logs_warning
    assert len(recs) == 1
E   assert 2 == 1
E    +  where 2 = len([<LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/coercion.py, 108, "[CONFIG] invalid streaming_chunk_seconds value %r; resetting to default 12.0">, <LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/loader.py, 442, "[CONFIG] %s loading config %s: %s. Using defaults.">])
```

### 61. `tests.test_config_load_corruption.TestConfigLoadCaughtFailureModes.test_field_with_null_for_float_returns_defaults_and_logs_warning`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_load_corruption.py:111`

```
+  where 2 = len([<LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/coercion.py, 108, "[CONFIG] invalid streaming_chunk_seconds value %r; resetting to default 12.0">, <LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/loader.py, 442, "[CONFIG] %s loading config %s: %s. Using defaults.">])

assert 2 == 1
 +  where 2 = len([<LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/coercion.py, 108, "[CONFIG] invalid streaming_chunk_seconds value %r; resetting to default 12.0">, <LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/loader.py, 442, "[CONFIG] %s loading config %s: %s. Using defaults.">])
tests/test_config_load_corruption.py:111: in test_field_with_null_for_float_returns_defaults_and_logs_warning
    assert len(recs) == 1
E   assert 2 == 1
E    +  where 2 = len([<LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/coercion.py, 108, "[CONFIG] invalid streaming_chunk_seconds value %r; resetting to default 12.0">, <LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/loader.py, 442, "[CONFIG] %s loading config %s: %s. Using defaults.">])
```

### 62. `tests.test_config_load_corruption.TestConfigLoadCaughtFailureModes.test_field_with_uncoercible_int_for_float_returns_defaults_and_logs_warning`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_load_corruption.py:126`

```
+  where 2 = len([<LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/coercion.py, 108, "[CONFIG] invalid streaming_chunk_seconds value %r; resetting to default 12.0">, <LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/loader.py, 442, "[CONFIG] %s loading config %s: %s. Using defaults.">])

assert 2 == 1
 +  where 2 = len([<LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/coercion.py, 108, "[CONFIG] invalid streaming_chunk_seconds value %r; resetting to default 12.0">, <LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/loader.py, 442, "[CONFIG] %s loading config %s: %s. Using defaults.">])
tests/test_config_load_corruption.py:126: in test_field_with_uncoercible_int_for_float_returns_defaults_and_logs_warning
    assert len(recs) == 1
E   assert 2 == 1
E    +  where 2 = len([<LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/coercion.py, 108, "[CONFIG] invalid streaming_chunk_seconds value %r; resetting to default 12.0">, <LogRecord: voice_typer.server.config, 30, /home/runner/work/Lausu/Lausu/voice_typer/server/config/loader.py, 442, "[CONFIG] %s loading config %s: %s. Using defaults.">])
```

### 63. `tests.test_config_load_corruption.TestConfigLoadLegitimateCasesPreserved.test_valid_config_loads_normally`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_load_corruption.py:303`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f9>'

  - <f9>
  + <caps_lock>
tests/test_config_load_corruption.py:303: in test_valid_config_loads_normally
    assert cfg.hotkey == "<f9>"
E   AssertionError: assert '<caps_lock>' == '<f9>'
E
E     - <f9>
E     + <caps_lock>
```

### 64. `tests.test_config_load_corruption.TestConfigLoadLegitimateCasesPreserved.test_unknown_keys_ignored`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_load_corruption.py:314`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f5>'

  - <f5>
  + <caps_lock>
tests/test_config_load_corruption.py:314: in test_unknown_keys_ignored
    assert cfg.hotkey == "<f5>"
E   AssertionError: assert '<caps_lock>' == '<f5>'
E
E     - <f5>
E     + <caps_lock>
```

### 65. `tests.test_config_load_corruption.TestConfigLoadLegitimateCasesPreserved.test_round_trip_preserved`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_load_corruption.py:322`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f7>'

  - <f7>
  + <caps_lock>
tests/test_config_load_corruption.py:322: in test_round_trip_preserved
    assert c2.hotkey == "<f7>"
E   AssertionError: assert '<caps_lock>' == '<f7>'
E
E     - <f7>
E     + <caps_lock>
```

### 66. `tests.test_config_load_corruption.TestConfigLoadLegitimateCasesPreserved.test_schema_migration_still_runs`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_load_corruption.py:333`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f3>'

  - <f3>
  + <caps_lock>
tests/test_config_load_corruption.py:333: in test_schema_migration_still_runs
    assert cfg.hotkey == "<f3>"
E   AssertionError: assert '<caps_lock>' == '<f3>'
E
E     - <f3>
E     + <caps_lock>
```

### 67. `tests.test_config_load_secrets_migration.TestSecretsMigrationDeferralPreserved.test_deferral_preserved_when_keyring_unavailable`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_load_secrets_migration.py:96`

```
- sk-keep-me-plaintext

AssertionError: assert '' == 'sk-keep-me-plaintext'

  - sk-keep-me-plaintext
tests/test_config_load_secrets_migration.py:96: in test_deferral_preserved_when_keyring_unavailable
    assert cfg.openai_api_key == "sk-keep-me-plaintext"
E   AssertionError: assert '' == 'sk-keep-me-plaintext'
E
E     - sk-keep-me-plaintext
```

### 68. `tests.test_config_load_secrets_migration.TestSecretsMigrationDeferralPreserved.test_migration_reruns_after_keyring_becomes_available`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_load_secrets_migration.py:156`

```
- sk-migrate-me-after-keyring-installed

AssertionError: assert '' == 'sk-migrate-m...ing-installed'

  - sk-migrate-me-after-keyring-installed
tests/test_config_load_secrets_migration.py:156: in test_migration_reruns_after_keyring_becomes_available
    assert cfg1.openai_api_key == "sk-migrate-me-after-keyring-installed"
E   AssertionError: assert '' == 'sk-migrate-m...ing-installed'
E
E     - sk-migrate-me-after-keyring-installed
```

### 69. `tests.test_config_load_secrets_migration.TestNonDeferredMigrationStillSetsFlag.test_flag_true_when_migration_succeeds`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_load_secrets_migration.py:201`

```
+  where False = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).secrets_migrated

AssertionError: assert False is True
 +  where False = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_
… (truncated)
```

### 70. `tests.test_config_load_secrets_migration.TestNonDeferredMigrationStillSetsFlag.test_flag_true_when_no_secrets_to_migrate`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_load_secrets_migration.py:214`

```
+  where False = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).secrets_migrated

AssertionError: assert False is True
 +  where False = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_
… (truncated)
```

### 71. `tests.test_config_migration_schema_version.TestMigratorFailureDoesNotBumpSchemaVersion.test_failure_at_v2_leaves_schema_version_at_loaded_version`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_migration_schema_version.py:52`

```
+  where 5 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).schema_version

AssertionError: regression: schema_version was bumped to 5 even though the v2 migrator raised. The config is now bricked in a half-migrated state -- the next launch will see version==current and skip the failed migrator permanently.
assert 5 == 0
 +  where 5 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=T
… (truncated)
```

### 72. `tests.test_config_migration_schema_version.TestMigratorFailureDoesNotBumpSchemaVersion.test_failure_at_v3_after_v2_succeeds_leaves_schema_version_at_v2`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_migration_schema_version.py:72`

```
+  where 5 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).schema_version

AssertionError: regression: when v2 succeeded but v3 raised, schema_version was set to 5 instead of 2 (the last successful version).  This means the next launch will either skip v3 (if bumped to 3) or needlessly re-run v2 (if set to 0) -- both are wrong.
assert 5 == 2
 +  where 5 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.
… (truncated)
```

### 73. `tests.test_config_migration_schema_version.TestFailureIsLoggedAtError.test_load_does_not_raise_on_migrator_failure`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_migration_schema_version.py:271`

```
+  where 5 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).schema_version

AssertionError: assert 5 == 0
 +  where 5 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.
… (truncated)
```

### 74. `tests.test_config_package_split.TestEndToEnd.test_construct_save_reload_roundtrip`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_package_split.py:316`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f9>'

  - <f9>
  + <caps_lock>
tests/test_config_package_split.py:316: in test_construct_save_reload_roundtrip
    assert reloaded.hotkey == "<f9>"
E   AssertionError: assert '<caps_lock>' == '<f9>'
E
E     - <f9>
E     + <caps_lock>
```

### 75. `tests.test_config_pep604_union.TestWrongTypedPep604FieldsResetOnLoad.test_microphone_int_resets_to_none`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_pep604_union.py:73`

```
+  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_microphone_int_resets_to_none.<locals>.<genexpr> at 0x7f9e2e011af0>)

AssertionError: FR-51: microphone=123 reset did not surface in last_load_warnings: []
assert False
 +  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_microphone_int_resets_to_none.<locals>.<genexpr> at 0x7f9e2e011af0>)
tests/test_config_pep604_union.py:73: in test_microphone_int_resets_to_none
    assert any("microphone" in w for w in warnings), (
E   AssertionError: FR-51: microphone=123 reset did not surface in last_load_warnings: []
E   assert False
E    +  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_microphone_int_resets_to_none.<locals>.<genexpr> at 0x7f9e2e011af0>)
```

### 76. `tests.test_config_pep604_union.TestWrongTypedPep604FieldsResetOnLoad.test_qwen_model_path_int_resets_to_none`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_pep604_union.py:83`

```
+  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_qwen_model_path_int_resets_to_none.<locals>.<genexpr> at 0x7f9e2e012f80>)

AssertionError: FR-51: qwen_model_path=42 reset did not surface in last_load_warnings: []
assert False
 +  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_qwen_model_path_int_resets_to_none.<locals>.<genexpr> at 0x7f9e2e012f80>)
tests/test_config_pep604_union.py:83: in test_qwen_model_path_int_resets_to_none
    assert any("qwen_model_path" in w for w in warnings), (
E   AssertionError: FR-51: qwen_model_path=42 reset did not surface in last_load_warnings: []
E   assert False
E    +  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_qwen_model_path_int_resets_to_none.<locals>.<genexpr> at 0x7f9e2e012f80>)
```

### 77. `tests.test_config_pep604_union.TestWrongTypedPep604FieldsResetOnLoad.test_parakeet_model_path_int_resets_to_none`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_pep604_union.py:95`

```
+  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_parakeet_model_path_int_resets_to_none.<locals>.<genexpr> at 0x7f9e2e013d80>)

AssertionError: FR-51: parakeet_model_path=999 reset did not surface in last_load_warnings: []
assert False
 +  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_parakeet_model_path_int_resets_to_none.<locals>.<genexpr> at 0x7f9e2e013d80>)
tests/test_config_pep604_union.py:95: in test_parakeet_model_path_int_resets_to_none
    assert any("parakeet_model_path" in w for w in warnings), (
E   AssertionError: FR-51: parakeet_model_path=999 reset did not surface in last_load_warnings: []
E   assert False
E    +  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_parakeet_model_path_int_resets_to_none.<locals>.<genexpr> at 0x7f9e2e013d80>)
```

### 78. `tests.test_config_pep604_union.TestWrongTypedPep604FieldsResetOnLoad.test_corrections_path_bool_resets_to_none`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_pep604_union.py:107`

```
+  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_corrections_path_bool_resets_to_none.<locals>.<genexpr> at 0x7f9e2e012f80>)

AssertionError: FR-51: corrections_path=False reset did not surface in last_load_warnings: []
assert False
 +  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_corrections_path_bool_resets_to_none.<locals>.<genexpr> at 0x7f9e2e012f80>)
tests/test_config_pep604_union.py:107: in test_corrections_path_bool_resets_to_none
    assert any("corrections_path" in w for w in warnings), (
E   AssertionError: FR-51: corrections_path=False reset did not surface in last_load_warnings: []
E   assert False
E    +  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_corrections_path_bool_resets_to_none.<locals>.<genexpr> at 0x7f9e2e012f80>)
```

### 79. `tests.test_config_pep604_union.TestWrongTypedPep604FieldsResetOnLoad.test_custom_theme_non_dict_resets_to_none`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_pep604_union.py:119`

```
+  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_custom_theme_non_dict_resets_to_none.<locals>.<genexpr> at 0x7f9e2e012b20>)

AssertionError: FR-51: custom_theme='not a dict' reset did not surface in last_load_warnings: []
assert False
 +  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_custom_theme_non_dict_resets_to_none.<locals>.<genexpr> at 0x7f9e2e012b20>)
tests/test_config_pep604_union.py:119: in test_custom_theme_non_dict_resets_to_none
    assert any("custom_theme" in w for w in warnings), (
E   AssertionError: FR-51: custom_theme='not a dict' reset did not surface in last_load_warnings: []
E   assert False
E    +  where False = any(<generator object TestWrongTypedPep604FieldsResetOnLoad.test_custom_theme_non_dict_resets_to_none.<locals>.<genexpr> at 0x7f9e2e012b20>)
```

### 80. `tests.test_config_pep604_union.TestValidPep604FieldsPreservedOnLoad.test_valid_microphone_string_preserved`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_pep604_union.py:130`

```
+  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).microphone

AssertionError: assert None == 'My USB Mic'
 +  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_t
… (truncated)
```

### 81. `tests.test_config_pep604_union.TestValidPep604FieldsPreservedOnLoad.test_valid_custom_theme_dict_preserved`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_pep604_union.py:166`

```
+  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).custom_theme

AssertionError: FR-51 over-correction: a VALID custom_theme dict was reset on load. Got: None
assert None == {'light': {'--background': '#ffffff', '--foreground': '#000000', '--primary': '#0066cc', '--bg-subtle': '#f0f0f0', ...}, 'dark': {'--background': '#000000', '--foreground': '#ffffff', '--primary': '#3399ff', '--bg-subtle': '#1a1a1a', ...}}
 +  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_
… (truncated)
```

### 82. `tests.test_config_sanitizer.TestHistoryEnabledField.test_history_enabled_round_trips_through_save_load`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_sanitizer.py:280`

```
+  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).history_enabled

AssertionError: FR-28: history_enabled=False did not round-trip through save/load. The dictation_pipeline gate (P4-A4) relies on this field persisting correctly.
assert True is False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnois
… (truncated)
```

### 83. `tests.test_config_editor_lock.TestReloadPicksUpDiskChanges.test_config_reloaded_after_macos_editor_closes`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_editor_lock.py:500`

```
+    where Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95) = <voice_typer.server.app.LausuApp object at 0x7f8af05965c0>.config

AssertionError: B-4: after the editor closes, the in-memory config must reflect the user's saved edits on disk.
assert True is False
 +  where True = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=T
… (truncated)
```

### 84. `tests.test_config_validate_on_load.TestValidateConfigCalledOnLoad.test_validate_config_is_called_on_load`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validate_on_load.py:53`

```
assert 0 >= 1

AssertionError: Config.load() must call validate_config() on the constructed instance. The call did not happen.
assert 0 >= 1
tests/test_config_validate_on_load.py:53: in test_validate_config_is_called_on_load
    assert call_count >= 1, (
E   AssertionError: Config.load() must call validate_config() on the constructed instance. The call did not happen.
E   assert 0 >= 1
```

### 85. `tests.test_config_validate_on_load.TestValidateConfigCalledOnLoad.test_validate_config_errors_appended_to_last_load_warnings`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validate_on_load.py:73`

```
TypeError: 'NoneType' object is not iterable

TypeError: 'NoneType' object is not iterable
tests/test_config_validate_on_load.py:73: in test_validate_config_errors_appended_to_last_load_warnings
    validate_warnings = [w for w in instance.last_load_warnings if "validate_config:" in w]
E   TypeError: 'NoneType' object is not iterable
```

### 86. `tests.test_config_validate_on_load.TestValidateConfigCalledOnLoad.test_validate_config_no_warnings_for_valid_config`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validate_on_load.py:94`

```
TypeError: 'NoneType' object is not iterable

TypeError: 'NoneType' object is not iterable
tests/test_config_validate_on_load.py:94: in test_validate_config_no_warnings_for_valid_config
    validate_warnings = [w for w in instance.last_load_warnings if "validate_config:" in w]
E   TypeError: 'NoneType' object is not iterable
```

### 87. `tests.test_config_validate_on_load.TestNonFiniteFloatFieldsResetOnLoad.test_nan_float_is_reset_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validate_on_load.py:162`

```
assert []

AssertionError: load() should append a 'non-finite float value' warning for 'streaming_silence_threshold'. last_load_warnings=None
assert []
tests/test_config_validate_on_load.py:162: in test_nan_float_is_reset_to_default
    assert reset_warnings, (
E   AssertionError: load() should append a 'non-finite float value' warning for 'streaming_silence_threshold'. last_load_warnings=None
E   assert []
```

### 88. `tests.test_config_validate_on_load.TestNonFiniteFloatFieldsResetOnLoad.test_positive_infinity_float_is_reset_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validate_on_load.py:191`

```
assert []

AssertionError: load() should append a 'non-finite float value' warning for +Inf on 'streaming_silence_threshold'. last_load_warnings=None
assert []
tests/test_config_validate_on_load.py:191: in test_positive_infinity_float_is_reset_to_default
    assert reset_warnings, (
E   AssertionError: load() should append a 'non-finite float value' warning for +Inf on 'streaming_silence_threshold'. last_load_warnings=None
E   assert []
```

### 89. `tests.test_config_validate_on_load.TestNonFiniteFloatFieldsResetOnLoad.test_negative_infinity_float_is_reset_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validate_on_load.py:212`

```
assert []

AssertionError: load() should append a 'non-finite float value' warning for -Inf on 'streaming_silence_threshold'. last_load_warnings=None
assert []
tests/test_config_validate_on_load.py:212: in test_negative_infinity_float_is_reset_to_default
    assert reset_warnings, (
E   AssertionError: load() should append a 'non-finite float value' warning for -Inf on 'streaming_silence_threshold'. last_load_warnings=None
E   assert []
```

### 90. `tests.test_config_validate_on_load.TestNonFiniteFloatFieldsResetOnLoad.test_numeric_string_infinity_is_reset_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validate_on_load.py:237`

```
assert []

AssertionError: load() should append a 'non-finite float value' warning when a numeric string parses to a non-finite float. last_load_warnings=None
assert []
tests/test_config_validate_on_load.py:237: in test_numeric_string_infinity_is_reset_to_default
    assert reset_warnings, (
E   AssertionError: load() should append a 'non-finite float value' warning when a numeric string parses to a non-finite float. last_load_warnings=None
E   assert []
```

### 91. `tests.test_config_validate_on_load.TestNonFiniteFloatFieldsResetOnLoad.test_finite_float_still_loads_without_reset_warning`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validate_on_load.py:252`

```
+  where 0.003 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).streaming_silence_threshold

AssertionError: a finite in-range float must load unchanged; got 0.003
assert 0.003 == 0.05
 +  where 0.003 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', n
… (truncated)
```

### 92. `tests.test_config_validate_on_load.TestNonFiniteFloatFieldsResetOnLoad.test_int_value_for_float_field_still_loads_without_reset_warning`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validate_on_load.py:270`

```
+  where 0.003 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).streaming_silence_threshold

AssertionError: int 0 must coerce to 0.0 for the float field; got 0.003
assert 0.003 == 0.0
 +  where 0.003 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', n
… (truncated)
```

### 93. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_cmd_q_warns_on_non_darwin_platform`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:144`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:144: in test_cmd_q_warns_on_non_darwin_platform
    warning = _cross_platform_hotkey_warning("<cmd>+<q>", "hotkey")
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 94. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_win_l_warns_on_non_win32_platform`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:153`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:153: in test_win_l_warns_on_non_win32_platform
    warning = _cross_platform_hotkey_warning("<win>+<l>", "repaste_hotkey")
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 95. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_cmd_b_warns_on_non_darwin_platform`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:160`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:160: in test_cmd_b_warns_on_non_darwin_platform
    warning = _cross_platform_hotkey_warning("<cmd>+<b>", "hotkey")
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 96. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_win_a_warns_on_non_win32_platform`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:169`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:169: in test_win_a_warns_on_non_win32_platform
    warning = _cross_platform_hotkey_warning("<win>+<a>", "hotkey")
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 97. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_cmd_z_warns_on_non_darwin_platform`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:178`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:178: in test_cmd_z_warns_on_non_darwin_platform
    warning = _cross_platform_hotkey_warning("<cmd>+<z>", "repaste_hotkey")
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 98. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_win_s_warns_on_non_win32_platform`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:188`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:188: in test_win_s_warns_on_non_win32_platform
    warning = _cross_platform_hotkey_warning("<win>+<s>", "repaste_hotkey")
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 99. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_alt_shift_aliases_warn_on_non_win32_platform`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:197`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:197: in test_alt_shift_aliases_warn_on_non_win32_platform
    warning = _cross_platform_hotkey_warning("<alt_l>+<shift_l>", "hotkey")
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 100. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_blanket_blocked_combos_via_cross_platform_warnings`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:211`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:211: in test_blanket_blocked_combos_via_cross_platform_warnings
    warnings = cross_platform_hotkey_warnings(cfg)
voice_typer/server/config_validators/cross_field.py:140: in cross_platform_hotkey_warnings
    warning = _cross_platform_hotkey_warning(value, field_name)
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 101. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_no_warning_for_unreserved_hotkey`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:219`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:219: in test_no_warning_for_unreserved_hotkey
    warning = _cross_platform_hotkey_warning("<f5>", "hotkey")
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 102. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_current_platform_not_consulted`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:235`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:235: in test_current_platform_not_consulted
    warning = _cross_platform_hotkey_warning("<alt>+<tab>", "hotkey")
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 103. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_warnings_for_multiple_fields_on_cfg`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:244`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:244: in test_warnings_for_multiple_fields_on_cfg
    warnings = cross_platform_hotkey_warnings(cfg)
voice_typer/server/config_validators/cross_field.py:140: in cross_platform_hotkey_warnings
    warning = _cross_platform_hotkey_warning(value, field_name)
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 104. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_no_warnings_for_clean_cfg`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:255`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:255: in test_no_warnings_for_clean_cfg
    warnings = cross_platform_hotkey_warnings(cfg)
voice_typer/server/config_validators/cross_field.py:140: in cross_platform_hotkey_warnings
    warning = _cross_platform_hotkey_warning(value, field_name)
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 105. `tests.test_config_validators_cross_field.TestCrossPlatformWarnings.test_skips_missing_attributes`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_validators_cross_field.py:273`

```
TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'

TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
tests/test_config_validators_cross_field.py:273: in test_skips_missing_attributes
    warnings = cross_platform_hotkey_warnings(cfg)
voice_typer/server/config_validators/cross_field.py:140: in cross_platform_hotkey_warnings
    warning = _cross_platform_hotkey_warning(value, field_name)
voice_typer/server/config_validators/cross_field.py:119: in _cross_platform_hotkey_warning
    err = _check_os_shell_combos(parts, platform)
E   TypeError: _check_os_shell_combos() missing 1 required positional argument: 'normalized_tokens'
```

### 106. `tests.test_config_warnings_surface.TestLoadResetsInvalidEnumFields.test_invalid_asr_backend_reset_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:132`

```
assert []

AssertionError: AP-22: a reset warning for asr_backend must be appended to last_load_warnings. Got: None
assert []
tests/test_config_warnings_surface.py:132: in test_invalid_asr_backend_reset_to_default
    assert reset_warnings, (
E   AssertionError: AP-22: a reset warning for asr_backend must be appended to last_load_warnings. Got: None
E   assert []
```

### 107. `tests.test_config_warnings_surface.TestLoadResetsInvalidEnumFields.test_invalid_theme_mode_reset_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:149`

```
assert []

AssertionError: AP-22: a reset warning for theme_mode must be appended to last_load_warnings. Got: None
assert []
tests/test_config_warnings_surface.py:149: in test_invalid_theme_mode_reset_to_default
    assert reset_warnings, (
E   AssertionError: AP-22: a reset warning for theme_mode must be appended to last_load_warnings. Got: None
E   assert []
```

### 108. `tests.test_config_warnings_surface.TestLoadResetsInvalidEnumFields.test_invalid_recording_mode_reset_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:166`

```
assert []

AssertionError: AP-22: a reset warning for recording_mode must be appended to last_load_warnings. Got: None
assert []
tests/test_config_warnings_surface.py:166: in test_invalid_recording_mode_reset_to_default
    assert reset_warnings, (
E   AssertionError: AP-22: a reset warning for recording_mode must be appended to last_load_warnings. Got: None
E   assert []
```

### 109. `tests.test_config_warnings_surface.TestLoadResetsInvalidEnumFields.test_invalid_bubble_position_reset_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:183`

```
assert []

AssertionError: AP-22: a reset warning for bubble_position must be appended to last_load_warnings. Got: None
assert []
tests/test_config_warnings_surface.py:183: in test_invalid_bubble_position_reset_to_default
    assert reset_warnings, (
E   AssertionError: AP-22: a reset warning for bubble_position must be appended to last_load_warnings. Got: None
E   assert []
```

### 110. `tests.test_config_warnings_surface.TestLoadResetsInvalidEnumFields.test_invalid_tray_left_click_action_reset_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:205`

```
assert []

AssertionError: AP-22: a reset warning for tray_left_click_action must be appended to last_load_warnings. Got: None
assert []
tests/test_config_warnings_surface.py:205: in test_invalid_tray_left_click_action_reset_to_default
    assert reset_warnings, (
E   AssertionError: AP-22: a reset warning for tray_left_click_action must be appended to last_load_warnings. Got: None
E   assert []
```

### 111. `tests.test_config_warnings_surface.TestLoadResetsInvalidEnumFields.test_invalid_theme_preset_reset_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:222`

```
assert []

AssertionError: AP-22: a reset warning for theme_preset must be appended to last_load_warnings. Got: None
assert []
tests/test_config_warnings_surface.py:222: in test_invalid_theme_preset_reset_to_default
    assert reset_warnings, (
E   AssertionError: AP-22: a reset warning for theme_preset must be appended to last_load_warnings. Got: None
E   assert []
```

### 112. `tests.test_config_warnings_surface.TestLoadResetsInvalidEnumFields.test_invalid_bubble_behavior_reset_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:239`

```
assert []

AssertionError: AP-22: a reset warning for bubble_behavior must be appended to last_load_warnings. Got: None
assert []
tests/test_config_warnings_surface.py:239: in test_invalid_bubble_behavior_reset_to_default
    assert reset_warnings, (
E   AssertionError: AP-22: a reset warning for bubble_behavior must be appended to last_load_warnings. Got: None
E   assert []
```

### 113. `tests.test_config_warnings_surface.TestLoadResetsInvalidEnumFields.test_valid_enum_values_are_not_reset`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:266`

```
+ whisper

AssertionError: assert 'whisper' == 'qwen'

  - qwen
  + whisper
tests/test_config_warnings_surface.py:266: in test_valid_enum_values_are_not_reset
    assert cfg.asr_backend == "qwen"
E   AssertionError: assert 'whisper' == 'qwen'
E
E     - qwen
E     + whisper
```

### 114. `tests.test_config_warnings_surface.TestLoadResetsInvalidEnumFields.test_reset_works_for_multiple_invalid_fields`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:320`

```
assert []

AssertionError: AP-22: expected a reset warning for asr_backend. Got warnings: []
assert []
tests/test_config_warnings_surface.py:320: in test_reset_works_for_multiple_invalid_fields
    assert field_reset_warnings, f"AP-22: expected a reset warning for {field}. Got warnings: {warnings!r}"
E   AssertionError: AP-22: expected a reset warning for asr_backend. Got warnings: []
E   assert []
```

### 115. `tests.test_config_warnings_surface.TestWarningsSurfaceThroughSanitizer.test_load_then_sanitize_surfaces_reset_warning`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:342`

```
assert []

AssertionError: AP-21+AP-22: the reset warning for asr_backend must surface through sanitize_config_for_ipc. Got: []
assert []
tests/test_config_warnings_surface.py:342: in test_load_then_sanitize_surfaces_reset_warning
    assert reset_warnings, (
E   AssertionError: AP-21+AP-22: the reset warning for asr_backend must surface through sanitize_config_for_ipc. Got: []
E   assert []
```

### 116. `tests.test_config_warnings_surface.TestEditorReloadFeedback.test_notification_fires_when_warnings_present`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:439`

```
assert []

AssertionError: AP-25: expected last_load_warnings to be non-empty after loading a config with an invalid asr_backend.
assert []
tests/test_config_warnings_surface.py:439: in test_notification_fires_when_warnings_present
    assert warnings, (
E   AssertionError: AP-25: expected last_load_warnings to be non-empty after loading a config with an invalid asr_backend.
E   assert []
```

### 117. `tests.test_config_warnings_surface.TestEditorReloadFeedback.test_notification_truncates_long_first_warning`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:477`

```
+    where [] = <tests.test_config_warnings_surface._FakeTray object at 0x7f9e1b3014b0>.calls

assert 0 >= 1
 +  where 0 = len([])
 +    where [] = <tests.test_config_warnings_surface._FakeTray object at 0x7f9e1b3014b0>.calls
tests/test_config_warnings_surface.py:477: in test_notification_truncates_long_first_warning
    assert len(tray.calls) >= 1
E   assert 0 >= 1
E    +  where 0 = len([])
E    +    where [] = <tests.test_config_warnings_surface._FakeTray object at 0x7f9e1b3014b0>.calls
```

### 118. `tests.test_config_warnings_surface.TestOptionalNumericFieldsNoSpuriousWarnings.test_invalid_numeric_value_still_warns`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_config_warnings_surface.py:559`

```
assert []

AssertionError: VT-1: a genuinely invalid bubble_x value must still warn + reset. Got warnings: []
assert []
tests/test_config_warnings_surface.py:559: in test_invalid_numeric_value_still_warns
    assert bubble_warnings, (
E   AssertionError: VT-1: a genuinely invalid bubble_x value must still warn + reset. Got warnings: []
E   assert []
```

### 119. `tests.test_consent_and_privacy.TestConfigDeclaresConsentFlags.test_consent_fields_round_trip_via_save_load`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_consent_and_privacy.py:60`

```
+  where False = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).huggingface_consent

AssertionError: assert False is True
 +  where False = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_clo
… (truncated)
```

### 120. `tests.test_log_dedupe_and_emit_lock.TestValidateConfigWarningDedupe.test_repeated_loads_log_each_error_once`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_log_dedupe_and_emit_lock.py:54`

```
assert []

AssertionError: expected at least one validate_config WARNING to be logged
assert []
tests/test_log_dedupe_and_emit_lock.py:54: in test_repeated_loads_log_each_error_once
    assert logged, "expected at least one validate_config WARNING to be logged"
E   AssertionError: expected at least one validate_config WARNING to be logged
E   assert []
```

### 121. `tests.test_no_model_state.TestConfigLoadPreservesNoModelState.test_invalid_model_size_still_resets_to_default`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_no_model_state.py:34`

```
+  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).last_load_warnings

AssertionError: invalid model_size must surface a warning
assert None
 +  where None = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_d
… (truncated)
```

### 122. `tests.test_noise_suppressor_gtcrn.TestLoaderLegacyValueRemap.test_deepfilternet_loads_as_gtcrn`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_noise_suppressor_gtcrn.py:411`

```
+ rnnoise

AssertionError: the legacy 'deepfilternet' value must load as 'gtcrn' (got 'rnnoise')
assert 'rnnoise' == 'gtcrn'

  - gtcrn
  + rnnoise
tests/test_noise_suppressor_gtcrn.py:411: in test_deepfilternet_loads_as_gtcrn
    assert instance.noise_suppression_method == "gtcrn", (
E   AssertionError: the legacy 'deepfilternet' value must load as 'gtcrn' (got 'rnnoise')
E   assert 'rnnoise' == 'gtcrn'
E
E     - gtcrn
E     + rnnoise
```

### 123. `tests.test_noise_suppressor_gtcrn.TestLoaderLegacyValueRemap.test_live_values_pass_through_untouched`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_noise_suppressor_gtcrn.py:458`

```
+ rnnoise

AssertionError: assert 'rnnoise' == 'gtcrn'

  - gtcrn
  + rnnoise
tests/test_noise_suppressor_gtcrn.py:458: in test_live_values_pass_through_untouched
    assert instance.noise_suppression_method == "gtcrn"
E   AssertionError: assert 'rnnoise' == 'gtcrn'
E
E     - gtcrn
E     + rnnoise
```

### 124. `tests.test_onboarding.TestOnboardingFirstRun.test_not_first_run_with_config`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_onboarding.py:36`

```
+    where is_first_run = <voice_typer.server.onboarding.OnboardingController object at 0x7f9e183a4f40>.is_first_run

assert True is False
 +  where True = is_first_run()
 +    where is_first_run = <voice_typer.server.onboarding.OnboardingController object at 0x7f9e183a4f40>.is_first_run
tests/test_onboarding.py:36: in test_not_first_run_with_config
    assert ctrl.is_first_run() is False
E   assert True is False
E    +  where True = is_first_run()
E    +    where is_first_run = <voice_typer.server.onboarding.OnboardingController object at 0x7f9e183a4f40>.is_first_run
```

### 125. `tests.test_onboarding.TestOnboardingWizard.test_full_wizard_flow`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_onboarding.py:220`

```
+ <caps_lock>

AssertionError: assert '<caps_lock>' == '<f4>'

  - <f4>
  + <caps_lock>
tests/test_onboarding.py:220: in test_full_wizard_flow
    assert cfg2.hotkey == "<f4>"
E   AssertionError: assert '<caps_lock>' == '<f4>'
E
E     - <f4>
E     + <caps_lock>
```

### 126. `tests.test_onboarding.TestMarkCompleteFailurePropagation.test_apply_settings_marker_failure_does_not_reappear`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_onboarding.py:584`

```
+    where is_first_run = <voice_typer.server.onboarding.OnboardingController object at 0x7f9df8378a00>.is_first_run

AssertionError: Wizard must NOT reappear when config.onboarding_completed=True is persisted, even if the .onboarding_complete marker is missing
assert True is False
 +  where True = is_first_run()
 +    where is_first_run = <voice_typer.server.onboarding.OnboardingController object at 0x7f9df8378a00>.is_first_run
tests/test_onboarding.py:584: in test_apply_settings_marker_failure_does_not_reappear
    assert ctrl2.is_first_run() is False, (
E   AssertionError: Wizard must NOT reappear when config.onboarding_completed=True is persisted, even if the .onboarding_complete marker is missing
E   assert True is False
E    +  where True = is_first_run()
E    +    where is_first_run = <voice_typer.server.onboarding.OnboardingController object at 0x7f9df8378a00>.is_first_run
```

### 127. `tests.test_property_based.TestConfigSerializationRoundtrip.test_config_roundtrip`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `(unknown location)`

```
(no error line)

exceptiongroup.ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub-exceptions)
+ Exception Group Traceback (most recent call last):
  |   File "/home/runner/work/Lausu/Lausu/tests/test_property_based.py", line 123, in test_config_roundtrip
  |     hotkey=st.sampled_from(["<f2>", "<f5>", "<f9>", "<caps_lock>"]),
  |   File "/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/site-packages/hypothesis/core.py", line 2295, in wrapped_test
  |     raise the_error_hypothesis_found
  | exceptiongroup.ExceptionGroup: Hypothesis found 2 distinct failures. (2 sub-exceptions)
  +-+---------------- 1 ----------------
    | Traceback (most recent call last):
    |   File "/home/runner/work/Lausu/Lausu/tests/test_property_based.py", line 141, in test_config_roundtrip
    |     assert loaded.beam_size == beam_size
    | AssertionError: assert 1 == 2
    |  +  where 1 = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).beam_size
    | Failing test case: test_config_roundtrip(
    |     # The test always failed when commented parts were varied together.
    |     self=<tests.test_property_based.TestConfigSerializationRoundtrip object at 0x7f8b0880d630>,
    |     tmp_config_dir=PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_config_roundtrip0'),
    |     hotkey='<caps_lock>',
    |     model_size='tiny.en',  # or any other generated value
    |     device='cuda',  # or any other generated value
    |     beam_size=2,
    | )
    |
    | You can reproduce this test case by temporarily adding @reproduce_failure('6.168.5', b'AEEDQQBBAEEC') as a decorator on your test function
    +---------------- 2 ---
… (truncated)
```

### 128. `tests.test_qwen_engine.TestQwenConfigKeys.test_asr_backend_persists`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_qwen_engine.py:181`

```
+ whisper

AssertionError: assert 'whisper' == 'qwen'

  - qwen
  + whisper
tests/test_qwen_engine.py:181: in test_asr_backend_persists
    assert loaded.asr_backend == "qwen"
E   AssertionError: assert 'whisper' == 'qwen'
E
E     - qwen
E     + whisper
```

### 129. `tests.test_qwen_engine.TestWhisperSkipWhenQwenActive.test_startup_skips_whisper_when_qwen_active`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_qwen_engine.py:318`

```
AssertionError: Expected 'load' to have been called once. Called 0 times.

AssertionError: Expected 'load' to have been called once. Called 0 times.
tests/test_qwen_engine.py:318: in test_startup_skips_whisper_when_qwen_active
    app.models._qwen_engine.load.assert_called_once()
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/unittest/mock.py:908: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'load' to have been called once. Called 0 times.
```

### 130. `tests.test_qwen_engine.TestWhisperSkipWhenQwenActive.test_startup_falls_back_to_whisper_when_qwen_fails`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_qwen_engine.py:352`

```
AssertionError: Expected 'load' to have been called once. Called 0 times.

AssertionError: Expected 'load' to have been called once. Called 0 times.
tests/test_qwen_engine.py:352: in test_startup_falls_back_to_whisper_when_qwen_fails
    app.models._qwen_engine.load.assert_called_once()
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/unittest/mock.py:908: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'load' to have been called once. Called 0 times.
```

### 131. `tests.test_qwen_engine.TestWhisperSkipWhenQwenActive.test_start_dictation_lazy_loads_whisper_when_qwen_unavailable`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_qwen_engine.py:383`

```
AssertionError: Expected 'start' to have been called once. Called 0 times.

AssertionError: Expected 'start' to have been called once. Called 0 times.
tests/test_qwen_engine.py:383: in test_start_dictation_lazy_loads_whisper_when_qwen_unavailable
    app.recorder.start.assert_called_once()
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/unittest/mock.py:908: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'start' to have been called once. Called 0 times.
```

### 132. `tests.test_security_hardening.TestHallucinationLogging.test_privacy_warning_on_log_transcriptions`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_security_hardening.py:336`

```
+  where False = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95).log_transcriptions

AssertionError: assert False is True
 +  where False = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=True, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model=...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_clos
… (truncated)
```

### 133. `tests.test_startup_onboarding_marker.TestOnboardingStartedMarker.test_stale_state_auto_heals_when_config_exists_but_no_started_marker`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_startup_onboarding_marker.py:97`

```
+    where Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=False, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms=200.0, noise_filter_rnnoise=True, noise_filter_post_capture=True, noise_suppression_method='rnnoise', noise_filter_gate_open_threshold_db=-26.0, noise_filter_gate_close_threshold_db=-32.0, noise_filter_gate_attack_ms=25.0, noise_filter_gate_release_ms=150.0, noise_filter_gate_adaptive=False, noise_filter_eq=True, noise_filter_eq_low_db=-3.0, noise_filter_eq_mid_db=3.0, noise_filter_eq_high_db=2.0, noise_filter_compressor=True, noise_filter_compressor_threshold_db=-18.0, noise_filter_compressor_ratio=3.0, noise_filter_compressor_attack_ms=6.0, noise_filter_compressor_release_ms=60.0, noise_filter_compressor_output_gain_db=0.0, noise_filter_limiter=True, noise_filter_limiter_ceiling_db=-6.0, noise_filter_limiter_release_ms=60.0, noise_filter_notch=False, noise_filter_notch_frequency_hz=0.0, custom_presets=[], active_custom_preset=None, ai_enhancement_enabled=False, auto_capitalize=True, auto_punctuate=True, fix_grammar_basics=True, vocabulary_automation_enabled=False, vocabulary_auto_confidence_threshold=0.7, vocabulary_auto_apply_threshold=0.95) = <voice_typer.server.app.LausuApp object at 0x7f8ac03eada0>.config

AssertionError: Stale onboarding state (config.json exists, .onboarding_started missing) must auto-heal by marking onboarding_completed=True
assert False is True
 +  where False = Config(schema_version=5, secrets_migrated=False, hotkey='<caps_lock>', sample_rate=16000, microphone=None, model_size='', active_plugin='', language='en', device='cuda', beam_size=1, best_of=1, condition_on_previous_text=False, vad_filter_enabled=True, hallucination_filter_mode='balanced', whisper_beam_size=1, streaming_transcription=True, streaming_chunk_seconds=12.0, streaming_step_seconds=5.0, streaming_left_overlap_seconds=3.0, streaming_right_guard_seconds=1.5, streaming_min_first_chunk_seconds=6.0, streaming_silence_threshold=0.003, autostart=True, paste_on_stop=True, unsafe_paste_on_unknown_focus=False, show_notifications=True, warn_elevated_paste=True, warn_password_paste=True, fast_startup=True, offline_pack_consent=True, asr_backend='whisper', qwen_model_path=None, parakeet_model_path=None, disabled_backends=[], trusted_extra_hosts=[], text_cleanup_enabled=True, corrections_path=None, log_transcriptions=False, clipboard_save_restore=True, clipboard_restore_delay_ms=150, recording_mode='toggle', esc_cancel_enabled=False, repaste_hotkey='<ctrl>+<alt>+v', auto_punctuation=True, templates_enabled=True, vocabulary_enabled=True, cloud_api_key='', cloud_api_url='', cloud_model...e_filter_enabled=True, noise_filter_highpass=True, noise_filter_highpass_cutoff_hz=80.0, noise_filter_gate=True, noise_filter_gate_hold_ms
… (truncated)
```

### 134. `tests.test_trusted_extra_hosts.TestConfigLoadReappliesTrustedHosts.test_load_reapplies_persisted_hosts`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_trusted_extra_hosts.py:53`

```
- ]

AssertionError: assert [] == ['my-vllm.lan']

  Right contains one more item: 'my-vllm.lan'

  Full diff:
  + []
  - [
  -     'my-vllm.lan',
  - ]
tests/test_trusted_extra_hosts.py:53: in test_load_reapplies_persisted_hosts
    assert cfg.trusted_extra_hosts == ["my-vllm.lan"]
E   AssertionError: assert [] == ['my-vllm.lan']
E
E     Right contains one more item: 'my-vllm.lan'
E
E     Full diff:
E     + []
E     - [
E     -     'my-vllm.lan',
E     - ]
```
