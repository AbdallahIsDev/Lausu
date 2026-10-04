# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**30 failing/errored tests** across 11 matrix legs.

### 1. `tests.model_download.test_segmented_download_helpers.test_install_blob_places_nested_snapshot_file`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/model_download/test_segmented_download_helpers.py:176`

```
+    where exists = PosixPath('/private/var/folders/s6/5hzmn6lx4dz5nxs7k_0slzph0000gn/T/pytest-of-runner/pytest-1/popen-gw2/test_install_blob_places_neste0/hf-cache/snapshots/abc123/model/weights.bin').exists

AssertionError: assert False
 +  where False = exists()
 +    where exists = PosixPath('/private/var/folders/s6/5hzmn6lx4dz5nxs7k_0slzph0000gn/T/pytest-of-runner/pytest-1/popen-gw2/test_install_blob_places_neste0/hf-cache/snapshots/abc123/model/weights.bin').exists
tests/model_download/test_segmented_download_helpers.py:176: in test_install_blob_places_nested_snapshot_file
    assert placed.exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/private/var/folders/s6/5hzmn6lx4dz5nxs7k_0slzph0000gn/T/pytest-of-runner/pytest-1/popen-gw2/test_install_blob_places_neste0/hf-cache/snapshots/abc123/model/weights.bin').exists
```

### 2. `tests.tauri.mig16.test_autostart_installer_macos.test_single_instance_plugin_enforced`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_autostart_installer_macos.py:463`

```
assert ('get_webview_window' in '//! Tauri v2 host (ADR-0020). Wiring-only (C-ARCH-1): builder, plugins,\n//! `.setup` glue, window-event dispatch, command registration. Logic lives\n//! in focused modules.\n\n#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]\n\n// Clippy lint gate lives in `Cargo.toml` `[lints.clippy]` (single source).\n\nmod branding;\nmod commands;\nmod error;\nmod host_events;\nmod launch_args;\nmod migrate;\nmod notify_aumid;\nmod platform;\nmod shortcuts;\nmod sidecar;\nmod startup_timeline;\nmod state;\nmod theme_icon;\nmod tray;\nmod util;\nmod window_bootstrap;\nmod window_events;\n\n// C-TEST-5: sibling test modules.\n#[cfg(test)]\nmod error_tests;\n#[cfg(test)]\nmod launch_args_tests;\n#[cfg(test)]\nmod state_tests;\n#[cfg(test)]\nmod theme_icon_tests;\n// Shared test-only helpers (panic-hook serialization lock).\n#[cfg(test)]\nmod test_support;\n\nuse std::sync::Arc;\n\n// `Listener` for `app.listen`; `RunEvent` for `.run` (incl. macOS Reopen).\nuse tauri::{Listener, Manager, RunEvent};\n\nuse commands::bubble::{\n    bubble_dismiss, bubble_hide_complete, bubble_move_by, bubble_resize, bubble_set_draggable,\n    bubble_set_position, bubble_show, bubble_signal_ready,...     })\n        .on_window_event(crate::window_events::handle)\n        // Split `.run(ctx)` into `.build(ctx)?.run(cb)` so `RunEvent::Exit`\n        // / `ExitRequested` can tear down the sidecar (else it leaks on\n        // `app.exit()` / tray-quit). Build failure logs [FATAL] then exit(1).\n        .build(tauri::generate_context!())\n        .unwrap_or_else(|e| {\n            eprintln!("[FATAL] tauri build failed: {e:?}");\n            log::error!("[FATAL] tauri build failed: {e:?}");\n            std::process::exit(1);\n        })\n        .run(|app_handle, event| match event {\n            RunEvent::ExitRequested { .. } | RunEvent::Exit => {\n                // `state::on_host_exit`: dedicated thread + bounded-time\n                // `block_on` (see `sidecar::lifecycle`).\n                crate::state::on_host_exit(app_handle);\n            }\n            // macOS Dock activation: process outlives the last window, so\n            // a Dock click brings the dashboard back.\n            #[cfg(target_os = "macos")]\n            RunEvent::Reopen { .. } => {\n                crate::host_events::show_main_window(app_handle);\n            }\n            _ => {}\n        });\n}\n')

AssertionError: single-instance callback must show + focus the existing main window (second launch → focus first, no duplicate window)
assert ('get_webview_window' in '//! Tauri v2 host (ADR-0020). Wiring-only (C-ARCH-1): builder, plugins,\n//! `.setup` glue, window-event dispatch, command registration. Logic lives\n//! in focused modules.\n\n#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]\n\n// Clippy lint gate lives in `Cargo.toml` `[lints.clippy]` (single source).\n\nmod branding;\nmod commands;\nmod error;\nmod host_events;\nmod launch_args;\nmod migrate;\nmod notify_aumid;\nmod platform;\nmod shortcuts;\nmod sidecar;\nmod startup_timeline;\nmod state;\nmod theme_icon;\nmod tray;\nmod util;\nmod window_bootstrap;\nmod window_events;\n\n// C-TEST-5: sibling test modules.\n#[cfg(test)]\nmod error_tests;\n#[cfg(test)]\nmod launch_args_tests;\n#[cfg(test)]\nmod state_tests;\n#[cfg(test)]\nmod theme_icon_tests;\n// Shared test-only helpers (panic-hook serialization lock).\n#[cfg(test)]\nmod test_support;\n\nuse std::sync::Arc;\n\n// `Listener` for `app.listen`; `RunEvent` for `.run` (incl. macOS Reopen).\nuse tauri::{Listener, Manager, RunEvent};\n\nuse commands::bubble::{\n    bubble_dismiss, bubble_hide_complete, bubble_move_by, bubble_resize, bubble_set_draggable,\n    bubble_set_position, bubble_show, bubble_signal_ready,...     })\n        .on_window_event(crate::window_events::handle)\n        // Split `.run(ctx)` into `.build(ctx)?.run(cb)` so `RunEvent::Exit`\n        // / `ExitRequested` can tear down the sidecar
… (truncated)
```

