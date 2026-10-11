use crate::platform::worker_path::{
    HOST_MIN_PROTO_VERSION, HOST_PROTO_VERSION, PackProtoStatus, WORKER_BIN_BASE_NAME,
    check_pack_manifest_for_exe, pack_version,
};
use crate::state::SidecarHandle;
use crate::state::WorkerState;
use crate::state::{SidecarState, lock as state_lock};
use crate::util::{DEV_SERVER_STARTED_TIMEOUT_MS, SERVER_STARTED_TIMEOUT_MS};
use serde_json::{Value, json};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::{Emitter, Manager};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::{Command, CommandEvent};
use tokio::sync::mpsc;
use tokio_tungstenite::tungstenite::Message;

use super::dev_mode::is_dev_mode;
use super::env_allowlist::passthrough_env_allowlist;
use super::handshake::parse_worker_started;
use super::handshake_loop::{
    HandshakeLabels, read_handshake_from_command_events, read_handshake_from_stdout_lines,
    register_kill_on_parent_exit_best_effort,
};
use super::initialize_worker;

/// Exit code the worker (`python -m voice_typer.worker` in dev, the
/// frozen `lausu-worker` binary in release) uses when another worker
/// already holds the single-instance lock. Mirrors
/// `EXIT_DUPLICATE_INSTANCE` in `voice_typer/worker/__main__.py`; keep
/// the two in lockstep.
pub(crate) const WORKER_EXIT_DUPLICATE_INSTANCE: i32 = 3;

/// True when a spawn error means "another worker is already running".
/// Matches the dev-loop EOF spelling (`... (exit=3)`) and the release
/// `Terminated` spelling (`... (code=Some(3))`); anything else (real
/// crash, timeout, the `"shutdown"` sentinel) is a genuine failure.
pub(crate) fn is_worker_duplicate_exit(err: &str) -> bool {
    err.contains(&format!("(exit={WORKER_EXIT_DUPLICATE_INSTANCE})"))
        || err.contains(&format!("(code=Some({WORKER_EXIT_DUPLICATE_INSTANCE}))"))
}

pub(crate) fn worker_shared_env(token: &str) -> Vec<(&'static str, String)> {
    vec![
        ("VOICE_TYPER_IPC_TOKEN", token.to_string()),
        // Parent PID for the worker's orphan self-exit (if this host
        // dies without reaping the worker, the worker notices the dead
        // parent and shuts down instead of squatting the
        // single-instance lock forever). Mirrors
        // `PARENT_PID_ENV_VAR` in `voice_typer/worker/_parent_watch.py`.
        ("VOICE_TYPER_PARENT_PID", std::process::id().to_string()),
        // Share the host's per-process session ID so the
        // worker's log lines correlate with the host + sidecar.
        (
            "VOICE_TYPER_SESSION_ID",
            crate::util::session_id().to_string(),
        ),
        // The worker reads the shared config dir for `fast_startup`
        // (prewarm toggle) + its log location.
        (
            "VOICE_TYPER_CONFIG_DIR",
            crate::platform::paths::config_dir()
                .to_string_lossy()
                .to_string(),
        ),
    ]
}

/// Worker launch source (slim install + runtime pack). The pack copy wins when
/// present (updatable without reinstall); otherwise the bundled
/// externalBin copy (full-offline installer); neither means a slim
/// install whose pack never downloaded.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum WorkerLaunchTarget {
    PackExe(std::path::PathBuf),
    Bundled,
    Absent,
}

/// Pure target decision over existence probes (fs reads stay in the caller).
pub(crate) fn classify_worker_launch_target(
    pack_exe: Option<std::path::PathBuf>,
    bundled_present: bool,
) -> WorkerLaunchTarget {
    match (pack_exe, bundled_present) {
        (Some(path), _) => WorkerLaunchTarget::PackExe(path),
        (None, true) => WorkerLaunchTarget::Bundled,
        (None, false) => WorkerLaunchTarget::Absent,
    }
}

