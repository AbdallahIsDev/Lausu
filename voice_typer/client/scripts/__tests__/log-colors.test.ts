// @vitest-environment node
/**
 * TTY + env gating for the restored ANSI palette (`scripts/log-colors.mjs`).
 *
 * This is the Tauri-era successor of the deleted Electron guard
 * `src/main/logging/__tests__/colors-tty.test.ts`. The original contract is
 * preserved: colours are emitted ONLY when a terminal is attached, so
 * redirected output (files, pipes, CI) stays clean and grep-friendly —
 * mirroring Node's own `isTTY` detection and the Python side's
 * `do_color = sys.stderr.isatty()` gate.
 *
 * One behaviour is NEW, and it is the whole point of the restore: the Tauri
 * dev chain loses the TTY (`tauri dev` spawns the app with a piped stderr,
 * and the Rust host then hands that pipe to the Python sidecar), so an
 * explicit `FORCE_COLOR` must be able to turn the palette back on for a
 * descendant that cannot see a terminal itself. `NO_COLOR` always wins.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

const ENV_KEYS = ["FORCE_COLOR", "NO_COLOR"] as const;

function setTty(value: boolean): void {
	Object.defineProperty(process.stdout, "isTTY", {
		value,
		configurable: true,
	});
	Object.defineProperty(process.stderr, "isTTY", {
		value,
		configurable: true,
	});
}

function clearEnv(): void {
	for (const key of ENV_KEYS) {
		delete process.env[key];
	}
}

type Palette = {
	ANSI_ENABLED_FLAG: boolean;
	DIM: string;
	RESET: string;
	BUBBLE_CLR: string;
	RENDERER_CLR: string;
	INFO_CLR: string;
	WARN_CLR: string;
	ERROR_CLR: string;
};

async function load(): Promise<Palette> {
	return (await import("../log-colors.mjs")) as unknown as Palette;
}

afterEach(() => {
	vi.resetModules();
	clearEnv();
	setTty(false);
});

describe("restored palette resolves to empty strings when output is redirected", () => {
	it("no terminal, no env override", async () => {
		clearEnv();
		setTty(false);
		const p = await load();
		expect(p.ANSI_ENABLED_FLAG).toBe(false);
		expect(p.DIM).toBe("");
		expect(p.RESET).toBe("");
		expect(p.BUBBLE_CLR).toBe("");
		expect(p.RENDERER_CLR).toBe("");
		expect(p.INFO_CLR).toBe("");
		expect(p.WARN_CLR).toBe("");
		expect(p.ERROR_CLR).toBe("");
	});

	it("FORCE_COLOR=0 turns the palette off even on a terminal", async () => {
		setTty(true);
		process.env.FORCE_COLOR = "0";
		const p = await load();
		expect(p.ANSI_ENABLED_FLAG).toBe(false);
		expect(p.WARN_CLR).toBe("");
		expect(p.ERROR_CLR).toBe("");
	});
});

describe("restored palette emits the original codes", () => {
	it("on a terminal, byte-identical to the deleted Electron colors.ts", async () => {
		clearEnv();
		setTty(true);
		const p = await load();
		expect(p.ANSI_ENABLED_FLAG).toBe(true);
		expect(p.DIM).toBe("\x1b[38;5;242m");
		expect(p.RESET).toBe("\x1b[0m");
		expect(p.BUBBLE_CLR).toBe("\x1b[38;5;39m");
		expect(p.RENDERER_CLR).toBe("\x1b[38;5;227m");
		expect(p.INFO_CLR).toBe("\x1b[38;5;39m");
		// WARN stays yellow (38;5;226), never the orange 38;5;214 that
		// quantized to bright-red on Windows conhost.
		expect(p.WARN_CLR).toBe("\x1b[38;5;226m");
		expect(p.ERROR_CLR).toBe("\x1b[38;5;196m");
	});

	it("with FORCE_COLOR=1 even though there is NO terminal (the Tauri dev case)", async () => {
		setTty(false);
		process.env.FORCE_COLOR = "1";
		const p = await load();
		expect(p.ANSI_ENABLED_FLAG).toBe(true);
		expect(p.WARN_CLR).toBe("\x1b[38;5;226m");
		expect(p.ERROR_CLR).toBe("\x1b[38;5;196m");
	});
});

describe("NO_COLOR always wins", () => {
	it("beats a terminal", async () => {
		setTty(true);
		process.env.NO_COLOR = "1";
		const p = await load();
		expect(p.ANSI_ENABLED_FLAG).toBe(false);
		expect(p.INFO_CLR).toBe("");
	});

	it("beats FORCE_COLOR=1", async () => {
		setTty(false);
		process.env.NO_COLOR = "1";
		process.env.FORCE_COLOR = "1";
		const p = await load();
		expect(p.ANSI_ENABLED_FLAG).toBe(false);
		expect(p.ERROR_CLR).toBe("");
	});
});