### 3. `tests.tauri.mig16.test_externalbin_spawn_macos.test_spawn_rs_server_started_log_line_format`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_externalbin_spawn_macos.py:270`

```
+    where <built-in method search of re.Pattern object at 0x12b485db0> = re.compile('\\[SIDECAR\\]\\s*server_started\\s*port=\\{[^}]*\\}').search

AssertionError: spawn.rs must log '[SIDECAR] server_started port={}' on success (runbook §5 pass criteria greps for this line on macOS)
assert None
 +  where None = <built-in method search of re.Pattern object at 0x12b485db0>('//! Sidecar spawn + stdout handshake (ADR-0020 §1 + §4.1 + §14).\n//! Submodules own the actual process spawn; this file is orchestration.\n//! Both spawn paths `.env_clear()` then re-add only the OS-required allowlist.\n//! C-TOKIO-1: panic capture is `AssertUnwindSafe(fut).catch_unwind().await`,\n//! never `block_on` on a runtime worker.\n//! Layout: docs/code-notes/tauri-host.md#module-layout\n\n// `pub(crate)` so lifecycle can consult `is_dev_mode()` for tray-Restart.\npub(crate) mod dev_mode;\n// Dev interpreter discovery (python.exe often missing from GUI PATH).\npub(crate) mod dev_python;\nmod env_allowlist;\nmod handshake;\nmod handshake_loop;\n// Permanent child-event drain: keeps the bounded shell event channel\n// drained post-handshake so child stderr can never block its writers.\npub(crate) mod event_drain;\nmod release_mode;\n// Worker exe spawn (runtime-pack split). Sidecar is the worker\'s WS client.\npub(crate) mod worker;\n// `pub(crate)` so platform::worker_path can resolve the per-platform worker name.\npub(crate) mod target_triple;\n\n// Test-only re-exports for spawn_tests.rs (`use super::*`).\n#[cfg(test)]\npub(crate) use dev_mode::is_dev_mode_for;\n#[cfg(...ng worker_started relay (port={})",\n        port\n    );\n    tauri::async_runtime::spawn(async move {\n        for _ in 0..RELAY_RETRY_ATTEMPTS {\n            tokio::time::sleep(std::time::Duration::from_millis(RELAY_RETRY_INTERVAL_MS)).await;\n            if state.shutting_down.load(Ordering::SeqCst) {\n                return;\n            }\n            if send_worker_started_frame(&state, pid, &version, port).is_some() {\n                return;\n            }\n        }\n        log::warn!(\n            "[WORKER-INIT] worker_started relay undelivered after retries (port={})",\n            port\n        );\n    });\n}\n\n/// `offline_pack_verified` trigger (called from the WS reader, sync\n/// context: the async work runs on a spawned task, never `block_on`:\n/// C-TOKIO-1). Delegates to the shared start sequence so a bad pack\n/// can never trip a respawn loop (no supervisor yet, plan §7.2).\npub(crate) fn on_pack_verified(app: &tauri::AppHandle) {\n    let app_handle = app.clone();\n    tauri::async_runtime::spawn(async move {\n        let state = app_handle.state::<Arc<WorkerState>>().inner().clone();\n        start_worker_if_ready(&app_handle, state).await;\n    });\n}\n')
 +    where <built-in method search of re.Pattern object at 0x12b485db0> = re.compile('\\[SIDECAR\\]\\s*server_started\\s*port=\\{[^}]*\\}').search
tests/tauri/mig16/test_externalbin_spawn_macos.py:270: in test_spawn_rs_server_started_log_line_format
    assert port_log_re.search(spawn_rs_source), (
E   AssertionError: spawn.rs must log '[SIDECAR] server_started port={}' on success (runbook §5 pass criteria greps for this line on macOS)
E   assert None
E    +  where None = <built-in method search of re.Pattern object at 0x12b485db0>('//! Sidecar spawn + stdout handshake (ADR-0020 §1 + §4.1 + §14).\n//! Submodules own the actual process spawn; this file is orchestration.\n//! Both spawn paths `.env_clear()` then re-add only the OS-required allowlist.\n//! C-TOKIO-1: panic capture is `AssertUnwindSafe(fut).catch_unwind().await`,\n//! never `block_on` on a runtime worker.\n//! Layout: docs/code-notes/tauri-host.md#module-layout\n\n// `pub(crate)` so lifecycle can consult `is_dev_mode()` for tray-Restart.\npub(crate) mod dev_mode;\n// Dev interpreter discovery (python.exe often missing from GUI PATH).\npub(crate) mod dev_python;\nmod env_allowlist;\nmod handshake;\nmod handshake_loop;\n// Permanent child-even
… (truncated)
```

