import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "@/i18n/translations/en.json";

// Flatten the nested en.json into dot-separated keys, mirroring what
// the real i18n module does at load time. Used by the t() spy below.
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

// Non-optional lookup for assertion arguments, a missing key is a test
// setup bug, not an empty matcher.
function enText(key: string): string {
	const value = enFlat.get(key);
	if (value === undefined) {
		throw new Error(`Missing en.json key: ${key}`);
	}
	return value;
}

// Hoist the spy so the vi.mock factory can reference it.
const { tSpy } = vi.hoisted(() => ({
	tSpy: vi.fn((key: string, params?: Record<string, string>) => {
		let value = enFlat.get(key) ?? key;
		if (params) {
			for (const [k, v] of Object.entries(params)) {
				value = value.replace(new RegExp(`\\{${k}\\}`, "g"), v);
			}
		}
		return value;
	}),
}));

vi.mock("@/i18n/i18n", () => ({ t: tSpy }));

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

vi.mock("@/components/audio/AudioFilterChain", () => ({
	AudioFilterChain: () => <div data-testid="audio-filter-chain" />,
}));

// InfoTooltip's real implementation mounts a Radix Tooltip.Root, which
// requires the app-global TooltipProvider boundary (App.tsx). These
// PresetAccordionSelector tests only need the trigger contract, a
// focusable trigger whose accessible name is composed through t() exactly
// like the real component ("More info about {label}"), so a plain
// stand-in keeps them provider-free. Radix hover/focus behaviour itself
// is pinned in components/feedback/__tests__/InfoTooltip.test.tsx.
// The mock mirrors the real triggerAs contract: "button" (default) →
// role=button; "inline" → a focusable role-less span whose clicks do
// NOT propagate (the real inline span stops propagation so activating
// it never toggles the wrapping accordion/row).
vi.mock("@/components/feedback/InfoTooltip", () => ({
	InfoTooltip: ({
		text,
		contextLabel,
		triggerAs,
	}: {
		text: string;
		contextLabel?: string;
		triggerAs?: "button" | "inline";
	}) => {
		const ariaLabel = tSpy("a11y.moreInfoAbout", {
			label: contextLabel ?? "",
		});
		if (triggerAs === "inline") {
			return (
				// biome-ignore lint/a11y/noStaticElementInteractions: mirrors the real inline trigger (focusable span whose clicks never select the row).
				// biome-ignore lint/a11y/useKeyWithClickEvents: mirrors the real inline trigger, click propagation is suppressed; keyboard opens the tooltip via focus.
				// biome-ignore lint/a11y/useAriaPropsSupportedByRole: mirrors the real inline trigger (aria-label as the sole accessible name, no role).
				<span
					// biome-ignore lint/a11y/noNoninteractiveTabindex: mirrors the real inline trigger (focusable by design; tooltip opens on focus).
					tabIndex={0}
					data-testid="info-tooltip-trigger"
					data-tooltip-text={text}
					aria-label={ariaLabel}
					onClick={(event) => event.stopPropagation()}
				/>
			);
		}
		return (
			<button
				type="button"
				data-testid="info-tooltip-trigger"
				data-tooltip-text={text}
				aria-label={ariaLabel}
			/>
		);
	},
}));

import { MicrophoneListItem } from "@/components/microphone/MicrophoneListItem";
import { TestReviewPanel } from "@/components/microphone/TestReviewPanel";
import { RadioGroup } from "@/components/ui/radio-group";
import { AvailableMicrophonesList } from "@/pages/microphone/components/AvailableMicrophonesList";
import { PresetAccordionSelector } from "@/pages/microphone/components/PresetAccordionSelector";
import type { LausuConfig, MicrophoneDevice } from "@/types/config";

// ── Fixtures ──────────────────────────────────────────────────────────
const micA: MicrophoneDevice = {
	index: 0,
	id: "mic-a",
	name: "Blue Yeti X",
	host_api: "ALSA",
	default: false,
	channels: 2,
	rate: 48000,
};

const micB: MicrophoneDevice = {
	index: 1,
	id: "mic-b",
	name: "Rode NT-USB",
	host_api: "ALSA",
	default: false,
	channels: 1,
	rate: 44100,
};

// Minimal LausuConfig, only the fields PresetAccordionSelector
// itself reads (audio_preset + the noise_filter_* fields handed to the
// stubbed AudioFilterChain). The full object is too noisy for this unit
// test.
const minimalConfig = {
	audio_preset: "auto",
} as unknown as LausuConfig;

