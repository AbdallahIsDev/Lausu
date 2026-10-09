import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Contract pins for the boot-failure fallback (public/boot-fallback.js +
// its index.html wiring + the main.tsx handshake). The fallback runs
// dependency-free outside the module graph by design, so it cannot be
// covered by a behavioral render test; these source pins are the
// regression net (same pattern as the Dashboard source-shape tests).
const RENDERER_ROOT = path.resolve(__dirname, "..", "..");
const FALLBACK_SRC = fs.readFileSync(
	path.join(RENDERER_ROOT, "public", "boot-fallback.js"),
	"utf8",
);
const INDEX_SRC = fs.readFileSync(
	path.join(RENDERER_ROOT, "index.html"),
	"utf8",
);
const MAIN_SRC = fs.readFileSync(
	path.join(RENDERER_ROOT, "src", "main.tsx"),
	"utf8",
);

describe("boot-failure fallback contract", () => {
	it("fallback stands down on the boot flag and offers reload", () => {
		expect(FALLBACK_SRC).toMatch(/__lausu_booted/);
		expect(FALLBACK_SRC).toMatch(/__lausu_bootFailedDismiss/);
		expect(FALLBACK_SRC).toMatch(/location\.reload/);
	});

	it("fallback renders loader text safely (no remote, no HTML injection)", () => {
		// Same-origin only: a remote URL here would be a C-DATA-1 hole.
		expect(FALLBACK_SRC).not.toMatch(/https?:\/\//);
		// Loader detail goes through textContent, never innerHTML.
		expect(FALLBACK_SRC).toMatch(/textContent/);
	});

	it("index.html loads the fallback before the module graph", () => {
		const fallbackAt = INDEX_SRC.indexOf("/boot-fallback.js");
		const mainAt = INDEX_SRC.indexOf("/src/main.tsx");
		expect(fallbackAt).toBeGreaterThan(-1);
		expect(mainAt).toBeGreaterThan(-1);
		// Classic script (runs first); module scripts always defer.
		expect(fallbackAt).toBeLessThan(mainAt);
	});

	it("main.tsx performs the boot handshake after first render", () => {
		expect(MAIN_SRC).toMatch(/__lausu_booted = true/);
		expect(MAIN_SRC).toMatch(/__lausu_bootFailedDismiss/);
	});
});
