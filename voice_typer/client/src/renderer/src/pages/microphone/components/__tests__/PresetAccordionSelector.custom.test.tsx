import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { makeConfig } from "@/__tests__/helpers/fixtures";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { CustomMicPreset } from "@/types/config";
import { PresetAccordionSelector } from "../PresetAccordionSelector";

const customs: CustomMicPreset[] = [
	{
		id: "night",
		name: "Night Calls",
		values: { noise_filter_gate: false, noise_filter_compressor: false },
	},
	{
		id: "desk",
		name: "Desk Fan",
		values: { noise_filter_gate: true, noise_filter_compressor: true },
	},
];

// Row order contract: stock presets, then user presets, Advanced last.
const ROW_ORDER = [
	"auto",
	"studio",
	"noisy_room",
	"custom:night",
	"custom:desk",
	"custom",
];

function renderSelector(overrides: Record<string, unknown> = {}) {
	const props = {
		preset: "custom" as const,
		config: makeConfig({
			audio_preset: "custom",
			active_custom_preset: "night",
			noise_filter_gate: false,
			noise_filter_compressor: false,
		}),
		onPresetChange: vi.fn(),
		onConfigChange: vi.fn(),
		customPresets: customs,
		activeCustomPresetId: "night",
		onSelectCustomPreset: vi.fn(),
		onSaveCustomPreset: vi.fn(),
		onRestoreMicDefaults: vi.fn(),
		...overrides,
	};
	const utils = render(
		<TooltipProvider delayDuration={200}>
			<PresetAccordionSelector {...props} />
		</TooltipProvider>,
	);
	return { ...utils, props };
}

describe("PresetAccordionSelector flat preset list", () => {
	it("lists stock presets, saved user presets, then Advanced last", () => {
		renderSelector();

		const FOLLOWING = Node.DOCUMENT_POSITION_FOLLOWING;
		for (let i = 0; i < ROW_ORDER.length - 1; i += 1) {
			const current = screen.getByTestId(`mic-preset-option-${ROW_ORDER[i]}`);
			const next = screen.getByTestId(`mic-preset-option-${ROW_ORDER[i + 1]}`);
			expect(current.compareDocumentPosition(next) & FOLLOWING).toBeTruthy();
		}
	});

	it("exposes help for built-ins only (saved presets have no info trigger)", () => {
		renderSelector();
		expect(screen.getByLabelText("More info about Advanced")).toBeTruthy();
		expect(screen.getByLabelText("More info about Studio")).toBeTruthy();
		expect(screen.queryByLabelText("More info about Night Calls")).toBeNull();
	});

	it("info-tooltip clicks never change the selected preset", () => {
		const { props } = renderSelector({
			preset: "auto",
			activeCustomPresetId: null,
		});
		fireEvent.click(screen.getByLabelText("More info about Studio"));
		expect(props.onPresetChange).not.toHaveBeenCalled();
	});

	it("renders saved customs as options and selects by id", () => {
		const { props } = renderSelector({ activeCustomPresetId: null });
		expect(
			screen.getByTestId("mic-preset-option-custom:night"),
		).toBeInTheDocument();
		fireEvent.click(screen.getByTestId("mic-preset-option-custom:night"));
		expect(props.onSelectCustomPreset).toHaveBeenCalledWith("night");
	});

	it("reveals the filter chain inline as soon as Advanced is selected", () => {
		const { props, rerender } = renderSelector({ preset: "auto" });
		expect(screen.queryByText("Save as preset")).toBeNull();

		// One click picks Advanced; the parent then persists the preset.
		fireEvent.click(screen.getByTestId("mic-preset-option-custom"));
		expect(props.onPresetChange).toHaveBeenCalledWith("custom");

		rerender(
			<TooltipProvider delayDuration={200}>
				<PresetAccordionSelector
					{...props}
					preset="custom"
					activeCustomPresetId={null}
				/>
			</TooltipProvider>,
		);

		// Chain is visible with no second click and no disclosure control.
		expect(screen.getByText("Noise Suppression")).toBeInTheDocument();
		expect(screen.getByText("Save as preset")).toBeInTheDocument();
		expect(screen.queryByText("Custom filters")).toBeNull();
	});

	it("keeps the chain hidden while a saved user preset is selected", () => {
		renderSelector();
		expect(screen.queryByText("Save as preset")).toBeNull();
		expect(screen.queryByText("Noise Suppression")).toBeNull();
	});

	it("hides the preset list when filtering is switched off and restores it on", () => {
		const { props, rerender } = renderSelector({ preset: "studio" });
		expect(screen.getByTestId("mic-preset-radio-group")).toBeInTheDocument();

		fireEvent.click(screen.getByTestId("mic-quality-switch"));
		expect(props.onPresetChange).toHaveBeenCalledWith("off");

		rerender(
			<TooltipProvider delayDuration={200}>
				<PresetAccordionSelector
					{...props}
					preset="off"
					activeCustomPresetId={null}
				/>
			</TooltipProvider>,
		);
		expect(screen.queryByTestId("mic-preset-radio-group")).toBeNull();

		fireEvent.click(screen.getByTestId("mic-quality-switch"));
		expect(props.onPresetChange).toHaveBeenCalledWith("studio");
	});
});

