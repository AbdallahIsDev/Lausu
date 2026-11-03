/**
 * The card is the only surface that tells the user the chain is serving a
 * different denoiser than the one selected (C-UI-15). Pure presentational
 * contract: the note renders verbatim as a polite status line, and the slot
 * disappears entirely when there is nothing to report.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
} from "@/__tests__/helpers/stableMocks";
import {
	ActiveMicrophoneCard,
	type ActiveMicrophoneCardProps,
} from "@/pages/microphone/components/ActiveMicrophoneCard";

vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());
vi.mock("@/pages/microphone/hooks/useMicrophoneTestSession", () => ({
	MICROPHONE_TEST_DURATION_SEC: 10,
}));

const NOTE = "DPDFNet isn't available on this device — using GTCRN.";

const noop = () => undefined;

const baseProps: ActiveMicrophoneCardProps = {
	activeMicName: "System Default",
	isSystemDefault: true,
	canTest: true,
	testRunning: false,
	testStarting: false,
	testElapsed: 0,
	testDurationMs: 0,
	level: 0.06,
	micMonitoring: true,
	testAudioBase64: null,
	rawAudioBase64: null,
	testQuality: null,
	testTranscription: null,
	testTranscriptionUnavailable: false,
	enhancementActive: true,
	playing: false,
	playingOriginal: false,
	config: null,
	customPresets: [],
	activeCustomPresetId: null,
	onSelectCustomPreset: noop,
	onSaveCustomPreset: noop,
	onRestoreMicDefaults: noop,
	liveListening: false,
	liveStarting: false,
	liveListenError: null,
	liveListenDisabled: false,
	onToggleLiveListen: noop,
	onStartTest: noop,
	onStopTest: noop,
	onPlayEnhanced: noop,
	onPlayOriginal: noop,
	onStopPlayback: noop,
	onPresetChange: noop,
	onConfigChange: noop,
};

describe("ActiveMicrophoneCard denoiser fallback note", () => {
	it("renders the note as a polite status line", () => {
		render(<ActiveMicrophoneCard {...baseProps} denoiserNote={NOTE} />);

		const note = screen.getByTestId("mic-denoiser-fallback");
		expect(note.textContent).toBe(NOTE);
		expect(note).toHaveAttribute("role", "status");
	});

	it("renders no slot when the serving backend is the selected one", () => {
		render(<ActiveMicrophoneCard {...baseProps} denoiserNote={null} />);

		expect(screen.queryByTestId("mic-denoiser-fallback")).toBeNull();
	});
});
