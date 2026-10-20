import { cleanup, render, screen } from "@testing-library/react";
import type React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TestReviewPanel } from "@/components/microphone/TestReviewPanel";
import enMessages from "@/i18n/translations/en.json";

// Flatten the nested en.json into dot-separated keys, mirroring what the
// matches the catalog VALUE (so the test stays locale-source-accurate
// without duplicating the English copy inline).
const enFlat = new Map<string, string>();
function flatten(obj: Record<string, unknown>, prefix = ""): void {
	for (const [k, v] of Object.entries(obj)) {
		const key = prefix ? `${prefix}.${k}` : k;
		if (v && typeof v === "object") {
			flatten(v as Record<string, unknown>, key);
		} else if (typeof v === "string") {
			enFlat.set(key, v);
		}
	}
}
flatten(enMessages as Record<string, unknown>);

function enText(key: string): string {
	const value = enFlat.get(key);
	if (value === undefined) {
		throw new Error(`Missing en.json key: ${key}`);
	}
	return value;
}

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: ({
		children,
		icon,
	}: {
		children?: React.ReactNode;
		icon?: { name?: string };
	}) => (
		<span data-testid="hugeicon" data-name={icon?.name}>
			{children}
		</span>
	),
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

const qualityData = {
	volume_level: "good" as const,
	volume_rms: 0.1,
	peak_level: 0.5,
	noise_level: "moderate" as const,
	has_voice: true,
	has_clipping: false,
	detected_issues: [],
	estimated_transcription_quality: 0,
	silence_ratio: 0.2,
};

function renderNoModelPanel() {
	render(
		<TestReviewPanel
			durationMs={5000}
			quality={qualityData}
			transcription={null}
			transcriptionUnavailable={true}
			testAudioBase64="AAAA"
			rawAudioBase64={null}
			playing={false}
			playingOriginal={false}
			onPlayEnhanced={() => {}}
			onPlayOriginal={() => {}}
			onStop={() => {}}
		/>,
	);
}

