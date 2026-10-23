# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**3 failing/errored tests** across 2 matrix legs.

### 1. `tests.test_mic_level_push_event.TestMicLevelPublishedWhenActive.test_payload_values_match_chunk`

- Legs: macos-14-3.10
- Location: `tests/test_mic_level_push_event.py:178`

```
+  where 0.7242014169692994 = abs((0.0757985830307007 - 0.8))

AssertionError: pushed level 0.0757985830307007 != display-gain value 0.8
assert 0.7242014169692994 < 1e-06
 +  where 0.7242014169692994 = abs((0.0757985830307007 - 0.8))
tests/test_mic_level_push_event.py:178: in test_payload_values_match_chunk
    assert abs(evt["data"]["level"] - expected_level) < 1e-6, (
E   AssertionError: pushed level 0.0757985830307007 != display-gain value 0.8
E   assert 0.7242014169692994 < 1e-06
E    +  where 0.7242014169692994 = abs((0.0757985830307007 - 0.8))
```

### 2. `tests.test_crash_recovery_del_extraction.TestDelPreservesOriginalContract.test_del_is_noop_when_entries_empty_post_clear`

- Legs: windows-2022-3.10
- Location: `tests/conftest.py:576`

```
KeyError: 6096

failed on setup with "KeyError: 6096"
C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\site-packages\pytest_asyncio\plugin.py:926: in pytest_fixture_setup
    return (yield)
tests\conftest.py:576: in _isolate_shared_hf_cache
    monkeypatch.setattr(
C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
E   KeyError: 6096
```

### 3. `tests.test_dictation_pipeline_stage_timer.TestTimedStageContextManager.test_records_positive_duration_in_dict`

- Legs: windows-2022-3.10
- Location: `tests/test_dictation_pipeline_stage_timer.py:24`

```
assert 1.0 < 0.6158000001050823

assert 1.0 < 0.6158000001050823
tests\test_dictation_pipeline_stage_timer.py:24: in test_records_positive_duration_in_dict
    assert 1.0 < timings["transcribe"] < 1000.0
E   assert 1.0 < 0.6158000001050823
```
