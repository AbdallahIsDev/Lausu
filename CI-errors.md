# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**7 failing/errored tests** across 5 matrix legs.

### 1. `tests.test_audio_filter_reset_zero_buffers.test_streaming_resampler_chunked_matches_oneshot`

- Legs: macos-14-3.13
- Location: `tests/test_audio_filter_reset_zero_buffers.py:129`

```
+      where <ufunc 'absolute'> = np.abs

AssertionError: assert np.float32(9.313226e-10) == 0.0
 +  where np.float32(9.313226e-10) = <function max at 0x104295af0>(array([0.000000e+00, 0.000000e+00, 0.000000e+00, ..., 4.656613e-10,\n       5.820766e-11, 0.000000e+00], shape=(1024,), dtype=float32))
 +    where <function max at 0x104295af0> = np.max
 +    and   array([0.000000e+00, 0.000000e+00, 0.000000e+00, ..., 4.656613e-10,\n       5.820766e-11, 0.000000e+00], shape=(1024,), dtype=float32) = <ufunc 'absolute'>((array([ 9.2539922e-09,  2.2526635e-06, -3.3697943e-05, ...,\n        4.0074368e-03, -4.0152267e-04,  2.5318800e-03],\n      shape=(1024,), dtype=float32) - array([ 9.2539922e-09,  2.2526635e-06, -3.3697943e-05, ...,\n        4.0074373e-03, -4.0152261e-04,  2.5318800e-03],\n      shape=(1024,), dtype=float32)))
 +      where <ufunc 'absolute'> = np.abs
tests/test_audio_filter_reset_zero_buffers.py:129: in test_streaming_resampler_chunked_matches_oneshot
    assert np.max(np.abs(ref - streamed)) == 0.0
E   AssertionError: assert np.float32(9.313226e-10) == 0.0
E    +  where np.float32(9.313226e-10) = <function max at 0x104295af0>(array([0.000000e+00, 0.000000e+00, 0.000000e+00, ..., 4.656613e-10,\n       5.820766e-11, 0.000000e+00], shape=(1024,), dtype=float32))
E    +    where <function max at 0x104295af0> = np.max
E    +    and   array([0.000000e+00, 0.000000e+00, 0.000000e+00, ..., 4.656613e-10,\n       5.820766e-11, 0.000000e+00], shape=(1024,), dtype=float32) = <ufunc 'absolute'>((array([ 9.2539922e-09,  2.2526635e-06, -3.3697943e-05, ...,\n        4.0074368e-03, -4.0152267e-04,  2.5318800e-03],\n      shape=(1024,), dtype=float32) - array([ 9.2539922e-09,  2.2526635e-06, -3.3697943e-05, ...,\n        4.0074373e-03, -4.0152261e-04,  2.5318800e-03],\n      shape=(1024,), dtype=float32)))
E    +      where <ufunc 'absolute'> = np.abs
```

### 2. `tests.app.test_config_wiring.TestTextCleanupConfig.test_cleanup_skipped_when_disabled`

- Legs: windows-2022-3.10, windows-2022-3.12
- Location: `(unknown location)`

```
(no error line)

failed on setup with "worker 'gw0' crashed while running 'tests/app/test_config_wiring.py::TestTextCleanupConfig::test_cleanup_skipped_when_disabled'"
worker 'gw0' crashed while running 'tests/app/test_config_wiring.py::TestTextCleanupConfig::test_cleanup_skipped_when_disabled'
```

### 3. `tests.app.test_config_wiring.TestSettingsWindowIntegration.test_restart_hotkey_stops_existing_backend_and_registers_new_one`

- Legs: windows-2022-3.10, windows-2022-3.11
- Location: `(unknown location)`

```
(no error line)

failed on setup with "worker 'gw1' crashed while running 'tests/app/test_config_wiring.py::TestSettingsWindowIntegration::test_restart_hotkey_stops_existing_backend_and_registers_new_one'"
worker 'gw1' crashed while running 'tests/app/test_config_wiring.py::TestSettingsWindowIntegration::test_restart_hotkey_stops_existing_backend_and_registers_new_one'
```

### 4. `pytest.internal`

- Legs: windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `(pytest internal error, no test location)`

```
internal error

internal error
Traceback (most recent call last):
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\_pytest\main.py", line 330, in wrap_session
    session.exitstatus = doit(config, session) or 0
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\_pytest\main.py", line 384, in _main
    config.hook.pytest_runtestloop(session=session)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_caller.py", line 197, in __call__
    return self._hookexec(
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_manager.py", line 183, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_execution.py", line 195, in _multicall
    raise exception
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_execution.py", line 167, in _multicall
    teardown.throw(exception)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\_pytest\logging.py", line 816, in pytest_runtestloop
    return (yield)  # Run all the tests.
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_execution.py", line 167, in _multicall
    teardown.throw(exception)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\_pytest\terminal.py", line 708, in pytest_runtestloop
    result = yield
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_execution.py", line 167, in _multicall
    teardown.throw(exception)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pytest_cov\plugin.py", line 348, in pytest_runtestloop
    result = yield
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pluggy\_execution.py", line 147, in _multicall
    res = hook_impl.function(*args)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\dsession.py", line 138, in pytest_runtestloop
    self.loop_once()
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\dsession.py", line 163, in loop_once
    call(**kwargs)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\dsession.py", line 306, in worker_collectionfinish
    self.sched.schedule()
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\scheduler\loadscope.py", line 354, in schedule
    self._reschedule(node)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\scheduler\loadscope.py", line 336, in _reschedule
    self._assign_work_unit(node)
  File "C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\xdist\scheduler\loadscope.py", line 275, in _assign_work_unit
    worker_collection = self.registered_collections[node]
```

### 5. `tests.app.test_config_wiring.TestConfigWiring.test_autostart_disabled_when_config_false`

- Legs: windows-2022-3.11, windows-2022-3.13
- Location: `(unknown location)`

```
(no error line)

failed on setup with "worker 'gw0' crashed while running 'tests/app/test_config_wiring.py::TestConfigWiring::test_autostart_disabled_when_config_false'"
worker 'gw0' crashed while running 'tests/app/test_config_wiring.py::TestConfigWiring::test_autostart_disabled_when_config_false'
```

### 6. `tests.app.test_lifecycle.TestStartupResilience.test_startup_survives_model_load_exception`

- Legs: windows-2022-3.11
- Location: `(unknown location)`

```
(no error line)

failed on setup with "worker 'gw2' crashed while running 'tests/app/test_lifecycle.py::TestStartupResilience::test_startup_survives_model_load_exception'"
worker 'gw2' crashed while running 'tests/app/test_lifecycle.py::TestStartupResilience::test_startup_survives_model_load_exception'
```

### 7. `tests.app.test_lifecycle.TestAppStartupIntegration.test_tray_icon_created_on_start`

- Legs: windows-2022-3.12
- Location: `(unknown location)`

```
(no error line)

failed on setup with "worker 'gw1' crashed while running 'tests/app/test_lifecycle.py::TestAppStartupIntegration::test_tray_icon_created_on_start'"
worker 'gw1' crashed while running 'tests/app/test_lifecycle.py::TestAppStartupIntegration::test_tray_icon_created_on_start'
```
