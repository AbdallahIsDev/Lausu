# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**3 failing/errored tests** across 5 matrix legs.

### 1. `tests.test_tts_runtimes.test_install_rejects_absolute_member_path`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_tts_runtimes.py:70`

```
Failed: DID NOT RAISE TtsError

Failed: DID NOT RAISE TtsError
tests/test_tts_runtimes.py:70: in test_install_rejects_absolute_member_path
    with pytest.raises(TtsError, match="unsafe path"):
E   Failed: DID NOT RAISE TtsError
```

### 2. `tests.providers.test_catalogue_cache.test_a_stale_snapshot_still_serves_the_selected_id`

- Legs: windows-2022-3.11, windows-2022-3.12
- Location: `tests/providers/test_catalogue_cache.py:24`

```
+  where False = CatalogueSnapshot(provider='openrouter', models=[{'id': 'old/model', 'domains': ['llm']}], fetched_at=1793737821.1870565, ttl_seconds=0).stale

AssertionError: assert False is True
 +  where False = CatalogueSnapshot(provider='openrouter', models=[{'id': 'old/model', 'domains': ['llm']}], fetched_at=1793737821.1870565, ttl_seconds=0).stale
tests\providers\test_catalogue_cache.py:24: in test_a_stale_snapshot_still_serves_the_selected_id
    assert snap.stale is True
E   AssertionError: assert False is True
E    +  where False = CatalogueSnapshot(provider='openrouter', models=[{'id': 'old/model', 'domains': ['llm']}], fetched_at=1793737821.1870565, ttl_seconds=0).stale
```

### 3. `tests.test_tauri_e2e_checklist.TestLogCleanliness.test_happy_path_flows_are_log_clean`

- Legs: windows-2022-3.12
- Location: `tests/test_tauri_e2e_checklist.py:753`

```
#x1B[0m#x1B[92m+ ]#x1B[39;49;00m#x1B[90m#x1B[39;49;00m

AssertionError: WARNING voice_typer.server.microphone_watcher._windows: [MIC-WATCHER] RegisterClassExW failed (err=0), falling back to TTL polling
assert [<LogRecord: ...TTL polling">] == []

[+7 more lines; full report in element text]
tests\test_tauri_e2e_checklist.py:753: in test_happy_path_flows_are_log_clean
    assert offenders == [], "\n".join(f"{r.levelname} {r.name}: {r.message}" for r in offenders)
E   AssertionError: WARNING voice_typer.server.microphone_watcher._windows: [MIC-WATCHER] RegisterClassExW failed (err=0), falling back to TTL polling
E   assert [<LogRecord: ...TTL polling">] == []
E
E     Left contains one more item: #x1B[0m<LogRecord: voice_typer.server.microphone_watcher._windows, #x1B[94m30#x1B[39;49;00m, D:\a\Lausu\Lausu\voice_typer\server\microphone_watcher\_windows.py, #x1B[94m121#x1B[39;49;00m, #x1B[33m"#x1B[39;49;00m#x1B[33m[MIC-WATCHER] RegisterClassExW failed (err=#x1B[39;49;00m#x1B[33m%d#x1B[39;49;00m#x1B[33m), falling back to TTL polling#x1B[39;49;00m#x1B[33m"#x1B[39;49;00m>#x1B[90m#x1B[39;49;00m
E
E     Full diff: (-: missing in left side, +: extra in left side)
E     #x1B[0m#x1B[91m- []#x1B[39;49;00m#x1B[90m#x1B[39;49;00m
E     #x1B[0m#x1B[92m+ [#x1B[39;49;00m#x1B[90m#x1B[39;49;00m
E     #x1B[0m#x1B[92m+     <LogRecord: voice_typer.server.microphone_watcher._windows, 30, D:\a\Lausu\Lausu\voice_typer\server\microphone_watcher\_windows.py, 121, "[MIC-WATCHER] RegisterClassExW failed (err=%d), falling back to TTL polling">,#x1B[39;49;00m#x1B[90m#x1B[39;49;00m
E     #x1B[0m#x1B[92m+ ]#x1B[39;49;00m#x1B[90m#x1B[39;49;00m
```
