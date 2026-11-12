import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InlineSlider } from "@/components/ui/inline-slider";

const BASE = {
	label: "Volume",
	value: 50,
	min: 0,
	max: 100,
	step: 10,
	format: (value: number) => `${value}%`,
} as const;

describe("InlineSlider", () => {
	it("renders the inline label, formatted readout and ARIA value contract", () => {
		render(<InlineSlider {...BASE} />);

		expect(screen.getByText("Volume")).toBeInTheDocument();
		expect(screen.getByText("50%")).toBeInTheDocument();
		const slider = screen.getByRole("slider");
		expect(slider).toHaveAttribute("aria-label", "Volume");
		expect(slider).toHaveAttribute("aria-valuemin", "0");
		expect(slider).toHaveAttribute("aria-valuemax", "100");
		expect(slider).toHaveAttribute("aria-valuenow", "50");
		expect(slider).toHaveAttribute("aria-valuetext", "50%");
	});

	it("moves to the next snap stop with ArrowRight", () => {
		const onValueChange = vi.fn();
		render(<InlineSlider {...BASE} onValueChange={onValueChange} />);

		fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowRight" });

		expect(onValueChange).toHaveBeenCalledTimes(1);
		const next = onValueChange.mock.calls[0]?.[0] as number;
		expect(next).toBeGreaterThan(50);
		expect(next).toBeLessThanOrEqual(100);
	});

	it("Home and End jump to the range ends", () => {
		const onValueChange = vi.fn();
		render(<InlineSlider {...BASE} onValueChange={onValueChange} />);
		const slider = screen.getByRole("slider");

		fireEvent.keyDown(slider, { key: "Home" });
		expect(onValueChange).toHaveBeenLastCalledWith(0);

		fireEvent.keyDown(slider, { key: "End" });
		expect(onValueChange).toHaveBeenLastCalledWith(100);
	});

	it("disabled removes the tab stop and blocks keyboard changes", () => {
		const onValueChange = vi.fn();
		render(<InlineSlider {...BASE} disabled onValueChange={onValueChange} />);
		const slider = screen.getByRole("slider");

		expect(slider).toHaveAttribute("aria-disabled", "true");
		expect(slider.tabIndex).toBe(-1);

		fireEvent.keyDown(slider, { key: "ArrowRight" });

		expect(onValueChange).not.toHaveBeenCalled();
	});
});
