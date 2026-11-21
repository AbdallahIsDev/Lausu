# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.
> Source SHA: `991e0c4c2ece0a1407c27d7b305e441cc27a3da2`

**40 failing/errored tests** across 3 matrix legs.

### 1. `tests.packaging.test_third_party_notices_generated.test_artifact_is_deterministic_and_handwritten_sections_survive`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/packaging/test_third_party_notices_generated.py:77`

```
| zstandard _cffi.pyd / backend_c.pyd | PRESENT | PRESENT; no dist-info or licence text. Upstream https://github.com/facebook/zstd |

AssertionError: committed artifact is stale; rerun the generator
assert '\n## Consoli...ok/zstd |\n\n' == '\n## Consoli...ok/zstd |\n\n'


    ## Consolidated Windows-installer inventory (generated)

    Regenerate with `python scripts/generate_third_party_notices.py` (`--check` verifies
    the committed artifact). Deterministic, offline, stdlib-only; no legal conclusions.
    The hand-written Lausu / yt-dlp / PyAV / FFmpeg / RNNoise / pystray / Deno / DPDFNet2
[+1644 more lines; full report in element text]
tests/packaging/test_third_party_notices_generated.py:77: in test_artifact_is_deterministic_and_handwritten_sections_survive
    assert text.split(module.BEGIN, 1)[1].split(module.END, 1)[0] == rendered.split(
E   AssertionError: committed artifact is stale; rerun the generator
E   assert '\n## Consoli...ok/zstd |\n\n' == '\n## Consoli...ok/zstd |\n\n'
E
E
E       ## Consolidated Windows-installer inventory (generated)
E
E       Regenerate with `python scripts/generate_third_party_notices.py` (`--check` verifies
E       the committed artifact). Deterministic, offline, stdlib-only; no legal conclusions.
E       The hand-written Lausu / yt-dlp / PyAV / FFmpeg / RNNoise / pystray / Deno / DPDFNet2
E       sections outside these markers are preserved verbatim by regeneration.
E
E       ### Evidence and scope
E
E       - Shipping is established from the Windows bundle config and the extracted
E         onefile/installed folders, NEVER from a lockfile alone.
E       - `requirements-lock.txt`: 82 pinned distributions (read-only).
E       - `package-lock.json`: production closure of 138 packages (licenses: 0BSD × 1, Apache-2.0 × 2, ISC × 14, MIT × 119, MIT and ISC × 1, Unlicense × 1).
E       - `Cargo.lock`: 524 package entries across all targets (Windows graph audited as 310 crates).
E     - - Installed dist-info metadata: 0 distributions read, indicative only.
E     ?                                 ^
E     + - Installed dist-info metadata: 148 distributions read, indicative only.
E     ?                                 ^^^
E       - Build drift is real: shipped python312.dll is 3.12.10 while dev .venv is 3.13.7;
E         shipped onnxruntime.dll is 1.28.0 while dist-info says 1.29.0. Local metadata never
E         overrides shipped-file evidence. UNVERIFIED means no local licence file was found.
E
```

### 2. `tests.plugins.test_extension_install.TestInstallAuthority.test_one_profile_from_one_authority[tools.internal_plugins.anthropic_stt.plugin]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_extension_install.py:44`

```
FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/anthropic_stt/config.json'

FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/anthropic_stt/config.json'
tests/plugins/test_extension_install.py:44: in test_one_profile_from_one_authority
    descriptor = json.loads((module.HERE / "config.json").read_text(encoding="utf-8"))
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/pathlib.py:1058: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/pathlib.py:1044: in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/anthropic_stt/config.json'
```

### 3. `tests.plugins.test_extension_install.TestInstallAuthority.test_one_profile_from_one_authority[tools.internal_plugins.google_stt.plugin]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_extension_install.py:44`

```
FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/google_stt/config.json'

FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/google_stt/config.json'
tests/plugins/test_extension_install.py:44: in test_one_profile_from_one_authority
    descriptor = json.loads((module.HERE / "config.json").read_text(encoding="utf-8"))
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/pathlib.py:1058: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/pathlib.py:1044: in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/google_stt/config.json'
```

