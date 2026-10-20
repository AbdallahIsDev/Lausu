import { cleanup, render, screen } from "@testing-library/react";
import type React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TestReviewPanel } from "@/components/microphone/TestReviewPanel";
import enMessages from "@/i18n/translations/en.json";

// Flatten en.json exactly like the i18n loader so assertions compare the
// rendered copy against the locale source, never a duplicated literal.
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
	noise_level: "low" as const,
	has_voice: true,
	has_clipping: false,
	detected_issues: [],
	estimated_transcription_quality: 90,
	silence_ratio: 0.1,
};

function renderPanel(
	enhancementActive: boolean,
	overrides: {
		testAudioBase64?: string | null;
		rawAudioBase64?: string | null;
	} = {},
) {
	render(
		<TestReviewPanel
			durationMs={5100}
			quality={qualityData}
			transcription="hello world"
			transcriptionUnavailable={false}
			enhancementActive={enhancementActive}
			testAudioBase64={
				overrides.testAudioBase64 === undefined
					? "AAAA"
					: overrides.testAudioBase64
			}
			rawAudioBase64={
				overrides.rawAudioBase64 === undefined
					? "BBBB"
					: overrides.rawAudioBase64
			}
			playing={false}
			playingOriginal={false}
			onPlayEnhanced={() => {}}
			onPlayOriginal={() => {}}
			onStop={() => {}}
		/>,
	);
}

describe("TestReviewPanel playback buttons vs microphone-quality chain", () => {
	afterEach(() => {
		cleanup();
	});

	it("shows only Play Original while the quality chain is off", () => {
		renderPanel(false);

		expect(
			screen.getByText(enText("microphoneTest.playOriginal")),
		).toBeTruthy();
		expect(
			screen.queryByText(enText("microphoneTest.playEnhanced")),
		).toBeNull();
		expect(screen.getAllByRole("button")).toHaveLength(1);
	});

	it("shows both A/B buttons while the quality chain is active", () => {
		renderPanel(true);

		const enhanced = screen.getByText(enText("microphoneTest.playEnhanced"));
		const original = screen.getByText(enText("microphoneTest.playOriginal"));
		expect(
			enhanced.compareDocumentPosition(original) &
				Node.DOCUMENT_POSITION_FOLLOWING,
		).toBeTruthy();
	});

	it("renders no playback buttons when a chain-off result has no raw audio", () => {
		renderPanel(false, { rawAudioBase64: null });

		expect(
			screen.queryByText(enText("microphoneTest.playEnhanced")),
		).toBeNull();
		expect(
			screen.queryByText(enText("microphoneTest.playOriginal")),
		).toBeNull();
	});
});
