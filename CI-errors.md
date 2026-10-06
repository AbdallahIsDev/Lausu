# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**4 failing/errored tests** across 10 matrix legs.

### 1. `tests.plugins.test_plugin_registry.TestPluginsUiVisibility.test_owner_workspace_exposes_the_surface`

- Legs: macos-14-3.10, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/plugins/test_plugin_registry.py:244`

```
+    where <function internal_surface_enabled at 0x1059eb910> = hook.internal_surface_enabled

assert False is True
 +  where False = <function internal_surface_enabled at 0x1059eb910>()
 +    where <function internal_surface_enabled at 0x1059eb910> = hook.internal_surface_enabled
tests/plugins/test_plugin_registry.py:244: in test_owner_workspace_exposes_the_surface
    assert hook.internal_surface_enabled() is True
E   assert False is True
E    +  where False = <function internal_surface_enabled at 0x1059eb910>()
E    +    where <function internal_surface_enabled at 0x1059eb910> = hook.internal_surface_enabled
```

### 2. `tests.plugins.test_plugin_registry.TestPluginsUiVisibility.test_visibility_ignores_the_active_plugin`

- Legs: macos-14-3.10, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/plugins/test_plugin_registry.py:264`

```
+    where <function internal_surface_enabled at 0x1059eb910> = hook.internal_surface_enabled

assert False is True
 +  where False = <function internal_surface_enabled at 0x1059eb910>()
 +    where <function internal_surface_enabled at 0x1059eb910> = hook.internal_surface_enabled
tests/plugins/test_plugin_registry.py:264: in test_visibility_ignores_the_active_plugin
    assert hook.internal_surface_enabled() is True
E   assert False is True
E    +  where False = <function internal_surface_enabled at 0x1059eb910>()
E    +    where <function internal_surface_enabled at 0x1059eb910> = hook.internal_surface_enabled
```

### 3. `tests.test_device_caps.TestProbe.test_ct2_cuda_wins_over_cpu_only_ort`

- Legs: macos-14-3.10, macos-14-3.13
- Location: `tests/test_device_caps.py:92`

```
+    where <function gpu_available at 0x10f89a7a0> = device_caps.gpu_available

assert False is True
 +  where False = <function gpu_available at 0x10f89a7a0>(refresh=True)
 +    where <function gpu_available at 0x10f89a7a0> = device_caps.gpu_available
tests/test_device_caps.py:92: in test_ct2_cuda_wins_over_cpu_only_ort
    assert device_caps.gpu_available(refresh=True) is True
E   assert False is True
E    +  where False = <function gpu_available at 0x10f89a7a0>(refresh=True)
E    +    where <function gpu_available at 0x10f89a7a0> = device_caps.gpu_available
```

### 4. `tests.server.test_early_ws_bind.TestMainEarlyWsBind.test_ws_transport_entered_before_construction_completes`

- Legs: windows-2022-3.10
- Location: `tests/server/test_early_ws_bind.py:274`

```
assert 'construct:started' in ['run:entered']

AssertionError: the ws-startup thread must have begun construction
assert 'construct:started' in ['run:entered']
tests\server\test_early_ws_bind.py:274: in test_ws_transport_entered_before_construction_completes
    assert "construct:started" in events, "the ws-startup thread must have begun construction"
E   AssertionError: the ws-startup thread must have begun construction
E   assert 'construct:started' in ['run:entered']
```
