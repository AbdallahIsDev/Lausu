import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	pythonMock,
	resetStableMocks,
	sonnerMock,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";
import { TtsPanel } from "@/components/models/TtsPanel";

vi.mock("@/hooks/usePython", () =>
	pythonMock({ captureEvents: stableMocks.pythonEventHandlers }),
);

vi.mock("sonner", () => sonnerMock());

// Radix Select calls pointer-capture methods that jsdom does not implement.
if (typeof Element.prototype.hasPointerCapture !== "function") {
	Element.prototype.hasPointerCapture = function hasPointerCapture() {
		return false;
	};
	Element.prototype.setPointerCapture = function setPointerCapture() {};
	Element.prototype.releasePointerCapture = function releasePointerCapture() {};
}

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: ({
		children,
		icon,
		className,
	}: {
		children?: React.ReactNode;
		icon?: { name?: string };
		className?: string;
	}) => (
		<span data-testid="hugeicon" data-name={icon?.name} className={className}>
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

const { mockCall, pythonEventHandlers, toastError } = stableMocks;

const MAGPIE_VOICES = [
	{ id: "Aria", label: "Aria", gender: "female" },
	{ id: "Sofia", label: "Sofia", gender: "female" },
	{ id: "Jason", label: "Jason", gender: "male" },
	{ id: "Leo", label: "Leo", gender: "male" },
	{ id: "John", label: "John", gender: "male" },
];

const MAGPIE_LANGUAGES = ["en-US", "ar-MSA", "hi-IN"];

function engineInfo(
	available: boolean,
	label: string,
	voices: { id: string; label: string; gender: string }[] = [],
	languages: string[] = ["en-US"],
) {
	return {
		available,
		label,
		download_bytes: 647_000_000,
		models_dir: "C:/cache/tts/models",
		voices,
		languages,
		default_voice: voices[0]?.id ?? "",
	};
}

function statusPayload(
	active: string,
	available: { audio8: boolean; magpie: boolean },
	options: { voice?: string; enabled?: boolean; sofiaCached?: boolean } = {},
) {
	return {
		data: {
			engine: active,
			enabled: options.enabled ?? false,
			voice: options.voice ?? "Aria",
			language: "en-US",
			voices: active === "magpie" ? MAGPIE_VOICES : [],
			languages: active === "magpie" ? MAGPIE_LANGUAGES : ["en-US"],
			sample_cached: {
				magpie: Object.fromEntries(
					MAGPIE_VOICES.map((voice) => [
						voice.id,
						Object.fromEntries(
							MAGPIE_LANGUAGES.map((code) => [
								code,
								Boolean(options.sofiaCached && voice.id === "Sofia"),
							]),
						),
					]),
				),
				audio8: { default: { "en-US": false } },
			},
			engines: {
				audio8: engineInfo(available.audio8, "Audio8 TTS Realistic 0.6B", [
					{ id: "default", label: "Default", gender: "" },
				]),
				magpie: engineInfo(
					available.magpie,
					"MagpieTTS Multilingual 357M",
					MAGPIE_VOICES,
					MAGPIE_LANGUAGES,
				),
			},
		},
	};
}

function mockStatus(
	active: string,
	available: { audio8: boolean; magpie: boolean },
	options: { voice?: string; enabled?: boolean; sofiaCached?: boolean } = {},
) {
	mockCall.mockImplementation((command: string) => {
		if (command === "tts_status") {
			return Promise.resolve(statusPayload(active, available, options));
		}
		if (command === "tts_speak") {
			return Promise.resolve({
				data: { ok: true, engine: active, voice: options.voice ?? "Aria" },
			});
		}
		if (command === "tts_stop") {
			return Promise.resolve({ data: { stopped: true } });
		}
		return Promise.resolve({ success: true });
	});
}

async function renderPanel(
	active: string,
	available: { audio8: boolean; magpie: boolean },
	options: { voice?: string; enabled?: boolean; sofiaCached?: boolean } = {},
) {
	mockStatus(active, available, options);
	render(<TtsPanel />);
	await waitFor(() => {
		expect(screen.getByText("Audio8 TTS Realistic 0.6B")).toBeTruthy();
	});
}

const BOTH = { audio8: true, magpie: true };
const SELECT_NAME = /^Select /;
const ACTIVE_NAME = /^Active: /;

/** One Test control per runnable engine row, in display order (audio8, magpie). */
const AUDIO8_ROW = 0;
const MAGPIE_ROW = 1;

function nthButton(name: string, row: number): HTMLElement {
	const button = screen.getAllByRole("button", { name })[row];
	if (button === undefined) {
		throw new Error(`missing ${name} button at row ${row}`);
	}
	return button;
}

function testButton(row: number = AUDIO8_ROW): HTMLElement {
	return nthButton("Test voice", row);
}

function stopButton(row: number = AUDIO8_ROW): HTMLElement {
	return nthButton("Stop voice", row);
}

beforeEach(() => {
	resetStableMocks();
});

afterEach(() => {
	cleanup();
});

describe("TtsPanel row actions", () => {
	it("offers Download, and no Select/Test, while the pack is missing", async () => {
		await renderPanel("off", { audio8: false, magpie: false });

		expect(
			screen.getAllByRole("button", { name: /^Download \(/ }),
		).toHaveLength(2);
		expect(screen.queryByRole("button", { name: SELECT_NAME })).toBeNull();
		expect(screen.queryByRole("button", { name: ACTIVE_NAME })).toBeNull();
		expect(screen.queryByRole("button", { name: "Test voice" })).toBeNull();
	});

	it("persists the engine selection through set_config", async () => {
		await renderPanel("off", { audio8: true, magpie: false });

		await userEvent.click(screen.getByRole("button", { name: SELECT_NAME }));

		expect(mockCall).toHaveBeenCalledWith("set_config", {
			tts_engine: "audio8",
		});
	});

	it("renders no status line under an engine name", async () => {
		await renderPanel("off", { audio8: true, magpie: false });

		expect(screen.queryByText("Ready")).toBeNull();
		expect(screen.queryByText("Not downloaded")).toBeNull();
	});

	it("keeps the enable switch off the engine rows", async () => {
		await renderPanel("off", BOTH);

		await userEvent.click(screen.getByRole("switch", { name: "Enable" }));

		expect(mockCall).toHaveBeenCalledWith("set_config", { tts_enabled: true });
	});
});

describe("TtsPanel engine configuration", () => {
	it("groups the five Magpie voices by gender", async () => {
		await renderPanel("magpie", BOTH);

		await userEvent.click(screen.getByRole("combobox", { name: "Voice" }));

		expect(await screen.findByText("Female")).toBeTruthy();
		expect(screen.getByText("Male")).toBeTruthy();
		for (const voice of ["Aria", "Sofia", "Jason", "Leo", "John"]) {
			expect(await screen.findByRole("option", { name: voice })).toBeTruthy();
		}
	});

	it("offers every advertised language for the active engine", async () => {
		await renderPanel("magpie", BOTH);

		await userEvent.click(screen.getByRole("combobox", { name: "Language" }));

		expect(await screen.findByRole("option", { name: "hi-IN" })).toBeTruthy();
		expect(screen.getByRole("option", { name: "ar-MSA" })).toBeTruthy();
	});

	it("writes the picked voice and language through set_config", async () => {
		await renderPanel("magpie", BOTH);

		await userEvent.click(screen.getByRole("combobox", { name: "Voice" }));
		await userEvent.click(await screen.findByRole("option", { name: "Jason" }));
		expect(mockCall).toHaveBeenCalledWith("set_config", { tts_voice: "Jason" });

		await userEvent.click(screen.getByRole("combobox", { name: "Language" }));
		await userEvent.click(
			await screen.findByRole("option", { name: "ar-MSA" }),
		);
		expect(mockCall).toHaveBeenCalledWith("set_config", {
			tts_language: "ar-MSA",
		});
	});

	it("explains Audio8 instead of showing an empty voice picker", async () => {
		await renderPanel("audio8", BOTH);

		expect(
			screen.getByText(
				"Clones a voice from a reference recording; no preset voices.",
			),
		).toBeTruthy();
		expect(screen.queryByRole("combobox", { name: "Voice" })).toBeNull();
		expect(screen.queryByRole("combobox", { name: "Language" })).toBeNull();
	});

	it("hints how to configure when no engine is active", async () => {
		await renderPanel("off", BOTH);

		expect(
			screen.getByText("Select an engine to choose its voice and language."),
		).toBeTruthy();
		expect(screen.queryByRole("combobox")).toBeNull();
	});
});

describe("TtsPanel test control", () => {
	it("is icon-only and keeps its accessible name", async () => {
		await renderPanel("magpie", BOTH);

		const button = testButton(MAGPIE_ROW);
		expect(button.textContent).toBe("");
		expect(button.getAttribute("aria-label")).toBe("Test voice");
		expect(button.querySelector('[data-name="PlayIcon"]')).toBeTruthy();
	});

	it("plays a cached clip with no generating state at all", async () => {
		await renderPanel("audio8", BOTH, { sofiaCached: true });

		await userEvent.click(testButton());

		await waitFor(() =>
			expect(mockCall).toHaveBeenCalledWith("tts_speak", {
				engine: "audio8",
				sample: true,
			}),
		);
		expect(
			testButton().querySelector('[data-name="Loading03Icon"]'),
		).toBeNull();
	});

	it("shows the spinner only while an uncached clip renders", async () => {
		await renderPanel("audio8", BOTH);
		let resolveSpeak: (value: unknown) => void = () => {};
		const pending = new Promise((resolve) => {
			resolveSpeak = resolve;
		});
		mockCall.mockImplementation((command: string) => {
			if (command === "tts_speak") return pending;
			if (command === "tts_status") {
				return Promise.resolve(statusPayload("audio8", BOTH));
			}
			return Promise.resolve({ success: true });
		});

		await userEvent.click(testButton());

		expect(
			testButton().querySelector('[data-name="Loading03Icon"]'),
		).toBeTruthy();
		await act(async () => {
			resolveSpeak({ data: { ok: true, engine: "audio8" } });
			await pending;
		});
		await waitFor(() =>
			expect(
				testButton().querySelector('[data-name="Loading03Icon"]'),
			).toBeNull(),
		);
	});

	it("switches to the stop glyph while playing and stops on click", async () => {
		await renderPanel("audio8", BOTH, { sofiaCached: true });
		mockCall.mockImplementation((command: string) => {
			if (command === "tts_status") {
				return Promise.resolve(statusPayload("audio8", BOTH));
			}
			return Promise.resolve({ data: { ok: true, engine: "audio8" } });
		});

		act(() => {
			pythonEventHandlers.tts_playback_state?.({
				engine: "audio8",
				voice: "default",
				state: "playing",
				cached: true,
			});
		});

		expect(stopButton().querySelector('[data-name="StopIcon"]')).toBeTruthy();
		await userEvent.click(stopButton());

		expect(mockCall).toHaveBeenCalledWith("tts_stop");
		await waitFor(() =>
			expect(
				screen.getAllByRole("button", { name: "Test voice" })[AUDIO8_ROW],
			).toBeTruthy(),
		);
	});

	it("returns to play when the clip ends on its own", async () => {
		await renderPanel("audio8", BOTH);

		act(() => {
			pythonEventHandlers.tts_playback_state?.({
				engine: "audio8",
				voice: "default",
				state: "playing",
				cached: true,
			});
		});
		expect(stopButton()).toBeTruthy();

		act(() => {
			pythonEventHandlers.tts_playback_state?.({
				engine: "audio8",
				voice: "default",
				state: "finished",
				cached: true,
			});
		});

		expect(testButton().querySelector('[data-name="PlayIcon"]')).toBeTruthy();
	});
});

describe("TtsPanel errors", () => {
	it("shows plain-language copy with a retry action, never engine text", async () => {
		await renderPanel("audio8", BOTH);
		mockCall.mockImplementation((command: string) => {
			if (command === "tts_status") {
				return Promise.resolve(statusPayload("audio8", BOTH));
			}
			if (command === "tts_speak") {
				return Promise.resolve({
					data: { ok: false, error: "no_output" },
				});
			}
			return Promise.resolve({ success: true });
		});

		await userEvent.click(testButton());

		await waitFor(() => expect(toastError).toHaveBeenCalled());
		const [title, options] = toastError.mock.calls[0] as [
			string,
			{ description: string; action?: { label: string } },
		];
		expect(title).toBe("Could not play the voice");
		expect(options.description).toContain("speakers");
		expect(options.action?.label).toBe("Try again");
		const rendered = `${title} ${options.description}`;
		expect(rendered).not.toMatch(/\/|HTTP|Traceback|Error:/);
	});

	it("renders no timing, cache or runtime diagnostics in the card", async () => {
		await renderPanel("magpie", BOTH);

		expect(screen.queryByText(/sample/i)).toBeNull();
		expect(screen.queryByText(/realtime|wall|cached/i)).toBeNull();
	});
});