/// Bundled externalBin path: beside the host exe under the plain base
/// name (the bundler strips the triple at install time, so the shell
/// plugin joins the name verbatim). Mirrors the plugin's `deps/`
/// test-harness rule so probes stay honest under `cargo test`.
fn bundled_worker_exe_path() -> Option<std::path::PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    let base = if dir.ends_with("deps") {
        dir.parent().unwrap_or(dir)
    } else {
        dir
    };
    let mut path = base.join(WORKER_BIN_BASE_NAME);
    if cfg!(windows) {
        path.as_mut_os_string().push(".exe");
    }
    Some(path)
}

fn bundled_worker_present() -> bool {
    bundled_worker_exe_path().is_some_and(|p| p.exists())
}

fn pack_worker_exe_present() -> Option<std::path::PathBuf> {
    let path = crate::platform::worker_path::worker_exe_path();
    path.exists().then(|| path.to_path_buf())
}

fn resolve_worker_launch_target() -> WorkerLaunchTarget {
    classify_worker_launch_target(pack_worker_exe_present(), bundled_worker_present())
}

/// Shared tail for both release launch paths: spawn, handshake, wrap.
async fn launch_worker_command(
    cmd: Command,
    shutting_down: Option<&AtomicBool>,
) -> Result<(u16, SidecarHandle, mpsc::Receiver<CommandEvent>), String> {
    let (rx, child) = cmd
        .spawn()
        .map_err(|e| format!("failed to spawn worker: {e}"))?;

    // Kill-on-parent-exit so the OS reaps the orphan worker when the
    // host dies (mirrors spawn_sidecar_release). Best-effort.
    let worker_pid = child.pid();
    register_kill_on_parent_exit_best_effort(
        "[WORKER]",
        "worker may be orphaned on host crash",
        worker_pid,
    );

    let (port, child, rx) = read_handshake_from_command_events(
        &HandshakeLabels {
            log_tag: "[WORKER]",
            err_noun: "worker",
            event_name: "worker_started",
            kill_target: "worker",
            fresh_target: "worker",
        },
        rx,
        child,
        shutting_down,
        parse_worker_started,
        SERVER_STARTED_TIMEOUT_MS,
    )
    .await?;
    Ok((port, SidecarHandle::ShellPlugin(Some(child)), rx))
}

/// Pure refusal text for the spawn-boundary backstop (no emit here).
pub(crate) fn pack_refusal_message(exe_path: &std::path::Path, status: &PackProtoStatus) -> String {
    match status {
        PackProtoStatus::Mismatch { min_proto_version } => format!(
            "refusing stale pack worker (min_proto_version={min_proto_version}, \
             host supports {HOST_MIN_PROTO_VERSION}..={HOST_PROTO_VERSION}): {}",
            exe_path.display()
        ),
        PackProtoStatus::MissingManifest { reason } => format!(
            "refusing pack worker without a readable manifest ({reason}): {}",
            exe_path.display()
        ),
        PackProtoStatus::Match { .. } => format!("pack worker verified: {}", exe_path.display()),
    }
}

pub(crate) async fn spawn_worker_release(
    app: &tauri::AppHandle,
    token: &str,
    shutting_down: Option<&AtomicBool>,
) -> Result<(u16, SidecarHandle, mpsc::Receiver<CommandEvent>), String> {
    match resolve_worker_launch_target() {
        WorkerLaunchTarget::PackExe(path) => {
            // Pack-proto enforcement backstop: the start gate already refused +
            // signalled, but a swapped pack between gate and spawn must
            // still refuse here (no emit: never double-signal).
            let status = check_pack_manifest_for_exe(&path);
            if !status.launch_allowed() {
                return Err(pack_refusal_message(&path, &status));
            }
            // Rust-side absolute launch needs no shell scope (ACL gates
            // the JS surface only, not `app.shell()`).
            let cmd = app
                .shell()
                .command(&path)
                .env_clear()
                .envs(passthrough_env_allowlist())
                .envs(worker_shared_env(token))
                .env("KMP_DUPLICATE_LIB_OK", "TRUE");
            launch_worker_command(cmd, shutting_down).await
        }
        WorkerLaunchTarget::Bundled => {
            let worker = app
                .shell()
                .sidecar("lausu-worker")
                .map_err(|e| format!("failed to resolve worker binary: {e}"))?;

            let cmd = worker
                .env_clear()
                .envs(passthrough_env_allowlist())
                .envs(worker_shared_env(token))
                .env("KMP_DUPLICATE_LIB_OK", "TRUE");
            launch_worker_command(cmd, shutting_down).await
        }
        WorkerLaunchTarget::Absent => Err("no worker binary on disk".to_string()),
    }
}

