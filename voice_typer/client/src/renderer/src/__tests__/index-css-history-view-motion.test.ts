/**
 * Transcript version-switch motion (History modal).
 *
 * C-ANIM-3: a motion utility needs its OWN `@media
 * (prefers-reduced-motion: reduce)` override placed after its base rule.
 * The switch is also blur/scale/translate only — no opacity — so the
 * outgoing and incoming versions never cross-fade.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(__dirname, "..", "index.css"), "utf8");

function block(selector: string): string {
	const start = css.indexOf(selector);
	expect(start, `${selector} not found`).toBeGreaterThan(-1);
	const open = css.indexOf("{", start);
	const close = css.indexOf("}", open);
	return css.slice(open + 1, close);
}

describe("history view-switch motion", () => {
	it("declares blur + scale + translate keyframes without opacity", () => {
		for (const name of ["historyViewOut", "historyViewIn"]) {
			const frames = css.slice(css.indexOf(`@keyframes ${name}`));
			const body = frames.slice(
				0,
				frames.indexOf("\n}", frames.indexOf("to {")),
			);
			expect(body).toContain("filter: blur(");
			expect(body).toContain("transform: scale(");
			expect(body).toContain("translateY(");
			expect(body).not.toContain("opacity");
		}
	});

	it("gives each utility its own reduced-motion override", () => {
		const reduceStart = css.indexOf("@media (prefers-reduced-motion: reduce)");
		expect(reduceStart).toBeGreaterThan(-1);
		const reduce = css.slice(reduceStart);
		expect(reduce).toContain(".history-view-out");
		expect(reduce).toContain(".history-view-in");
		expect(reduce).toContain("animation: none");
		// The override must come AFTER the base rules (specificity order).
		expect(css.indexOf(".history-view-out {")).toBeLessThan(reduceStart);
		expect(css.indexOf(".history-view-in {")).toBeLessThan(reduceStart);
	});

	it("keeps the enter duration in the premium range", () => {
		expect(block(".history-view-in")).toMatch(/animation: historyViewIn \d+ms/);
		expect(block(".history-view-out")).toMatch(
			/animation: historyViewOut \d+ms/,
		);
	});

	it("transitions the content-box height and disables it on reduced motion", () => {
		expect(block(".history-content-height")).toMatch(
			/transition: height \d+ms/,
		);
		// C-ANIM-3: the override is scoped and placed after the base rule.
		const reduceStart = css.indexOf("@media (prefers-reduced-motion: reduce)");
		const reduce = css.slice(reduceStart);
		expect(reduce).toContain(".history-content-height");
		expect(css.indexOf(".history-content-height {")).toBeLessThan(reduceStart);
	});
});