### 4. `tests.plugins.test_extension_install.TestInstallAuthority.test_one_port_and_one_token_store[tools.internal_plugins.anthropic_stt.plugin-claude]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_extension_install.py:68`

```
+    where is_file = (PosixPath('/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge') / 'token.json').is_file

AssertionError: assert False
 +  where False = is_file()
 +    where is_file = (PosixPath('/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge') / 'token.json').is_file
tests/plugins/test_extension_install.py:68: in test_one_port_and_one_token_store
    assert (BRIDGE / "token.json").is_file()
E   AssertionError: assert False
E    +  where False = is_file()
E    +    where is_file = (PosixPath('/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge') / 'token.json').is_file
```

### 5. `tests.plugins.test_extension_install.TestInstallAuthority.test_one_port_and_one_token_store[tools.internal_plugins.google_stt.plugin-gemini]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_extension_install.py:68`

```
+    where is_file = (PosixPath('/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge') / 'token.json').is_file

AssertionError: assert False
 +  where False = is_file()
 +    where is_file = (PosixPath('/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge') / 'token.json').is_file
tests/plugins/test_extension_install.py:68: in test_one_port_and_one_token_store
    assert (BRIDGE / "token.json").is_file()
E   AssertionError: assert False
E    +  where False = is_file()
E    +    where is_file = (PosixPath('/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge') / 'token.json').is_file
```

### 6. `tests.plugins.test_extension_install.TestVerifierLiveRegistration.test_live_bridge_counts_as_registered_before_chrome_flushes_prefs`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_extension_install.py:192`

```
FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge/extension/generated/config.js'

FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge/extension/generated/config.js'
tests/plugins/test_extension_install.py:192: in test_live_bridge_counts_as_registered_before_chrome_flushes_prefs
    (target / "generated" / "config.js").write_bytes(source_cfg.read_bytes())
                                                     ^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/pathlib.py:1050: in read_bytes
    with self.open(mode='rb') as f:
         ^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/pathlib.py:1044: in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge/extension/generated/config.js'
```

### 7. `tests.plugins.test_extension_install.TestVerifierOutput.test_healthy_case`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_extension_install.py:225`

```
FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge/extension/generated/config.js'

FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge/extension/generated/config.js'
tests/plugins/test_extension_install.py:225: in test_healthy_case
    (target / "generated" / "config.js").write_bytes(source_cfg.read_bytes())
                                                     ^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/pathlib.py:1050: in read_bytes
    with self.open(mode='rb') as f:
         ^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/pathlib.py:1044: in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/Lausu/Lausu/tools/internal_plugins/_common/bridge/extension/generated/config.js'
```

### 8. `tests.plugins.test_shared_bridge_contract.TestOneSharedAuthority.test_descriptor_and_client[tools.internal_plugins.anthropic_stt.plugin-anthropic_stt-claude-https://claude.ai/new]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_shared_bridge_contract.py:43`

```
? ++ ^^  ++++

AssertionError: assert 'C:/Users/11/...e-stt-profile' == '/home/runner...e-stt-profile'

  - /home/runner/AppData/Local/voice-typer-internal-plugins/google-stt-profile
  ?  ^^^^^^^^^
  + C:/Users/11/AppData/Local/voice-typer-internal-plugins/google-stt-profile
  ? ++ ^^  ++++
tests/plugins/test_shared_bridge_contract.py:43: in test_descriptor_and_client
    assert descriptor["profileDir"] == chrome_profile.PROFILE_DIR
E   AssertionError: assert 'C:/Users/11/...e-stt-profile' == '/home/runner...e-stt-profile'
E
E     - /home/runner/AppData/Local/voice-typer-internal-plugins/google-stt-profile
E     ?  ^^^^^^^^^
E     + C:/Users/11/AppData/Local/voice-typer-internal-plugins/google-stt-profile
E     ? ++ ^^  ++++
```

### 9. `tests.plugins.test_shared_bridge_contract.TestOneSharedAuthority.test_descriptor_and_client[tools.internal_plugins.google_stt.plugin-google_stt-gemini-https://gemini.google.com/app]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/plugins/test_shared_bridge_contract.py:43`

