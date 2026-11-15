# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**1 failing/errored tests** across 1 matrix legs.

### 1. `tests.test_shutdown_fast.TestWin32RoutingFastCleanup.test_ctrl_c_still_routes_to_quit`

- Legs: windows-2022-3.11
- Location: `tests/test_shutdown_fast.py:218`

```
AssertionError: Expected 'mock' to be called once. Called 0 times.

AssertionError: Expected 'mock' to be called once. Called 0 times.
tests\test_shutdown_fast.py:218: in test_ctrl_c_still_routes_to_quit
    controller.quit.assert_called_once_with()
C:\hostedtoolcache\windows\Python\3.11.9\x64\Lib\unittest\mock.py:950: in assert_called_once_with
    raise AssertionError(msg)
E   AssertionError: Expected 'mock' to be called once. Called 0 times.
```