pub(crate) async fn spawn_worker_dev_mode(
    token: &str,
    shutting_down: Option<&AtomicBool>,
) -> Result<(u16, SidecarHandle), String> {
    let python_bin = super::dev_python::resolve_dev_python();

    let mut cmd = tokio::process::Command::new(&python_bin);
    cmd.args(["-m", "voice_typer.worker"])
        .env_clear()
        .envs(passthrough_env_allowlist())
        .envs(worker_shared_env(token))
        .env("KMP_DUPLICATE_LIB_OK", "TRUE")
        .env("VOICE_TYPER_DEBUG", "1")
        .stdout(std::process::Stdio::piped())
        // Dev mode: inherit stderr so the developer sees Python
        // tracebacks in the `cargo tauri dev` console.
        .stderr(std::process::Stdio::inherit())
        // Ensure the dev worker dies with the host (no zombie python).
        .kill_on_drop(true);

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("failed to spawn dev worker ({}): {e}", python_bin))?;

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "dev worker stdout not captured".to_string())?;
    let mut reader = tokio::io::BufReader::new(stdout);

    let port = read_handshake_from_stdout_lines(
        &HandshakeLabels {
            log_tag: "[WORKER-DEV]",
            err_noun: "dev worker",
            event_name: "worker_started",
            kill_target: "worker",
            fresh_target: "dev worker",
        },
        &mut reader,
        &mut child,
        shutting_down,
        parse_worker_started,
        DEV_SERVER_STARTED_TIMEOUT_MS,
    )
    .await?;
    Ok((port, SidecarHandle::DevMode(child)))
}

pub(crate) fn try_claim_restart_slot(flag: &AtomicBool) -> bool {
    flag.compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
        .is_ok()
}

fn worker_binary_present() -> bool {
    // Dev always has a worker (`python -m`); release needs the pack
    // copy or the bundled externalBin copy (slim installs have neither).
    is_dev_mode() || !matches!(resolve_worker_launch_target(), WorkerLaunchTarget::Absent)
}

pub(crate) async fn stop_worker_child(state: &Arc<WorkerState>) {
    let taken = crate::state::lock(&state.child).take();
    if let Some(child) = taken {
        if let Err(e) = child.kill_tree().await {
            log::warn!(
                "[WORKER-INIT] stop worker child kill_tree failed (best-effort): {}",
                e
            );
        } else {
            log::info!("[WORKER-INIT] stopped previous worker child");
        }
    }
}

/// Pure start gate: run only while the host is alive AND a worker
/// binary exists. Pure so both triggers stay unit-testable.
pub(crate) fn should_start_worker(shutting_down: bool, binary_present: bool) -> bool {
    !shutting_down && binary_present
}

/// Shared start sequence for cold boot + pack-verified events:
/// stop-first (frees the pack dir on Windows) then
/// `initialize_worker`. Serialized on the restart slot; a missing
/// binary or a quitting host skips quietly (C-WS-3 generation
/// stamping lands with the worker WS bridge, no WS yet to stamp).
pub(crate) async fn start_worker_if_ready(app_handle: &tauri::AppHandle, state: Arc<WorkerState>) {
    if !try_claim_restart_slot(&state.respawn_in_progress) {
        log::info!("[WORKER-INIT] worker (re)start already in flight: skipping duplicate");
        return;
    }
    stop_worker_child(&state).await;
    if !should_start_worker(
        state.shutting_down.load(Ordering::SeqCst),
        worker_binary_present(),
    ) {
        if !state.shutting_down.load(Ordering::SeqCst) {
            log::info!("[WORKER-INIT] no worker binary on disk: skipping worker start");
        }
        state.respawn_in_progress.store(false, Ordering::SeqCst);
        return;
    }
    // Stale-pack fast refuse (release pack launches only: dev spawns python,
    // which has no pack manifest to gate on).
    if !is_dev_mode() {
        if let WorkerLaunchTarget::PackExe(path) = resolve_worker_launch_target() {
            match check_pack_manifest_for_exe(&path) {
                PackProtoStatus::Match { .. } => {}
                PackProtoStatus::Mismatch { min_proto_version } => {
                    log::warn!(
                        "[WORKER-INIT] refusing stale pack (min_proto_version={min_proto_version}, \
                         host supports {HOST_MIN_PROTO_VERSION}..={HOST_PROTO_VERSION}): outdated signal emitted"
                    );
                    relay_pack_outdated_to_sidecar(app_handle, &pack_version(), min_proto_version);
                    state.respawn_in_progress.store(false, Ordering::SeqCst);
                    return;
                }
                PackProtoStatus::MissingManifest { reason } => {
                    log::warn!(
                        "[WORKER-INIT] pack manifest {reason}, refusing pack worker launch (fail-closed)"
                    );
                    state.respawn_in_progress.store(false, Ordering::SeqCst);
                    return;
                }
            }
        }
    }
    initialize_worker(app_handle, state.clone()).await;
    state.respawn_in_progress.store(false, Ordering::SeqCst);
}

