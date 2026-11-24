import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeConfig } from "@/__tests__/helpers/fixtures";
import { OverlaySettingsSection } from "@/components/settings/OverlaySettingsSection";
import { TooltipProvider } from "@/components/ui/tooltip";

const alwaysVisible = () => true;

function renderSection(
	overrides: Parameters<typeof makeConfig>[0] = {},
	updateConfig: (updates: object) => void = () => {},
) {
	return render(
		<TooltipProvider delayDuration={200}>
			<OverlaySettingsSection
				config={makeConfig(overrides)}
				updateConfig={updateConfig}
				updateConfigDebounced={() => {}}
				isVisible={alwaysVisible}
			/>
		</TooltipProvider>,
	);
}

afterEach(() => {
	cleanup();
});

describe("OverlaySettingsSection, bubble controls without the preview card", () => {
	it("offers Hidden alongside Show on Record and Always Visible", () => {
		renderSection();
		expect(screen.getByText("Show on Record")).toBeTruthy();
		expect(screen.getByText("Always Visible")).toBeTruthy();
		expect(screen.getByText("Hidden")).toBeTruthy();
	});

	it("locks the timer toggle when behavior is hidden", () => {
		renderSection({ bubble_behavior: "hidden" });
		const toggle = screen.getByLabelText("Recording Timer");
		expect(toggle).toBeInTheDocument();
		expect(toggle).toBeDisabled();
	});

	it("keeps position and drag visible but locked when behavior is hidden", () => {
		const updateConfig = vi.fn();
		renderSection({ bubble_behavior: "hidden" }, updateConfig);
		expect(screen.getByText("Bubble Behavior")).toBeTruthy();
		const positionGroup = screen.getByRole("radiogroup", {
			name: "Bubble Position",
		});
		const positionRadios = positionGroup.querySelectorAll<HTMLInputElement>(
			'input[type="radio"]',
		);
		expect(positionRadios).toHaveLength(2);
		positionRadios.forEach((radio) => {
			expect(radio).toBeDisabled();
		});
		const drag = screen.getByLabelText("Drag to Move");
		expect(drag).toBeInTheDocument();
		expect(drag).toBeDisabled();
		fireEvent.click(drag);
		expect(updateConfig).not.toHaveBeenCalled();
	});

	it("shows position and drag when behavior is not hidden", () => {
		renderSection({ bubble_behavior: "show_on_record" });
		expect(screen.getByText("Bubble Position")).toBeTruthy();
		expect(screen.getByLabelText("Drag to Move")).toBeTruthy();
		expect(screen.getByLabelText("Drag to Move")).toBeEnabled();
	});

	it("locks the startup toggle until Always Visible is picked", () => {
		renderSection({ bubble_behavior: "show_on_record" });
		const startup = screen.getByLabelText("Show on App Startup");
		expect(startup).toBeInTheDocument();
		expect(startup).toBeDisabled();

		cleanup();
		renderSection({ bubble_behavior: "always_visible" });
		expect(screen.getByLabelText("Show on App Startup")).toBeEnabled();
	});

	it("shows the mic toggle for show on record, not just always visible", () => {
		renderSection({ bubble_behavior: "show_on_record" });
		expect(screen.getByLabelText("Bubble Mic Button")).toBeTruthy();
	});

	it("shows the timer toggle otherwise and commits the toggle", () => {
		const updateConfig = vi.fn();
		renderSection({ bubble_behavior: "show_on_record" }, updateConfig);
		const toggle = screen.getByLabelText("Recording Timer");
		expect(toggle).toBeTruthy();
		fireEvent.click(toggle);
		expect(updateConfig).toHaveBeenCalledWith({
			bubble_show_recording_timer: true,
		});
	});

	it("renders exactly one card, with no mock bubble variants", () => {
		renderSection({ bubble_behavior: "always_visible" });
		expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(1);
		expect(screen.queryByText("Bubble Preview")).toBeNull();
		expect(screen.queryByText("Idle")).toBeNull();
		expect(screen.queryByText("Transcribing")).toBeNull();
		expect(
			document.querySelectorAll('[aria-label="Start dictation"]'),
		).toHaveLength(0);
		expect(
			document.querySelector('[data-slot="bubble-recording-timer"]'),
		).toBeNull();
	});

	it("offers the screenshot beta toggle off by default and commits the toggle", () => {
		const updateConfig = vi.fn();
		renderSection({}, updateConfig);
		const toggle = screen.getByLabelText("Screenshot capture (Beta)");
		expect(toggle).toBeTruthy();
		expect(toggle).not.toBeChecked();
		fireEvent.click(toggle);
		expect(updateConfig).toHaveBeenCalledWith({
			screenshot_beta_enabled: true,
		});
	});

	it("locks the screenshot beta toggle when behavior is hidden", () => {
		renderSection({ bubble_behavior: "hidden" });
		const toggle = screen.getByLabelText("Screenshot capture (Beta)");
		expect(toggle).toBeInTheDocument();
		expect(toggle).toBeDisabled();
	});
});
