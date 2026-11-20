import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: () => <span data-testid="hugeicon" />,
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

vi.mock("@/lib/sound-manager", () => ({
	playSoundCue: vi.fn(),
	setSoundFeedbackEnabled: vi.fn(),
}));

vi.mock("@/components/hotkey/HotkeyPicker", () => ({
	HotkeyPicker: () => <div data-testid="hotkey-picker" />,
}));

vi.mock("@/components/feedback/InfoTooltip", () => ({
	InfoTooltip: ({ text }: { text: string }) => (
		<span data-testid="info-tooltip" data-text={text} />
	),
}));

import { makeConfig } from "@/__tests__/helpers/fixtures";
import { PrivacySettingsSection } from "@/components/settings/PrivacySettingsSection";
import { RecordingSettingsSection } from "@/components/settings/RecordingSettingsSection";
import { playSoundCue, setSoundFeedbackEnabled } from "@/lib/sound-manager";

const alwaysVisible = () => true;
const noopUpdate = () => {};

describe("RecordingSettingsSection, fixed cue level + Test Sound", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		cleanup();
	});

	it("renders NO volume control: the cue level is fixed, not a setting", () => {
		render(
			<RecordingSettingsSection
				config={makeConfig({ sound_feedback_enabled: true })}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		// A loud cue is picked up by the microphone and makes volume ducking
		// think something is playing, so the level is fixed at 30% and the
		// slider was removed rather than left adjustable.
		expect(screen.queryByRole("slider")).toBeNull();
		expect(screen.queryByText("Sound Volume")).toBeNull();
	});

	it("renders the Test Start Sound and Test Stop Sound buttons", () => {
		render(
			<RecordingSettingsSection
				config={makeConfig({ sound_feedback_enabled: true })}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		expect(screen.getByTestId("test-start-sound-button")).toBeTruthy();
		expect(screen.getByTestId("test-stop-sound-button")).toBeTruthy();
	});

	it("Test Start Sound plays the start cue", () => {
		render(
			<RecordingSettingsSection
				config={makeConfig({ sound_feedback_enabled: true })}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		fireEvent.click(screen.getByTestId("test-start-sound-button"));
		expect(playSoundCue).toHaveBeenCalledWith("start");
	});

	it("Test Stop Sound plays the stop cue", () => {
		render(
			<RecordingSettingsSection
				config={makeConfig({ sound_feedback_enabled: true })}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		fireEvent.click(screen.getByTestId("test-stop-sound-button"));
		expect(playSoundCue).toHaveBeenCalledWith("stop");
	});

	it("both test-sound buttons are disabled while sound feedback is off", () => {
		render(
			<RecordingSettingsSection
				config={makeConfig({ sound_feedback_enabled: false })}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		const startBtn = screen.getByTestId(
			"test-start-sound-button",
		) as HTMLButtonElement;
		expect(startBtn.disabled).toBe(true);
		const stopBtn = screen.getByTestId(
			"test-stop-sound-button",
		) as HTMLButtonElement;
		expect(stopBtn.disabled).toBe(true);
	});

	it("the sound-feedback toggle still syncs the manager (existing contract)", () => {
		const updateConfig = vi.fn();
		render(
			<RecordingSettingsSection
				config={makeConfig({ sound_feedback_enabled: true })}
				updateConfig={updateConfig}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		// The existing Sound Feedback switch resolves to the real en.json
		// label ("Sound Feedback").
		const soundSwitch = screen
			.getAllByRole("switch")
			.find((el) => el.getAttribute("aria-label") === "Sound Feedback");
		expect(soundSwitch).toBeTruthy();
		fireEvent.click(soundSwitch as HTMLElement);
		expect(updateConfig).toHaveBeenCalledWith(
			expect.objectContaining({ sound_feedback_enabled: false }),
		);
		expect(setSoundFeedbackEnabled).toHaveBeenCalledWith(false);
	});
});

describe("RecordingSettingsSection, paste-safety row", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		cleanup();
	});

	it("renders the password-paste switch and no removed paste switches", () => {
		render(
			<RecordingSettingsSection
				config={makeConfig({ warn_password_paste: true })}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		expect(screen.getByTestId("warn-password-paste-switch")).toBeTruthy();
		expect(screen.queryByTestId("warn-elevated-paste-switch")).toBeNull();
		expect(screen.queryByTestId("unsafe-paste-switch")).toBeNull();
	});

	it("persists warn_password_paste = false via updateConfig", () => {
		const updateConfig = vi.fn();
		render(
			<RecordingSettingsSection
				config={makeConfig({ warn_password_paste: true })}
				updateConfig={updateConfig}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		fireEvent.click(screen.getByTestId("warn-password-paste-switch"));
		expect(updateConfig).toHaveBeenCalledWith(
			expect.objectContaining({ warn_password_paste: false }),
		);
	});
});

describe("PrivacySettingsSection, hidden config rows", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		cleanup();
	});

	it("renders log_transcriptions + clipboard_save_restore rows", () => {
		render(
			<PrivacySettingsSection
				config={makeConfig({
					log_transcriptions: false,
					clipboard_save_restore: true,
				})}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		expect(screen.getByTestId("log-transcriptions-switch")).toBeTruthy();
		expect(screen.getByTestId("clipboard-save-restore-switch")).toBeTruthy();
	});

	it("persists log_transcriptions = true via updateConfig", () => {
		const updateConfig = vi.fn();
		render(
			<PrivacySettingsSection
				config={makeConfig({ log_transcriptions: false })}
				updateConfig={updateConfig}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		fireEvent.click(screen.getByTestId("log-transcriptions-switch"));
		expect(updateConfig).toHaveBeenCalledWith(
			expect.objectContaining({ log_transcriptions: true }),
		);
	});

	it("persists clipboard_save_restore = false via updateConfig", () => {
		const updateConfig = vi.fn();
		render(
			<PrivacySettingsSection
				config={makeConfig({ clipboard_save_restore: true })}
				updateConfig={updateConfig}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		fireEvent.click(screen.getByTestId("clipboard-save-restore-switch"));
		expect(updateConfig).toHaveBeenCalledWith(
			expect.objectContaining({ clipboard_save_restore: false }),
		);
	});
});
