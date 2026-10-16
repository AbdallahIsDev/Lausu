/**
 * Listen-Live preview controls on the active-microphone card.
 *
 * One user-visible contract each:
 *   1. the preview-volume slider renders the PERSISTED level
 *      (`config.live_listen_level`, committed on release), so a revisit
 *      shows what the user set instead of snapping back to the default;
 *   2. the S0 guidance line renders unconditionally, so starting/stopping
 *      the preview never introduces or removes a line around the buttons.
 *
 * The preview gain itself (level × ceiling, limiter node) is pinned in
 * `pages/microphone/hooks/__tests__/useLiveListen.test.ts`.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeConfig } from "@/__tests__/helpers/fixtures";
import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
} from "@/__tests__/helpers/stableMocks";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
	ActiveMicrophoneCard,
	type ActiveMicrophoneCardProps,
} from "@/pages/microphone/components/ActiveMicrophoneCard";

vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());
vi.mock("@/components/audio/AudioFilterChain", () => ({
	AudioFilterChain: () => <div data-testid="audio-filter-chain" />,
}));
vi.mock("@/pages/microphone/hooks/useMicrophoneTestSession", () => ({
	MICROPHONE_TEST_DURATION_SEC: 10,
}));

const noop = () => undefined;

function baseProps(
	overrides: Partial<ActiveMicrophoneCardProps> = {},
): ActiveMicrophoneCardProps {
	return {
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
		playing: false,
		playingOriginal: false,
		hasFiltersEnabled: false,
		showAdvanced: false,
		config: makeConfig({}),
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
		onRetest: noop,
		onToggleAdvanced: noop,
		onPresetChange: noop,
		onConfigChange: noop,
		...overrides,
	};
}

afterEach(() => {
	cleanup();
});

describe("ActiveMicrophoneCard, Live preview volume", () => {
	it("renders the slider at the persisted level", () => {
		render(
			<TooltipProvider>
				<ActiveMicrophoneCard
					{...baseProps({ config: makeConfig({ live_listen_level: 0.35 }) })}
				/>
			</TooltipProvider>,
		);

		expect(screen.getByText("Preview volume")).toBeTruthy();
		expect(screen.getByRole("slider").getAttribute("aria-valuenow")).toBe("35");
	});

	it("falls back to the default level when the config predates the key", () => {
		render(
			<TooltipProvider>
				<ActiveMicrophoneCard {...baseProps({ config: makeConfig({}) })} />
			</TooltipProvider>,
		);

		expect(screen.getByRole("slider").getAttribute("aria-valuenow")).toBe("50");
	});

	it("commits a new level through the normal config plumbing on release", () => {
		const onConfigChange = vi.fn();
		render(
			<TooltipProvider>
				<ActiveMicrophoneCard
					{...baseProps({
						config: makeConfig({ live_listen_level: 0.35 }),
						onConfigChange,
					})}
				/>
			</TooltipProvider>,
		);

		const thumb = screen.getByRole("slider");
		fireEvent.focus(thumb);
		fireEvent.keyDown(thumb, { key: "ArrowRight" });
		fireEvent.blur(thumb);

		expect(onConfigChange).toHaveBeenCalledWith({ live_listen_level: 0.4 });
	});
});

describe("ActiveMicrophoneCard, S0 guidance", () => {
	it("shows the static headphones note, and the listening hint stays separate", () => {
		const { rerender } = render(
			<TooltipProvider>
				<ActiveMicrophoneCard {...baseProps()} />
			</TooltipProvider>,
		);

		const guide = screen.getByText(
			"Headphones are recommended for Listen live on laptop or desktop speakers.",
		);
		expect(guide).toBeTruthy();
		// The while-listening hint is NOT the same line (the note only
		// complements it).
		expect(
			screen.queryByText(
				"You should hear yourself now. Use headphones to avoid echo.",
			),
		).toBeNull();

		rerender(
			<TooltipProvider>
				<ActiveMicrophoneCard {...baseProps({ liveListening: true })} />
			</TooltipProvider>,
		);

		expect(
			screen.getByText(
				"You should hear yourself now. Use headphones to avoid echo.",
			),
		).toBeTruthy();
		// Starting the preview does not remove or move the static note.
		expect(
			screen.getByText(
				"Headphones are recommended for Listen live on laptop or desktop speakers.",
			),
		).toBeTruthy();
	});
});