### 4. `tests.tauri.mig16.test_externalbin_spawn_macos.test_sidecar_ws_binds_loopback_ephemeral_port`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_externalbin_spawn_macos.py:402`

```
+    where <function search at 0x1024bf560> = re.search

AssertionError: sidecar_ws.py must define _LOOPBACK_HOST = '127.0.0.1' (hard loopback, no 0.0.0.0/:: bind, ADR-0020 §1)
assert None
 +  where None = <function search at 0x1024bf560>('_LOOPBACK_HOST\\s*=\\s*"127\\.0\\.0\\.1"', '"""Tauri sidecar WebSocket transport, server side.\n\nADR-0020 §1 + §2: this module turns the existing :class:`IPCServer`\ndispatch layer into a localhost WebSocket server so the Tauri Rust\nhost can connect to it as a WS client.\n\nArchitecture\n------------\n::\n\n    Tauri host (Rust)\n        │  spawns sidecar via externalBin\n        │  passes VOICE_TYPER_IPC_TOKEN env\n        ▼\n    sidecar_main.py (this module\'s run() entrypoint)\n        │  binds websockets.serve on 127.0.0.1:0\n        │  OS assigns an ephemeral port\n        │  writes ONE structured line to stdout:\n        │     {"event":"server_started","port":<n>}\n        ▼\n    Rust reads stdout, parses the JSON, opens a WS client to\n    ws://127.0.0.1:<n>, sends the bearer-token auth frame, then forwards\n    invoke(\'dispatch\', {cmd, data}) envelopes over the WS.\n\n    Auth model (ADR-0020 §3)\n    -----------------------------------------------\n    The handshake is a **one-shot bearer-token** check, NOT an HMAC\n    scheme. The Rust host generates a 256-bit bearer token via\n    ``secrets.token_bytes(32)`` and the Python sidecar compares it with\n    :func:`hmac.compare_digest` (constant-time *comparison ...d`` module-object read at call\n  ``PROTOCOL_VERSION``.\n"""\n\nfrom __future__ import annotations\n\nimport contextlib\nimport json\nimport sys\n\n\ndef _force_line_buffered_stdout() -> None:\n    """so this is always available, but the guard is defensive)."""\n    try:\n        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined, union-attr]\n    except (AttributeError, ValueError):\n        # Fallback: reopen stdout with buffering=1 (line-buffered).\n        with contextlib.suppress(Exception):\n            sys.stdout = open(  # noqa: SIM115 - intentional reopen\n                sys.stdout.fileno(),\n                "w",\n                buffering=1,\n                encoding="utf-8",\n                closefd=False,\n            )\n\n\ndef _emit_server_started(port: int, protocol: int | None = None) -> None:\n    """Write the one structured stdout line the host is parsing for."""\n    if protocol is not None:\n        print(\n            json.dumps({"event": "server_started", "port": int(port), "protocol": int(protocol)}),\n            flush=True,\n        )\n    else:\n        print(json.dumps({"event": "server_started", "port": int(port)}), flush=True)\n')
 +    where <function search at 0x1024bf560> = re.search
tests/tauri/mig16/test_externalbin_spawn_macos.py:402: in test_sidecar_ws_binds_loopback_ephemeral_port
    assert re.search(
E   AssertionError: sidecar_ws.py must define _LOOPBACK_HOST = '127.0.0.1' (hard loopback, no 0.0.0.0/:: bind, ADR-0020 §1)
E   assert None
E    +  where None = <function search at 0x1024bf560>('_LOOPBACK_HOST\\s*=\\s*"127\\.0\\.0\\.1"', '"""Tauri sidecar WebSocket transport, server side.\n\nADR-0020 §1 + §2: this module turns the existing :class:`IPCServer`\ndispatch layer into a localhost WebSocket server so the Tauri Rust\nhost can connect to it as a WS client.\n\nArchitecture\n------------\n::\n\n    Tauri host (Rust)\n        │  spawns sidecar via externalBin\n        │  passes VOICE_TYPER_IPC_TOKEN env\n        ▼\n    sidecar_main.py (this module\'s run() entrypoint)\n        │  binds websockets.serve on 127.0.0.1:0\n        │  OS assigns an ephemeral port\n        │  writes ONE structured line to stdout:\n        │     {"event":"server_started","port":<n>}\n        ▼\n    Rust reads stdout, parses the JSON, opens a WS client to\n    ws://127.0.0.1:<n>, sends the bearer-token auth frame, then forwards\n    invoke(\'dispatch\', {cmd, data}) envelopes over the WS.\n\n    Auth model (ADR-0020 §3)\n    ----------
… (truncated)
```