```
? ++ ^^  ++++

AssertionError: assert 'C:/Users/11/...e-stt-profile' == '/home/runner...e-stt-profile'

  - /home/runner/AppData/Local/voice-typer-internal-plugins/google-stt-profile
  ?  ^^^^^^^^^
  + C:/Users/11/AppData/Local/voice-typer-internal-plugins/google-stt-profile
  ? ++ ^^  ++++
tests/plugins/test_shared_bridge_contract.py:43: in test_descriptor_and_client
    assert descriptor["profileDir"] == chrome_profile.PROFILE_DIR
E   AssertionError: assert 'C:/Users/11/...e-stt-profile' == '/home/runner...e-stt-profile'
E
E     - /home/runner/AppData/Local/voice-typer-internal-plugins/google-stt-profile
E     ?  ^^^^^^^^^
E     + C:/Users/11/AppData/Local/voice-typer-internal-plugins/google-stt-profile
E     ? ++ ^^  ++++
```

### 10. `tests.tauri.bridge_parity.test_host_surface_parity.TestCommandAllowlistParity.test_command_allowlists_stay_in_lockstep_across_python_and_rust`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/bridge_parity/test_host_surface_parity.py:347`

```
assert not ['bubble_host_hidden']

AssertionError: commands in the Python registry but not the Rust allowlist (add to allowlist.rs or DOCUMENTED_COMMAND_ASYMMETRY): ['bubble_host_hidden']
assert not ['bubble_host_hidden']
tests/tauri/bridge_parity/test_host_surface_parity.py:347: in test_command_allowlists_stay_in_lockstep_across_python_and_rust
    assert not unexpected_registry_only, (
E   AssertionError: commands in the Python registry but not the Rust allowlist (add to allowlist.rs or DOCUMENTED_COMMAND_ASYMMETRY): ['bubble_host_hidden']
E   assert not ['bubble_host_hidden']
```

### 11. `tests.tauri.mig19.test_phase4_validation.test_command_contract_is_frozen_no_untested_additions`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig19/test_phase4_validation.py:727`

```
Do NOT silently grow the wire contract.

Failed: ADR-0020 §16: _COMMAND_REGISTRY contains commands NOT in the frozen 68-command table AND NOT in the KNOWN_UNDOCUMENTED_COMMANDS allowlist:
  bubble_host_hidden

To resolve, EITHER:
  (a) Remove the command from _COMMAND_REGISTRY (it was added without an ADR addendum), OR
  (b) Add it to EXPECTED_COMMANDS in this test + add an ADR-0020 addendum + add a _validate_dict_payload schema + add a test in tests/test_ipc_dispatch_errors.py, OR
[+2 more lines; full report in element text]
tests/tauri/mig19/test_phase4_validation.py:727: in test_command_contract_is_frozen_no_untested_additions
    pytest.fail(
E   Failed: ADR-0020 §16: _COMMAND_REGISTRY contains commands NOT in the frozen 68-command table AND NOT in the KNOWN_UNDOCUMENTED_COMMANDS allowlist:
E     bubble_host_hidden
E
E   To resolve, EITHER:
E     (a) Remove the command from _COMMAND_REGISTRY (it was added without an ADR addendum), OR
E     (b) Add it to EXPECTED_COMMANDS in this test + add an ADR-0020 addendum + add a _validate_dict_payload schema + add a test in tests/test_ipc_dispatch_errors.py, OR
E     (c) Add it to KNOWN_UNDOCUMENTED_COMMANDS in this test with a comment naming the PR + reason (this is the explicit-gap path; the test_known_undocumented_commands_are_reported test below will then keep the entry in sync with reality).
E   Do NOT silently grow the wire contract.
```

### 12. `tests.tauri.mig19.test_phase4_validation.test_known_undocumented_commands_are_reported`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig19/test_phase4_validation.py:769`

```
bubble_host_hidden

Failed: Commands in _COMMAND_REGISTRY but NOT in EXPECTED_COMMANDS and NOT in KNOWN_UNDOCUMENTED_COMMANDS (add to KNOWN_UNDOCUMENTED_COMMANDS with a comment, OR close the gap by adding to EXPECTED_COMMANDS + ADR addendum):
  bubble_host_hidden
tests/tauri/mig19/test_phase4_validation.py:769: in test_known_undocumented_commands_are_reported
    pytest.fail("\n\n".join(msg_parts))
E   Failed: Commands in _COMMAND_REGISTRY but NOT in EXPECTED_COMMANDS and NOT in KNOWN_UNDOCUMENTED_COMMANDS (add to KNOWN_UNDOCUMENTED_COMMANDS with a comment, OR close the gap by adding to EXPECTED_COMMANDS + ADR addendum):
E     bubble_host_hidden
```