/// Stale-pack signal for the UI: the pack's
/// `min_proto_version` fell outside the host range, so the UI offers
/// re-download instead of a dead worker.
pub(crate) const PACK_OUTDATED_EVENT: &str = "offline_pack_outdated";

/// Pure outdated payload. Versions stay typed (E9: u32 both sides).
pub(crate) fn pack_outdated_payload(version: &str, min_proto_version: u32) -> Value {
    json!({
        "version": version,
        "min_proto_version": min_proto_version,
        "host_min_proto_version": HOST_MIN_PROTO_VERSION,
        "host_proto_version": HOST_PROTO_VERSION,
    })
}

/// Pure frame for the host→sidecar hop. Wire shape (until the sidecar
/// slice intercepts it, the frame lands as an orphaned-reply debug,
/// never a UI error):
/// `{"type": "offline_pack_outdated", "data": {...}, "id": N}`.
pub(crate) fn pack_outdated_relay_frame(version: &str, min_proto_version: u32, id: u64) -> Value {
    json!({"type": PACK_OUTDATED_EVENT, "data": pack_outdated_payload(version, min_proto_version), "id": id})
}

/// Best-effort immediate send over the host→sidecar hop.
fn send_pack_outdated_frame(
    state: &Arc<SidecarState>,
    version: &str,
    min_proto_version: u32,
) -> Option<u64> {
    let ws_tx = state_lock(&state.ws_tx).clone()?;
    let id = state.next_id.fetch_add(1, Ordering::Relaxed);
    let frame = pack_outdated_relay_frame(version, min_proto_version, id);
    match ws_tx.try_send(Message::Text(frame.to_string().into())) {
        Ok(_) => {
            log::info!(
                "[WORKER-INIT] pack-outdated relay sent (version={}, min_proto_version={}, id={})",
                version,
                min_proto_version,
                id
            );
            Some(id)
        }
        Err(e) => {
            log::warn!(
                "[WORKER-INIT] pack-outdated relay try_send failed (id={}): {}",
                id,
                e
            );
            None
        }
    }
}

/// Emit the outdated signal: direct renderer event first (drives the
/// UI with no sidecar round-trip), then the sidecar hop with the same
/// bounded retry as the worker_started relay (cold-start race cover).
pub(crate) fn relay_pack_outdated_to_sidecar(
    app: &tauri::AppHandle,
    version: &str,
    min_proto_version: u32,
) {
    let _ = app.emit(
        PACK_OUTDATED_EVENT,
        pack_outdated_payload(version, min_proto_version),
    );
    let state: tauri::State<'_, Arc<SidecarState>> = app.state();
    let state = state.inner().clone();
    if send_pack_outdated_frame(&state, version, min_proto_version).is_some() {
        return;
    }
    log::info!("[WORKER-INIT] sidecar link down, retrying pack-outdated relay");
    let version = version.to_string();
    tauri::async_runtime::spawn(async move {
        for _ in 0..RELAY_RETRY_ATTEMPTS {
            tokio::time::sleep(std::time::Duration::from_millis(RELAY_RETRY_INTERVAL_MS)).await;
            if state.shutting_down.load(Ordering::SeqCst) {
                return;
            }
            if send_pack_outdated_frame(&state, &version, min_proto_version).is_some() {
                return;
            }
        }
        log::warn!("[WORKER-INIT] pack-outdated relay undelivered after retries");
    });
}