### 5. `tests.tauri.mig16.test_faster_whisper_macos.test_build_script_check_flag_validates_ct2_backend_importable`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_faster_whisper_macos.py:46`

```
assert 'import faster_whisper, ctranslate2' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n'

AssertionError: build script's --check branch must validate that both faster_whisper AND ctranslate2 are importable in the build env
assert 'import faster_whisper, ctranslate2' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUIT
… (truncated)
```

### 6. `tests.tauri.mig16.test_faster_whisper_macos.test_build_script_includes_ct2_native_libs_singular_layout`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_faster_whisper_macos.py:82`

```
assert ('ctranslate2/lib' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n')

AssertionError: build script must include --include-data-dir for ctranslate2/lib (the directory holding libctranslate2.dylib + libiomp5.dylib)
assert ('ctranslate2/lib' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-id
… (truncated)
```

### 7. `tests.tauri.mig16.test_faster_whisper_macos.test_build_script_includes_faster_whisper_and_ctranslate2_packages`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_faster_whisper_macos.py:74`

```
assert '--include-package=faster_whisper' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n'

AssertionError: Nuitka must include the faster_whisper Python package
assert '--include-package=faster_whisper' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY"
… (truncated)
```

### 8. `tests.tauri.mig16.test_faster_whisper_macos.test_build_script_includes_ct2_libs_plural_layout_guarded`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_faster_whisper_macos.py:96`

```
assert 'ctranslate2/libs' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n'

AssertionError: build script must reference the plural ctranslate2/libs path (some wheel variants ship dylibs there instead of ctranslate2/lib)
assert 'ctranslate2/libs' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-id
… (truncated)
```

### 9. `tests.tauri.mig16.test_nuitka_macos_build.test_sidecar_script_contains_expected_nuitka_flag[--include-package=faster_whisper]`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_nuitka_macos_build.py:120`

```
assert '--include-package=faster_whisper' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n'

AssertionError: build_sidecar_macos.sh is missing required Nuitka flag `--include-package=faster_whisper`. ADR-0020 §4.3 mandates this flag for the macOS sidecar freeze.
assert '--include-package=faster_whisper' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it do
… (truncated)
```

