import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: ({ icon }: { icon?: { name?: string } }) => (
		<span data-testid="hugeicon" data-name={icon?.name} />
	),
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

import { DateRangePicker } from "@/components/ui/date-range-picker";

afterEach(() => {
	cleanup();
});

// Smoke pins for the vendored picker (lucide-react was removed in favor
// of the app's Hugeicons set). Behavior (presets, keyboard, range
// highlight) is the vendor's own; what matters here is that the Hugeicons
// swap renders and the trigger exposes its accessible name.
describe("DateRangePicker, Hugeicons + trigger contract", () => {
	it("renders the trigger with its accessible name and Hugeicons glyphs", () => {
		const { container } = render(<DateRangePicker />);
		expect(screen.getByRole("button", { name: /Date range/ })).toBeTruthy();
		// Calendar + chevron glyphs come from Hugeicons, not lucide.
		const glyphs = Array.from(
			container.querySelectorAll('[data-testid="hugeicon"]'),
		).map((el) => el.getAttribute("data-name"));
		expect(glyphs).toContain("Calendar01Icon");
		expect(glyphs).toContain("ChevronDownIcon");
	});

	it("accepts translated copy through the strings prop", () => {
		render(
			<DateRangePicker
				label="Período"
				strings={{
					cancelLabel: "Cancelar",
					applyLabel: "Aplicar",
				}}
			/>,
		);
		expect(screen.getByRole("button", { name: /Período/ })).toBeTruthy();
	});
});
