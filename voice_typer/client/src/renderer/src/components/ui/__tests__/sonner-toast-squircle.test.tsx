/**
 * Corner contract for the sonner toast (the in-app notification).
 *
 * `rounded-lg` is the app's single radius step, and — unlike a bare
 * `border-radius` declaration — the CLASS is also what opts an element into
 * the global squircle corner-shape: index.css shapes corners via
 * `:where(.rounded-lg)` inside `@supports (corner-shape: squircle)`.
 * Sonner's toast `<li>` ships with no utility class of its own (it painted
 * its radius from `--border-radius` alone), so on a native corner-shape
 * engine the toast rendered a plain superellipse(1) corner while every card
 * in the app renders superellipse(2) — the notification read as a different
 * material. Same contract as `date-range-picker.tsx`.
 *
 * The radius VALUE is not duplicated here: `--border-radius` is fed from
 * `--radius-lg` → `--radius`, so the toast follows the token in both
 * branches (1.625rem with native support, 0.625rem without).
 *
 * jsdom has no CSS engine, so `@supports` / `corner-shape` cannot be
 * evaluated — the class↔gate link is asserted as a source shape. The class
 * actually landing on the rendered toast IS observable, and is asserted
 * against real sonner (not the mocked wrapper used by sonner.test.tsx).
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act, cleanup, render, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { afterEach, describe, expect, it } from "vitest";

import { Toaster } from "../sonner";

const read = (...segments: string[]) =>
	readFileSync(resolve(__dirname, "..", ...segments), "utf8");

// `read` already steps out of `__tests__`, so `..` lands on `src/`.
const CSS = read("..", "..", "index.css");
const WRAPPER = read("sonner.tsx");

/** Text inside the braces that open at/after `start`. */
function blockAfter(source: string, start: number): string {
	const open = source.indexOf("{", start);
	expect(open).toBeGreaterThan(start);
	let depth = 1;
	for (let index = open + 1; index < source.length; index += 1) {
		if (source[index] === "{") depth += 1;
		if (source[index] === "}") depth -= 1;
		if (depth === 0) return source.slice(open + 1, index);
	}
	throw new Error("unclosed CSS block");
}

afterEach(() => {
	cleanup();
	toast.dismiss();
});

describe("sonner toast corner contract", () => {
	it("puts the shared rounded-lg class on the rendered toast", async () => {
		render(<Toaster />);
		await act(async () => {
			await new Promise((done) => {
				setTimeout(done, 0);
			});
		});
		await act(async () => {
			toast.success("Model downloaded");
		});
		await waitFor(() => {
			expect(document.querySelector("[data-sonner-toast]")).toBeTruthy();
		});

		const li = document.querySelector("[data-sonner-toast]");
		const classes = li?.getAttribute("class")?.split(/\s+/) ?? [];
		// Without this class the toast has a radius but NOT the squircle
		// corner shape, which is the whole point of the class.
		expect(classes).toContain("rounded-lg");
	});

	it("keeps data-styled=true so the index.css toast overrides still match", async () => {
		// Every `.toaster [data-sonner-toast][data-styled="true"]` rule in
		// index.css (1px border, the stacked grid, per-type icon colours,
		// description colour, action/cancel surfaces, focus rings) keys off
		// this attribute. Sonner derives it from `jsx` / `unstyled` only, so
		// handing the toast a class must not flip it — if it ever does, the
		// entire toast design dies silently with no other test noticing.
		render(<Toaster />);
		await act(async () => {
			await new Promise((done) => {
				setTimeout(done, 0);
			});
		});
		await act(async () => {
			toast.success("Model downloaded");
		});
		await waitFor(() => {
			expect(document.querySelector("[data-sonner-toast]")).toBeTruthy();
		});

		expect(
			document
				.querySelector("[data-sonner-toast]")
				?.getAttribute("data-styled"),
		).toBe("true");
	});

	it("hands the toast a class the corner-shape gate actually shapes", () => {
		// Cross-file link: the class sonner puts on the toast must be one of
		// the classes index.css shapes. Removing `.rounded-lg` from the gate
		// family (or the class from the wrapper) breaks the toast alone.
		const classNamesBlock = /classNames:\s*\{\s*toast:\s*"([^"]+)"/.exec(
			WRAPPER,
		);
		const toastClass = classNamesBlock?.[1];
		expect(toastClass).toBe("rounded-lg");

		const gateStart = CSS.indexOf("@supports (corner-shape: squircle)");
		expect(gateStart).toBeGreaterThan(-1);
		const gate = blockAfter(CSS, gateStart);
		const familyStart = gate.indexOf(`.${toastClass}`);
		const circlesStart = gate.indexOf(".rounded-full");
		expect(familyStart).toBeGreaterThan(-1);
		expect(circlesStart).toBeGreaterThan(familyStart);
		expect(gate.slice(familyStart, circlesStart)).toContain(
			"corner-shape: var(--corner-shape",
		);
	});

	it("feeds the toast radius from the shared token, never a literal", () => {
		// The wrapper must not hardcode a radius: `--border-radius` has to
		// resolve through `--radius-lg` → `--radius`, so the toast follows
		// the token in BOTH branches (the two radius values themselves are
		// pinned by index-css-corner-shape.test.ts).
		expect(WRAPPER).toMatch(/"--border-radius":\s*"var\(--radius-lg\)"/);
		expect(CSS).toMatch(/--radius-lg:\s*var\(--radius\);/);
	});
});
