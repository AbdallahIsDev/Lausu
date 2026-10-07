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

describe("OverlaySettingsSection, bubble behavior + timer + preview", () => {
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
		// The live preview card has nothing to mirror while the bubble
		// itself is hidden, so it stays out of the way.
		expect(screen.queryByText("Bubble Preview")).toBeNull();
	});

	it("shows position, drag, and preview when behavior is not hidden", () => {
		renderSection({ bubble_behavior: "show_on_record" });
		expect(screen.getByText("Bubble Position")).toBeTruthy();
		expect(screen.getByLabelText("Drag to Move")).toBeTruthy();
		expect(screen.getByLabelText("Drag to Move")).toBeEnabled();
		expect(screen.getByText("Bubble Preview")).toBeTruthy();
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

	it("idle preview shows the mic only when it can appear on the real bubble", () => {
		const { unmount } = renderSection({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
		});
		expect(
			document.querySelectorAll('[aria-label="Start dictation"]'),
		).toHaveLength(1);
		unmount();
		cleanup();
		renderSection({ bubble_behavior: "show_on_record" });
		expect(
			document.querySelectorAll('[aria-label="Start dictation"]'),
		).toHaveLength(0);
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

	it("renders idle/recording previews with a live fake timer", () => {
		renderSection({
			bubble_behavior: "show_on_record",
			bubble_show_recording_timer: true,
		});
		expect(screen.getByText("Bubble Preview")).toBeTruthy();
		expect(screen.getByText("Idle")).toBeTruthy();
		expect(screen.getByText("Recording")).toBeTruthy();
		expect(screen.queryByText("Transcribing")).toBeNull();
		expect(document.querySelector(".bubble-shimmer-text")).toBeNull();
		const timer = document.querySelector(
			'[data-slot="bubble-recording-timer"]',
		);
		expect(timer).toBeTruthy();
		expect(timer?.textContent).toBe("00:00");
	});

	it("recording preview omits the timer when the toggle is off", () => {
		renderSection({
			bubble_behavior: "show_on_record",
			bubble_show_recording_timer: false,
		});
		expect(
			document.querySelector('[data-slot="bubble-recording-timer"]'),
		).toBeNull();
	});

	it("renders the preview as its own card, not a row of the Overlay card", () => {
		renderSection({ bubble_behavior: "always_visible" });
		const headings = screen.getAllByRole("heading", { level: 2 });
		expect(headings.map((h) => h.textContent)).toEqual([
			"Overlay",
			"Bubble Preview",
		]);
		// The preview pills live in the preview's own <section>, not in
		// the Overlay card's row list.
		const overlaySection = screen
			.getByRole("heading", { level: 2, name: "Overlay" })
			.closest("section");
		const previewSection = screen
			.getByRole("heading", { level: 2, name: "Bubble Preview" })
			.closest("section");
		expect(overlaySection).not.toBe(previewSection);
		expect(
			overlaySection?.querySelector('[aria-label="Start dictation"]'),
		).toBeNull();
		expect(
			previewSection?.querySelector('[aria-label="Start dictation"]'),
		).toBeTruthy();
	});

	it("drops the dismiss button from the preview when the bubble is not dismissable", () => {
		renderSection({ bubble_behavior: "always_visible" });
		expect(
			document.querySelectorAll('[aria-label="Dismiss bubble"]'),
		).toHaveLength(1);
		cleanup();
		renderSection({ bubble_behavior: "show_on_record" });
		expect(
			document.querySelectorAll('[aria-label="Dismiss bubble"]'),
		).toHaveLength(0);
	});

	it("mirrors bubble position into the preview", () => {
		renderSection({
			bubble_behavior: "always_visible",
			bubble_position: "top",
		});
		expect(screen.getByText("Bubble Position: Top Center")).toBeTruthy();
		cleanup();
		renderSection({
			bubble_behavior: "always_visible",
			bubble_position: "bottom",
		});
		expect(screen.getByText("Bubble Position: Bottom Center")).toBeTruthy();
	});
});
