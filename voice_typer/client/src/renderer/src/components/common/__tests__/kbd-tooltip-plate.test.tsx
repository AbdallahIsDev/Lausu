import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { KBD_CHIP_CLASSES, Kbd } from "@/components/common/Kbd";
import { HotkeyChips } from "@/components/hotkey/HotkeyChips";

afterEach(cleanup);

/**
 * Owner decision 2026-11-18 (global-first): a keycap is a solid plate EVERYWHERE
 * it appears, not only inside a tooltip. The plate therefore lives in the shared
 * base class so every consumer inherits it by construction.
 */
describe("Kbd plate is global", () => {
	it("paints the plate in the shared base classes for both schemes", () => {
		expect(KBD_CHIP_CLASSES).toContain("bg-neutral-100");
		expect(KBD_CHIP_CLASSES).toContain("dark:bg-black");
		expect(KBD_CHIP_CLASSES).toContain("text-foreground");
		expect(KBD_CHIP_CLASSES).toContain("border-border/30");
		expect(KBD_CHIP_CLASSES).toContain("font-mono");
	});

	it("has no tooltip-context-only variant left", () => {
		expect(KBD_CHIP_CLASSES).not.toContain("in-data-[slot=tooltip-content]");
		render(<Kbd>Ctrl</Kbd>);
		const cls = document.querySelector("[data-slot=kbd]")?.className ?? "";
		expect(cls).not.toContain("in-data-[slot=tooltip-content]");
		expect(cls).not.toContain("bg-surface-subtle");
	});

	it("gives every HotkeyChips keycap the shared plate classes", () => {
		const { container } = render(<HotkeyChips keys="Ctrl+Shift+Alt+D" />);
		const chips = container.querySelectorAll("[data-slot=kbd]");
		expect(chips).toHaveLength(4);
		for (const chip of chips) {
			expect(chip.classList.contains("bg-neutral-100")).toBe(true);
			expect(chip.classList.contains("dark:bg-black")).toBe(true);
			expect(chip.classList.contains("font-mono")).toBe(true);
		}
	});
});
