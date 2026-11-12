// Media progress layout (owner request 2026-10-27): the percentage is the
// only readout above the bar; remaining time + total length read below it.
// Order is pinned with compareDocumentPosition (class-only assertions pass
// through layout changes).

import { act, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/__tests__/helpers/render";

const callMock = vi.fn();
type Handler = (data: unknown) => void;
const eventHandlers = new Map<string, Handler>();

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
	eventHandlers.clear();
	// The ack MUST carry a job_id: a start that comes back without one is a
	// backend that cannot address the job, and the page drops the row rather
	// than leaving a "starting" ghost no event can ever finish.
	callMock.mockImplementation((cmd: string, args?: { client_id?: string }) => {
		if (cmd === "media_transcribe_status") {
			return Promise.resolve({ job: null });
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

describe("Media page progress layout", () => {
	it("keeps only the percent above the bar, left/duration below it", async () => {
		const { default: MediaPage } = await import("@/pages/Media");
		const { container, getByPlaceholderText, getByRole } = renderWithProviders(
			<MediaPage />,
		);

		fireEvent.change(getByPlaceholderText(/example\.com/), {
			target: { value: "https://example.com/v" },
		});
		fireEvent.click(getByRole("button", { name: /transcribe/i }));
		// Let the start ack add the job row; the progress push below only
		// reaches a row that already exists.
		await waitFor(() => {
			if (!container.querySelector('[role="progressbar"]')) {
				throw new Error("job row not rendered yet");
			}
		});

		act(() => {
			eventHandlers.get("media_transcribe_progress")?.({
				phase: "transcribing",
				progress: 0.12,
				eta_seconds: 491,
				duration_seconds: 1023,
				job_id: "job-1",
			});
		});

		// The row that received the progress event: its percent reads 12%
		// (the skeleton sample has its own value), so this is the live row
		// even while skullet still marks the reveal pane inert.
		const percent = await waitFor(() => {
			const el = Array.from(
				container.querySelectorAll<HTMLElement>(
					'[data-testid="media-progress-percent"]',
				),
			).find((node) => node.textContent === "12%");
			if (!el) throw new Error("progress row not rendered yet");
			return el;
		});
		// The row container is the nearest ancestor that also holds the bar.
		let row = percent.parentElement;
		while (row && !row.querySelector('[role="progressbar"]')) {
			row = row.parentElement;
		}
		if (!row) throw new Error("progress row container not found");
		const bar = row.querySelector<HTMLElement>('[role="progressbar"]');
		if (!bar) throw new Error("progress bar not rendered");
		const meta = row.querySelector<HTMLElement>(
			'[data-testid="media-progress-meta"]',
		);
		if (!meta) throw new Error("progress meta not rendered");
		expect(percent.textContent).toBe("12%");
		expect(
			percent.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING,
		).toBeTruthy();
		expect(meta.textContent).toMatch(/08:11 left/);
		expect(meta.textContent).toContain("Duration");
		expect(meta.textContent).toContain("17:03");
		expect(
			meta.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_PRECEDING,
		).toBeTruthy();
	});

	// Owner decision 2026-10-28: the slots counter and its "Clear finished"
	// action are gone for good. A finished row carries its own Dismiss, so the
	// page needs no bulk clear and no capacity readout above the queue.
	it("renders no slot counter and no clear-finished action", async () => {
		const { default: MediaPage } = await import("@/pages/Media");
		const {
			container,
			getByPlaceholderText,
			getByRole,
			queryByRole,
			queryByTestId,
		} = renderWithProviders(<MediaPage />);

		fireEvent.change(getByPlaceholderText(/example\.com/), {
			target: { value: "https://example.com/v" },
		});
		fireEvent.click(getByRole("button", { name: /transcribe/i }));

		await waitFor(() => {
			if (!container.querySelector('[role="progressbar"]')) {
				throw new Error("job row not rendered yet");
			}
		});

		act(() => {
			eventHandlers.get("media_transcribe_complete")?.({
				job_id: "job-1",
				client_id: null,
				row_id: 3,
				chars: 10,
				partial: false,
			});
		});

		await waitFor(() => {
			if (!queryByRole("button", { name: /dismiss/i })) {
				throw new Error("completed row not rendered yet");
			}
		});

		expect(queryByTestId("media-slots")).toBeNull();
		expect(queryByRole("button", { name: /clear finished/i })).toBeNull();
		// The completed row still owns its own Dismiss action.
		expect(getByRole("button", { name: /dismiss/i })).toBeTruthy();
	});
});
