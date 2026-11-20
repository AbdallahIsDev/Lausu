import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const cssPath = resolve(__dirname, "..", "index.css");
const css = readFileSync(cssPath, "utf8");
// Selector parsing runs on a comment-free copy: a `*/` immediately before a
// rule otherwise leaks a stray "/" into the selector list.
const cssNoComments = css.replace(/\/\*[\s\S]*?\*\//g, "");

/** Extract a top-level `@keyframes <name> { ... }` block (brace-balanced). */
function extractKeyframes(name: string): string | null {
	const marker = `@keyframes ${name} {`;
	const start = css.indexOf(marker);
	if (start === -1) return null;
	let depth = 0;
	for (let i = start + marker.length - 1; i < css.length; i++) {
		const ch = css[i];
		if (ch === "{") depth++;
		else if (ch === "}") {
			depth--;
			if (depth === 0) return css.slice(start, i + 1);
		}
	}
	return null;
}

/** Every declaration block, as `{selectorText, declarations}`. */
function rules(): { selectors: string[]; declarations: string }[] {
	const out: { selectors: string[]; declarations: string }[] = [];
	let cursor = 0;
	while (cursor < cssNoComments.length) {
		const open = cssNoComments.indexOf("{", cursor);
		if (open === -1) break;
		const close = cssNoComments.indexOf("}", open);
		if (close === -1) break;
		// A selector list stays inside one line-run before the brace; walk back
		// to the previous closing brace (or the document start) so grouped
		// selectors survive intact.
		const headStart =
			Math.max(
				cssNoComments.lastIndexOf("}", open - 1),
				cssNoComments.lastIndexOf(";", open - 1),
			) + 1;
		const selectors = cssNoComments
			.slice(headStart, open)
			.split(",")
			.map((entry) => entry.trim())
			.filter((entry) => entry !== "");
		out.push({
			selectors,
			declarations: cssNoComments.slice(open + 1, close),
		});
		cursor = close + 1;
	}
	return out;
}

const ALL_RULES = rules();

/** Declarations of every rule whose selector list contains `selector`. */
function declarationsFor(selector: string): string {
	return ALL_RULES.filter((rule) => rule.selectors.includes(selector))
		.map((rule) => rule.declarations)
		.join("\n");
}

/** Declarations of the LAST rule whose selector list contains `selector`. */
function lastDeclarationsFor(selector: string): string {
	const hits = ALL_RULES.filter((rule) => rule.selectors.includes(selector));
	const last = hits[hits.length - 1];
	return last ? last.declarations : "";
}

describe("glowPulse, compositor-only glow animation contract", () => {
	it("the keyframes animate opacity ONLY (no box-shadow repaint per frame)", () => {
		const keyframes = extractKeyframes("glowPulse");
		expect(keyframes).toBeTruthy();
		expect(keyframes).toContain("opacity");
		expect(keyframes).not.toContain("box-shadow");
	});

	it("the glow is a static box-shadow painted once on the ::after pseudo-element", () => {
		const shared = declarationsFor(".animate-glow-pulse::after");
		expect(shared).toContain("content:");
		expect(shared).toContain("position: absolute");
		// Inherit the host radius (the mic button is rounded-full) and
		// never intercept clicks.
		expect(shared).toContain("border-radius: inherit");
		expect(shared).toContain("pointer-events: none");
		// The paint itself is a static box-shadow, never an animated one.
		expect(shared).toContain("box-shadow:");
	});

	it("the host selector opts the element into positioning (relative) for the pseudo overlay", () => {
		const host = declarationsFor(".animate-glow-pulse");
		expect(host).toContain("position: relative");
	});

	it("the animation rhythm is preserved (2.5s ease-in-out infinite)", () => {
		expect(declarationsFor(".animate-glow-pulse::after")).toContain(
			"animation: glowPulse 2.5s ease-in-out infinite",
		);
	});

	it("prefers-reduced-motion still covers the pseudo-element (pulse stops)", () => {
		// Do NOT take the FIRST `@media (prefers-reduced-motion: reduce)`:
		// component-scoped blocks (bubble shimmer) may precede the global
		// one. Find the block that actually declares the global
		// `*` / `*::before` / `*::after` clamp.
		const anchor = css.indexOf("*::after");
		expect(anchor).toBeGreaterThanOrEqual(0);
		const start = css.lastIndexOf(
			"@media (prefers-reduced-motion: reduce)",
			anchor,
		);
		expect(start).toBeGreaterThanOrEqual(0);
		const reduceBlock = css.slice(start, css.indexOf("}", start) + 400);
		// The global selector list includes *::after, which matches the
		// glow pseudo-element, the 0.01ms/1-iteration clamp settles it
		// onto its base (static, dim) opacity instead of looping.
		expect(reduceBlock).toContain("*::after");
		expect(reduceBlock).toContain("animation-duration: 0.01ms");
		expect(reduceBlock).toContain("animation-iteration-count: 1");
	});

	it("glows in the brand accent while idle, never destructive (C-UI-12)", () => {
		// The idle mic button must not emit a red halo while NOT recording.
		const idle = lastDeclarationsFor(".animate-glow-pulse::after").length
			? // The idle colour is the only variant block that mentions primary.
				ALL_RULES.filter(
					(rule) =>
						rule.selectors.includes(".animate-glow-pulse::after") &&
						rule.declarations.includes("box-shadow"),
				)
					.map((rule) => rule.declarations)
					.join("\n")
			: "";
		expect(idle).toContain("var(--primary)");
		expect(idle).not.toContain("var(--destructive)");
	});

	it("the recording variant repaints the same glow in the recording colour", () => {
		// Recording keeps the idle rhythm and swaps ONLY the colour, so the
		// button reads as the same control in red (no second halo).
		const recording = ALL_RULES.filter(
			(rule) =>
				rule.selectors.includes(".animate-glow-pulse-destructive::after") &&
				rule.declarations.includes("box-shadow"),
		)
			.map((rule) => rule.declarations)
			.join("\n");
		expect(recording).toContain("var(--destructive)");
		expect(recording).not.toContain("var(--primary)");
	});

	it("the expanding wave animation is gone", () => {
		// Product decision 2026-11-17: the record button changes fill +
		// shadow colour and nothing else, so no keyframes may reintroduce
		// the growing ring behind it.
		expect(css).not.toContain("pulseRing");
		expect(css).not.toContain(".animate-pulse-ring");
	});
});
