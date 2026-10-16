import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { LiveQualityFeedback } from "@/components/feedback/LiveQualityFeedback";

// The readout is the trailing element of the card's test-controls row: a
// pulsing red dot + the countdown, and nothing else. It replaced the old
// "Recording… 00:0N / 00:10" line that sat between the level bar and the
// buttons and pushed the buttons down the moment a test started. jsdom has
// no layout, so the "no layout shift" half is pinned as class facts (the
// component renders null while idle, and the dot is the same size/token as
// the bubble's recording dot) plus the card-level document-order test in
// `microphone-page-interactions.test.tsx`.

const baseProps = {
	isRecording: true,
	elapsedSeconds: 3,
	totalSeconds: 10,
};

describe("LiveQualityFeedback, recording dot + countdown", () => {
	afterEach(() => {
		cleanup();
	});

	beforeEach(() => {
		cleanup();
	});

	it("renders nothing when isRecording is false, so the row cannot grow", () => {
		const { container } = render(
			<LiveQualityFeedback {...baseProps} isRecording={false} />,
		);
		expect(container.firstChild).toBeNull();
	});

	it("renders the countdown 00:03 / 00:10", () => {
		render(<LiveQualityFeedback {...baseProps} />);
		expect(screen.getByText("00:03 / 00:10")).toBeInTheDocument();
	});

	it("pads minutes and seconds (MM:SS format)", () => {
		render(
			<LiveQualityFeedback
				{...baseProps}
				elapsedSeconds={65}
				totalSeconds={600}
			/>,
		);
		expect(screen.getByText("01:05 / 10:00")).toBeInTheDocument();
	});

	it("renders the dot and NO text label at all", () => {
		// The word "Recording…" was removed (and its i18n key deleted from
		// all 8 locales). Asserting the whole text content leaves no room
		// for a label to come back, in any language.
		const { container } = render(<LiveQualityFeedback {...baseProps} />);
		const root = container.firstElementChild;
		if (!root) throw new Error("readout did not render");
		expect(root.textContent).toBe("00:03 / 00:10");
		expect(screen.queryByText(/recording/i)).toBeNull();
	});

	it("uses the shared pulsing red dot (same token + size as the bubble's)", () => {
		const { container } = render(<LiveQualityFeedback {...baseProps} />);
		const dot = container.querySelector(
			"[data-slot='microphone-recording-dot']",
		);
		expect(dot).not.toBeNull();
		// Class assertions, not computed styles: jsdom resolves neither
		// `animate-pulse` nor the `--destructive` token.
		expect(dot?.className).toBe(
			"w-1.5 h-1.5 rounded-full bg-destructive animate-pulse",
		);
		expect(dot?.getAttribute("aria-hidden")).not.toBeNull();
	});

	it("pushes itself to the trailing edge with a logical margin", () => {
		// `ms-auto` (not `ml-auto`): mirrors correctly under RTL, and the
		// readout must never wrap onto a second line.
		const { container } = render(<LiveQualityFeedback {...baseProps} />);
		const root = container.firstElementChild;
		expect(root?.className).toContain("ms-auto");
		expect(root?.className).not.toContain("ml-auto");
	});

	it("does NOT render the removed voice-quality status messages", () => {
		// The live level bar owns level feedback; these textual states were
		// redundant noise and are permanently removed.
		const { container } = render(<LiveQualityFeedback {...baseProps} />);
		expect(screen.queryByText(/Voice detected/i)).toBeNull();
		expect(screen.queryByText(/Waiting for voice/i)).toBeNull();
		expect(screen.queryByText(/Low volume/i)).toBeNull();
		expect(container.querySelector("[aria-live]")).toBeNull();
	});
});
