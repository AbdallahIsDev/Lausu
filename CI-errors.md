# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**1 failing/errored tests** across 9 matrix legs.

### 1. `tests.handlers.test_error_envelope_code_field.TestHandlerFilesUseHelper.test_every_handler_file_uses_a_standardized_helper`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/handlers/test_error_envelope_code_field.py:130`

```
assert not ['media_job_runners.py']

AssertionError: every handler file must use either _respond_with_error or _error_response; missing: ['media_job_runners.py']
assert not ['media_job_runners.py']
tests/handlers/test_error_envelope_code_field.py:130: in test_every_handler_file_uses_a_standardized_helper
    assert not missing, (
E   AssertionError: every handler file must use either _respond_with_error or _error_response; missing: ['media_job_runners.py']
E   assert not ['media_job_runners.py']
```
