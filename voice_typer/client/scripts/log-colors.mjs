/**
 * ANSI colour constants for the Tauri dev orchestrator (`tauri-dev.mjs`).
 *
 * Restored from the Electron main process's `src/main/logging/colors.ts`,
 * which was deleted together with the Electron shell in `17461108`
 * (`refactor(client)!: delete Electron shell, Tauri-only frontend`). Only
 * the module syntax changed (TypeScript -> ESM); every colour code is
 * byte-identical to the deleted original, so the terminal looks the way it
 * did before the migration.
 *
 * The palette matches the Python backend's `_ColorFormatter`
 * (`voice_typer/server/log/formatters.py`) and the Rust host's
 * `platform::logging::color` module, so Node, Rust and Python log lines
 * look identical in one terminal.
 *
 * WARN is `38;5;226` (yellow), NOT `38;5;214` (orange): on Windows conhost
 * (the default terminal for `cargo tauri dev` on Windows) 256->16-colour
 * quantization maps orange to bright-red, which made WARN look red and
 * ERROR look yellow, the exact inversion the Python colour-quantization fix
 * was designed to prevent.
 *
 * Leaf module, no imports.
 */

/** Truthy matcher for `FORCE_COLOR`: `"1"` / `"true"` / `"yes"`, or empty. */
function truthy(value) {
	const v = (value ?? "").trim().toLowerCase();
	return v === "" || v === "1" || v === "true" || v === "yes";
}

/** Falsy matcher for `FORCE_COLOR`: `"0"` / `"false"` / `"no"`. */
function falsy(value) {
	const v = (value ?? "").trim().toLowerCase();
	return v === "0" || v === "false" || v === "no";
}

// ANSI colours are emitted ONLY when attached to a terminal. When output is
// redirected to files, pipes, or CI, every constant below resolves to "" so
// NO escape codes reach the file, the log stays clean, `less`-friendly and
// grep-safe. Mirrors Node's own `isTTY` detection and the Python side's
// `do_color = sys.stderr.isatty()` gate; a real terminal keeps the full
// palette.
//
// The env overrides are checked FIRST because the Tauri dev chain loses the
// TTY: `tauri dev` spawns the app with a PIPED stderr
// (`tauri-cli/src/interface/rust/desktop.rs`), so a descendant cannot detect
// the terminal by itself and must be told. `NO_COLOR` always wins.
const ANSI_ENABLED = process.env.NO_COLOR
	? false
	: process.env.FORCE_COLOR !== undefined && truthy(process.env.FORCE_COLOR)
		? true
		: falsy(process.env.FORCE_COLOR)
			? false
			: Boolean(process.stdout?.isTTY || process.stderr?.isTTY);

/** Internal flag: whether a terminal is attached (colours enabled). */
export const ANSI_ENABLED_FLAG = ANSI_ENABLED;

const esc = (code) => (ANSI_ENABLED ? `\x1b[${code}m` : "");

/** Dim grey for timestamps. */
export const DIM = esc("38;5;242");

/** ANSI reset. */
export const RESET = ANSI_ENABLED ? "\x1b[0m" : "";

/** Bright cyan for `[BUBBLE]` tags. */
export const BUBBLE_CLR = esc("38;5;39");

/** Bright yellow for `[MAIN renderer]` tags. */
export const RENDERER_CLR = esc("38;5;227");

/**
 * Bright cyan for the structured `log` logger's `[INFO]` prefix.
 * Intentionally matches `BUBBLE_CLR`, INFO is the "happy" level and
 * visually parallels the `[BUBBLE]` tag colour.
 */
export const INFO_CLR = esc("38;5;39");

/** Yellow (`38;5;226`) for `[WARN]` prefixes; matches Python's WARN. */
export const WARN_CLR = esc("38;5;226");

/** Bright red for `[ERROR]` prefixes. */
export const ERROR_CLR = esc("38;5;196");