### 10. `tests.tauri.mig16.test_nuitka_macos_build.test_sidecar_script_contains_expected_nuitka_flag[--include-package=ctranslate2]`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_nuitka_macos_build.py:120`

```
assert '--include-package=ctranslate2' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n'

AssertionError: build_sidecar_macos.sh is missing required Nuitka flag `--include-package=ctranslate2`. ADR-0020 §4.3 mandates this flag for the macOS sidecar freeze.
assert '--include-package=ctranslate2' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not in
… (truncated)
```

### 11. `tests.tauri.mig16.test_nuitka_macos_build.test_sidecar_script_includes_ctranslate2_data_dir`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_nuitka_macos_build.py:128`

```
assert '--include-data-dir' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n'

assert '--include-data-dir' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ───────────────────────────────────────────────────
… (truncated)
```

### 12. `tests.tauri.mig16.test_nuitka_macos_build.test_sidecar_script_has_ctranslate2_lib_guard_singular`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_nuitka_macos_build.py:152`

```
assert 'CT2_LIB_DIR=' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n'

assert 'CT2_LIB_DIR=' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ───────────────────────────────────────────────────────────────
… (truncated)
```

### 13. `tests.tauri.mig16.test_nuitka_macos_build.test_sidecar_script_has_xplat3_ctranslate2_libs_guard`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_nuitka_macos_build.py:138`

```
assert 'CT2_LIBS_DIR=' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n'

AssertionError: build_sidecar_macos.sh must define CT2_LIBS_DIR (the ctranslate2/libs plural path).
assert 'CT2_LIBS_DIR=' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuit
… (truncated)
```

### 14. `tests.tauri.mig16.test_nuitka_macos_build.test_sidecar_script_runs_otool_verify`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_nuitka_macos_build.py:327`

```
assert ('otool -L' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n' or 'otool ' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -
… (truncated)
```

### 15. `tests.tauri.mig16.test_nuitka_macos_build.test_sidecar_script_supports_check_mode`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_nuitka_macos_build.py:282`

```
assert ('import faster_whisper, ctranslate2' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n' or ('import faster_whisper' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ───────────────────────────────────
… (truncated)
```

### 16. `tests.tauri.mig16.test_nuitka_macos_build.test_sidecar_script_sanity_checks_ctranslate2_import`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_nuitka_macos_build.py:296`

```
assert 'import faster_whisper, ctranslate2, websockets' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n'

AssertionError: build_sidecar_macos.sh must sanity-check that faster_whisper + ctranslate2 + websockets all import in the build env.
assert 'import faster_whisper, ctranslate2, websockets' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not in
… (truncated)
```

### 17. `tests.tauri.mig16.test_nuitka_macos_build.test_linux_sibling_has_xplat3_ctranslate2_libs_guard`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_nuitka_macos_build.py:347`

```
assert 'CT2_LIBS_DIR' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n'

assert 'CT2_LIBS_DIR' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT l
… (truncated)
```

### 18. `tests.tauri.mig16.test_toast_macos.TestWsRsNotificationEventName.test_ws_rs_emits_canonical_notification_event`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_toast_macos.py:137`

