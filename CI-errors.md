# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**5 failing/errored tests** across 4 matrix legs.

### 1. `tests.clipboard.win32.test_win32_send_ctrl_v.TestInputStructLayout.test_input_union_carries_all_three_branches`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/clipboard/win32/test_win32_send_ctrl_v.py:224`

```
+    where <built-in function sizeof> = ctypes.sizeof

AssertionError: the INPUT union must be as wide as MOUSEINPUT (32 bytes on x64); got 48 -- SendInput rejects the batch
assert 48 == 32
 +  where 48 = <built-in function sizeof>(<class 'voice_typer.server.clipboard.windows.InputUnion'>)
 +    where <built-in function sizeof> = ctypes.sizeof
tests/clipboard/win32/test_win32_send_ctrl_v.py:224: in test_input_union_carries_all_three_branches
    assert ctypes.sizeof(InputUnion) == 32, (
E   AssertionError: the INPUT union must be as wide as MOUSEINPUT (32 bytes on x64); got 48 -- SendInput rejects the batch
E   assert 48 == 32
E    +  where 48 = <built-in function sizeof>(<class 'voice_typer.server.clipboard.windows.InputUnion'>)
E    +    where <built-in function sizeof> = ctypes.sizeof
```

### 2. `tests.clipboard.win32.test_win32_send_ctrl_v.TestInputStructLayout.test_input_size_matches_win32`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/clipboard/win32/test_win32_send_ctrl_v.py:233`

```
+    where <built-in function sizeof> = ctypes.sizeof

AssertionError: sizeof(INPUT) must be 40 on this pointer width; got 56 -- SendInput returns 0
assert 56 == 40
 +  where 56 = <built-in function sizeof>(<class 'voice_typer.server.clipboard.windows.INPUT'>)
 +    where <built-in function sizeof> = ctypes.sizeof
tests/clipboard/win32/test_win32_send_ctrl_v.py:233: in test_input_size_matches_win32
    assert ctypes.sizeof(INPUT) == expected, (
E   AssertionError: sizeof(INPUT) must be 40 on this pointer width; got 56 -- SendInput returns 0
E   assert 56 == 40
E    +  where 56 = <built-in function sizeof>(<class 'voice_typer.server.clipboard.windows.INPUT'>)
E    +    where <built-in function sizeof> = ctypes.sizeof
```

### 3. `tests.clipboard.win32.test_win32_send_ctrl_v.TestInputStructLayout.test_sendinput_receives_the_real_struct_size`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/clipboard/win32/test_win32_send_ctrl_v.py:249`

```
assert 56 == 40

assert 56 == 40
tests/clipboard/win32/test_win32_send_ctrl_v.py:249: in test_sendinput_receives_the_real_struct_size
    assert mock_user32.SendInput.call_args[0][2] == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
E   assert 56 == 40
```

### 4. `tests.test_tts_runtimes.test_install_rejects_absolute_member_path`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_tts_runtimes.py:70`

```
Failed: DID NOT RAISE TtsError

Failed: DID NOT RAISE TtsError
tests/test_tts_runtimes.py:70: in test_install_rejects_absolute_member_path
    with pytest.raises(TtsError, match="unsafe path"):
E   Failed: DID NOT RAISE TtsError
```

### 5. `tests.providers.test_catalogue_cache.test_a_stale_snapshot_still_serves_the_selected_id`

- Legs: windows-2022-3.11
- Location: `tests/providers/test_catalogue_cache.py:24`

```
+  where False = CatalogueSnapshot(provider='openrouter', models=[{'id': 'old/model', 'domains': ['llm']}], fetched_at=1794740698.807244, ttl_seconds=0).stale

AssertionError: assert False is True
 +  where False = CatalogueSnapshot(provider='openrouter', models=[{'id': 'old/model', 'domains': ['llm']}], fetched_at=1794740698.807244, ttl_seconds=0).stale
tests\providers\test_catalogue_cache.py:24: in test_a_stale_snapshot_still_serves_the_selected_id
    assert snap.stale is True
E   AssertionError: assert False is True
E    +  where False = CatalogueSnapshot(provider='openrouter', models=[{'id': 'old/model', 'domains': ['llm']}], fetched_at=1794740698.807244, ttl_seconds=0).stale
```
