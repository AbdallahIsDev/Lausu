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
		const { container, getByPlaceholderText, getByRole, getByTestId } =
			renderWithProviders(<MediaPage />);

		fireEvent.change(getByPlaceholderText(/example\.com/), {
			target: { value: "https://example.com/v" },
		});
		fireEvent.click(getByRole("button", { name: /transcribe/i }));

		const bar = await waitFor(() => {
			const el = container.querySelector('[role="progressbar"]');
			if (!el) throw new Error("progressbar not rendered yet");
			return el as HTMLElement;
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

		// Percent is the ONLY readout above the bar.
		const percent = getByTestId("media-progress-percent");
		expect(percent.textContent).toBe("12%");
		expect(
			percent.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING,
		).toBeTruthy();

		// Left + duration read below the bar.
		const meta = getByTestId("media-progress-meta");
		expect(meta.textContent).toMatch(/08:11 left/);
		expect(meta.textContent).toContain("Duration");
		expect(meta.textContent).toContain("17:03");
		expect(
			meta.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_PRECEDING,
		).toBeTruthy();
	});
});
