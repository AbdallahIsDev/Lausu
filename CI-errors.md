# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**4 failing/errored tests** across 8 matrix legs.

### 1. `tests.tauri.test_internal_plugin_tools_absent.TestInternalPluginToolsNotInMainRepo.test_root_gitignore_covers_plugin_tools`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
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

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
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

### 3. `tests.test_qwen_engine.TestQwenEngineUnit.test_load_success_onnx_dir`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
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

### 4. `tests.test_qwen_onnx_model.TestQwenEngineOnnxIntegration.test_load_selects_onnx_backend_and_pins_cpu`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
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
