import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RangeSlider } from "@/components/common/RangeSlider";

function handle(): HTMLElement {
	return screen.getByRole("slider");
}

function track(): HTMLElement {
	const element = handle().parentElement;
	if (!element) throw new Error("slider track missing");
	return element;
}

const TRACK_RECT = {
	left: 0,
	top: 0,
	right: 208,
	bottom: 40,
	width: 208,
	height: 40,
	x: 0,
	y: 0,
	toJSON: () => ({}),
} as DOMRect;

describe("RangeSlider", () => {
	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it("renders one focusable slider with the formatted value and no duplicate label", () => {
		render(
			<RangeSlider
				value={50}
				min={0}
				max={100}
				step={1}
				suffix="%"
				ariaLabel="Volume"
				onChange={vi.fn()}
			/>,
		);

		const slider = handle();
		expect(slider).toHaveAttribute("aria-label", "Volume");
		expect(slider).toHaveAttribute("aria-valuenow", "50");
		expect(slider).toHaveAttribute("aria-valuetext", "50%");
		expect(screen.getByText("50%")).toBeInTheDocument();
		// The surrounding SettingRow already shows "Volume"; the slider must
		// not repeat it inside the track.
		expect(screen.queryByText("Volume")).toBeNull();
	});

	it("commits arrow-key changes immediately when deferApply is off", () => {
		const onChange = vi.fn();
		render(
			<RangeSlider
				value={50}
				min={0}
				max={100}
				step={1}
				suffix="%"
				ariaLabel="Volume"
				onChange={onChange}
			/>,
		);

		fireEvent.keyDown(handle(), { key: "ArrowRight" });

		expect(onChange).toHaveBeenCalledTimes(1);
		expect(onChange.mock.calls[0]?.[0]).toBeGreaterThan(50);
	});

	it("End jumps to the maximum", () => {
		const onChange = vi.fn();
		render(
			<RangeSlider
				value={50}
				min={0}
				max={100}
				step={1}
				suffix="%"
				ariaLabel="Volume"
				onChange={onChange}
			/>,
		);

		fireEvent.keyDown(handle(), { key: "End" });

		expect(onChange).toHaveBeenCalledWith(100);
	});

	it("keeps the readout live during a deferred drag and commits once on release", async () => {
		const onChange = vi.fn();
		render(
			<RangeSlider
				value={50}
				min={0}
				max={100}
				step={1}
				suffix="%"
				ariaLabel="Volume"
				deferApply
				onChange={onChange}
			/>,
		);
		const element = track();
		vi.spyOn(element, "getBoundingClientRect").mockReturnValue(TRACK_RECT);

		fireEvent.pointerDown(element, { clientX: 20, pointerId: 1, button: 0 });
		fireEvent.pointerMove(element, { clientX: 170, pointerId: 1 });

		await waitFor(() => expect(screen.queryByText("50%")).toBeNull());
		expect(onChange).not.toHaveBeenCalled();

		fireEvent.pointerUp(element, { clientX: 170, pointerId: 1 });

		expect(onChange).toHaveBeenCalledTimes(1);
		expect(onChange.mock.calls[0]?.[0]).toBeGreaterThan(50);
	});

	it("does not fire for a disabled slider", () => {
		const onChange = vi.fn();
		render(
			<RangeSlider
				value={50}
				min={0}
				max={100}
				step={1}
				suffix="%"
				ariaLabel="Volume"
				disabled
				onChange={onChange}
			/>,
		);

		const slider = handle();
		expect(slider).toHaveAttribute("aria-disabled", "true");
		expect(slider.tabIndex).toBe(-1);

		fireEvent.keyDown(slider, { key: "ArrowRight" });

		expect(onChange).not.toHaveBeenCalled();
	});

	it("syncs the readout when the committed value changes", () => {
		const { rerender } = render(
			<RangeSlider
				value={50}
				min={0}
				max={100}
				step={1}
				suffix="%"
				ariaLabel="Volume"
				onChange={vi.fn()}
			/>,
		);

		rerender(
			<RangeSlider
				value={75}
				min={0}
				max={100}
				step={1}
				suffix="%"
				ariaLabel="Volume"
				onChange={vi.fn()}
			/>,
		);

		expect(screen.getByText("75%")).toBeInTheDocument();
	});
});