describe("PresetAccordionSelector custom presets", () => {
	it("keeps the save button disabled until a value drifts", () => {
		renderSelector({ activeCustomPresetId: null });
		expect(screen.getByText("Save as preset")).toBeDisabled();
	});

	it("enables save after a value drifts and restores on demand", () => {
		const { props, rerender } = renderSelector({
			activeCustomPresetId: null,
			config: makeConfig({
				audio_preset: "custom",
				active_custom_preset: null,
				noise_filter_gate: false,
			}),
		});
		expect(screen.getByText("Save as preset")).toBeDisabled();

		rerender(
			<TooltipProvider delayDuration={200}>
				<PresetAccordionSelector
					{...props}
					preset="custom"
					activeCustomPresetId={null}
					config={makeConfig({
						audio_preset: "custom",
						active_custom_preset: null,
						noise_filter_gate: true,
					})}
				/>
			</TooltipProvider>,
		);
		expect(screen.getByText("Save as preset")).not.toBeDisabled();
		fireEvent.click(screen.getByText("Restore microphone defaults"));
		expect(props.onRestoreMicDefaults).toHaveBeenCalledTimes(1);
	});

	it("save flow blocks duplicate names and submits unique ones", async () => {
		const { props, rerender } = renderSelector({
			activeCustomPresetId: null,
			config: makeConfig({
				audio_preset: "custom",
				active_custom_preset: null,
				noise_filter_gate: false,
			}),
		});
		rerender(
			<TooltipProvider delayDuration={200}>
				<PresetAccordionSelector
					{...props}
					preset="custom"
					activeCustomPresetId={null}
					config={makeConfig({
						audio_preset: "custom",
						active_custom_preset: null,
						noise_filter_gate: true,
					})}
				/>
			</TooltipProvider>,
		);
		fireEvent.click(screen.getByText("Save as preset"));
		expect(screen.getByLabelText("Preset name")).toBeInTheDocument();

		const input = screen.getByLabelText("Preset name");
		const saveButton = screen.getByRole("button", { name: "Save preset" });
		fireEvent.change(input, { target: { value: "night calls" } });
		fireEvent.click(saveButton);
		await waitFor(() =>
			expect(
				screen.getByText("A preset with this name already exists"),
			).toBeInTheDocument(),
		);
		expect(props.onSaveCustomPreset).not.toHaveBeenCalled();

		fireEvent.change(input, { target: { value: "Focus Time" } });
		fireEvent.click(screen.getByRole("button", { name: "Save preset" }));
		await waitFor(() =>
			expect(props.onSaveCustomPreset).toHaveBeenCalledWith("Focus Time"),
		);
	});

	it("advanced panel shows the simplified set only", () => {
		renderSelector({ activeCustomPresetId: null });
		expect(screen.getByText("Noise Suppression")).toBeInTheDocument();
		expect(screen.getByText("Noise Gate")).toBeInTheDocument();
		expect(screen.queryByText("Limiter")).not.toBeInTheDocument();
		expect(screen.queryByText("Equalizer")).not.toBeInTheDocument();
	});
});
