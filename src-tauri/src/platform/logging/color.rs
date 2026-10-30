//! ANSI palette for the host's stderr terminal sink.
//!
//! Restored from the Electron main process's `src/main/logging/colors.ts`,
//! deleted together with the Electron shell (`17461108`
//! `refactor(client)!: delete Electron shell, Tauri-only frontend`), and
//! kept byte-identical to the Python sidecar's `_ColorFormatter`
//! (`voice_typer/server/log/formatters.py`) so the Rust host and the Python
//! sidecar render the same palette in one terminal.
//!
//! Why the HOST has to own this: `tauri dev` spawns the app with a PIPED
//! stderr (`tauri-cli/src/interface/rust/desktop.rs`:
//! `dev_cmd.stdout(os_pipe::dup_stdout())` + `dev_cmd.stderr(Stdio::piped())`),
//! and this host then spawns the Python sidecar with `Stdio::inherit()`. So
//! neither process can see a terminal, and Python's
//! `do_color = sys.stderr.isatty()` gate silently falls back to its plain
//! formatter. `scripts/tauri-dev.mjs`, the only process in the chain that
//! still owns the real terminal, decides once and exports `FORCE_COLOR`;
//! this module honours it.
//!
//! C-LOG-1 is preserved: [`colorize_terminal_line`] produces EXACTLY the
//! bytes of `format_terminal_line` plus ANSI wrappers, so stripping the
//! escape codes yields the pinned plain line for every level.

use std::io::IsTerminal;
use std::sync::OnceLock;

use super::combined::format_terminal_line;

/// Dim grey, for the timestamp of INFO/DEBUG lines.
const DIM: &str = "38;5;242";

/// WARN: yellow. NOT `38;5;214` (orange) — Windows conhost's 256->16-colour
/// quantization maps orange to bright-red, which inverted WARN and ERROR.
/// Same fix the Python side carries (`LOG-COLOR-FIX` in `formatters.py`).
const WARN: &str = "38;5;226";

/// ERROR: bright red.
const ERROR: &str = "38;5;196";

