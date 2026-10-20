# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**1 failing/errored tests** across 1 matrix legs.

### 1. `tests.test_paste_cycle_zombie_guard.TestLiveCycleStillPastes.test_live_cycle_copies_and_dispatches`

- Legs: macos-14-3.12
- Location: `tests/test_paste_cycle_zombie_guard.py:189`

```
AssertionError: Expected '_dispatch_keystroke' to have been called once. Called 0 times.

AssertionError: Expected '_dispatch_keystroke' to have been called once. Called 0 times.
tests/test_paste_cycle_zombie_guard.py:189: in test_live_cycle_copies_and_dispatches
    dispatch.assert_called_once()
/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/unittest/mock.py:928: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected '_dispatch_keystroke' to have been called once. Called 0 times.
```
