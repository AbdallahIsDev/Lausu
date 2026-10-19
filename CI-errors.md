# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**1 failing/errored tests** across 1 matrix legs.

### 1. `tests.test_audio_filter_reset_zero_buffers.test_streaming_resampler_chunk_cost_within_budget`

- Legs: windows-2022-3.10
- Location: `tests/test_audio_filter_reset_zero_buffers.py:173`

```
assert 14.833699999940109 < 10.0

AssertionError: resampler too slow: best 14.8 ms/chunk (mean 18.7)
assert 14.833699999940109 < 10.0
tests\test_audio_filter_reset_zero_buffers.py:173: in test_streaming_resampler_chunk_cost_within_budget
    assert best_ms < 10.0, f"resampler too slow: best {best_ms:.1f} ms/chunk (mean {mean_ms:.1f})"
E   AssertionError: resampler too slow: best 14.8 ms/chunk (mean 18.7)
E   assert 14.833699999940109 < 10.0
```
