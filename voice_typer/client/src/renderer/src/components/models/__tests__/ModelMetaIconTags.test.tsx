import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
	CloudTag,
	DistilledTag,
	LanguageScopeTag,
	SpeedTag,
} from "@/components/models/ModelMetaIconTags";
import { TooltipProvider } from "@/components/ui/tooltip";

// The chip's icon is the only visual; the glyph identity is asserted
// through the shared hugeicons mock's data-name attribute.
vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: ({
		icon,
	}: {
		children?: React.ReactNode;
		icon?: { name?: string };
	}) => (
		<span data-testid="hugeicon" data-name={icon?.name}>
			{""}
		</span>
	),
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

/** Wrap in the shared TooltipProvider the App root mounts. */
function renderChip(node: React.ReactNode) {
	return render(<TooltipProvider delayDuration={200}>{node}</TooltipProvider>);
}

describe("metadata icon chips, icon-only with a hover/focus tooltip", () => {
	afterEach(() => cleanup());

	it("multilingual renders a globe chip labelled 'Multilingual'", () => {
		renderChip(<LanguageScopeTag multilingual />);
		const chip = screen.getByRole("button", { name: "Multilingual" });
		expect(chip.querySelector('[data-testid="hugeicon"]')).toHaveAttribute(
			"data-name",
			"Globe02Icon",
		);
		// Icon-only: the chip's own subtree carries no visible text.
		expect(chip.textContent).toBe("");
	});

	it("English-only renders the 'Aa' text glyph chip", () => {
		renderChip(<LanguageScopeTag multilingual={false} />);
		const chip = screen.getByRole("button", { name: "English Only" });
		expect(chip.querySelector('[data-testid="hugeicon"]')).toHaveAttribute(
			"data-name",
			"TextFontIcon",
		);
	});

	it("the speed chip is a bolt whose label states the rating", () => {
		renderChip(<SpeedTag rating="fast" />);
		const chip = screen.getByRole("button", { name: "Fast Speed" });
		expect(chip.querySelector('[data-testid="hugeicon"]')).toHaveAttribute(
			"data-name",
			"ZapIcon",
		);
	});

	it("the distilled chip is a flask labelled 'Distilled'", () => {
		renderChip(<DistilledTag />);
		const chip = screen.getByRole("button", { name: "Distilled" });
		expect(chip.querySelector('[data-testid="hugeicon"]')).toHaveAttribute(
			"data-name",
			"FlaskConicalIcon",
		);
	});

	it("the cloud chip is a cloud labelled 'Cloud'", () => {
		renderChip(<CloudTag />);
		const chip = screen.getByRole("button", { name: "Cloud" });
		expect(chip.querySelector('[data-testid="hugeicon"]')).toHaveAttribute(
			"data-name",
			"CloudIcon",
		);
	});

	it("focusing a chip opens a tooltip carrying the same meaning", async () => {
		renderChip(<SpeedTag rating="slow" />);
		screen.getByRole("button", { name: "Slow Speed" }).focus();
		// Radix opens on focus as well as hover, so the tooltip text is
		// assertable without synthetic pointer events.
		const tip = await screen.findByRole("tooltip");
		expect(tip.textContent).toContain("Slow Speed");
	});
});
