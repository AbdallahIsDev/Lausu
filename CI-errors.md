# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.
> Source SHA: `3c9fd7acf2850c27f24a62783584b8f9d010cae8`

**3 failing/errored tests** across 4 matrix legs.

### 1. `tests.hotkeys.test_polling_strategy.TestPressHoldReleaseNoRepeat.test_two_press_cycles_fire_exactly_twice`

- Legs: macos-15-3.13
- Location: `tests/hotkeys/test_polling_strategy.py:249`

```
AssertionError: Callback did not fire on press (cycle 2) (waited 2.0s)

AssertionError: Callback did not fire on press (cycle 2) (waited 2.0s)
tests/hotkeys/test_polling_strategy.py:249: in test_two_press_cycles_fire_exactly_twice
    _wait_until(
tests/hotkeys/test_polling_strategy.py:89: in _wait_until
    raise AssertionError(f"{msg} (waited {timeout}s)")
E   AssertionError: Callback did not fire on press (cycle 2) (waited 2.0s)
```

### 2. `tests.tauri.test_windows_freeze_drift.test_gate_resolves_newest_versioned_extraction_dir_without_build_stamp`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/test_windows_freeze_drift.py:132`

```
+    where <function onefile_extraction_dir at 0x7fc7b485b1a0> = <module '_windows_bundle_gate' from '/home/runner/work/Lausu/Lausu/scripts/verify_windows_bundle.py'>.onefile_extraction_dir

AssertionError: gate must pick the newest versioned onefile-tmp; it must not depend on the freeze job's BUILD_STAMP (different job/runner)
assert PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_gate_resolves_newest_vers0/LausuSidecar/2026.01.01.0000/onefile-tmp') == PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_gate_resolves_newest_vers0/LausuSidecar/2026.11.22.1234/onefile-tmp')
[+2 more lines; full report in element text]
tests/tauri/test_windows_freeze_drift.py:132: in test_gate_resolves_newest_versioned_extraction_dir_without_build_stamp
    assert gate.onefile_extraction_dir() == new, (
E   AssertionError: gate must pick the newest versioned onefile-tmp; it must not depend on the freeze job's BUILD_STAMP (different job/runner)
E   assert PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_gate_resolves_newest_vers0/LausuSidecar/2026.01.01.0000/onefile-tmp') == PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_gate_resolves_newest_vers0/LausuSidecar/2026.11.22.1234/onefile-tmp')
E    +  where PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_gate_resolves_newest_vers0/LausuSidecar/2026.01.01.0000/onefile-tmp') = <function onefile_extraction_dir at 0x7fc7b485b1a0>()
E    +    where <function onefile_extraction_dir at 0x7fc7b485b1a0> = <module '_windows_bundle_gate' from '/home/runner/work/Lausu/Lausu/scripts/verify_windows_bundle.py'>.onefile_extraction_dir
```

### 3. `tests.test_windows_bundle_gate.test_pinned_spec_is_per_build_and_per_product`

- Legs: ubuntu-22.04-3.11
- Location: `tests/test_windows_bundle_gate.py:76`

```
+    where <function onefile_extraction_dir at 0x7fc7c91c2ac0> = gate.onefile_extraction_dir

AssertionError: assert PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_pinned_spec_is_per_build_0/LausuSidecar/2026.01.01.0000/onefile-tmp') == PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_pinned_spec_is_per_build_0/LausuSidecar/2026.11.21.1635/onefile-tmp')
 +  where PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_pinned_spec_is_per_build_0/LausuSidecar/2026.01.01.0000/onefile-tmp') = <function onefile_extraction_dir at 0x7fc7c91c2ac0>()
[+1 more line; full report in element text]
tests/test_windows_bundle_gate.py:76: in test_pinned_spec_is_per_build_and_per_product
    assert gate.onefile_extraction_dir() == new
E   AssertionError: assert PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_pinned_spec_is_per_build_0/LausuSidecar/2026.01.01.0000/onefile-tmp') == PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_pinned_spec_is_per_build_0/LausuSidecar/2026.11.21.1635/onefile-tmp')
E    +  where PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_pinned_spec_is_per_build_0/LausuSidecar/2026.01.01.0000/onefile-tmp') = <function onefile_extraction_dir at 0x7fc7c91c2ac0>()
E    +    where <function onefile_extraction_dir at 0x7fc7c91c2ac0> = gate.onefile_extraction_dir
```
