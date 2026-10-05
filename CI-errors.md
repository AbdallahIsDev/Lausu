# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**6 failing/errored tests** across 5 matrix legs.

### 1. `tests.plugins.test_plugin_registry.TestPluginsUiVisibility.test_owner_workspace_exposes_the_surface`

- Legs: macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_plugin_registry.py:244`

```
+    where <function internal_surface_enabled at 0x108972ca0> = hook.internal_surface_enabled

assert False is True
 +  where False = <function internal_surface_enabled at 0x108972ca0>()
 +    where <function internal_surface_enabled at 0x108972ca0> = hook.internal_surface_enabled
tests/plugins/test_plugin_registry.py:244: in test_owner_workspace_exposes_the_surface
    assert hook.internal_surface_enabled() is True
E   assert False is True
E    +  where False = <function internal_surface_enabled at 0x108972ca0>()
E    +    where <function internal_surface_enabled at 0x108972ca0> = hook.internal_surface_enabled
```

### 2. `tests.plugins.test_plugin_registry.TestPluginsUiVisibility.test_visibility_ignores_the_active_plugin`

- Legs: macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_plugin_registry.py:264`

```
+    where <function internal_surface_enabled at 0x104b27100> = hook.internal_surface_enabled

assert False is True
 +  where False = <function internal_surface_enabled at 0x104b27100>()
 +    where <function internal_surface_enabled at 0x104b27100> = hook.internal_surface_enabled
tests/plugins/test_plugin_registry.py:264: in test_visibility_ignores_the_active_plugin
    assert hook.internal_surface_enabled() is True
E   assert False is True
E    +  where False = <function internal_surface_enabled at 0x104b27100>()
E    +    where <function internal_surface_enabled at 0x104b27100> = hook.internal_surface_enabled
```

### 3. `tests.test_device_caps.TestProbe.test_ct2_cuda_wins_over_cpu_only_ort`

- Legs: macos-14-3.13
- Location: `tests/test_device_caps.py:92`

```
+    where <function gpu_available at 0x10cf83c40> = device_caps.gpu_available

assert False is True
 +  where False = <function gpu_available at 0x10cf83c40>(refresh=True)
 +    where <function gpu_available at 0x10cf83c40> = device_caps.gpu_available
tests/test_device_caps.py:92: in test_ct2_cuda_wins_over_cpu_only_ort
    assert device_caps.gpu_available(refresh=True) is True
E   assert False is True
E    +  where False = <function gpu_available at 0x10cf83c40>(refresh=True)
E    +    where <function gpu_available at 0x10cf83c40> = device_caps.gpu_available
```

### 4. `tests.test_slim_core_ml_ratchet.TestBaselineContract.test_repo_tree_does_not_exceed_baseline`

- Legs: macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_slim_core_ml_ratchet.py:187`

```
+  where 1 = main([])

assert 1 == 0
 +  where 1 = main([])
tests/test_slim_core_ml_ratchet.py:187: in test_repo_tree_does_not_exceed_baseline
    assert main([]) == 0
E   assert 1 == 0
E    +  where 1 = main([])
```

### 5. `tests.test_slim_core_ml_ratchet.TestBaselineContract.test_current_count_matches_baseline_sites`

- Legs: macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_slim_core_ml_ratchet.py:193`

```
assert 1 <= 0

assert 1 <= 0
tests/test_slim_core_ml_ratchet.py:193: in test_current_count_matches_baseline_sites
    assert current["total_count"] <= baseline["total_count"]
E   assert 1 <= 0
```

### 6. `tests.test_hotkeys_win32.TestModifierOnlyHotkeys.test_alt_only_hotkey_starts_without_error`

- Legs: ubuntu-22.04-3.12
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