```
assert ('emit("notification"' in '//! WebSocket reconnect + reader/writer tasks (ADR-0020 §1 + §9 + §10).\n//! C-WS-1 handshake order / C-WS-2 TEXT frames / C-WS-3 generation.\n//! NOTE: see docs/code-notes/tauri-host.md#ws-handshake-order-c-ws-1\n\nmod event_protocol;\nmod heartbeat;\nmod reader;\nmod respawn_scheduler;\nmod writer;\n\npub(crate) use event_protocol::translate_event_name;\npub(crate) use heartbeat::abort_heartbeat;\n\n// Re-export for ws_tests.rs (private submodule visibility).\npub(super) use event_protocol::{\n    is_allowed_event_type, is_high_rate_event_type, python_event_envelope,\n};\nuse heartbeat::spawn_heartbeat_task;\nuse reader::spawn_reader_task;\nuse respawn_scheduler::cleanup_and_trigger_respawn;\nuse writer::spawn_writer_task;\n\nuse crate::state::lock as mutex_lock;\nuse crate::state::SidecarState;\nuse crate::util::MAX_FRAME_BYTES;\nuse futures_util::{\n    stream::{SplitSink, SplitStream},\n    FutureExt, StreamExt,\n};\nuse serde_json::{json, Value};\nuse std::panic::AssertUnwindSafe;\nuse std::sync::atomic::Ordering;\nuse std::sync::Arc;\nuse std::time::Duration;\nuse tauri::Emitter;\nuse tokio::sync::{mpsc, oneshot};\nuse tokio_tungstenite::{\n    connect_async_with_config, ... current_generation\n                );\n            }\n        }\n        if !state_for_cleanup.shutting_down.load(Ordering::SeqCst) {\n            let current_generation = state_for_cleanup.ws_generation.load(Ordering::SeqCst);\n            if current_generation == my_generation {\n                if let Err(e) = app_for_cleanup.emit(\n                    "supervisor_relaunching",\n                    json!({"reason": "writer_half_closed"}),\n                ) {\n                    log::warn!("[WS-WRITER] failed to emit supervisor_relaunching: {}", e);\n                }\n                log::warn!("[WS-WRITER] write half closed, triggering supervisor respawn");\n                trigger_respawn_off_thread(\n                    app_for_cleanup.clone(),\n                    state_for_cleanup.clone(),\n                    Some(my_generation),\n                );\n            } else {\n                log::info!(\n                    "[WS-WRITER] cleanup skipping respawn trigger: generation mismatch \\\n                     (mine={}, current={})",\n                    my_generation,\n                    current_generation\n                );\n            }\n        }\n    });\n}\n' or 'notification' in '//! WebSocket reconnect + reader/writer tasks (ADR-0020 §1 + §9 + §10).\n//! C-WS-1 handshake order / C-WS-2 TEXT frames / C-WS-3 generation.\n//! NOTE: see docs/code-notes/tauri-host.md#ws-handshake-order-c-ws-1\n\nmod event_protocol;\nmod heartbeat;\nmod reader;\nmod respawn_scheduler;\nmod writer;\n\npub(crate) use event_protocol::translate_event_name;\npub(crate) use heartbeat::abort_heartbeat;\n\n// Re-export for ws_tests.rs (private submodule visibility).\npub(super) use event_protocol::{\n    is_allowed_event_type, is_high_rate_event_type, python_event_envelope,\n};\nuse heartbeat::spawn_heartbeat_task;\nuse reader::spawn_reader_task;\nuse respawn_scheduler::cleanup_and_trigger_respawn;\nuse writer::spawn_writer_task;\n\nuse crate::state::lock as mutex_lock;\nuse crate::state::SidecarState;\nuse crate::util::MAX_FRAME_BYTES;\nuse futures_util::{\n    stream::{SplitSink, SplitStream},\n    FutureExt, StreamExt,\n};\nuse serde_json::{json, Value};\nuse std::panic::AssertUnwindSafe;\nuse std::sync::atomic::Ordering;\nuse std::sync::Arc;\nuse std::time::Duration;\nuse tauri::Emitter;\nuse tokio::sync::{mpsc, oneshot};\nuse tokio_tungstenite::{\n    connect_async_with_config, ... current_generation\n                );\n            }\n        }\n        if !state_for_cleanup.shutting_down.load(Ordering::SeqCst) {\n            let current_generation = state_for_cleanup.ws_generation.load(Ordering::SeqCst);\n            if current_generation == my_generation {\n                if let Err(e) = app_for_cleanup.emit(\n
… (truncated)
```

### 19. `tests.tauri.mig16.test_toast_macos.TestValidateOnMacOSHostBlock.test_docstring_contains_validate_on_macos_host_header`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_toast_macos.py:457`

```
assert 'VALIDATE ON MACOS HOST:' in 'toast notification wiring validation (macOS).'

AssertionError: Module docstring MUST contain 'VALIDATE ON MACOS HOST:' header, this is the canonical marker the macOS host validator scans for.
assert 'VALIDATE ON MACOS HOST:' in 'toast notification wiring validation (macOS).'
tests/tauri/mig16/test_toast_macos.py:457: in test_docstring_contains_validate_on_macos_host_header
    assert "VALIDATE ON MACOS HOST:" in doc, (
E   AssertionError: Module docstring MUST contain 'VALIDATE ON MACOS HOST:' header, this is the canonical marker the macOS host validator scans for.
E   assert 'VALIDATE ON MACOS HOST:' in 'toast notification wiring validation (macOS).'
```

### 20. `tests.tauri.mig16.test_toast_macos.TestValidateOnMacOSHostBlock.test_docstring_documents_signing_prerequisite`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_toast_macos.py:465`