describe("TestReviewPanel without transcription renders translated text (never a raw key)", () => {
	afterEach(() => {
		cleanup();
	});

	it("renders Speech Quality but hides Estimated Transcription Quality", () => {
		renderNoModelPanel();

		expect(
			screen.getByText(enText("microphoneTest.audioQuality")),
		).toBeTruthy();
		expect(screen.getByTestId("audio-quality-value").textContent).toBe("88%");
		expect(
			screen.queryByText(enText("microphoneTest.estimatedQuality")),
		).toBeNull();
		expect(screen.queryByTestId("estimated-quality-value")).toBeNull();
	});

	it("hides the estimated row for an empty transcription without a model", () => {
		render(
			<TestReviewPanel
				durationMs={5000}
				quality={qualityData}
				transcription={null}
				transcriptionUnavailable={false}
				testAudioBase64="AAAA"
				rawAudioBase64={null}
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		expect(
			screen.queryByText(enText("microphoneTest.estimatedQuality")),
		).toBeNull();
		expect(screen.getByTestId("audio-quality-value")).toBeTruthy();
	});

	it("never renders the raw translation key anywhere in the panel", () => {
		renderNoModelPanel();

		// The historical bug rendered the literal key string because the
		// call-site key was missing one path segment. Assert NO raw i18n
		// key (dot-separated, camelCase) leaks into the visible text.
		const panelText = document.body.textContent ?? "";
		expect(panelText).not.toContain("microphoneTest.qualityNotApplicable");
		expect(panelText).not.toMatch(/\bmicrophoneTest\.[a-zA-Z.]+\b/);
	});

	it("shows the backend speech score instead of the capture heuristic", () => {
		render(
			<TestReviewPanel
				durationMs={5000}
				quality={{ ...qualityData, speech_quality: 0 }}
				transcription={null}
				transcriptionUnavailable={true}
				testAudioBase64="AAAA"
				rawAudioBase64={null}
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		expect(screen.getByTestId("audio-quality-value").textContent).toBe("0%");
	});

	it("still renders the numeric quality score when a model IS available", () => {
		render(
			<TestReviewPanel
				durationMs={5000}
				quality={{ ...qualityData, estimated_transcription_quality: 72 }}
				transcription="hello world"
				transcriptionUnavailable={false}
				testAudioBase64="AAAA"
				rawAudioBase64={null}
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		expect(screen.getByTestId("estimated-quality-value").textContent).toBe(
			"72%",
		);
		expect(screen.getByTestId("audio-quality-value").textContent).toBe("88%");
	});
});

describe("TestReviewPanel result-card redesign (declutter)", () => {
	afterEach(() => {
		cleanup();
	});

	it("uses the standard subtle surface as a divider section, not the legacy primary tint", () => {
		renderNoModelPanel();

		// The panel is a section of the parent card now, separated by a
		// top divider, so it carries the standard subtle surface but no
		// own rounded border. The legacy primary-tinted surface
		// (border-primary/20 bg-primary/5) must not return.
		const panel = screen
			.getByText(enText("microphoneTest.title"))
			.closest("div.bg-surface-subtle");
		expect(panel).toBeTruthy();
		expect(panel?.className).toContain("border-t");
		expect(panel?.className).toContain("border-border/8");
		expect(panel?.className).not.toContain("rounded-lg");
		expect(panel?.className).not.toContain("bg-primary/5");
		expect(panel?.className).not.toContain("border-primary/20");
	});

	it("does not render the redundant per-metric grid", () => {
		renderNoModelPanel();

		// Every non-good metric state already surfaces as a detected
		// issue, so the Volume / Noise / Clipping / Voice grid
		// duplicated the issues list. Assert none of its labels render.
		const panelText = document.body.textContent ?? "";
		expect(panelText).not.toContain(enText("microphoneTest.volume"));
		expect(panelText).not.toContain(enText("microphoneTest.backgroundNoise"));
		expect(panelText).not.toContain(enText("microphoneTest.clipping"));
	});
});

describe("TestReviewPanel fetch-failure verdict fallback (playback missing, verdict kept)", () => {
	afterEach(() => {
		cleanup();
	});

	it("renders the verdict when both audio refs are null but quality/duration exist", () => {
		render(
			<TestReviewPanel
				durationMs={5000}
				quality={{ ...qualityData, estimated_transcription_quality: 64 }}
				transcription="hello world"
				transcriptionUnavailable={false}
				testAudioBase64={null}
				rawAudioBase64={null}
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		expect(screen.getByText(enText("microphoneTest.title"))).toBeTruthy();
		expect(screen.getByTestId("estimated-quality-value").textContent).toBe(
			"64%",
		);
		expect(screen.getByTestId("test-transcription").textContent).toBe(
			"hello world",
		);
	});

	it("renders no playback buttons when both audio refs are null", () => {
		render(
			<TestReviewPanel
				durationMs={5000}
				quality={{ ...qualityData, estimated_transcription_quality: 64 }}
				transcription={null}
				transcriptionUnavailable={false}
				testAudioBase64={null}
				rawAudioBase64={null}
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		expect(
			screen.queryByText(enText("microphoneTest.playEnhanced")),
		).toBeNull();
		expect(
			screen.queryByText(enText("microphoneTest.playOriginal")),
		).toBeNull();
		// No controls remain: Retest was removed, and playback is unavailable
		// without audio refs.
		expect(screen.queryAllByRole("button")).toHaveLength(0);
	});

	it("keeps an empty closed collapse wrapper when no audio and no verdict exist", () => {
		const { container } = render(
			<TestReviewPanel
				durationMs={0}
				quality={null}
				transcription={null}
				transcriptionUnavailable={false}
				testAudioBase64={null}
				rawAudioBase64={null}
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		const root = container.firstElementChild;
		expect(root).toHaveClass("collapse-root");
		expect(root).toHaveAttribute("data-open", "false");
		expect(container.textContent).toBe("");
	});

	it("always renders Enhanced-left / Original-right (no order swap, no third label)", () => {
		render(
			<TestReviewPanel
				durationMs={5200}
				quality={{ ...qualityData, estimated_transcription_quality: 100 }}
				transcription={null}
				transcriptionUnavailable={false}
				testAudioBase64="AAA="
				rawAudioBase64="AAA="
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		const enhanced = screen.getByText(enText("microphoneTest.playEnhanced"));
		const original = screen.getByText(enText("microphoneTest.playOriginal"));
		// DOM order: Enhanced first (left in LTR), Original second (right).
		expect(
			enhanced.compareDocumentPosition(original) &
				Node.DOCUMENT_POSITION_FOLLOWING,
		).toBeTruthy();
	});
});

describe("TestReviewPanel unknown-issue fallback contract (no recommendation, no CTA, no crash)", () => {
	afterEach(() => {
		cleanup();
	});

	it("renders the raw label with no recommendation or CTA for an unmapped literal", () => {
		const rawIssue = "Calibration drift detected in channel 2";
		render(
			<TestReviewPanel
				durationMs={5000}
				quality={{ ...qualityData, detected_issues: [rawIssue] }}
				transcription={null}
				transcriptionUnavailable={false}
				testAudioBase64="AAAA"
				rawAudioBase64={null}
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		expect(screen.getByTestId("detected-issue-row")).toBeTruthy();
		expect(screen.getByText(rawIssue)).toBeTruthy();
		expect(screen.queryByTestId("issue-recommendation")).toBeNull();
		expect(screen.queryByTestId("issue-apply-preset")).toBeNull();
	});
});
