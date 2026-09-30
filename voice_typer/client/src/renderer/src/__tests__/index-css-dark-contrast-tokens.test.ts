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

describe("index.css .dark, opaque input token", () => {
	it("--input is opaque (no alpha) at the preset dark lightness", () => {
		const match = /--input:\s*([^;]+);/.exec(darkBlock());
		const value = match?.[1];
		if (!value) throw new Error("no --input declaration in the .dark block");
		expect(value.trim()).not.toContain("/");
		// Current dark input token is the percent-form lightness `oklch(25% 0 0)`
		// (opaque, no alpha). Keep this pinned so an alpha composite cannot
		// sneak back into the base fallback.
		expect(value.trim()).toMatch(/^oklch\(25%/);
	});

	it("no alpha-composited oklch(1 0 0 / N%) tokens remain in the .dark block", () => {
		expect(darkBlock()).not.toMatch(/oklch\(1 0 0 \//);
	});
});
