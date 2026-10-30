# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**1 failing/errored tests** across 1 matrix legs.

### 1. `tests.test_shutdown_recording_fixes.TestToggleLockReleasedDuringModelLoad.test_lock_actually_released_during_load_at_runtime`

- Legs: windows-2022-3.11
- Location: `tests/test_shutdown_recording_fixes.py:485`

```
+    where wait = <threading.Event at 0x2a756e4e4d0: set>.wait

AssertionError: IN-20: ensure_active_engine_loaded was never called
assert False
 +  where False = wait(timeout=1.0)
 +    where wait = <threading.Event at 0x2a756e4e4d0: set>.wait
tests\test_shutdown_recording_fixes.py:485: in test_lock_actually_released_during_load_at_runtime
    assert load_started.wait(timeout=1.0), "IN-20: ensure_active_engine_loaded was never called"
E   AssertionError: IN-20: ensure_active_engine_loaded was never called
E   assert False
E    +  where False = wait(timeout=1.0)
E    +    where wait = <threading.Event at 0x2a756e4e4d0: set>.wait
```