// ── Test setup ────────────────────────────────────────────────────────
beforeEach(() => {
	tSpy.mockClear();
	cleanup();
});

afterEach(() => {
	cleanup();
});

//Mic list radio rows: each row exposes an accessible name, checked
// state tracks the selection, and items are REALLY disabled during a test.
describe("mic selection rows expose radio semantics with per-row accessible names", () => {
	it("renders one radiogroup whose radios carry the device names (System Default included)", () => {
		render(
			<AvailableMicrophonesList
				microphones={[micA, micB]}
				activeMicId={null}
				testRunning={false}
				onSelectMicrophone={() => {}}
			/>,
		);

		const group = screen.getByRole("radiogroup");
		expect(group).toBeTruthy();

		// Per-row accessible names, the regression BG-45 called out was
		// N indistinguishable controls; each radio now announces WHICH
		// microphone it selects.
		expect(screen.getByRole("radio", { name: "Blue Yeti X" })).toBeTruthy();
		expect(screen.getByRole("radio", { name: "Rode NT-USB" })).toBeTruthy();
		expect(screen.getByRole("radio", { name: "System Default" })).toBeTruthy();
	});

	it("marks the active selection via aria-checked on its radio", () => {
		render(
			<AvailableMicrophonesList
				microphones={[micA, micB]}
				activeMicId="mic-a"
				testRunning={false}
				onSelectMicrophone={() => {}}
			/>,
		);

		expect(screen.getByRole("radio", { name: "Blue Yeti X" })).toBeChecked();
		expect(
			screen.getByRole("radio", { name: "Rode NT-USB" }),
		).not.toBeChecked();
	});

	it("disables every radio while a test recording is running", () => {
		render(
			<AvailableMicrophonesList
				microphones={[micA, micB]}
				activeMicId="mic-a"
				testRunning={true}
				onSelectMicrophone={() => {}}
			/>,
		);

		for (const name of ["System Default", "Blue Yeti X", "Rode NT-USB"]) {
			expect(screen.getByRole("radio", { name })).toBeDisabled();
		}
	});
});