/// `[TOPIC]` -> colour, mirroring Python's `_TOPIC_COLOR` exactly
/// (`voice_typer/server/log/formatters.py`). A parity test in
/// `logging_tests.rs` reads the Python table and pins the two in step, so a
/// new topic added on the Python side fails the Rust suite instead of
/// silently rendering uncoloured.
pub(crate) const TOPIC_COLOR: &[(&str, &str)] = &[
    ("PARAKEET", "38;5;69"),
    ("QWEN", "38;5;69"),
    ("MODEL", "38;5;69"),
    ("CUDA-PROBE", "38;5;75"),
    ("HOTKEY", "38;5;141"),
    ("HOTKEY FIRED", "38;5;141"),
    ("HOTKEY FALLBACK", "38;5;141"),
    ("KEYBOARD_OWNERSHIP", "38;5;141"),
    ("RECORDING", "38;5;79"),
    ("AUDIO_QUALITY", "38;5;215"),
    ("DICTATION", "38;5;215"),
    ("TRANSCRIBE", "38;5;120"),
    ("VOLUME", "38;5;111"),
    ("VAD", "38;5;245"),
    ("CLIPBOARD", "38;5;120"),
    ("STARTUP", "38;5;103"),
    ("STREAMING", "38;5;110"),
    ("CLOUD", "38;5;110"),
    ("FOCUS", "38;5;102"),
    ("CLEANUP", "38;5;102"),
    ("TEMPLATE", "38;5;102"),
    ("WIN32", "38;5;102"),
    ("SIGNAL", "38;5;102"),
    ("HISTORY", "38;5;102"),
    ("HISTORY_DB", "38;5;102"),
    ("SHUTDOWN", "38;5;95"),
    ("QUIT", "38;5;95"),
    ("RESTART", "38;5;95"),
    ("CANCEL", "38;5;215"),
    ("CRASH", "38;5;167"),
    ("ENV", "38;5;103"),
    ("LAUNCHER", "38;5;110"),
    ("MIC-WATCHER", "38;5;215"),
    ("REPASTE", "38;5;120"),
    ("CONFIG", "38;5;102"),
    ("TRAY", "38;5;102"),
    ("LLM_POLISH", "38;5;140"),
    ("ASR_REGISTRY", "38;5;141"),
    ("ASR_SETUP", "38;5;102"),
    ("WAVEFORM", "38;5;102"),
    ("ONBOARDING", "38;5;102"),
    ("RECOVERY", "38;5;102"),
    ("ATEXIT", "38;5;102"),
    ("PIPELINE", "38;5;102"),
    ("IPC", "38;5;102"),
    ("TCP", "38;5;244"),
    ("A11Y", "38;5;102"),
    ("AI_ENHANCE", "38;5;140"),
    ("APP", "38;5;102"),
    ("AUDIO-CHAIN", "38;5;215"),
    ("AUDIO-MIC", "38;5;215"),
    ("AUDIO-PROC", "38;5;215"),
    ("AUMID", "38;5;102"),
    ("AUTOSTART", "38;5;103"),
    ("BUBBLE", "38;5;102"),
    ("BUNDLE-ID", "38;5;102"),
    ("CLIPBOARD-AUDIT", "38;5;120"),
    ("CLIPBOARD-SNAPSHOT", "38;5;120"),
    ("CONFIG-SANITIZER", "38;5;102"),
    ("CRASH-BUF", "38;5;167"),
    ("CREDENTIAL_STORE", "38;5;102"),
    ("CUDA-DLL", "38;5;75"),
    ("DISK", "38;5;102"),
    ("dispatch", "38;5;110"),
    ("GPU", "38;5;75"),
    ("GTCRN", "38;5;69"),
    ("HEARTBEAT", "38;5;110"),
    ("HIGHPASS", "38;5;69"),
    ("HOST-EVENTS", "38;5;102"),
    ("HOTKEY-WAYLAND", "38;5;141"),
    ("INIT", "38;5;103"),
    ("KILL-TREE", "38;5;103"),
    ("LEVEL-MON", "38;5;215"),
    ("LOG-SETUP", "38;5;102"),
    ("MEDIA", "38;5;110"),
    ("MIC", "38;5;215"),
    ("MIC-GUARD", "38;5;215"),
    ("MIC-WATCHER-CA", "38;5;215"),
    ("MIGRATE", "38;5;102"),
    ("NATIVE-BINARY", "38;5;102"),
    ("NATIVE-HOTKEY", "38;5;141"),
    ("NOISE-SUPPRESS", "38;5;69"),
    ("NOTCH", "38;5;69"),
    ("PACK", "38;5;102"),
    ("PAUSE", "38;5;215"),
    ("PERF", "38;5;111"),
    ("PERMISSION", "38;5;111"),
    ("PIPELINE-PERF", "38;5;111"),
    ("PLATFORM", "38;5;102"),
    ("POWER", "38;5;102"),
    ("PREWARM", "38;5;103"),
    ("PROC-CHAIN", "38;5;102"),
    ("QWEN-ONNX", "38;5;69"),
    ("RECORDER", "38;5;79"),
    ("RESOURCE", "38;5;102"),
    ("SECURITY", "38;5;167"),
    ("SERVICE", "38;5;110"),
    ("SESSION", "38;5;102"),
    ("SETUP", "38;5;103"),
    ("SHORTCUTS", "38;5;141"),
    ("SIDECAR-DEV", "38;5;110"),
    ("SIDECAR-ENV", "38;5;110"),
    ("SIDECAR-WS", "38;5;110"),
    ("START", "38;5;103"),
    ("SUPERVISOR", "38;5;103"),
    ("TASK", "38;5;102"),
    ("TEMPLATES", "38;5;102"),
    ("THEME-ICON", "38;5;102"),
    ("THREAD-REGISTRY", "38;5;102"),
    ("TIMER", "38;5;102"),
    ("UNDO", "38;5;120"),
    ("UNINSTALL", "38;5;95"),
    ("UPDATE", "38;5;110"),
    ("URL-Allowlist", "38;5;110"),
    ("WORKER", "38;5;110"),
    ("WORKER-DEV", "38;5;110"),
    ("WORKER-INIT", "38;5;110"),
    ("WORKER-PATH", "38;5;110"),
    ("VOCAB", "38;5;102"),
    ("VOCAB_AUTO", "38;5;102"),
    ("VOLUME-CRASH", "38;5;167"),
    ("VOLUME-LINUX", "38;5;111"),
    ("VOLUME-MAC", "38;5;111"),
    ("VOLUME-WIN", "38;5;111"),
    ("WS", "38;5;110"),
    ("WS-AUTH", "38;5;110"),
    ("WS-READER", "38;5;110"),
    ("WS-WRITER", "38;5;110"),
    ("XRUN", "38;5;215"),
    ("YTDLP", "38;5;110"),
];

