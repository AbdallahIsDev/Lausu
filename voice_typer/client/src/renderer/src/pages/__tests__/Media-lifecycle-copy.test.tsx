// Media lifecycle copy (ADR-0023 addendum): what the row SAYS about a job.
//
// Three shipped defects are pinned here:
//  * the row labelled every pre-transcribe stage "Loading model…", so a job
//    that reused an already-loaded engine looked like a mysterious load;
//  * a job that fell back to streaming looked identical to a clean run;
//  * a job that transcribed nothing showed "0 characters were added", which
//    reads as a silent success.

import { act, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/__tests__/helpers/render";
import { t } from "@/i18n/i18n";

const callMock = vi.fn();
const toastError = vi.fn();
const toastWarning = vi.fn();

type Handler = (data: never) => void;
const eventHandlers = new Map<string, Handler>();

vi.mock("sonner", () => ({
	toast: { error: toastError, warning: toastWarning, success: vi.fn() },
}));

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: callMock }),
	usePythonEvent: (name: string, handler: Handler) => {
		eventHandlers.set(name, handler);
	},
}));

afterEach(() => {
	cleanup();
});

beforeEach(() => {
	callMock.mockReset();
	toastError.mockReset();
	toastWarning.mockReset();
	eventHandlers.clear();
	callMock.mockImplementation((cmd: string, args?: { client_id?: string }) => {
		if (cmd === "media_transcribe_status") {
			return Promise.resolve({ jobs: [], max_jobs: 4 });
		}
		if (cmd === "media_transcribe_start") {
			return Promise.resolve({
				job_id: "job-1",
				client_id: args?.client_id ?? null,
			});
		}
		return Promise.resolve({});
	});
});

async function startOneJob() {
	const { default: MediaPage } = await import("@/pages/Media");
	const view = renderWithProviders(<MediaPage />);
	fireEvent.change(view.getByPlaceholderText(/example\.com/), {
		target: { value: "https://example.com/v" },
	});
	fireEvent.click(view.getByRole("button", { name: /transcribe/i }));
	await waitFor(() => {
		if (!view.container.querySelector('[role="progressbar"]')) {
			throw new Error("job row not rendered yet");
		}
	});
	return view;
}

function pushProgress(data: Record<string, unknown>) {
	act(() => {
		eventHandlers.get("media_transcribe_progress")?.({
			job_id: "job-1",
			client_id: null,
			progress: 0.1,
			eta_seconds: null,
			duration_seconds: 30,
			tier: null,
			note: null,
			...data,
		} as never);
	});
}

function pushComplete(data: Record<string, unknown>) {
	act(() => {
		eventHandlers.get("media_transcribe_complete")?.({
			job_id: "job-1",
			client_id: null,
			row_id: 7,
			chars: 12,
			partial: false,
			tier: "download",
			quality: null,
			note: null,
			...data,
		} as never);
	});
}

describe("media row phase copy", () => {
	it("renders 'Preparing' for a fresh job, never 'Loading model'", async () => {
		const { container } = await startOneJob();
		const row = container.querySelector('[role="progressbar"]')?.parentElement;
		expect(row?.textContent).toContain("Preparing");
		expect(row?.textContent).not.toContain("Loading model");
	});

	it("keeps 'Preparing' during the download and names the download as detail", async () => {
		const { container, getByTestId } = await startOneJob();
		pushProgress({ phase: "downloading", progress: 0.3 });
		const row = await waitFor(() => {
			const el = container.querySelector('[role="progressbar"]')?.parentElement;
			if (!el) throw new Error("row gone");
			return el;
		});
		expect(row.textContent).toContain("Preparing");
		expect(row.textContent).not.toContain("Loading model");
		expect(getByTestId("media-phase-detail").textContent).toContain(
			"Downloading audio",
		);
	});

	it("switches to 'Transcribing' only after the first window", async () => {
		const { container } = await startOneJob();
		pushProgress({ phase: "transcribing", progress: 0.55 });
		const row = await waitFor(() => {
			const el = container.querySelector('[role="progressbar"]')?.parentElement;
			if (!el) throw new Error("row gone");
			return el;
		});
		expect(row.textContent).toContain("Transcribing");
		expect(row.textContent).not.toContain("Preparing");
	});
});

