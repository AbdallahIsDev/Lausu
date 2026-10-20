# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**1 failing/errored tests** across 1 matrix legs.

### 1. `tests.test_crash_recovery_deque.TestEntriesIsBoundedDeque.test_entries_maxlen_matches_constant`

- Legs: ubuntu-22.04-3.10
- Location: `tests/conftest.py:547`

```
KeyError: 140221933169536

failed on setup with "KeyError: 140221933169536"
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/site-packages/pytest_asyncio/plugin.py:926: in pytest_fixture_setup
    return (yield)
tests/conftest.py:547: in _isolate_user_config_dir
    patch_config_dir_refs(monkeypatch, tmp_path)
tests/fixtures/config_helpers.py:12: in patch_config_dir_refs
    monkeypatch.setattr("voice_typer.server.config._config_dir", lambda: path)
/opt/hostedtoolcache/Python/3.10.22/x64/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
E   KeyError: 140221933169536
```
