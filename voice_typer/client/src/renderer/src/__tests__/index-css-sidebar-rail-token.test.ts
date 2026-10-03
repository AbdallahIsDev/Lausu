import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const cssPath = resolve(__dirname, "..", "index.css");
const css = readFileSync(cssPath, "utf8");

/** Extract the raw `.dark { ... }` block from the stylesheet. */
function darkBlock(): string {
	const start = css.indexOf(".dark {");
	expect(start).toBeGreaterThan(-1);
	const end = css.indexOf("}", start);
	expect(end).toBeGreaterThan(start);
	return css.slice(start, end);
}

/** Read a `--token: <value>;` declaration out of a CSS block. */
function tokenIn(block: string, name: string): string {
	const match = new RegExp(`--${name}:\\s*([^;]+);`).exec(block);
	const value = match?.[1];
	if (!value) throw new Error(`no --${name} declaration in block`);
	return value.trim();
}

/** OKLCH lightness (the L slot) of an `oklch(L C H)` literal. */
function lightness(value: string): number {
	const match = /oklch\(\s*([\d.]+)/.exec(value);
	const l = match?.[1];
	if (l === undefined) throw new Error(`not an oklch literal: ${value}`);
	return Number.parseFloat(l);
}

describe("index.css sidebar rail token", () => {
	it("the dark rail is DERIVED from --background, not a fixed palette step", () => {
		// The rail must stay "one step below the canvas" on every theme
		// preset. Presets override --background and never --sidebar, so a
		// literal step (e.g. `var(--gray-900)`) would make the rail LIGHTER
		// than the canvas on 9 of the 11 dark presets — amoled is L 0,
		// github L 0.11, ayu/tokyo-night L 0.12 — an inverted rail. Keeping
		// the reference to --background is what prevents that.
		const value = tokenIn(darkBlock(), "sidebar");
		expect(value).toContain("var(--background)");
		expect(value).toContain("color-mix(");
		expect(value).not.toMatch(/oklch\(/);
	});

	it("the dark rail is darker than the canvas (mix percentage below 100)", () => {
		const value = tokenIn(darkBlock(), "sidebar");
		const pct = /var\(--background\)\s+([\d.]+)%/.exec(value)?.[1];
		if (pct === undefined) {
			throw new Error(`no mix percentage found in: ${value}`);
		}
		const share = Number.parseFloat(pct);
		expect(share).toBeGreaterThan(0);
		expect(share).toBeLessThan(100);
	});

	it("resolves to gray-900 (#0f0f0f) on the default dark palette", () => {
		// The spec is "sidebar bg should be gray 900". The default dark
		// canvas is --gray-800 (L 0.187); the mix must land on the
		// --gray-900 lightness (L 0.168) — i.e. 0.187 x 90% = 0.168.
		const rootBlock = css.slice(css.indexOf(":root {"), css.indexOf(".dark {"));
		const value = tokenIn(darkBlock(), "sidebar");
		const pct = /var\(--background\)\s+([\d.]+)%/.exec(value)?.[1];
		if (pct === undefined) {
			throw new Error(`no mix percentage found in: ${value}`);
		}
		const share = Number.parseFloat(pct) / 100;

		const canvasL = lightness(tokenIn(rootBlock, "gray-800"));
		const railL = lightness(tokenIn(rootBlock, "gray-900"));
		expect(canvasL * share).toBeCloseTo(railL, 3);
	});

	it("light scheme: the rail is the canvas (no separate fill)", () => {
		// Light surfaces separate with borders, not fills. Deriving from
		// --background also lets light presets (sepia et al) flow through.
		const rootBlock = css.slice(css.indexOf(":root {"), css.indexOf(".dark {"));
		expect(tokenIn(rootBlock, "sidebar")).toBe("var(--background)");
	});
});