/// ADR-0024 Step 2 port relay: host pushes `worker_started
/// {pid, version, port}` to the sidecar over the existing host↔sidecar
/// WS hop (fire-and-forget TEXT frame + numeric id, same envelope as
/// `send_fire_and_forget_frame`). `port` is additive: old
/// {pid, version} readers keep working, no allowlist churn.
/// NOTE: see docs/code-notes/worker-port-relay.md#host-emit

/// Pure frame constructor. `port` is u16 on both sides of the hop
/// (E9); the sidecar validates 1..=65535 and drops anything else.
pub(crate) fn worker_started_relay_frame(pid: u32, version: &str, port: u16, id: u64) -> Value {
    json!({"type": "worker_started", "data": {"pid": pid, "version": version, "port": port}, "id": id})
}

/// Best-effort immediate send. `Some(id)` on queued, `None` when the
/// sidecar link is down (caller falls back to the bounded retry).
fn send_worker_started_frame(
    state: &Arc<SidecarState>,
    pid: u32,
    version: &str,
    port: u16,
) -> Option<u64> {
    let ws_tx = state_lock(&state.ws_tx).clone()?;
    let id = state.next_id.fetch_add(1, Ordering::Relaxed);
    let frame = worker_started_relay_frame(pid, version, port, id);
    match ws_tx.try_send(Message::Text(frame.to_string().into())) {
        Ok(_) => {
            log::info!(
                "[WORKER-INIT] worker_started relay sent (pid={}, port={}, id={})",
                pid,
                port,
                id
            );
            Some(id)
        }
        Err(e) => {
            log::warn!(
                "[WORKER-INIT] worker_started relay try_send failed (id={}): {}",
                id,
                e
            );
            None
        }
    }
}

// Cold-start race cover: worker and sidecar spawn in parallel, so the
// link may be down when the worker bind lands. Bounded so a dead link
// can never retry forever (respawn policy is Step 5 territory).
const RELAY_RETRY_ATTEMPTS: u32 = 20;
const RELAY_RETRY_INTERVAL_MS: u64 = 500;

/// Relay the worker bind to the sidecar. Skips (warn) when the pid is
/// unknown rather than sending a garbage pid; retries briefly when the
/// sidecar link is not up yet.
pub(crate) fn relay_worker_started_to_sidecar(app: &tauri::AppHandle, pid: Option<u32>, port: u16) {
    let pid = match pid {
        Some(pid) => pid,
        None => {
            log::warn!(
                "[WORKER-INIT] worker pid unknown, skipping worker_started relay (port={})",
                port
            );
            return;
        }
    };
    let version = crate::platform::worker_path::pack_version();
    let state: tauri::State<'_, Arc<SidecarState>> = app.state();
    let state = state.inner().clone();
    if send_worker_started_frame(&state, pid, &version, port).is_some() {
        return;
    }
    log::info!(
        "[WORKER-INIT] sidecar link down, retrying worker_started relay (port={})",
        port
    );
    tauri::async_runtime::spawn(async move {
        for _ in 0..RELAY_RETRY_ATTEMPTS {
            tokio::time::sleep(std::time::Duration::from_millis(RELAY_RETRY_INTERVAL_MS)).await;
            if state.shutting_down.load(Ordering::SeqCst) {
                return;
            }
            if send_worker_started_frame(&state, pid, &version, port).is_some() {
                return;
            }
        }
        log::warn!(
            "[WORKER-INIT] worker_started relay undelivered after retries (port={})",
            port
        );
    });
}

/// `offline_pack_verified` trigger (called from the WS reader, sync
/// context: the async work runs on a spawned task, never `block_on`:
/// C-TOKIO-1). Delegates to the shared start sequence so a bad pack
/// can never trip a respawn loop (no supervisor yet, plan §7.2).
pub(crate) fn on_pack_verified(app: &tauri::AppHandle) {
    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        let state = app_handle.state::<Arc<WorkerState>>().inner().clone();
        start_worker_if_ready(&app_handle, state).await;
    });
}

// Sibling test module: tests live in `worker_tests.rs` (per C-TEST-5:
// no inline `#[cfg(test)] mod tests` blocks in production source).
#[cfg(test)]
#[path = "worker_tests.rs"]
mod worker_tests;
