# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.
> Source SHA: `9c099320dfdafb6782069a1948b2f045ecc2d102`

**3 failing/errored tests** across 6 matrix legs.

### 1. `pytest.internal`

- Legs: macos-15-3.11, ubuntu-22.04-3.11
- Location: `(pytest internal error, no test location)`

```
internal error

internal error
def worker_internal_error(
        self, node: WorkerController, formatted_error: str
    ) -> None:
        """
        pytest_internalerror() was called on the worker.

        pytest_internalerror() arguments are an excinfo and an excrepr, which can't
        be serialized, so we go with a poor man's solution of raising an exception
        here ourselves using the formatted message.
        """
        self._active_nodes.remove(node)
        try:
>           assert False, formatted_error
E           AssertionError: Traceback (most recent call last):
E               File "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages/_pytest/main.py", line 333, in wrap_session
E                 session.exitstatus = doit(config, session) or 0
E                                      ^^^^^^^^^^^^^^^^^^^^^
E               File "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages/_pytest/main.py", line 387, in _main
E                 config.hook.pytest_runtestloop(session=session)
E               File "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages/pluggy/_caller.py", line 197, in __call__
E                 return self._hookexec(
E                        ^^^^^^^^^^^^^^^
E               File "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages/pluggy/_manager.py", line 183, in _hookexec
E                 return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
E                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E               File "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages/pluggy/_execution.py", line 195, in _multicall
E                 raise exception
E               File "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages/pluggy/_execution.py", line 167, in _multicall
E                 teardown.throw(exception)
E               File "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages/_pytest/logging.py", line 829, in pytest_runtestloop
E                 return (yield)  # Run all the tests.
E                         ^^^^^
E               File "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages/pluggy/_execution.py", line 167, in _multicall
E                 teardown.throw(exception)
E               File "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages/_pytest/terminal.py", line 723, in pytest_runtestloop
E                 result = yield
E                          ^^^^^
```

### 2. `tests.tauri.test_windows_freeze_drift.test_gate_resolves_newest_versioned_extraction_dir_without_build_stamp`

- Legs: macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `(unknown location)`

```
NotImplementedError: cannot instantiate 'WindowsPath' on your system

NotImplementedError: cannot instantiate 'WindowsPath' on your system
/Users/runner/work/Lausu/Lausu/tests/tauri/test_windows_freeze_drift.py:129: in test_gate_resolves_newest_versioned_extraction_dir_without_build_stamp
    assert gate.onefile_extraction_dir() == new, (
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/runner/work/Lausu/Lausu/scripts/verify_windows_bundle.py:296: in onefile_extraction_dir
    root = expand_onefile_cache_spec(spec.split("/{VERSION}/")[0], cache, product)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/runner/work/Lausu/Lausu/scripts/verify_windows_bundle.py:278: in expand_onefile_cache_spec
    return Path(cache_dir) / suffix
           ^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/pathlib.py:721: in __truediv__
    return self.joinpath(key)
           ^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/pathlib.py:717: in joinpath
    return self.with_segments(self, *pathsegments)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/pathlib.py:385: in with_segments
    return type(self)(*pathsegments)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/pathlib.py:1434: in __new__
    raise NotImplementedError(
E   NotImplementedError: cannot instantiate 'WindowsPath' on your system
```

### 3. `tests.test_windows_bundle_gate.test_pinned_spec_is_per_build_and_per_product`

- Legs: macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `(unknown location)`

```
NotImplementedError: cannot instantiate 'WindowsPath' on your system

NotImplementedError: cannot instantiate 'WindowsPath' on your system
/Users/runner/work/Lausu/Lausu/tests/test_windows_bundle_gate.py:74: in test_pinned_spec_is_per_build_and_per_product
    assert gate.onefile_extraction_dir() == new
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/runner/work/Lausu/Lausu/scripts/verify_windows_bundle.py:296: in onefile_extraction_dir
    root = expand_onefile_cache_spec(spec.split("/{VERSION}/")[0], cache, product)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Users/runner/work/Lausu/Lausu/scripts/verify_windows_bundle.py:278: in expand_onefile_cache_spec
    return Path(cache_dir) / suffix
           ^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/pathlib.py:721: in __truediv__
    return self.joinpath(key)
           ^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/pathlib.py:717: in joinpath
    return self.with_segments(self, *pathsegments)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/pathlib.py:385: in with_segments
    return type(self)(*pathsegments)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/pathlib.py:1434: in __new__
    raise NotImplementedError(
E   NotImplementedError: cannot instantiate 'WindowsPath' on your system
```