describe("media row outcome copy", () => {
	it("shows the degraded stream note on a job that fell back to streaming", async () => {
		const { getByTestId, queryByTestId } = await startOneJob();
		expect(queryByTestId("media-stream-fallback-note")).toBeNull();
		pushComplete({ tier: "stream", note: "stream_fallback" });
		const note = await waitFor(() => getByTestId("media-stream-fallback-note"));
		expect(note.textContent).toContain("download failed");
	});

	it("reads as 'no speech' (not a success) when nothing was transcribed", async () => {
		const { getByText, queryByRole } = await startOneJob();
		pushComplete({ chars: 0, row_id: null });
		await waitFor(() => {
			if (!getByText(/No speech/i))
				throw new Error("outcome copy not rendered");
		});
		// Nothing was persisted, so there is no History to open.
		expect(queryByRole("button", { name: /open history/i })).toBeNull();
	});

	it("tags a low-confidence result without hiding the row", async () => {
		const { getByTestId } = await startOneJob();
		pushComplete({ quality: { avg_logprob: -1.4, no_speech_prob: 0.1 } });
		const tag = await waitFor(() => getByTestId("media-low-confidence"));
		expect(tag.textContent).toContain("Low confidence");
	});

	it("does not tag a confident result", async () => {
		const { queryByTestId } = await startOneJob();
		pushComplete({ quality: { avg_logprob: -0.2, no_speech_prob: 0.05 } });
		await waitFor(() => {
			if (
				!queryByTestId("media-low-confidence") &&
				!document.body.textContent
			) {
				throw new Error("row not settled");
			}
		});
		expect(queryByTestId("media-low-confidence")).toBeNull();
	});
});

describe("media model-switch refusal", () => {
	it("registers the refusal push and names the count that still holds the model", async () => {
		await startOneJob();
		const handler = eventHandlers.get("media_model_switch_refused");
		expect(handler).toBeTypeOf("function");
		act(() => {
			handler?.({ count: 2 } as never);
		});
		expect(toastWarning).toHaveBeenCalledTimes(1);
		const [, options] = toastWarning.mock.calls[0] as [
			string,
			{ id: string; description: string },
		];
		expect(options.id).toBe("media-model-switch-refused");
		expect(options.description).toContain("2 transcriptions");
		expect(options.description).toContain("current model");
	});
});

describe("media error copy", () => {
	it("names the item count for a multi-item link", async () => {
		await startOneJob();
		act(() => {
			eventHandlers.get("media_transcribe_error")?.({
				job_id: "job-1",
				client_id: null,
				code: "multi_item_url",
				message: "this link contains 3 videos; paste them one at a time",
				details: { count: 3 },
			} as never);
		});
		await waitFor(() => {
			if (toastError.mock.calls.length === 0) throw new Error("no toast yet");
		});
		const [, options] = toastError.mock.calls[0] as [
			string,
			{ description: string },
		];
		expect(options.description).toContain("3 videos");
	});

	it("keeps the failing URL out of the toast", async () => {
		await startOneJob();
		act(() => {
			eventHandlers.get("media_transcribe_error")?.({
				job_id: "job-1",
				client_id: null,
				code: "no_media_url",
				message:
					"Unsupported URL: https://openrouter.ai/activity?from=2026-10-29&to=2026-10-30",
				details: null,
			} as never);
		});
		await waitFor(() => {
			if (toastError.mock.calls.length === 0) throw new Error("no toast yet");
		});
		const [, options] = toastError.mock.calls[0] as [
			string,
			{ description: string },
		];
		// The reason copy names the subject itself, so the link contributes
		// no prefix: a long URL must never render inside a small toast.
		expect(options.description).toBe(t("media.errorNoMedia"));
		expect(options.description).not.toContain("http");
	});

	it("reports a still-loading model as retryable, not as 'choose a model'", async () => {
		await startOneJob();
		act(() => {
			eventHandlers.get("media_transcribe_error")?.({
				job_id: "job-1",
				client_id: null,
				code: "model_loading",
				message: "the speech model is still loading",
				details: null,
			} as never);
		});
		await waitFor(() => {
			if (toastError.mock.calls.length === 0) throw new Error("no toast yet");
		});
		const [title, options] = toastError.mock.calls[0] as [
			string,
			{ description: string },
		];
		expect(options.description).toContain("still loading");
		// The "Open Models" affordance belongs to server.no_model only.
		expect(title).not.toContain("model");
		expect(options.description).not.toContain("Open Models");
	});
});