```
assert 'Developer ID' in 'toast notification wiring validation (macOS).'

AssertionError: VALIDATE ON MACOS HOST block MUST mention 'Developer ID', unsigned dev builds silently fail to post notifications on macOS.
assert 'Developer ID' in 'toast notification wiring validation (macOS).'
tests/tauri/mig16/test_toast_macos.py:465: in test_docstring_documents_signing_prerequisite
    assert "Developer ID" in doc, (
E   AssertionError: VALIDATE ON MACOS HOST block MUST mention 'Developer ID', unsigned dev builds silently fail to post notifications on macOS.
E   assert 'Developer ID' in 'toast notification wiring validation (macOS).'
```

### 21. `tests.tauri.mig16.test_toast_macos.TestValidateOnMacOSHostBlock.test_docstring_documents_log_path`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_toast_macos.py:489`

```
assert '~/Library/Logs/lausu/lausu.log' in 'toast notification wiring validation (macOS).'

AssertionError: VALIDATE ON MACOS HOST block MUST document the macOS log path (~/Library/Logs/lausu/lausu.log) so the validator can confirm the notification event was emitted.
assert '~/Library/Logs/lausu/lausu.log' in 'toast notification wiring validation (macOS).'
tests/tauri/mig16/test_toast_macos.py:489: in test_docstring_documents_log_path
    assert "~/Library/Logs/lausu/lausu.log" in doc, (
E   AssertionError: VALIDATE ON MACOS HOST block MUST document the macOS log path (~/Library/Logs/lausu/lausu.log) so the validator can confirm the notification event was emitted.
E   assert '~/Library/Logs/lausu/lausu.log' in 'toast notification wiring validation (macOS).'
```

### 22. `tests.tauri.mig16.test_toast_macos.TestValidateOnMacOSHostBlock.test_docstring_documents_system_settings_fallback`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_toast_macos.py:476`

```
assert 'System Settings' in 'toast notification wiring validation (macOS).'

AssertionError: VALIDATE ON MACOS HOST block MUST mention 'System Settings', the macOS UI path where the user manually grants notification permission if the TCC prompt was dismissed.
assert 'System Settings' in 'toast notification wiring validation (macOS).'
tests/tauri/mig16/test_toast_macos.py:476: in test_docstring_documents_system_settings_fallback
    assert "System Settings" in doc, (
E   AssertionError: VALIDATE ON MACOS HOST block MUST mention 'System Settings', the macOS UI path where the user manually grants notification permission if the TCC prompt was dismissed.
E   assert 'System Settings' in 'toast notification wiring validation (macOS).'
```

### 23. `tests.tauri.mig16.test_toast_macos.TestValidateOnMacOSHostBlock.test_docstring_documents_unsigned_dev_build_caveat`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_toast_macos.py:498`

```
assert 'Unsigned dev builds' in 'toast notification wiring validation (macOS).'

AssertionError: VALIDATE ON MACOS HOST block MUST document the unsigned-dev-build caveat ('Unsigned dev builds may not show notifications, sign with Developer ID first.'), this is the troubleshooting hint for the most common silent-failure mode on macOS.
assert 'Unsigned dev builds' in 'toast notification wiring validation (macOS).'
tests/tauri/mig16/test_toast_macos.py:498: in test_docstring_documents_unsigned_dev_build_caveat
    assert "Unsigned dev builds" in doc, (
E   AssertionError: VALIDATE ON MACOS HOST block MUST document the unsigned-dev-build caveat ('Unsigned dev builds may not show notifications, sign with Developer ID first.'), this is the troubleshooting hint for the most common silent-failure mode on macOS.
E   assert 'Unsigned dev builds' in 'toast notification wiring validation (macOS).'
```

### 24. `tests.tauri.mig16.test_toast_macos.TestValidateOnMacOSHostBlock.test_docstring_documents_expected_timing`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13
- Location: `tests/tauri/mig16/test_toast_macos.py:508`

```
assert 'within 1s' in 'toast notification wiring validation (macOS).'

AssertionError: VALIDATE ON MACOS HOST block MUST document the expected timing ('within 1s'), the upper bound for how long the validator should wait for the banner before declaring the gate failed.
assert 'within 1s' in 'toast notification wiring validation (macOS).'
tests/tauri/mig16/test_toast_macos.py:508: in test_docstring_documents_expected_timing
    assert "within 1s" in doc, (
E   AssertionError: VALIDATE ON MACOS HOST block MUST document the expected timing ('within 1s'), the upper bound for how long the validator should wait for the banner before declaring the gate failed.
E   assert 'within 1s' in 'toast notification wiring validation (macOS).'
```

