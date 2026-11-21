# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.
> Source SHA: `afcc02326a196a5e52ba5c439747ecbd373d5995`

**3 failing/errored tests** across 7 matrix legs.

### 1. `tests.tauri.mig16.test_nuitka_macos_build.test_sidecar_script_onefile_tempdir_uses_caches`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13
- Location: `tests/tauri/mig16/test_nuitka_macos_build.py:264`

```
assert 'Library/Caches/lausu/onefile-tmp' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n'

AssertionError: build_sidecar_macos.sh --onefile-tempdir-spec must use $HOME/Library/Caches/lausu/onefile-tmp (purgeable cache dir, ADR-0020 §4.3). Application Support is user data: it is backed up and is not reaped by cache cleaners, so a frozen extract does not belong there.
[+1 more line; full report in element text]
tests/tauri/mig16/test_nuitka_macos_build.py:264: in test_sidecar_script_onefile_tempdir_uses_caches
    assert "Library/Caches/lausu/onefile-tmp" in sidecar_text, (
E   AssertionError: build_sidecar_macos.sh --onefile-tempdir-spec must use $HOME/Library/Caches/lausu/onefile-tmp (purgeable cache dir, ADR-0020 §4.3). Application Support is user data: it is backed up and is not reaped by cache cleaners, so a frozen extract does not belong there.
E   assert 'Library/Caches/lausu/onefile-tmp' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash script
… (truncated)
```

### 2. `tests.test_windows_bundle_gate.test_pinned_spec_is_per_build_and_per_product`

- Legs: macos-15-3.11, macos-15-3.12, macos-15-3.13, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_windows_bundle_gate.py:71`

```
+    where <function onefile_extraction_dir at 0x12d9a1a80> = gate.onefile_extraction_dir

AssertionError: assert None == PosixPath('/private/var/folders/9d/l02zfgrs7c16twd3wbpdmhkc0000gn/T/pytest-of-runner/pytest-1/popen-gw0/test_pinned_spec_is_per_build_0/LausuSidecar/2026.11.21.1635/onefile-tmp')
 +  where None = <function onefile_extraction_dir at 0x12d9a1a80>()
 +    where <function onefile_extraction_dir at 0x12d9a1a80> = gate.onefile_extraction_dir
tests/test_windows_bundle_gate.py:71: in test_pinned_spec_is_per_build_and_per_product
    assert gate.onefile_extraction_dir() == new
E   AssertionError: assert None == PosixPath('/private/var/folders/9d/l02zfgrs7c16twd3wbpdmhkc0000gn/T/pytest-of-runner/pytest-1/popen-gw0/test_pinned_spec_is_per_build_0/LausuSidecar/2026.11.21.1635/onefile-tmp')
E    +  where None = <function onefile_extraction_dir at 0x12d9a1a80>()
E    +    where <function onefile_extraction_dir at 0x12d9a1a80> = gate.onefile_extraction_dir
```

### 3. `tests.test_correction_usage.TestCorrectionUsageTracker.test_prune_days_drops_old_totals`

- Legs: windows-2022-3.11
- Location: `tests/test_correction_usage.py:104`

```
AssertionError: assert '2000-01-01' not in {'2030-03-17': 1, '2000-01-01': 99}

AssertionError: assert '2000-01-01' not in {'2030-03-17': 1, '2000-01-01': 99}
tests\test_correction_usage.py:104: in test_prune_days_drops_old_totals
    assert "2000-01-01" not in snap["corrections_by_day"]
E   AssertionError: assert '2000-01-01' not in {'2030-03-17': 1, '2000-01-01': 99}
```
