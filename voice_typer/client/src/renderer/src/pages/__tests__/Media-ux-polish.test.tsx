// Idle/running/result polish for the Media page: drop-zone affordance,
// in-field paste/clear + inline validation, and a result card that uses
// words and the new media metadata instead of a green check + characters.

import {
	act,
	cleanup,
	fireEvent,
	screen,
	waitFor,
} from "@testing-library/react";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/__tests__/helpers/render";
import { t } from "@/i18n/i18n";
import { useMediaSourceStore } from "@/stores/mediaSourceStore";

const callMock = vi.fn();
const handlers = new Map<string, (data: Record<string, unknown>) => void>();

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: callMock }),
	usePythonEvent: (
		type: string,
		handler: (data: Record<string, unknown>) => void,
	) => {
		handlers.set(type, handler);
	},
}));

vi.mock("sonner", () => ({
	toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}));

async function renderPage() {
	const { default: MediaPage } = await import("@/pages/Media");
	return renderWithProviders(<MediaPage />);
}

afterEach(() => {
	cleanup();
});

beforeEach(() => {
	callMock.mockReset();
	vi.mocked(toast.error).mockClear();
	handlers.clear();
	useMediaSourceStore.getState().clear();
	sessionStorage.clear();
	Object.defineProperty(navigator, "clipboard", {
		configurable: true,
		value: {
			readText: vi.fn().mockResolvedValue("https://example.com/clip.mp4"),
		},
	});
	let seq = 0;
	callMock.mockImplementation((cmd: string) => {
		if (cmd === "media_transcribe_status") {
			return Promise.resolve({ jobs: [], max_jobs: 4 });
		}
		if (cmd === "media_transcribe_start") {
			seq += 1;
			return Promise.resolve({ job_id: `job-${seq}`, status: "running" });
		}
		return Promise.resolve({});
	});
	(window as unknown as Record<string, unknown>).window_ = {};
});

describe("Media idle state", () => {
	it("swaps to a release label while dragging", async () => {
		const { container } = await renderPage();
		const zone = screen.getByRole("button", { name: t("media.dropZoneAria") });
		expect(zone.className).toContain("focus-visible:ring-1");
		fireEvent.dragOver(zone);
		expect(screen.getByText(t("media.dropRelease"))).toBeTruthy();
		expect(zone.className).toContain("bg-primary/10");
		fireEvent.dragLeave(zone);
		expect(container.querySelector("button[aria-disabled='true']")).toBeNull();
	});

	it("opts the link field out of browser and password-manager autofill", async () => {
		await renderPage();
		const input = screen.getByPlaceholderText(
			t("media.sourcePlaceholder"),
		) as HTMLInputElement;
		expect(input.type).toBe("text");
		expect(input.getAttribute("name")).toBe("mediaSourceField");
		expect(input.getAttribute("autocomplete")).toBe("off");
		expect(input.getAttribute("autocorrect")).toBe("off");
		expect(input.getAttribute("autocapitalize")).toBe("off");
		expect(input.getAttribute("spellcheck")).toBe("false");
		expect(input.getAttribute("data-lpignore")).toBe("true");
		expect(input.getAttribute("data-1p-ignore")).toBe("true");
		expect(input.getAttribute("data-form-type")).toBe("other");
	});

	it("shows only the Paste button while empty, then only Clear once filled", async () => {
		await renderPage();
		expect(screen.getByTestId("media-source-paste")).toBeTruthy();
		expect(screen.queryByTestId("media-source-clear")).toBeNull();

		fireEvent.click(screen.getByTestId("media-source-paste"));
		const input = screen.getByPlaceholderText(
			t("media.sourcePlaceholder"),
		) as HTMLInputElement;
		await waitFor(() =>
			expect(input.value).toBe("https://example.com/clip.mp4"),
		);
		expect(screen.queryByTestId("media-source-paste")).toBeNull();
		expect(screen.getByTestId("media-source-clear")).toBeTruthy();

		fireEvent.click(screen.getByTestId("media-source-clear"));
		expect(input.value).toBe("");
		expect(screen.getByTestId("media-source-paste")).toBeTruthy();
		expect(screen.queryByTestId("media-source-clear")).toBeNull();
	});

	it("validates only on submit: toast + red border, cleared on edit", async () => {
		await renderPage();
		const input = screen.getByPlaceholderText(
			t("media.sourcePlaceholder"),
		) as HTMLInputElement;
		fireEvent.change(input, { target: { value: "not a link" } });
		expect(vi.mocked(toast.error)).not.toHaveBeenCalled();
		expect(input.getAttribute("aria-invalid")).toBe("false");

		fireEvent.click(screen.getByRole("button", { name: t("media.start") }));
		expect(vi.mocked(toast.error)).toHaveBeenCalledWith(
			t("media.invalidSource"),
		);
		expect(input.getAttribute("aria-invalid")).toBe("true");
		expect(screen.queryByRole("alert")).toBeNull();

		fireEvent.change(input, { target: { value: "https://example.com/a.mp4" } });
		expect(input.getAttribute("aria-invalid")).toBe("false");
	});

	it("submits a valid link on Enter", async () => {
		await renderPage();
		const input = screen.getByPlaceholderText(t("media.sourcePlaceholder"));
		fireEvent.change(input, { target: { value: "https://example.com/a.mp4" } });
		fireEvent.keyDown(input, { key: "Enter" });
		await waitFor(() =>
			expect(
				callMock.mock.calls.filter(([cmd]) => cmd === "media_transcribe_start"),
			).toHaveLength(1),
		);
	});
});