### 25. `tests.tauri.test_internal_plugin_tools_absent.TestInternalPluginToolsNotInMainRepo.test_root_gitignore_covers_plugin_tools`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.10, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/test_internal_plugin_tools_absent.py:136`

```
assert 1 == 0

AssertionError: tools/internal_plugins must be listed in the root .gitignore (git check-ignore said: not ignored)
assert 1 == 0
tests/tauri/test_internal_plugin_tools_absent.py:136: in test_root_gitignore_covers_plugin_tools
    assert code == 0, (
E   AssertionError: tools/internal_plugins must be listed in the root .gitignore (git check-ignore said: not ignored)
E   assert 1 == 0
```

### 26. `tests.test_dev_console_launcher.test_launch_dev_console_windows_spawns_cmd`

- Legs: macos-14-3.11, macos-14-3.12, macos-14-3.13, ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_dev_console_launcher.py:18`

```
AttributeError: module 'subprocess' has no attribute 'CREATE_NEW_CONSOLE'

AttributeError: module 'subprocess' has no attribute 'CREATE_NEW_CONSOLE'
tests/test_dev_console_launcher.py:18: in test_launch_dev_console_windows_spawns_cmd
    rc = dev_console.launch_dev_console("dev")
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
voice_typer/server/autostart/dev_console.py:42: in launch_dev_console
    creationflags=subprocess.CREATE_NEW_CONSOLE,
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: module 'subprocess' has no attribute 'CREATE_NEW_CONSOLE'
```

### 27. `tests.test_hotkeys_win32.TestModifierOnlyHotkeys.test_alt_only_hotkey_starts_without_error`

- Legs: macos-14-3.11, macos-14-3.13
- Location: `tests/test_hotkeys_win32.py:278`

```
AssertionError: LL hook handle never installed for modifier-only spec (waited 3.0s)

AssertionError: LL hook handle never installed for modifier-only spec (waited 3.0s)
tests/test_hotkeys_win32.py:278: in test_alt_only_hotkey_starts_without_error
    _wait_until(
tests/test_hotkeys_win32.py:21: in _wait_until
    raise AssertionError(f"{msg} (waited {timeout}s)")
E   AssertionError: LL hook handle never installed for modifier-only spec (waited 3.0s)
```

### 28. `tests.test_volume_lifecycle.TestStopDictationRestoresVolume.test_stop_restores_volume`

- Legs: macos-14-3.12
- Location: `tests/test_volume_lifecycle.py:245`

```
TimeoutError: _busy_event still not set after 2.0s

TimeoutError: _busy_event still not set after 2.0s
tests/test_volume_lifecycle.py:245: in test_stop_restores_volume
    _wait_for_busy_clear(app)
tests/test_volume_lifecycle.py:155: in _wait_for_busy_clear
    raise TimeoutError(f"_busy_event still not set after {timeout}s")
E   TimeoutError: _busy_event still not set after 2.0s
```

### 29. `tests.test_volume_lifecycle.TestStopDictationRestoresVolume.test_stop_does_not_restore_when_disabled`

- Legs: macos-14-3.12
- Location: `tests/test_volume_lifecycle.py:301`

```
TimeoutError: _busy_event still not set after 2.0s

TimeoutError: _busy_event still not set after 2.0s
tests/test_volume_lifecycle.py:301: in test_stop_does_not_restore_when_disabled
    _wait_for_busy_clear(app)
tests/test_volume_lifecycle.py:155: in _wait_for_busy_clear
    raise TimeoutError(f"_busy_event still not set after {timeout}s")
E   TimeoutError: _busy_event still not set after 2.0s
```

### 30. `tests.model_download.test_segmented_download.TestDiskFull.test_enospc_surfaces_as_error_not_retry_loop`

- Legs: ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/model_download/test_segmented_download.py:486`

```
Failed: DID NOT RAISE OSError

Failed: DID NOT RAISE OSError
tests/model_download/test_segmented_download.py:486: in test_enospc_surfaces_as_error_not_retry_loop
    with pytest.raises(OSError):
E   Failed: DID NOT RAISE OSError
```
