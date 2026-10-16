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
		showAdvanced: true,
		onPresetChange: vi.fn(),
		onToggleAdvanced: vi.fn(),
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
	// The accordion mounts collapsed; expand it so options + panel exist.
	fireEvent.click(screen.getByRole("button", { name: /Microphone Quality/ }));
	return { ...utils, props };
}

describe("PresetAccordionSelector custom presets", () => {
	it("renders saved customs as options and selects by id", () => {
		const { props } = renderSelector({ activeCustomPresetId: null });
		expect(
			screen.getByTestId("mic-preset-option-custom:night"),
		).toBeInTheDocument();
		fireEvent.click(screen.getByTestId("mic-preset-option-custom:night"));
		expect(props.onSelectCustomPreset).toHaveBeenCalledWith("night");
	});

	it("keeps the save button disabled until a value drifts", () => {
		renderSelector();
		expect(screen.getByText("Save as preset")).toBeDisabled();
	});

	it("enables save after a config change and restores on demand", () => {
		const changed = makeConfig({
			audio_preset: "custom",
			active_custom_preset: "night",
			noise_filter_gate: true,
		});
		const { props } = renderSelector({ config: changed });
		expect(screen.getByText("Save as preset")).not.toBeDisabled();
		fireEvent.click(screen.getByText("Restore microphone defaults"));
		expect(props.onRestoreMicDefaults).toHaveBeenCalledTimes(1);
	});

	it("save flow blocks duplicate names and submits unique ones", async () => {
		const changed = makeConfig({
			audio_preset: "custom",
			active_custom_preset: "night",
			noise_filter_gate: true,
		});
		const { props } = renderSelector({ config: changed });
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
		renderSelector();
		expect(screen.getByText("Noise Suppression")).toBeInTheDocument();
		expect(screen.getByText("Noise Gate")).toBeInTheDocument();
		expect(screen.queryByText("Limiter")).not.toBeInTheDocument();
		expect(screen.queryByText("Equalizer")).not.toBeInTheDocument();
	});
});
