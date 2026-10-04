# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**6 failing/errored tests** across 10 matrix legs.

### 1. `tests.tauri.test_internal_plugin_tools_absent.TestInternalPluginToolsNotInMainRepo.test_root_gitignore_covers_plugin_tools`

- Legs: macos-14-3.10, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/test_internal_plugin_tools_absent.py:136`

```
assert 1 == 0

AssertionError: tools/internal_plugins must be listed in the root .gitignore (git check-ignore said: not ignored)
assert 1 == 0
tests/tauri/test_internal_plugin_tools_absent.py:136: in test_root_gitignore_covers_plugin_tools
    assert code == 0, (
E   AssertionError: tools/internal_plugins must be listed in the root .gitignore (git check-ignore said: not ignored)
E   assert 1 == 0
```

### 2. `tests.test_dev_console_launcher.test_launch_dev_console_windows_spawns_cmd`

- Legs: macos-14-3.10, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_dev_console_launcher.py:18`

```
AttributeError: module 'subprocess' has no attribute 'CREATE_NEW_CONSOLE'

AttributeError: module 'subprocess' has no attribute 'CREATE_NEW_CONSOLE'
tests/test_dev_console_launcher.py:18: in test_launch_dev_console_windows_spawns_cmd
    rc = dev_console.launch_dev_console("dev")
voice_typer/server/autostart/dev_console.py:42: in launch_dev_console
    creationflags=subprocess.CREATE_NEW_CONSOLE,
E   AttributeError: module 'subprocess' has no attribute 'CREATE_NEW_CONSOLE'
```

### 3. `tests.test_device_manager_permission_probe.TestHealthCheckerLoopPeriodicProbe.test_loop_calls_permission_probe_on_first_iteration`

- Legs: macos-14-3.10
- Location: `tests/test_device_manager_permission_probe.py:238`

```
+  where 0 = len([])

AssertionError: FR-17: health-checker loop must call the permission probe on the first wake when _permission_check_interval=1
assert 0 >= 1
 +  where 0 = len([])
tests/test_device_manager_permission_probe.py:238: in test_loop_calls_permission_probe_on_first_iteration
    assert len(probe_calls) >= 1, (
E   AssertionError: FR-17: health-checker loop must call the permission probe on the first wake when _permission_check_interval=1
E   assert 0 >= 1
E    +  where 0 = len([])
```

### 4. `tests.test_hotkeys_win32.TestModifierOnlyHotkeys.test_alt_only_hotkey_starts_without_error`

- Legs: macos-14-3.10, macos-14-3.13, ubuntu-22.04-3.11, windows-2022-3.10, windows-2022-3.11
- Location: `tests/test_hotkeys_win32.py:278`

```
AssertionError: LL hook handle never installed for modifier-only spec (waited 3.0s)

AssertionError: LL hook handle never installed for modifier-only spec (waited 3.0s)
tests/test_hotkeys_win32.py:278: in test_alt_only_hotkey_starts_without_error
    _wait_until(
tests/test_hotkeys_win32.py:21: in _wait_until
    raise AssertionError(f"{msg} (waited {timeout}s)")
E   AssertionError: LL hook handle never installed for modifier-only spec (waited 3.0s)
```

### 5. `tests.test_qwen_engine.TestQwenEngineUnit.test_load_success_onnx_dir`

- Legs: macos-14-3.10, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_qwen_engine.py:62`

```
+ CPU

AssertionError: assert 'CPU' == 'qwen/cpu'
  
  - qwen/cpu
  + CPU
tests/test_qwen_engine.py:62: in test_load_success_onnx_dir
    assert engine.device_info == "qwen/cpu"
E   AssertionError: assert 'CPU' == 'qwen/cpu'
E     
E     - qwen/cpu
E     + CPU
```

### 6. `tests.test_qwen_onnx_model.TestQwenEngineOnnxIntegration.test_load_selects_onnx_backend_and_pins_cpu`

- Legs: macos-14-3.10, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_qwen_onnx_model.py:415`

```
+ CPU

AssertionError: assert 'CPU' == 'qwen/cpu'
  
  - qwen/cpu
  + CPU
tests/test_qwen_onnx_model.py:415: in test_load_selects_onnx_backend_and_pins_cpu
    assert engine.device_info == "qwen/cpu"
E   AssertionError: assert 'CPU' == 'qwen/cpu'
E     
E     - qwen/cpu
E     + CPU
```