/// Look up a `[TOPIC]` label's colour.
pub(crate) fn topic_color_for(topic: &str) -> Option<&'static str> {
    TOPIC_COLOR
        .iter()
        .find(|(name, _)| *name == topic)
        .map(|(_, color)| *color)
}

/// Extract the bracketed topic prefix, e.g. `"[WS] connected"` -> `"WS"`.
///
/// Mirrors Python's `_extract_topic`. Only the literal prefix is honoured;
/// Python additionally infers a topic from message keywords
/// (`_TOPIC_KEYWORDS`), which the host does not need: every host log line
/// already carries an explicit `[TAG]` prefix.
fn extract_topic(msg: &str) -> Option<&str> {
    let rest = msg.strip_prefix('[')?;
    let close = rest.find(']')?;
    Some(&rest[..close])
}

/// Pure form of the colour gate, for unit testing (no caching, no globals).
///
/// `NO_COLOR` always wins. An explicit `FORCE_COLOR` then decides, using the
/// conventional values (`""`/`1`/`true`/`yes` on, `0`/`false`/`no` off).
/// With neither set, a terminal is required.
pub(crate) fn color_enabled_for(
    no_color: bool,
    force_color: Option<&str>,
    is_terminal: bool,
) -> bool {
    if no_color {
        return false;
    }
    match force_color {
        Some(v) => match v.trim().to_ascii_lowercase().as_str() {
            "" | "1" | "true" | "yes" => true,
            "0" | "false" | "no" => false,
            _ => is_terminal,
        },
        None => is_terminal,
    }
}

/// Production colour gate: reads the environment once and caches the result.
pub(crate) fn color_enabled() -> bool {
    static ENABLED: OnceLock<bool> = OnceLock::new();
    *ENABLED.get_or_init(|| {
        color_enabled_for(
            std::env::var_os("NO_COLOR").is_some(),
            std::env::var("FORCE_COLOR").ok().as_deref(),
            std::io::stderr().is_terminal(),
        )
    })
}

/// Render one terminal line with the restored palette.
///
/// Stripping the ANSI wrappers yields the plain line, except INFO (see
/// below); colour is a wrapper, never the template:
///
/// * WARN/ERROR take a FULL-LINE colour, exactly like Python's
///   `_ColorFormatter` does for `levelno >= WARNING`.
/// * INFO carries no level label: dim timestamp plus the
///   topic-coloured (or plain) message, like Python.
/// * DEBUG renders label + body in one colour; only the timestamp
///   stays dim, like Python.
///
/// With colour disabled every branch collapses to the plain line.
pub(crate) fn colorize_terminal_line(ts: &str, level: log::Level, msg: &str) -> String {
    colorize_with(ts, level, msg, color_enabled())
}

/// Pure form of [`colorize_terminal_line`], for unit testing.
pub(crate) fn colorize_with(ts: &str, level: log::Level, msg: &str, enabled: bool) -> String {
    if !enabled {
        return format_terminal_line(ts, level, msg);
    }
    match level {
        log::Level::Warn | log::Level::Error => {
            let color = if level == log::Level::Error {
                ERROR
            } else {
                WARN
            };
            format!("\x1b[{color}m{ts}  {level:5} {msg}\x1b[0m")
        }
        log::Level::Info => {
            let body = match extract_topic(msg).and_then(topic_color_for) {
                Some(color) => format!("\x1b[{color}m{msg}\x1b[0m"),
                None => msg.to_string(),
            };
            format!("\x1b[{DIM}m{ts}\x1b[0m  {body}")
        }
        log::Level::Debug => {
            let rest = format!("DEBUG {msg}");
            match extract_topic(msg).and_then(topic_color_for) {
                Some(color) => format!("\x1b[{DIM}m{ts}\x1b[0m  \x1b[{color}m{rest}\x1b[0m"),
                None => format!("\x1b[{DIM}m{ts}\x1b[0m  {rest}"),
            }
        }
        _ => {
            let body = match extract_topic(msg).and_then(topic_color_for) {
                Some(color) => format!("\x1b[{color}m{msg}\x1b[0m"),
                None => msg.to_string(),
            };
            format!("\x1b[{DIM}m{ts}\x1b[0m  {level:5} {body}")
        }
    }
}
