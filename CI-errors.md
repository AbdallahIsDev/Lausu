# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**11 failing/errored tests** across 10 matrix legs.

### 1. `tests.handlers.test_error_envelope_code_field.TestHandlerFilesUseHelper.test_every_handler_file_uses_a_standardized_helper`

- Legs: macos-14-3.11, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/handlers/test_error_envelope_code_field.py:122`

```
assert not ['system_permissions_handlers.py']

AssertionError: every handler file must use either _respond_with_error or _error_response; missing: ['system_permissions_handlers.py']
assert not ['system_permissions_handlers.py']
tests/handlers/test_error_envelope_code_field.py:122: in test_every_handler_file_uses_a_standardized_helper
    assert not missing, (
E   AssertionError: every handler file must use either _respond_with_error or _error_response; missing: ['system_permissions_handlers.py']
E   assert not ['system_permissions_handlers.py']
```

### 2. `tests.tauri.mig19.test_phase4_validation.test_command_contract_is_frozen_no_untested_additions`

- Legs: macos-14-3.11, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/mig19/test_phase4_validation.py:642`

```
Do NOT silently grow the wire contract.

Failed: ADR-0020 §16: _COMMAND_REGISTRY contains commands NOT in the frozen 68-command table AND NOT in the KNOWN_UNDOCUMENTED_COMMANDS allowlist:
  screenshot_capture
  screenshot_clear_cycle
  screenshot_get_status
  screenshot_set_consent

To resolve, EITHER:
  (a) Remove the command from _COMMAND_REGISTRY (it was added without an ADR addendum), OR
  (b) Add it to EXPECTED_COMMANDS in this test + add an ADR-0020 addendum + add a _validate_dict_payload schema + add a test in tests/test_ipc_dispatch_errors.py, OR
  (c) Add it to KNOWN_UNDOCUMENTED_COMMANDS in this test with a comment naming the PR + reason (this is the explicit-gap path; the test_known_undocumented_commands_are_reported test below will then keep the entry in sync with reality).
Do NOT silently grow the wire contract.
tests/tauri/mig19/test_phase4_validation.py:642: in test_command_contract_is_frozen_no_untested_additions
    pytest.fail(
E   Failed: ADR-0020 §16: _COMMAND_REGISTRY contains commands NOT in the frozen 68-command table AND NOT in the KNOWN_UNDOCUMENTED_COMMANDS allowlist:
E     screenshot_capture
E     screenshot_clear_cycle
E     screenshot_get_status
E     screenshot_set_consent
E   
E   To resolve, EITHER:
E     (a) Remove the command from _COMMAND_REGISTRY (it was added without an ADR addendum), OR
E     (b) Add it to EXPECTED_COMMANDS in this test + add an ADR-0020 addendum + add a _validate_dict_payload schema + add a test in tests/test_ipc_dispatch_errors.py, OR
E     (c) Add it to KNOWN_UNDOCUMENTED_COMMANDS in this test with a comment naming the PR + reason (this is the explicit-gap path; the test_known_undocumented_commands_are_reported test below will then keep the entry in sync with reality).
E   Do NOT silently grow the wire contract.
```

### 3. `tests.tauri.mig19.test_phase4_validation.test_known_undocumented_commands_are_reported`

- Legs: macos-14-3.11, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/mig19/test_phase4_validation.py:684`

```
screenshot_set_consent

Failed: Commands in _COMMAND_REGISTRY but NOT in EXPECTED_COMMANDS and NOT in KNOWN_UNDOCUMENTED_COMMANDS (add to KNOWN_UNDOCUMENTED_COMMANDS with a comment, OR close the gap by adding to EXPECTED_COMMANDS + ADR addendum):
  screenshot_capture
  screenshot_clear_cycle
  screenshot_get_status
  screenshot_set_consent
tests/tauri/mig19/test_phase4_validation.py:684: in test_known_undocumented_commands_are_reported
    pytest.fail("\n\n".join(msg_parts))
E   Failed: Commands in _COMMAND_REGISTRY but NOT in EXPECTED_COMMANDS and NOT in KNOWN_UNDOCUMENTED_COMMANDS (add to KNOWN_UNDOCUMENTED_COMMANDS with a comment, OR close the gap by adding to EXPECTED_COMMANDS + ADR addendum):
E     screenshot_capture
E     screenshot_clear_cycle
E     screenshot_get_status
E     screenshot_set_consent
```

### 4. `tests.test_architecture_doc_accuracy.test_module_paths_use_package_form`

- Legs: macos-14-3.11, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_architecture_doc_accuracy.py:277`

```
+  where 9 = len([PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/worker.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/test_recording_files.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/mic_level_push.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring_queries.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'), ...])

AssertionError: level_monitor/ must be a 5-file package (actual: 9).
assert 9 == 5
 +  where 9 = len([PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/worker.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/test_recording_files.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/mic_level_push.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring_queries.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'), ...])
tests/test_architecture_doc_accuracy.py:277: in test_module_paths_use_package_form
    assert len(level_files) == 5, f"level_monitor/ must be a 5-file package (actual: {len(level_files)})."
E   AssertionError: level_monitor/ must be a 5-file package (actual: 9).
E   assert 9 == 5
E    +  where 9 = len([PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/worker.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/test_recording_files.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/mic_level_push.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/monitoring_queries.py'), PosixPath('/Users/runner/work/Lausu/Lausu/voice_typer/server/level_monitor/__init__.py'), ...])
```

### 5. `tests.test_error_codes_registry.TestEmittedCodesAreRegisteredOrLegacy.test_all_emitted_codes_known`

- Legs: macos-14-3.11, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_error_codes_registry.py:150`

```
voice_typer/server/handlers/screenshot_handlers.py:40 -> 'screenshot_already_captured'

Failed: Unknown error codes emitted in the server tree. Either add the namespaced form to ERROR_CODES in voice_typer/server/ipc/validation.py, OR add the legacy form to LEGACY_ALIASES in this test (if it's a backward-compat alias).
Unknown emissions:
  voice_typer/server/handlers/screenshot_handlers.py:16 -> 'screenshot_unsupported'
  voice_typer/server/handlers/screenshot_handlers.py:18 -> 'screenshot_disabled'
  voice_typer/server/handlers/screenshot_handlers.py:20 -> 'screenshot_no_consent'
  voice_typer/server/handlers/screenshot_handlers.py:36 -> 'screenshot_unsupported'
  voice_typer/server/handlers/screenshot_handlers.py:40 -> 'screenshot_already_captured'
tests/test_error_codes_registry.py:150: in test_all_emitted_codes_known
    pytest.fail(
E   Failed: Unknown error codes emitted in the server tree. Either add the namespaced form to ERROR_CODES in voice_typer/server/ipc/validation.py, OR add the legacy form to LEGACY_ALIASES in this test (if it's a backward-compat alias).
E   Unknown emissions:
E     voice_typer/server/handlers/screenshot_handlers.py:16 -> 'screenshot_unsupported'
E     voice_typer/server/handlers/screenshot_handlers.py:18 -> 'screenshot_disabled'
E     voice_typer/server/handlers/screenshot_handlers.py:20 -> 'screenshot_no_consent'
E     voice_typer/server/handlers/screenshot_handlers.py:36 -> 'screenshot_unsupported'
E     voice_typer/server/handlers/screenshot_handlers.py:40 -> 'screenshot_already_captured'
```

### 6. `tests.test_hotkeys.TestApplyConfigReRegistersHotkeyForPushToTalk.test_service_apply_config_side_effects_handles_recording_mode`

- Legs: macos-14-3.11, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_hotkeys.py:29`

```
assert 'recording_mode' in '"""Config side-effect dispatcher (registered handlers, not an if-chain).\n\nNOTE: see docs/code-notes/security-config.md#config-preset-handlers\n\nImplementation split (every moved name re-exported here, so the\nhistorical import path keeps resolving):\n:mod:`voice_typer.server.config_applier_handlers` (the side-effect\nhandler registry + support helpers). This module keeps the ACL notify\npath, the preset-override keys, and :class:`ConfigApplier` -- the\nRACE-011 config-mutation lock and the SEC-002 allowlist check stay on\nthis facade, where tests exercise them.\n"""\n\nfrom __future__ import annotations\n\nimport contextlib\nimport json\nimport logging\nfrom typing import Any\n\nfrom voice_typer.server import i18n\nfrom voice_typer.server.branding import APP_NAME\nfrom voice_typer.server.config_applier_handlers import (  # noqa: F401  # facade re-export\n    _FILTER_CHAIN_KEYS,\n    ConfigSideEffect,\n    SideEffectContext,\n    SideEffectStatus,\n    _apply_audio_preset,\n    _AudioPresetHandler,\n    _AutostartSyncHandler,\n    _BubbleBehaviorHandler,\n    _DictationHotkeyHandler,\n    _EscHotkeyHandler,\n    _FilterChainHandler,\n    _NotificationsHandler,\n    _notify_sid..."non-allowlisted keys {sorted(_unknown)}; the IPC "\n                f"set_config handler should have dropped these via "\n                f"validate_config_update. Internal callers must only "\n                f"pass IPC_CONFIG_ALLOWLIST keys."\n            )\n        app = self._app\n        # (session-3): capture the side-effect status dict for\n        side_effect_status: SideEffectStatus = self._empty_side_effect_status()\n        # + : snapshot pre-setattr Config state. Used for\n        with app._config_mutation_lock:\n            updates = self._maybe_autoswitch_audio_preset(updates)\n            set_keys = self._setattr_updates(app, updates)\n            self._maybe_invalidate_llm_polisher(app, updates)\n            # Apply side effects inside the lock so Config mutations\n            side_effect_status = self.apply_config_side_effects(updates)\n            # ``save_strict`` raises RuntimeError if ``save()`` returned\n            self._save_updates_strict(app, updates, set_keys)\n            self._maybe_refresh_clipboard(app, updates)\n        # invalidate the tray menu cache so the next menu\n        self._post_save_tray_cleanup(app)\n        return side_effect_status\n'

assert 'recording_mode' in '"""Config side-effect dispatcher (registered handlers, not an if-chain).\n\nNOTE: see docs/code-notes/security-config.md#config-preset-handlers\n\nImplementation split (every moved name re-exported here, so the\nhistorical import path keeps resolving):\n:mod:`voice_typer.server.config_applier_handlers` (the side-effect\nhandler registry + support helpers). This module keeps the ACL notify\npath, the preset-override keys, and :class:`ConfigApplier` -- the\nRACE-011 config-mutation lock and the SEC-002 allowlist check stay on\nthis facade, where tests exercise them.\n"""\n\nfrom __future__ import annotations\n\nimport contextlib\nimport json\nimport logging\nfrom typing import Any\n\nfrom voice_typer.server import i18n\nfrom voice_typer.server.branding import APP_NAME\nfrom voice_typer.server.config_applier_handlers import (  # noqa: F401  # facade re-export\n    _FILTER_CHAIN_KEYS,\n    ConfigSideEffect,\n    SideEffectContext,\n    SideEffectStatus,\n    _apply_audio_preset,\n    _AudioPresetHandler,\n    _AutostartSyncHandler,\n    _BubbleBehaviorHandler,\n    _DictationHotkeyHandler,\n    _EscHotkeyHandler,\n    _FilterChainHandler,\n    _NotificationsHandler,\n    _notify_sid..."non-allowlisted keys {sorted(_unknown)}; the IPC "\n                f"set_config handler should have dropped these via "\n                f"validate_config_update. Internal callers must only "\n                f"pass IPC_CONFIG_ALLOWLIST keys."\n            )\n        app = self._app\n        # (session-3): capture the side-effect status di
… (truncated)
```

### 7. `tests.test_hotkeys.TestApplyConfigReRegistersHotkeyForPushToTalk.test_service_handles_hotkey_change`

- Legs: macos-14-3.11, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_hotkeys.py:34`

```
assert '"hotkey" in updates' in '"""Config side-effect dispatcher (registered handlers, not an if-chain).\n\nNOTE: see docs/code-notes/security-config.md#config-preset-handlers\n\nImplementation split (every moved name re-exported here, so the\nhistorical import path keeps resolving):\n:mod:`voice_typer.server.config_applier_handlers` (the side-effect\nhandler registry + support helpers). This module keeps the ACL notify\npath, the preset-override keys, and :class:`ConfigApplier` -- the\nRACE-011 config-mutation lock and the SEC-002 allowlist check stay on\nthis facade, where tests exercise them.\n"""\n\nfrom __future__ import annotations\n\nimport contextlib\nimport json\nimport logging\nfrom typing import Any\n\nfrom voice_typer.server import i18n\nfrom voice_typer.server.branding import APP_NAME\nfrom voice_typer.server.config_applier_handlers import (  # noqa: F401  # facade re-export\n    _FILTER_CHAIN_KEYS,\n    ConfigSideEffect,\n    SideEffectContext,\n    SideEffectStatus,\n    _apply_audio_preset,\n    _AudioPresetHandler,\n    _AutostartSyncHandler,\n    _BubbleBehaviorHandler,\n    _DictationHotkeyHandler,\n    _EscHotkeyHandler,\n    _FilterChainHandler,\n    _NotificationsHandler,\n    _notify_sid..."non-allowlisted keys {sorted(_unknown)}; the IPC "\n                f"set_config handler should have dropped these via "\n                f"validate_config_update. Internal callers must only "\n                f"pass IPC_CONFIG_ALLOWLIST keys."\n            )\n        app = self._app\n        # (session-3): capture the side-effect status dict for\n        side_effect_status: SideEffectStatus = self._empty_side_effect_status()\n        # + : snapshot pre-setattr Config state. Used for\n        with app._config_mutation_lock:\n            updates = self._maybe_autoswitch_audio_preset(updates)\n            set_keys = self._setattr_updates(app, updates)\n            self._maybe_invalidate_llm_polisher(app, updates)\n            # Apply side effects inside the lock so Config mutations\n            side_effect_status = self.apply_config_side_effects(updates)\n            # ``save_strict`` raises RuntimeError if ``save()`` returned\n            self._save_updates_strict(app, updates, set_keys)\n            self._maybe_refresh_clipboard(app, updates)\n        # invalidate the tray menu cache so the next menu\n        self._post_save_tray_cleanup(app)\n        return side_effect_status\n'

assert '"hotkey" in updates' in '"""Config side-effect dispatcher (registered handlers, not an if-chain).\n\nNOTE: see docs/code-notes/security-config.md#config-preset-handlers\n\nImplementation split (every moved name re-exported here, so the\nhistorical import path keeps resolving):\n:mod:`voice_typer.server.config_applier_handlers` (the side-effect\nhandler registry + support helpers). This module keeps the ACL notify\npath, the preset-override keys, and :class:`ConfigApplier` -- the\nRACE-011 config-mutation lock and the SEC-002 allowlist check stay on\nthis facade, where tests exercise them.\n"""\n\nfrom __future__ import annotations\n\nimport contextlib\nimport json\nimport logging\nfrom typing import Any\n\nfrom voice_typer.server import i18n\nfrom voice_typer.server.branding import APP_NAME\nfrom voice_typer.server.config_applier_handlers import (  # noqa: F401  # facade re-export\n    _FILTER_CHAIN_KEYS,\n    ConfigSideEffect,\n    SideEffectContext,\n    SideEffectStatus,\n    _apply_audio_preset,\n    _AudioPresetHandler,\n    _AutostartSyncHandler,\n    _BubbleBehaviorHandler,\n    _DictationHotkeyHandler,\n    _EscHotkeyHandler,\n    _FilterChainHandler,\n    _NotificationsHandler,\n    _notify_sid..."non-allowlisted keys {sorted(_unknown)}; the IPC "\n                f"set_config handler should have dropped these via "\n                f"validate_config_update. Internal callers must only "\n                f"pass IPC_CONFIG_ALLOWLIST keys."\n            )\n        app = self._app\n        # (session-3): capture the side-effect
… (truncated)
```

### 8. `tests.test_ipc_reference_doc_accuracy.test_ipc_reference_doc_has_row_for_every_registry_command`

- Legs: macos-14-3.11, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_ipc_reference_doc_accuracy.py:118`

```
assert not {'screenshot_capture', 'screenshot_clear_cycle', 'screenshot_get_status', 'screenshot_set_consent'}

AssertionError: _COMMAND_REGISTRY has 4 commands with no row in docs/ipc-reference.md: ['screenshot_capture', 'screenshot_clear_cycle', 'screenshot_get_status', 'screenshot_set_consent']. Add a row in the appropriate namespace section of the doc.
assert not {'screenshot_capture', 'screenshot_clear_cycle', 'screenshot_get_status', 'screenshot_set_consent'}
tests/test_ipc_reference_doc_accuracy.py:118: in test_ipc_reference_doc_has_row_for_every_registry_command
    assert not missing_from_doc, (
E   AssertionError: _COMMAND_REGISTRY has 4 commands with no row in docs/ipc-reference.md: ['screenshot_capture', 'screenshot_clear_cycle', 'screenshot_get_status', 'screenshot_set_consent']. Add a row in the appropriate namespace section of the doc.
E   assert not {'screenshot_capture', 'screenshot_clear_cycle', 'screenshot_get_status', 'screenshot_set_consent'}
```

### 9. `tests.test_ipc_reference_doc_accuracy.test_ipc_reference_doc_commands_header_count_matches_registry`

- Legs: macos-14-3.11, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_ipc_reference_doc_accuracy.py:146`

```
assert 80 == 84

AssertionError: docs/ipc-reference.md documents 80 total commands but _COMMAND_REGISTRY has 84. Update the header.
assert 80 == 84
tests/test_ipc_reference_doc_accuracy.py:146: in test_ipc_reference_doc_commands_header_count_matches_registry
    assert documented == actual, (
E   AssertionError: docs/ipc-reference.md documents 80 total commands but _COMMAND_REGISTRY has 84. Update the header.
E   assert 80 == 84
```

### 10. `tests.test_macos_bundle_id.TestOnboardingSource.test_uses_runtime_resolution_and_no_hardcoded_bundle_id`

- Legs: macos-14-3.11, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_macos_bundle_id.py:281`

```
assert 'resolve_host_bundle_id()' in '"""First-run detection + 4-step onboarding wizard controller.\n\nDetects whether the app is running for the first time (no config.json\nexists) and guides the user through initial setup:\n\nStep 1: Welcome screen, brief explanation of what the app does + the\n        app-language picker (changeable later in Settings).\nStep 2: Consent, consolidated grant of every consent flag (voice\n        biometric, HuggingFace model downloads, OpenAI / Groq /\n        Deepgram cloud ASR, LLM polish) with an "Agree to All"\n        convenience; the renderer persists each toggle immediately via\n        the allowlisted set_config fields, so no backend-side\n        collection is needed.\nStep 3: Model selection, local-vs-cloud backend choice + per-model\n        download, tiny (default), large-v3, large-v3-turbo\n        (multilingual Whisper variants), plus Parakeet\nStep 4: Hotkey selection, F2-F12 or custom combo. This is the LAST\n        step: its Continue button finalizes the wizard (applies every\n        selection + marks onboarding complete via ``apply_settings``\n        through the service layer\'s ``onboarding_apply``).\n\nRemoved from the original 7-step flow (user decision 2026-0...rror": ...}`` envelope so the\n        IPC handler surfaces it to the user). The config flag was\n        already persisted by the ``config.save()`` call above, so the\n        wizard will NOT reappear on the next launch even though the\n        marker file is missing, :meth:`is_first_run` falls through to\n        the config check and returns ``False``.\n        """\n        if self.selected_microphone is not None:\n            config.microphone = self.selected_microphone\n        config.hotkey = self.selected_hotkey\n        config.model_size = self.selected_model\n        # set the onboarding-completed flag BEFORE ``config.save()``\n        config.onboarding_completed = True\n        # ``config.save()`` returns ``False`` on failure (errors\n        save_result = config.save()\n        if save_result is False:\n            raise RuntimeError("failed to persist onboarding settings")\n        # only mark complete once the config has been\n        self.mark_complete()\n        log.info(\n            "[ONBOARDING] Settings applied: mic=%s | hotkey=%s | model=%s",\n            self.selected_microphone,\n            self.selected_hotkey,\n            self.selected_model,\n        )\n'

AssertionError: onboarding.py must resolve the host bundle ID at runtime (resolve_host_bundle_id) for the macOS permissions guidance (the tccutil re-grant command in the onboarding walkthrough).
assert 'resolve_host_bundle_id()' in '"""First-run detection + 4-step onboarding wizard controller.\n\nDetects whether the app is running for the first time (no config.json\nexists) and guides the user through initial setup:\n\nStep 1: Welcome screen, brief explanation of what the app does + the\n        app-language picker (changeable later in Settings).\nStep 2: Consent, consolidated grant of every consent flag (voice\n        biometric, HuggingFace model downloads, OpenAI / Groq /\n        Deepgram cloud ASR, LLM polish) with an "Agree to All"\n        convenience; the renderer persists each toggle immediately via\n        the allowlisted set_config fields, so no backend-side\n        collection is needed.\nStep 3: Model selection, local-vs-cloud backend choice + per-model\n        download, tiny (default), large-v3, large-v3-turbo\n        (multilingual Whisper variants), plus Parakeet\nStep 4: Hotkey selection, F2-F12 or custom combo. This is the LAST\n        step: its Continue button finalizes the wizard (applies every\n        selection + marks onboarding complete via ``apply_settings``\n        through the service layer\'s ``onboarding_apply``).\n\nRemoved from the original 7-step flow (user decision 2026-0...rror": ...}`` envelope so the\n        IPC handler surfaces it to the user). The config flag was\n        already persisted by t
… (truncated)
```

### 11. `tests.test_hotkeys_win32.TestModifierOnlyHotkeys.test_alt_only_hotkey_starts_without_error`

- Legs: windows-2022-3.10
- Location: `tests/test_hotkeys_win32.py:285`

```
AssertionError: LL hook handle never installed for modifier-only spec (waited 15.0s)

AssertionError: LL hook handle never installed for modifier-only spec (waited 15.0s)
tests\test_hotkeys_win32.py:285: in test_alt_only_hotkey_starts_without_error
    _wait_until(
tests\test_hotkeys_win32.py:28: in _wait_until
    raise AssertionError(f"{msg} (waited {timeout}s)")
E   AssertionError: LL hook handle never installed for modifier-only spec (waited 15.0s)
```