//TestReviewPanel exposes quality updates via aria-live +
// role=status, hides the decorative bullet from AT, and uses the
// theme warning token (no hardcoded palette classes).
describe("TestReviewPanel quality block is announced to AT", () => {
	const qualityWithIssues = {
		volume_level: "good" as const,
		volume_rms: 0.1,
		peak_level: 0.5,
		noise_level: "moderate" as const,
		has_voice: true,
		has_clipping: false,
		detected_issues: ["Moderate background noise"],
		estimated_transcription_quality: 70,
		silence_ratio: 0.2,
	};

	function renderReviewPanel() {
		return render(
			<TestReviewPanel
				durationMs={5000}
				quality={qualityWithIssues}
				transcription="test transcription"
				transcriptionUnavailable={false}
				enhancementActive={true}
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

	it("wraps the quality block in an aria-live=polite region with aria-atomic", () => {
		renderReviewPanel();

		// The quality summary (containing the "Estimated Transcription
		// Quality" label) is wrapped in an aria-live region.
		const qualityLabel = screen.getByText(
			enText("microphoneTest.estimatedQuality"),
		);
		// Find the live region ancestor of the quality label.
		const liveRegion = qualityLabel.closest('[aria-live="polite"]');
		expect(liveRegion).toBeTruthy();
		expect(liveRegion?.getAttribute("aria-atomic")).toBe("true");
	});

	it("marks the detected-issues heading with role=status", () => {
		renderReviewPanel();

		// The "Detected Issues" heading carries role="status" so SR users
		// are alerted when issues appear after a test. It renders as an
		// <output> element, the semantic status live-region element,
		// whose implicit ARIA role is status. Assert the COMPUTED role via
		// toHaveRole (the literal role attribute is absent on <output>).
		const detectedIssuesHeading = Array.from(
			document.querySelectorAll("output"),
		).find((el) => el.textContent === enText("microphoneTest.detectedIssues"));
		expect(detectedIssuesHeading).toBeTruthy();
		expect(detectedIssuesHeading).toHaveRole("status");
	});

	it("hides the decorative issue marker from assistive tech", () => {
		renderReviewPanel();

		// The marker is purely decorative; the list structure conveys its
		// meaning, so it must be aria-hidden. It uses the theme warning
		// TOKEN, never a hardcoded palette class like text-amber-500.
		const markers = Array.from(document.querySelectorAll("span.bg-warning"));
		expect(markers.length).toBeGreaterThanOrEqual(1);
		for (const marker of markers) {
			expect(marker.getAttribute("aria-hidden")).toBe("true");
			expect(marker.className).not.toContain("amber");
			expect(marker.className).toContain("rounded-full");
		}
	});
});

//TestReviewPanel transcription display (present-only; no explanatory block).
describe("TestReviewPanel test-transcription display", () => {
	it("renders the transcription under the You-said label when present", () => {
		render(
			<TestReviewPanel
				durationMs={5000}
				quality={null}
				transcription="hello world"
				transcriptionUnavailable={false}
				enhancementActive={true}
				testAudioBase64="AAAA"
				rawAudioBase64={null}
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		expect(screen.getByText("You said")).toBeTruthy();
		expect(screen.getByTestId("test-transcription").textContent).toBe(
			"hello world",
		);
	});

	it("omits the You-said block when no model can transcribe", () => {
		render(
			<TestReviewPanel
				durationMs={5000}
				quality={null}
				transcription={null}
				transcriptionUnavailable={true}
				enhancementActive={true}
				testAudioBase64="AAAA"
				rawAudioBase64={null}
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		expect(screen.queryByText("You said")).toBeNull();
		expect(screen.queryByTestId("test-transcription")).toBeNull();
		expect(screen.queryByTestId("test-transcription-unavailable")).toBeNull();
	});

	it("clamps long transcriptions to three lines and keeps the full text in title", () => {
		const longTranscription = "word ".repeat(120).trim();
		render(
			<TestReviewPanel
				durationMs={5000}
				quality={null}
				transcription={longTranscription}
				transcriptionUnavailable={false}
				enhancementActive={true}
				testAudioBase64="AAAA"
				rawAudioBase64={null}
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		const transcript = screen.getByTestId("test-transcription");
		expect(transcript.className).toContain("line-clamp-3");
		expect(transcript.getAttribute("title")).toBe(longTranscription);
		expect(transcript.textContent).toBe(longTranscription);
	});

	it("renders neither line without transcription data", () => {
		render(
			<TestReviewPanel
				durationMs={5000}
				quality={null}
				transcription={null}
				transcriptionUnavailable={false}
				enhancementActive={true}
				testAudioBase64="AAAA"
				rawAudioBase64={null}
				playing={false}
				playingOriginal={false}
				onPlayEnhanced={() => {}}
				onPlayOriginal={() => {}}
				onStop={() => {}}
			/>,
		);

		expect(screen.queryByText("You said")).toBeNull();
		expect(screen.queryByTestId("test-transcription")).toBeNull();
	});
});

//AvailableMicrophonesList keeps real list semantics (ul/li) around the
// unified radio rows.
describe("AvailableMicrophonesList renders a real list with ul/li + roles", () => {
	it("wraps the mic rows in a <ul role=list>", () => {
		render(
			<AvailableMicrophonesList
				microphones={[micA, micB]}
				activeMicId={null}
				testRunning={false}
				onSelectMicrophone={() => {}}
			/>,
		);

		// Computed-role assertion: a native <ul> exposes the "list"
		// role in the accessibility tree even without an explicit
		// role="list" attribute (the ARIA-in-HTML mapping). Querying by
		// role verifies the actual AT exposure, not the markup detail.
		const ul = screen.getByRole("list");
		expect(ul).toBeTruthy();
		expect(ul.tagName.toLowerCase()).toBe("ul");
	});

	it("renders one <li role=listitem> per row (system default + every device)", () => {
		render(
			<AvailableMicrophonesList
				microphones={[micA, micB]}
				activeMicId="mic-a"
				testRunning={false}
				onSelectMicrophone={() => {}}
			/>,
		);

		// 1 system-default row + 2 device rows = 3 list items. The ACTIVE
		// device is present too (radio groups need the selected option in
		// the set). Native <li> elements expose the "listitem" role
		// implicitly.
		const items = screen.getAllByRole("listitem");
		expect(items.length).toBe(3);
	});

	it("does not render any bare <div> as a direct child of the list (all rows are <li>)", () => {
		render(
			<AvailableMicrophonesList
				microphones={[micA, micB]}
				activeMicId={null}
				testRunning={false}
				onSelectMicrophone={() => {}}
			/>,
		);

		const ul = screen.getByRole("list");
		expect(ul).toBeTruthy();
		const directDivChildren = Array.from(ul?.children ?? []).filter(
			(child) => child.tagName.toLowerCase() === "div",
		);
		expect(directDivChildren.length).toBe(0);
	});
});

//PresetAccordionSelector memoizes getPresetOptions() instead of
// calling it inline per render.
describe("PresetAccordionSelector memoizes getPresetOptions() to a single call per mount", () => {
	it("calls t('settings.audioEnhancement.presetAuto') exactly once on initial render", () => {
		// The option array is built inside useMemo(() =>
		// getPresetOptions(), []) so each preset label/description key is
		// looked up exactly once per mount, no matter how often the
		// component re-renders (level pushes re-render the parent card).
		render(
			<PresetAccordionSelector
				preset="auto"
				config={minimalConfig}
				onPresetChange={() => {}}
				onConfigChange={() => {}}
			/>,
		);

		const presetAutoCalls = tSpy.mock.calls.filter(
			([key]) => key === "settings.audioEnhancement.presetAuto",
		).length;
		expect(presetAutoCalls).toBe(1);

		// Same invariant for the description key (proves both label
		// and description paths go through the memoized array).
		const presetAutoDescCalls = tSpy.mock.calls.filter(
			([key]) => key === "settings.audioEnhancement.presetAutoDescription",
		).length;
		expect(presetAutoDescCalls).toBe(1);
	});

	it("does NOT re-call getPresetOptions() on re-render when props change", () => {
		const { rerender } = render(
			<PresetAccordionSelector
				preset="auto"
				config={minimalConfig}
				onPresetChange={() => {}}
				onConfigChange={() => {}}
			/>,
		);
		const callsAfterFirstRender = tSpy.mock.calls.filter(
			([key]) => key === "settings.audioEnhancement.presetAuto",
		).length;
		expect(callsAfterFirstRender).toBe(1);

		// Re-render with a different preset. The memoized preset
		// array is reused (useMemo dep is []), so getPresetOptions()
		// is NOT called again, presetAuto should still have been
		// called only once total.
		rerender(
			<PresetAccordionSelector
				preset="studio"
				config={minimalConfig}
				onPresetChange={() => {}}
				onConfigChange={() => {}}
			/>,
		);

		const callsAfterRerender = tSpy.mock.calls.filter(
			([key]) => key === "settings.audioEnhancement.presetAuto",
		).length;
		expect(callsAfterRerender).toBe(1);
	});

	it("renders a flat header with no chip or disclosure, and restores the stashed preset", () => {
		const handlePresetChange = vi.fn();
		const { rerender } = render(
			<PresetAccordionSelector
				preset="studio"
				config={minimalConfig}
				onPresetChange={handlePresetChange}
				onConfigChange={() => {}}
			/>,
		);

		expect(screen.getByText("Microphone Quality")).toBeTruthy();
		// The old compact header affordances are gone: no value chip, no
		// accordion trigger, no second reveal step.
		expect(screen.queryByTestId("mic-preset-current")).toBeNull();
		expect(screen.queryByRole("button", { expanded: false })).toBeNull();
		expect(screen.getByTestId("mic-preset-radio-group")).toBeTruthy();
		expect(
			screen.getByRole("radio", { name: "Studio", checked: true }),
		).toBeTruthy();

		// "off" lives ONLY behind the Switch, there is no OFF radio.
		fireEvent.click(screen.getByTestId("mic-quality-switch"));
		expect(handlePresetChange).toHaveBeenCalledWith("off");

		rerender(
			<PresetAccordionSelector
				preset="off"
				config={minimalConfig}
				onPresetChange={handlePresetChange}
				onConfigChange={() => {}}
			/>,
		);
		expect(screen.queryByTestId("mic-preset-radio-group")).toBeNull();

		// Flipping the Switch back on restores the stashed preset.
		fireEvent.click(screen.getByTestId("mic-quality-switch"));
		expect(handlePresetChange).toHaveBeenCalledWith("studio");
	});

	it("reveals the filter chain inline under Advanced with no disclosure step", () => {
		const { rerender } = render(
			<PresetAccordionSelector
				preset="auto"
				config={minimalConfig}
				onPresetChange={() => {}}
				onConfigChange={() => {}}
			/>,
		);

		// Not Advanced → no chain and no intermediate disclosure control.
		expect(screen.queryByText("Custom filters")).toBeNull();
		expect(
			document.querySelector('[data-testid="audio-filter-chain"]'),
		).toBeFalsy();

		rerender(
			<PresetAccordionSelector
				preset="custom"
				config={minimalConfig}
				onPresetChange={() => {}}
				onConfigChange={() => {}}
			/>,
		);

		// Advanced selected → the chain is already open (no second click).
		expect(
			document.querySelector('[data-testid="audio-filter-chain"]'),
		).toBeTruthy();
		expect(screen.queryByText("Custom filters")).toBeNull();
	});

	it("keeps one horizontal inset on the section, never a second one on the list", () => {
		render(
			<PresetAccordionSelector
				preset="custom"
				config={minimalConfig}
				onPresetChange={() => {}}
				onConfigChange={() => {}}
			/>,
		);

		// The section owns the 16px inset; rows are pills inside it, so the
		// list itself must not add horizontal padding of its own.
		const group = screen.getByTestId("mic-preset-radio-group");
		expect(group.className).not.toContain("px-2");
		expect(group.className).not.toContain("px-4");
		expect(group.closest("section")?.className).toContain("p-4");
	});
});

//PresetAccordionSelector compact rows: option descriptions are NOT
// permanently visible, each option exposes a keyboard-focusable
// InfoTooltip trigger instead, and interacting with that trigger never
// changes the selected preset.
describe("PresetAccordionSelector descriptions live behind InfoTooltip triggers", () => {
	const baseProps = {
		config: minimalConfig,
		onConfigChange: () => {},
	};

	it("does not keep any option description permanently visible in the DOM", () => {
		render(
			<PresetAccordionSelector
				preset="auto"
				{...baseProps}
				onPresetChange={() => {}}
			/>,
		);

		expect(
			screen.queryByText(
				enText("settings.audioEnhancement.presetAutoDescription"),
			),
		).toBeNull();
		expect(
			screen.queryByText(
				enText("settings.audioEnhancement.presetOffDescription"),
			),
		).toBeNull();
	});

	it("exposes one info trigger per option plus one for the section, each named for its context", () => {
		render(
			<PresetAccordionSelector
				preset="auto"
				{...baseProps}
				onPresetChange={() => {}}
			/>,
		);

		// 4 built-in option triggers + the section trigger, all real
		// buttons in the flat list (no wrapping accordion trigger exists
		// anymore, so the inline-span workaround is gone too).
		const infoTriggers = screen.getAllByRole("button", {
			name: /^More info about/,
		});
		expect(infoTriggers.length).toBe(5);
		const headerTrigger = screen.getByLabelText(
			"More info about Microphone Quality",
		);
		expect(headerTrigger.tagName).toBe("BUTTON");
		expect(screen.getByLabelText("More info about Studio")).toBeTruthy();
	});

	it("toggling the enable-Switch never touches the radios, while a plain row click still selects", () => {
		const handlePresetChange = vi.fn();
		render(
			<PresetAccordionSelector
				preset="auto"
				{...baseProps}
				onPresetChange={handlePresetChange}
			/>,
		);

		// The Switch flips enablement only: on → "off" (stashing
		// "auto"), it never selects a radio preset.
		fireEvent.click(screen.getByTestId("mic-quality-switch"));
		expect(handlePresetChange).toHaveBeenCalledTimes(1);
		expect(handlePresetChange).toHaveBeenCalledWith("off");

		// Clicking the row body (not the radio control itself) selects.
		fireEvent.click(screen.getByTestId("mic-preset-option-studio"));
		expect(handlePresetChange).toHaveBeenCalledWith("studio");
	});
});

//MicrophoneListItem: badge + row rendering for the unified radio list.
describe("MicrophoneListItem radio row", () => {
	function renderRowInGroup(ui: React.ReactElement) {
		// Radix RadioGroupItem requires a Root ancestor (production always
		// renders rows inside the list's single RadioGroup).
		return render(<RadioGroup>{ui}</RadioGroup>);
	}

	it("renders the OS-default badge with the accent foreground token when not the active selection", () => {
		renderRowInGroup(
			<MicrophoneListItem
				mic={{ ...micA, default: true }}
				checked={false}
				showDefaultBadge={true}
				disabled={false}
				onSelect={() => {}}
			/>,
		);

		const badge = screen.getByText("Default");
		expect(badge.className).toContain("bg-accent");
		expect(badge.className).toContain("text-accent-foreground");
		expect(badge.className).not.toContain("text-white");
	});

	it("omits the badge when the OS default IS the active selection", () => {
		renderRowInGroup(
			<MicrophoneListItem
				mic={{ ...micA, default: true }}
				checked={true}
				showDefaultBadge={false}
				disabled={false}
				onSelect={() => {}}
			/>,
		);

		expect(screen.queryByText("Default")).toBeNull();
	});

	it("exposes the mic name as the radio's accessible name", () => {
		renderRowInGroup(
			<MicrophoneListItem
				mic={micA}
				checked={false}
				showDefaultBadge={false}
				disabled={false}
				onSelect={() => {}}
			/>,
		);

		expect(screen.getByRole("radio", { name: "Blue Yeti X" })).toBeTruthy();
	});
});