### 13. `tests.test_architecture_doc_accuracy.test_main_rs_line_count_is_269`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_architecture_doc_accuracy.py:263`

```
assert 271 == 269

AssertionError: src-tauri/src/main.rs must be 269 lines (actual: 271). Update the doc + this test together.
assert 271 == 269
tests/test_architecture_doc_accuracy.py:263: in test_main_rs_line_count_is_269
    assert actual == 269, (
E   AssertionError: src-tauri/src/main.rs must be 269 lines (actual: 271). Update the doc + this test together.
E   assert 271 == 269
```

### 14. `tests.test_crash_recovery_cycle_threading.TestCancellationGuardPrivacyGate.test_enabled_still_writes`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_crash_recovery_cycle_threading.py:84`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_crash_recovery_cycle_threading.py:84: in test_enabled_still_writes
    app._waveform_bubble.hide.assert_called_once()
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 15. `tests.test_doc_command_counts.test_security_md_states_current_counts`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_doc_command_counts.py:34`

```
+      where <built-in method group of re.Match object at 0x7fa0f2c681f0> = <re.Match object; span=(1766, 1788), match='registers 109 handlers'>.group

AssertionError: SECURITY.md documents 109 Python handlers but the actual registry count is 110.
assert 109 == 110
 +  where 109 = int('109')
 +    where '109' = <built-in method group of re.Match object at 0x7fa0f2c681f0>(1)
 +      where <built-in method group of re.Match object at 0x7fa0f2c681f0> = <re.Match object; span=(1766, 1788), match='registers 109 handlers'>.group
