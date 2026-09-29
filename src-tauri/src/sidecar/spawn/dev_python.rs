//! Resolve the interpreter for the source sidecar / worker in dev mode.
//! Bare `python.exe` is often missing from GUI-launched PATH; prefer
//! explicit env overrides and the repo virtualenv first.

use std::path::PathBuf;

fn candidate_paths() -> Vec<PathBuf> {
    let mut out = Vec::new();
    for key in ["VOICE_TYPER_PYTHON", "MIMO_PYTHON"] {
        if let Some(v) = std::env::var_os(key) {
            out.push(PathBuf::from(v));
        }
    }
    // Repo-root .venv (tauri dev runs with cwd = repo root or src-tauri/).
    if let Ok(cwd) = std::env::current_dir() {
        let roots = [cwd.clone(), cwd.parent().map(|p| p.to_path_buf()).unwrap_or(cwd)];
        for root in roots {
            if cfg!(windows) {
                out.push(root.join(".venv").join("Scripts").join("python.exe"));
            } else {
                out.push(root.join(".venv").join("bin").join("python3"));
                out.push(root.join(".venv").join("bin").join("python"));
            }
        }
    }
    out
}

/// Return the best available Python launcher (absolute path when known).
pub(crate) fn resolve_dev_python() -> String {
    for cand in candidate_paths() {
        if cand.is_file() {
            return cand.to_string_lossy().into_owned();
        }
    }
    // PATH fallback (tauri-dev.mjs prepends .venv\Scripts as well).
    if cfg!(windows) {
        "python.exe".to_string()
    } else {
        "python3".to_string()
    }
}
