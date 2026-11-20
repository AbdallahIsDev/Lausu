import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
	PluginsNewBadge,
	type PluginsBadgeHue,
} from "@/components/layout/PluginsNewBadge";

afterEach(cleanup);

function chipClasses(hue: PluginsBadgeHue): string {
	const { container } = render(
		<PluginsNewBadge label="New" collapsed={false} motionClass="" hue={hue} />,
	);
	const chip = container.querySelector('[data-testid="nav-new-badge"]')
		?.firstElementChild as HTMLElement;
	return chip.className;
}

describe("PluginsNewBadge", () => {
	it("uses three distinct saturated token hues with full-opacity labels", () => {
		const primary = chipClasses("primary");
		const red = chipClasses("red");
		const green = chipClasses("green");
		expect(primary).toContain("text-primary");
		expect(red).toContain("text-destructive");
		expect(green).toContain("text-success");
		expect(new Set([primary, red, green]).size).toBe(3);
		for (const cls of [primary, red, green]) {
			expect(cls).not.toMatch(/opacity-/);
			expect(cls).toContain("bg-");
			expect(cls).toContain("border-");
		}
	});

	it("keeps the stable test id and the sidebar's collapse slot", () => {
		render(<PluginsNewBadge label="New" collapsed motionClass="blur-[4px]" />);
		const slot = screen.getByTestId("nav-new-badge");
		expect(slot.className).toContain("max-w-0");
		expect(slot.className).toContain("blur-[4px]");
	});

	it("Sidebar still gates the badge on the one-way latch and renders it once", () => {
		const src = readFileSync(
			resolve(import.meta.dirname, "../Sidebar.tsx"),
			"utf-8",
		);
		expect(src).toContain("{item.badge && showNewBadge && (");
		expect(src.match(/<PluginsNewBadge\b/g)).toHaveLength(1);
		expect(src).not.toContain("bg-primary/15 text-primary");
	});
});
