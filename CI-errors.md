# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**1 failing/errored tests** across 2 matrix legs.

### 1. `tests.test_hotkeys_win32.TestModifierOnlyHotkeys.test_alt_only_hotkey_starts_without_error`

- Legs: macos-14-3.10, windows-2022-3.11
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
