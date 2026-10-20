/**
 * Layout contract for the active-microphone card.
 *
 * Two user-visible complaints are pinned here, both of which the page-level
 * test cannot reach (it never gets the card into a RUNNING state):
 *
 *   1. Pressing Start Test must not move the buttons. The readout that only
 *      exists during a test (pulsing dot + countdown) lives on the trailing
 *      edge of the CONTROLS row, and the always-on level readout lives on the
 *      header row above the bar — so the space under the bar is already
 *      reserved and nothing is inserted into the flow mid-test.
 *   2. The level readout bottom-aligns (`items-end` on the header row) while
 *      the mic icon + title/subtitle group keeps its own `items-center`; a
 *      bare `items-end` on the row dragged the icon down with it.
 *
 * jsdom measures no geometry, so both are pinned as document ORDER
 * (`compareDocumentPosition`) plus the flex classes that produce them.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
// The card needs exactly one value from this hook module — the duration
// constant — so the mock keeps this presentational test out of the hook's
// module graph (and out of its callbacks/IPC surface). The real value is 10s
// and is pinned by C-MIC-18 + the hook's own tests.
vi.mock("@/pages/microphone/hooks/useMicrophoneTestSession", () => ({
	MICROPHONE_TEST_DURATION_SEC: 10,
}));

const FOLLOWING = Node.DOCUMENT_POSITION_FOLLOWING;

const noop = () => undefined;

const completedResultProps = {
	testDurationMs: 5000,
	testQuality: {
		volume_level: "good",
		volume_rms: 0.1,
		peak_level: 0.5,
		noise_level: "low",
		has_voice: true,
		has_clipping: false,
		detected_issues: [],
		estimated_transcription_quality: 88,
		silence_ratio: 0.1,
	},
	testTranscription: "hello world",
	testTranscriptionUnavailable: false,
} satisfies Partial<ActiveMicrophoneCardProps>;

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
	playing: false,
	playingOriginal: false,
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
	onToggleAdvanced: noop,
	onPresetChange: noop,
	onConfigChange: noop,
};

function renderCard(overrides: Partial<ActiveMicrophoneCardProps> = {}) {
	return render(
		<TooltipProvider delayDuration={200}>
			<ActiveMicrophoneCard {...baseProps} {...overrides} />
		</TooltipProvider>,
	);
}

afterEach(() => {
	cleanup();
});

describe("ActiveMicrophoneCard, level readout placement", () => {
	it("sits above the bar, which sits above the controls row", () => {
		renderCard();

		const readout = screen.getByText(/^Level: \d+%$/);
		const bar = screen.getByRole("progressbar");
		const start = screen.getByRole("button", { name: /Start Test/i });

		expect(readout.compareDocumentPosition(bar) & FOLLOWING).toBeTruthy();
		expect(bar.compareDocumentPosition(start) & FOLLOWING).toBeTruthy();
	});

	it("bottom-aligns itself while the icon + title group stays centered", () => {
		renderCard();

		const readout = screen.getByText(/^Level: \d+%$/);
		const row = readout.parentElement;
		if (!row) throw new Error("level readout has no row");
		expect(row.className).toContain("items-end");

		const iconGroup = row.firstElementChild;
		expect(iconGroup?.className).toContain("items-center");
		// The truncation chain needs min-w-0 on this new level too.
		expect(iconGroup?.className).toContain("min-w-0");
		// The readout is the group's SIBLING, so centering the group cannot
		// move it and bottom-aligning the row cannot move the icon.
		expect(iconGroup?.contains(readout)).toBe(false);
	});
});

describe("ActiveMicrophoneCard, test readout placement", () => {
	it("renders nothing in the reserved slot while idle", () => {
		const { container } = renderCard({ testRunning: false });

		expect(
			container.querySelector("[data-slot='microphone-recording-dot']"),
		).toBeNull();
		expect(screen.queryByText(/^\d{2}:\d{2} \/ \d{2}:\d{2}$/)).toBeNull();
	});

	it("renders the dot + countdown on the controls row, after the button", () => {
		const { container } = renderCard({
			testRunning: true,
			testElapsed: 2,
			testDurationMs: 10_000,
		});

		const dot = container.querySelector(
			"[data-slot='microphone-recording-dot']",
		);
		expect(dot).not.toBeNull();
		const timer = screen.getByText("00:02 / 00:10");

		// Same row as the Stop button: the row is not a new one inserted
		// between the bar and the buttons. The buttons sit in a cluster
		// inside that row so the readout can take the trailing edge.
		const stop = screen.getByRole("button", { name: /Stop Test/i });
		const readoutRoot = dot?.parentElement;
		const controlsRow = readoutRoot?.parentElement;
		expect(controlsRow).not.toBeNull();
		expect(stop.parentElement?.parentElement).toBe(controlsRow);
		expect(controlsRow?.contains(timer)).toBe(true);
		// Trailing edge, i.e. after the button in document order.
		expect(stop.compareDocumentPosition(dot as Node) & FOLLOWING).toBeTruthy();
		// And still below the bar.
		const bar = screen.getByRole("progressbar");
		expect(
			bar.compareDocumentPosition(controlsRow as Node) & FOLLOWING,
		).toBeTruthy();
	});
});

describe("ActiveMicrophoneCard, test result expansion", () => {
	it("keeps one collapse wrapper mounted and opens it when a result arrives", () => {
		const { container, rerender } = renderCard();
		const closed = container.querySelector(".collapse-root");
		expect(closed).toHaveClass("collapse-root");
		expect(closed).toHaveAttribute("data-open", "false");

		rerender(
			<TooltipProvider delayDuration={200}>
				<ActiveMicrophoneCard {...baseProps} {...completedResultProps} />
			</TooltipProvider>,
		);

		const open = container.querySelector(".collapse-root");
		expect(open).toBe(closed);
		expect(open).toHaveAttribute("data-open", "true");
		expect(screen.getByTestId("audio-quality-value")).toBeInTheDocument();
	});

	it("keeps the result content through the close animation, then unmounts it", async () => {
		const { container, rerender } = renderCard(completedResultProps);
		const open = container.querySelector(".collapse-root");
		expect(open).toHaveAttribute("data-open", "true");
		expect(screen.getByTestId("audio-quality-value")).toBeInTheDocument();

		rerender(
			<TooltipProvider delayDuration={200}>
				<ActiveMicrophoneCard {...baseProps} />
			</TooltipProvider>,
		);

		const closing = container.querySelector(".collapse-root");
		expect(closing).toBe(open);
		expect(closing).toHaveAttribute("data-open", "false");
		expect(closing?.firstElementChild).toHaveAttribute("inert");
		expect(screen.getByTestId("audio-quality-value")).toBeInTheDocument();

		await waitFor(() =>
			expect(screen.queryByTestId("audio-quality-value")).toBeNull(),
		);
	});
});

describe("ActiveMicrophoneCard, live-listen button during a test", () => {
	it("stays mounted but disabled while a test runs (C-CACHE-6)", () => {
		renderCard({ testRunning: true, liveListenDisabled: true });

		const listen = screen.getByRole("button", { name: /listen live/i });
		expect(listen).toBeInTheDocument();
		expect(listen).toBeDisabled();
	});

	it("is enabled when idle", () => {
		renderCard({ testRunning: false, liveListenDisabled: false });

		const listen = screen.getByRole("button", { name: /listen live/i });
		expect(listen).toBeInTheDocument();
		expect(listen).not.toBeDisabled();
	});
});
