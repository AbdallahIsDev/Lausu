# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**4 failing/errored tests** across 4 matrix legs.

### 1. `tests.plugins.test_plugin_registry.TestPluginsUiVisibility.test_owner_workspace_exposes_the_surface`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_plugin_registry.py:244`

```
+    where <function internal_surface_enabled at 0x7faeedec7520> = hook.internal_surface_enabled

assert False is True
 +  where False = <function internal_surface_enabled at 0x7faeedec7520>()
 +    where <function internal_surface_enabled at 0x7faeedec7520> = hook.internal_surface_enabled
tests/plugins/test_plugin_registry.py:244: in test_owner_workspace_exposes_the_surface
    assert hook.internal_surface_enabled() is True
E   assert False is True
E    +  where False = <function internal_surface_enabled at 0x7faeedec7520>()
E    +    where <function internal_surface_enabled at 0x7faeedec7520> = hook.internal_surface_enabled
```

### 2. `tests.plugins.test_plugin_registry.TestPluginsUiVisibility.test_visibility_ignores_the_active_plugin`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_plugin_registry.py:264`

```
+    where <function internal_surface_enabled at 0x7faeedec7520> = hook.internal_surface_enabled

assert False is True
 +  where False = <function internal_surface_enabled at 0x7faeedec7520>()
 +    where <function internal_surface_enabled at 0x7faeedec7520> = hook.internal_surface_enabled
tests/plugins/test_plugin_registry.py:264: in test_visibility_ignores_the_active_plugin
    assert hook.internal_surface_enabled() is True
E   assert False is True
E    +  where False = <function internal_surface_enabled at 0x7faeedec7520>()
E    +    where <function internal_surface_enabled at 0x7faeedec7520> = hook.internal_surface_enabled
```

### 3. `tests.test_slim_core_ml_ratchet.TestBaselineContract.test_repo_tree_does_not_exceed_baseline`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
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

### 4. `tests.test_slim_core_ml_ratchet.TestBaselineContract.test_current_count_matches_baseline_sites`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_slim_core_ml_ratchet.py:193`

```
assert 1 <= 0

assert 1 <= 0
tests/test_slim_core_ml_ratchet.py:193: in test_current_count_matches_baseline_sites
    assert current["total_count"] <= baseline["total_count"]
E   assert 1 <= 0
```
