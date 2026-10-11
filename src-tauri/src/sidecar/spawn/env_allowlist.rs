pub(crate) fn passthrough_env_allowlist() -> Vec<(std::ffi::OsString, std::ffi::OsString)> {
    let mut out: Vec<(std::ffi::OsString, std::ffi::OsString)> = Vec::new();

    // Always-pass (cross-platform)
    const ALWAYS: &[&str] = &["PATH", "USER", "LANG", "TEMP", "TMP", "TMPDIR"];
    for name in ALWAYS {
        if let Some(val) = std::env::var_os(name) {
            out.push((std::ffi::OsString::from(name), val));
        }
    }

    // ── Colour decision (ANSI palette) ────────────────────────────────
    //
    // `tauri dev` spawns the app with a PIPED stderr
    // (`tauri-cli/src/interface/rust/desktop.rs`) and this host then spawns
    // the sidecar with `Stdio::inherit()`, so the sidecar inherits that
    // pipe: `sys.stderr.isatty()` is false and Python's `_ColorFormatter`
    // is silently bypassed for its plain `_TerminalFormatter`. The one
    // process that still owns the real terminal, `scripts/tauri-dev.mjs`,
    // states the decision explicitly, so the two vars carrying it MUST
    // reach the sidecar or the restore stops at the host boundary.
    // `NO_COLOR`/`FORCE_COLOR=0` are the user's explicit opt-outs and must
    // travel just as faithfully.
    const COLOR: &[&str] = &["FORCE_COLOR", "NO_COLOR"];
    for name in COLOR {
        if let Some(val) = std::env::var_os(name) {
            out.push((std::ffi::OsString::from(name), val));
        }
    }

    // POSIX: HOME
    #[cfg(unix)]
    if let Some(val) = std::env::var_os("HOME") {
        out.push((std::ffi::OsString::from("HOME"), val));
    }

    // Windows: USERPROFILE + USERNAME + SYSTEMROOT
    // USERNAME is required by the Windows ACL check on the config dir.
    #[cfg(windows)]
    if let Some(val) = std::env::var_os("USERPROFILE") {
        out.push((std::ffi::OsString::from("USERPROFILE"), val));
    }
    #[cfg(windows)]
    if let Some(val) = std::env::var_os("USERNAME") {
        out.push((std::ffi::OsString::from("USERNAME"), val));
    }
    #[cfg(windows)]
    if let Some(val) = std::env::var_os("SYSTEMROOT") {
        out.push((std::ffi::OsString::from("SYSTEMROOT"), val));
    }

    for (name, val) in std::env::vars_os() {
        if let Some(s) = name.to_str() {
            if s.starts_with("LC_") {
                out.push((name, val));
            }
        }
    }

    // ── Linux: GUI + session bus ──────────────────────────────────
    #[cfg(target_os = "linux")]
    {
        const LINUX_GUI: &[&str] = &[
            "DISPLAY",
            "WAYLAND_DISPLAY",
            "XDG_RUNTIME_DIR",
            "XDG_DATA_HOME",
            "XDG_CONFIG_HOME",
            "DBUS_SESSION_BUS_ADDRESS",
            "XDG_SESSION_TYPE",
            "XDG_CURRENT_DESKTOP",
        ];
        for name in LINUX_GUI {
            if let Some(val) = std::env::var_os(name) {
                out.push((std::ffi::OsString::from(name), val));
            }
        }
    }

    #[cfg(target_os = "macos")]
    if let Some(val) = std::env::var_os("XPC_SERVICE_NAME") {
        out.push((std::ffi::OsString::from("XPC_SERVICE_NAME"), val));
    }

    out
}

pub(crate) fn vt_start_hidden_env() -> Option<(std::ffi::OsString, std::ffi::OsString)> {
    std::env::var_os("VT_START_HIDDEN")
        .map(|val| (std::ffi::OsString::from("VT_START_HIDDEN"), val))
}