tests/test_doc_command_counts.py:34: in test_security_md_states_current_counts
    assert int(m_reg.group(1)) == actual_py, (
E   AssertionError: SECURITY.md documents 109 Python handlers but the actual registry count is 110.
E   assert 109 == 110
E    +  where 109 = int('109')
E    +    where '109' = <built-in method group of re.Match object at 0x7fa0f2c681f0>(1)
E    +      where <built-in method group of re.Match object at 0x7fa0f2c681f0> = <re.Match object; span=(1766, 1788), match='registers 109 handlers'>.group
```

### 16. `tests.test_doc_command_counts.test_features_md_states_command_counts`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_doc_command_counts.py:55`

```
+    where {'ack_cuda_activation', 'add_trusted_endpoint', 'bubble_host_hidden', 'cancel_cuda_download', 'cancel_model_download', 'chat_listen_start', ...} = _command_registry_entries()

AssertionError: FEATURES.md documents 109 commands total for _COMMAND_REGISTRY but the actual count is 110. Update FEATURES.md row #81.
assert 109 == 110
 +  where 109 = int('109')
 +    where '109' = <built-in method group of re.Match object at 0x7fa0f2df9630>(1)
 +      where <built-in method group of re.Match object at 0x7fa0f2df9630> = <re.Match object; span=(18181, 18228), match='_COMMAND_REGISTRY` registers 109 commands total'>.group
[+2 more lines; full report in element text]
tests/test_doc_command_counts.py:55: in test_features_md_states_command_counts
    assert int(m_reg.group(1)) == len(_command_registry_entries()), (
E   AssertionError: FEATURES.md documents 109 commands total for _COMMAND_REGISTRY but the actual count is 110. Update FEATURES.md row #81.
E   assert 109 == 110
E    +  where 109 = int('109')
E    +    where '109' = <built-in method group of re.Match object at 0x7fa0f2df9630>(1)
E    +      where <built-in method group of re.Match object at 0x7fa0f2df9630> = <re.Match object; span=(18181, 18228), match='_COMMAND_REGISTRY` registers 109 commands total'>.group
E    +  and   110 = len({'ack_cuda_activation', 'add_trusted_endpoint', 'bubble_host_hidden', 'cancel_cuda_download', 'cancel_model_download', 'chat_listen_start', ...})
E    +    where {'ack_cuda_activation', 'add_trusted_endpoint', 'bubble_host_hidden', 'cancel_cuda_download', 'cancel_model_download', 'chat_listen_start', ...} = _command_registry_entries()
```

### 17. `tests.test_doc_command_counts.test_contributing_md_states_registry_count`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_doc_command_counts.py:100`

```
+      where <built-in method group of re.Match object at 0x7fa0f2df95a0> = <re.Match object; span=(23942, 23973), match='reuses the 109-command registry'>.group

AssertionError: CONTRIBUTING.md documents 109-command registry but the actual _COMMAND_REGISTRY count is 110. Update the sidecar_ws.py row in CONTRIBUTING.md.
assert 109 == 110
 +  where 109 = int('109')
 +    where '109' = <built-in method group of re.Match object at 0x7fa0f2df95a0>(1)
 +      where <built-in method group of re.Match object at 0x7fa0f2df95a0> = <re.Match object; span=(23942, 23973), match='reuses the 109-command registry'>.group
tests/test_doc_command_counts.py:100: in test_contributing_md_states_registry_count
    assert int(m.group(1)) == actual, (
E   AssertionError: CONTRIBUTING.md documents 109-command registry but the actual _COMMAND_REGISTRY count is 110. Update the sidecar_ws.py row in CONTRIBUTING.md.
E   assert 109 == 110
E    +  where 109 = int('109')
E    +    where '109' = <built-in method group of re.Match object at 0x7fa0f2df95a0>(1)
E    +      where <built-in method group of re.Match object at 0x7fa0f2df95a0> = <re.Match object; span=(23942, 23973), match='reuses the 109-command registry'>.group
```

### 18. `tests.test_history_db_trigram_guard.TestMigrationSkippedOnOldSQLite.test_search_degrades_to_like_without_trigram_table`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_history_db_trigram_guard.py:88`

```
+  where False = any(<generator object TestMigrationSkippedOnOldSQLite.test_search_degrades_to_like_without_trigram_table.<locals>.<genexpr> at 0x7fa0b03af100>)

AssertionError: CJK LIKE fallback broken: []
assert False
 +  where False = any(<generator object TestMigrationSkippedOnOldSQLite.test_search_degrades_to_like_without_trigram_table.<locals>.<genexpr> at 0x7fa0b03af100>)
tests/test_history_db_trigram_guard.py:88: in test_search_degrades_to_like_without_trigram_table
    assert any("今天你好吗" in t for t in texts), f"CJK LIKE fallback broken: {texts}"
E   AssertionError: CJK LIKE fallback broken: []
E   assert False
E    +  where False = any(<generator object TestMigrationSkippedOnOldSQLite.test_search_degrades_to_like_without_trigram_table.<locals>.<genexpr> at 0x7fa0b03af100>)
```

### 19. `tests.test_history_db_trigram_guard.TestMigrationSkippedOnOldSQLite.test_modern_sqlite_still_migrates_to_v5`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_history_db_trigram_guard.py:107`

```
+  where 6 = int('6')

AssertionError: assert 6 == 5
 +  where 6 = int('6')
tests/test_history_db_trigram_guard.py:107: in test_modern_sqlite_still_migrates_to_v5
    assert int(row[0]) == 5
E   AssertionError: assert 6 == 5
E    +  where 6 = int('6')
```

### 20. `tests.test_ipc_server.TestCommandCostsContract.test_every_registered_command_has_explicit_cost`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_ipc_server.py:818`

```
assert not {'bubble_host_hidden'}

AssertionError: Commands registered in _COMMAND_REGISTRY but missing from COMMAND_COSTS: ['bubble_host_hidden']. Each registered command MUST have an explicit cost entry, add them to COMMAND_COSTS in voice_typer/server/ipc/rate_limiter.py. Cost tiers: 1=cheap read, 2=small write, 3=compute, 5=starts long-lived resource, 10=heavy I/O, 20=very heavy, 50=network-saturating download.
assert not {'bubble_host_hidden'}
tests/test_ipc_server.py:818: in test_every_registered_command_has_explicit_cost
    assert not missing, (
E   AssertionError: Commands registered in _COMMAND_REGISTRY but missing from COMMAND_COSTS: ['bubble_host_hidden']. Each registered command MUST have an explicit cost entry, add them to COMMAND_COSTS in voice_typer/server/ipc/rate_limiter.py. Cost tiers: 1=cheap read, 2=small write, 3=compute, 5=starts long-lived resource, 10=heavy I/O, 20=very heavy, 50=network-saturating download.
E   assert not {'bubble_host_hidden'}
```

### 21. `tests.test_ipc_server.TestRegistryExtraction.test_registry_dict_same_keys_and_values_as_before`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_ipc_server.py:2062`

```
+    where {'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...} = <module 'voice_typer.server.ipc.registry' from '/home/runner/work/Lausu/Lausu/voice_typer/server/ipc/registry.py'>._COMMAND_REGISTRY

AssertionError: registry._COMMAND_REGISTRY must contain 109 entries (105 forwarded in the Rust allowlist + shutdown + tray_click python-only + heartbeat + relaunch_ack host-dispatched); got 110. If the count drifted, update this test together with the registry + the TS/Rust allowlists.
assert 110 == 109
 +  where 110 = len({'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...})
[+1 more line; full report in element text]
tests/test_ipc_server.py:2062: in test_registry_dict_same_keys_and_values_as_before
    assert len(registry._COMMAND_REGISTRY) == 109, (
E   AssertionError: registry._COMMAND_REGISTRY must contain 109 entries (105 forwarded in the Rust allowlist + shutdown + tray_click python-only + heartbeat + relaunch_ack host-dispatched); got 110. If the count drifted, update this test together with the registry + the TS/Rust allowlists.
E   assert 110 == 109
E    +  where 110 = len({'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...})
E    +    where {'get_status': '_handle_get_status', 'toggle_dictation': '_handle_toggle_dictation', 'undo_last': '_handle_undo_last', 'repaste_last': '_handle_repaste_last', ...} = <module 'voice_typer.server.ipc.registry' from '/home/runner/work/Lausu/Lausu/voice_typer/server/ipc/registry.py'>._COMMAND_REGISTRY
```

### 22. `tests.test_ipc_server.TestRegistryExtraction.test_python_only_commands_unchanged`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_ipc_server.py:2075`

```
})

AssertionError: registry._PYTHON_ONLY_COMMANDS must be frozenset({'shutdown', 'tray_click'}); got frozenset({'tray_click', 'shutdown', 'bubble_host_hidden'}).
assert frozenset({'s...'tray_click'}) == frozenset({'b...'tray_click'})

  Extra items in the right set:
  'bubble_host_hidden'

  Full diff: (-: missing in left side, +: extra in left side)
    frozenset({
  -     'bubble_host_hidden',
        'shutdown',
        'tray_click',
    })
tests/test_ipc_server.py:2075: in test_python_only_commands_unchanged
    assert frozenset({"shutdown", "tray_click"}) == registry._PYTHON_ONLY_COMMANDS, (
E   AssertionError: registry._PYTHON_ONLY_COMMANDS must be frozenset({'shutdown', 'tray_click'}); got frozenset({'tray_click', 'shutdown', 'bubble_host_hidden'}).
E   assert frozenset({'s...'tray_click'}) == frozenset({'b...'tray_click'})
E
E     Extra items in the right set:
E     'bubble_host_hidden'
E
E     Full diff: (-: missing in left side, +: extra in left side)
E       frozenset({
E     -     'bubble_host_hidden',
E           'shutdown',
E           'tray_click',
E       })
```

### 23. `tests.test_media_ffmpeg_decoder.TestSafety.test_exception_in_consumer_still_reaps`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_media_ffmpeg_decoder.py:387`

```
voice_typer.server.media_ingest.errors.MediaIngestError: Audio decoding is unavailable. Reinstall the app to restore it.

voice_typer.server.media_ingest.errors.MediaIngestError: Audio decoding is unavailable. Reinstall the app to restore it.
tests/test_media_ffmpeg_decoder.py:387: in test_exception_in_consumer_still_reaps
    consume()
tests/test_media_ffmpeg_decoder.py:382: in consume
    for chunk in gen:
voice_typer/server/media_ingest/decoder.py:195: in decode_chunks
    raise MediaIngestError(
E   voice_typer.server.media_ingest.errors.MediaIngestError: Audio decoding is unavailable. Reinstall the app to restore it.
```

### 24. `tests.test_media_ffmpeg_decoder.TestBinaryResolver.test_shipped_binary_beats_path`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_media_ffmpeg_decoder.py:719`

```
+ /path/ffmpeg

AssertionError: assert '/path/ffmpeg' == '/tmp/pytest-..._path0/ffmpeg'

  - /tmp/pytest-of-runner/pytest-1/popen-gw0/test_shipped_binary_beats_path0/ffmpeg
  + /path/ffmpeg
tests/test_media_ffmpeg_decoder.py:719: in test_shipped_binary_beats_path
    assert pair.ffmpeg == str(tmp_path / ("ffmpeg" + ext))
E   AssertionError: assert '/path/ffmpeg' == '/tmp/pytest-..._path0/ffmpeg'
E
E     - /tmp/pytest-of-runner/pytest-1/popen-gw0/test_shipped_binary_beats_path0/ffmpeg
E     + /path/ffmpeg
```

### 25. `tests.test_media_ingest_aux.TestDecoderReal.test_wav_yields_16k_mono_float32_chunks`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_media_ingest_aux.py:41`

```
voice_typer.server.media_ingest.errors.MediaIngestError: Audio decoding is unavailable. Reinstall the app to restore it.

voice_typer.server.media_ingest.errors.MediaIngestError: Audio decoding is unavailable. Reinstall the app to restore it.
tests/test_media_ingest_aux.py:41: in test_wav_yields_16k_mono_float32_chunks
    chunks = list(decoder.decode_chunks(str(wav)))
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
voice_typer/server/media_ingest/decoder.py:195: in decode_chunks
    raise MediaIngestError(
E   voice_typer.server.media_ingest.errors.MediaIngestError: Audio decoding is unavailable. Reinstall the app to restore it.
```

### 26. `tests.test_media_ingest_aux.TestDurationProbe.test_reads_container_duration_and_fails_soft`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_media_ingest_aux.py:343`

```
assert None is not None

assert None is not None
tests/test_media_ingest_aux.py:343: in test_reads_container_duration_and_fails_soft
    assert probed is not None
E   assert None is not None
```

### 27. `tests.test_module_split_reexports_wave3.TestConfigApplierFacadeReexports.test_moved_symbols_resolve_to_the_sibling_modules`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_module_split_reexports_wave3.py:308`

```
AttributeError: module 'voice_typer.server.config_applier' has no attribute '_TrayLeftClickHandler'

AttributeError: module 'voice_typer.server.config_applier' has no attribute '_TrayLeftClickHandler'
tests/test_module_split_reexports_wave3.py:308: in test_moved_symbols_resolve_to_the_sibling_modules
    config_applier._TrayLeftClickHandler
E   AttributeError: module 'voice_typer.server.config_applier' has no attribute '_TrayLeftClickHandler'
```

### 28. `tests.test_module_split_reexports_wave3.TestConfigApplierFacadeReexports.test_handlers_take_side_effect_context_no_facade_global`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_module_split_reexports_wave3.py:344`

```
AttributeError: module 'voice_typer.server.config_applier_handlers' has no attribute '_TrayLeftClickHandler'

AttributeError: module 'voice_typer.server.config_applier_handlers' has no attribute '_TrayLeftClickHandler'
tests/test_module_split_reexports_wave3.py:344: in test_handlers_take_side_effect_context_no_facade_global
    apply = getattr(handlers, name).apply
            ^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: module 'voice_typer.server.config_applier_handlers' has no attribute '_TrayLeftClickHandler'
```

### 29. `tests.test_module_split_reexports_wave9.TestRecordingLifecycleStageOrderParity.test_pipeline_stage_order_matches_the_contract`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_module_split_reexports_wave9.py:659`

```
assert not ['app._waveform_bubble.show()', 'set_state("recording")']

AssertionError: missing stage markers: ['app._waveform_bubble.show()', 'set_state("recording")']
assert not ['app._waveform_bubble.show()', 'set_state("recording")']
tests/test_module_split_reexports_wave9.py:659: in test_pipeline_stage_order_matches_the_contract
    self._ordered_markers(feedback_src, self.INSTANT_START_FEEDBACK_ORDER) == self.INSTANT_START_FEEDBACK_ORDER
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_module_split_reexports_wave9.py:642: in _ordered_markers
    assert not missing, f"missing stage markers: {missing}"
E   AssertionError: missing stage markers: ['app._waveform_bubble.show()', 'set_state("recording")']
E   assert not ['app._waveform_bubble.show()', 'set_state("recording")']
```

### 30. `tests.test_paste_failure_toast.TestPasteFailureBubbleState.test_bubble_shows_paste_failed_with_timed_exit`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_paste_failure_toast.py:280`

```
AssertionError: Expected 'show' to be called once. Called 0 times.

AssertionError: Expected 'show' to be called once. Called 0 times.
tests/test_paste_failure_toast.py:280: in test_bubble_shows_paste_failed_with_timed_exit
    app._waveform_bubble.show.assert_called_once_with()
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/unittest/mock.py:950: in assert_called_once_with
    raise AssertionError(msg)
E   AssertionError: Expected 'show' to be called once. Called 0 times.
```

### 31. `tests.test_security_doc_command_count.test_command_registry_count_matches_rust_allowlist_with_host_delta`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_security_doc_command_count.py:133`

```
assert not ['bubble_host_hidden']

AssertionError: _COMMAND_REGISTRY has commands that are neither in allowed_commands() nor in the documented host delta: ['bubble_host_hidden'].
assert not ['bubble_host_hidden']
tests/test_security_doc_command_count.py:133: in test_command_registry_count_matches_rust_allowlist_with_host_delta
    assert not unaccounted, (
E   AssertionError: _COMMAND_REGISTRY has commands that are neither in allowed_commands() nor in the documented host delta: ['bubble_host_hidden'].
E   assert not ['bubble_host_hidden']
```

### 32. `tests.test_short_audio_energy_gate.test_boundary_matrix_is_stable[0]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:161`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:161: in test_boundary_matrix_is_stable
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 33. `tests.test_short_audio_energy_gate.test_boundary_matrix_is_stable[1]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:161`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:161: in test_boundary_matrix_is_stable
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 34. `tests.test_short_audio_energy_gate.test_boundary_matrix_is_stable[2]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:161`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:161: in test_boundary_matrix_is_stable
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 35. `tests.test_short_audio_energy_gate.test_loud_word_survives_and_loud_click_is_rejected`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:177`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:177: in test_loud_word_survives_and_loud_click_is_rejected
    _assert_discarded(_drive_gate(click))
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 36. `tests.test_short_audio_energy_gate.test_quiet_tap_and_long_silence_are_rejected`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:184`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:184: in test_quiet_tap_and_long_silence_are_rejected
    _assert_discarded(_drive_gate(_shape_audio(kind, duration_s, rng)))
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 37. `tests.test_short_audio_energy_gate.TestUnusableRmsIsDiscarded.test_garbage_last_rms_discards_without_crashing[magic_mock]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:313`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:313: in test_garbage_last_rms_discards_without_crashing
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 38. `tests.test_short_audio_energy_gate.TestUnusableRmsIsDiscarded.test_garbage_last_rms_discards_without_crashing[string]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:313`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:313: in test_garbage_last_rms_discards_without_crashing
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 39. `tests.test_short_audio_energy_gate.TestUnusableRmsIsDiscarded.test_garbage_last_rms_discards_without_crashing[none]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:313`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:313: in test_garbage_last_rms_discards_without_crashing
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```

### 40. `tests.test_short_audio_energy_gate.TestUnusableRmsIsDiscarded.test_garbage_last_rms_discards_without_crashing[nan]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_short_audio_energy_gate.py:313`

```
AssertionError: Expected 'hide' to have been called once. Called 0 times.

AssertionError: Expected 'hide' to have been called once. Called 0 times.
tests/test_short_audio_energy_gate.py:313: in test_garbage_last_rms_discards_without_crashing
    _assert_discarded(result)
tests/test_short_audio_energy_gate.py:124: in _assert_discarded
    result.app._waveform_bubble.hide.assert_called_once()
/opt/hostedtoolcache/Python/3.11.18/x64/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'hide' to have been called once. Called 0 times.
```
