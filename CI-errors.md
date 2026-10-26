# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**3 failing/errored tests** across 8 matrix legs.

### 1. `tests.test_stream_lifecycle_module.TestTransientOpenRetry.test_transient_failure_retries_same_candidate`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_stream_lifecycle_module.py:270`

```
- ]

assert [] == [0.25]

  Right contains one more item: 0.25

  Full diff:
  + []
  - [
  -     0.25,
  - ]
tests/test_stream_lifecycle_module.py:270: in test_transient_failure_retries_same_candidate
    assert sleeps == [0.25]
E   assert [] == [0.25]
E
E     Right contains one more item: 0.25
E
E     Full diff:
E     + []
E     - [
E     -     0.25,
E     - ]
```

### 2. `tests.test_stream_lifecycle_module.TestPortAudioReinitRetry.test_reinit_then_configured_retry_succeeds`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_stream_lifecycle_module.py:781`

```
assert None == 24

assert None == 24
tests/test_stream_lifecycle_module.py:781: in test_reinit_then_configured_retry_succeeds
    assert selected == 24
E   assert None == 24
```

### 3. `tests.test_stream_lifecycle_module.TestPortAudioReinitRetry.test_reinit_failure_falls_through_without_retry`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_stream_lifecycle_module.py:814`

```
+  where 1 = len([{'samplerate': 16000, 'channels': 1, 'dtype': <class 'numpy.float32'>, 'device': 24, ...}])

AssertionError: assert 1 == 2
 +  where 1 = len([{'samplerate': 16000, 'channels': 1, 'dtype': <class 'numpy.float32'>, 'device': 24, ...}])
tests/test_stream_lifecycle_module.py:814: in test_reinit_failure_falls_through_without_retry
    assert len(attempts) == 2
E   AssertionError: assert 1 == 2
E    +  where 1 = len([{'samplerate': 16000, 'channels': 1, 'dtype': <class 'numpy.float32'>, 'device': 24, ...}])
```