describe("Media running + result states", () => {
	it("disables the field while running and shows the step with elapsed time", async () => {
		await renderPage();
		const input = screen.getByPlaceholderText(
			t("media.sourcePlaceholder"),
		) as HTMLInputElement;
		fireEvent.change(input, { target: { value: "https://example.com/a.mp4" } });
		fireEvent.click(screen.getByRole("button", { name: t("media.start") }));
		await waitFor(() => expect(input.disabled).toBe(true));
		const zone = screen.getByRole("button", { name: t("media.dropZoneAria") });
		expect(zone.getAttribute("aria-disabled")).toBe("true");
		expect(screen.getByText(/Elapsed 00:00/)).toBeTruthy();

		act(() => {
			handlers.get("media_transcribe_progress")?.({
				job_id: "job-1",
				phase: "downloading",
				progress: 0.3,
			});
		});
		await waitFor(() =>
			expect(screen.getByText(t("media.phaseDownloading"))).toBeTruthy(),
		);
	});

	it("renders word count, metadata, a placeholder tile and Open History", async () => {
		await renderPage();
		const input = screen.getByPlaceholderText(t("media.sourcePlaceholder"));
		fireEvent.change(input, {
			target: { value: "https://youtube.com/watch?v=abc" },
		});
		fireEvent.click(screen.getByRole("button", { name: t("media.start") }));
		await waitFor(() =>
			expect(handlers.has("media_transcribe_complete")).toBe(true),
		);

		act(() => {
			handlers.get("media_transcribe_complete")?.({
				job_id: "job-1",
				client_id: null,
				row_id: 42,
				chars: 415,
				word_count: 75,
				partial: false,
				tier: "download",
				quality: null,
				note: null,
				title:
					"A very long video title that should clamp to two lines in the result card",
				thumbnail_data_url: null,
				media_duration_seconds: 754,
				processing_seconds: 48,
				source_type: "youtube",
				model_name: "large-v3",
				method: "transcription",
			});
		});

		await waitFor(() =>
			expect(screen.getByText("75 words added to your History")).toBeTruthy(),
		);
		expect(screen.getByTestId("media-preview-placeholder")).toBeTruthy();
		const meta = screen.getByText(/12:34/);
		expect(meta.textContent).toContain("48s");
		expect(meta.textContent).toContain("YouTube");
		expect(meta.textContent).toContain("large-v3");
		expect(meta.textContent).toContain(t("media.metaTranscription"));

		fireEvent.click(
			screen.getByRole("button", { name: t("media.openHistory") }),
		);
		expect(sessionStorage.getItem("lausu.history.highlight")).toBe("42");
	});
});
