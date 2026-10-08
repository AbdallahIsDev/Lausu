import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { hugeiconsReactMock } from "@/__tests__/helpers/stableMocks";

vi.mock("@hugeicons/react", () => hugeiconsReactMock());

import { StatCard } from "@/components/dashboard/StatCard";

afterEach(() => {
	cleanup();
});

// The real icon is an SVG path array; the mocked HugeiconsIcon only
// reads `icon?.name`, so a tagged object suffices here.
const TEST_ICON = { name: "SpeechToTextIcon" } as unknown as Parameters<
	typeof StatCard
>[0]["icon"];

function renderCard(props: {
	label?: string;
	value?: string;
	trend?: { pct: number; up: boolean };
}) {
	return render(
		<StatCard
			label={props.label ?? "Recording Time"}
			value={props.value ?? "1h 12m"}
			icon={TEST_ICON}
			trend={props.trend}
		/>,
	);
}

describe("StatCard", () => {
	it("renders the icon, label and main value", () => {
		renderCard({ label: "Characters", value: "12" });
		expect(screen.getByText("Characters")).toBeInTheDocument();
		expect(screen.getByText("12")).toBeInTheDocument();
		expect(screen.getByTestId("hugeicon")).toHaveAttribute(
			"data-name",
			"SpeechToTextIcon",
		);
	});

	it("keeps the value and the trend on ONE row, value first", () => {
		renderCard({ value: "12", trend: { pct: 20, up: true } });
		// The trend sits on the value's own line (value hard left,
		// percentage hard right) instead of stacked under it, so both
		// must be children of the same row element.
		const value = screen.getByText("12");
		const row = value.parentElement;
		expect(row).not.toBeNull();
		expect(row?.firstElementChild).toBe(value);
		expect(row).toContainElement(screen.getByText("20%"));
	});

	it("hands its card chrome to the parent when rendered inside a merged group", () => {
		// Merged-group contract (C-DESIGN-2): the shared container owns
		// the radius/border/background and draws the dividers between
		// cells, so a cell that re-drew its own border would sit a second
		// line on top of the divider. Padding stays with the cell.
		const { container } = render(
			<StatCard
				inGroup
				label="Recording Time"
				value="1h 12m"
				icon={TEST_ICON}
			/>,
		);
		const cell = container.firstElementChild;
		expect(cell?.className).toContain("p-3");
		expect(cell?.className).not.toContain("rounded-lg");
		expect(cell?.className).not.toContain("border-border/8");
		expect(cell?.className).not.toContain("bg-surface-subtle");
	});

	it("renders the trend indicator with the localized aria-label", () => {
		renderCard({ trend: { pct: 20, up: true } });
		expect(screen.getByText("▲")).toBeInTheDocument();
		expect(screen.getByText("20%")).toBeInTheDocument();
		expect(screen.getByRole("img")).toHaveAccessibleName(
			"20% more than the previous period",
		);
	});
});
