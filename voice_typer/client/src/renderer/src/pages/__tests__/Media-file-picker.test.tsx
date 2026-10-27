// The Media page's "Browse files" must hand the backend ABSOLUTE paths.
// A webview `<input type="file">` exposes only `file.name`, so the sidecar
// received a bare filename and reported `decode_failed` ("The media could
// not be decoded") for a perfectly good file (owner report 2026-10-27).
//
// Multi-select + capacity are pinned here too: one picker pass can enqueue
// several files (audio and video mixed), and at the backend's cap the drop
// zone and the link field are disabled so nothing else can be enqueued.

import { cleanup, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/__tests__/helpers/render";

const callMock = vi.fn();
const pickMediaFiles = vi.fn();

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: callMock }),
	usePythonEvent: () => {},
}));

afterEach(() => {
	cleanup();
});

beforeEach(() => {
	callMock.mockReset();
	pickMediaFiles.mockReset();
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
	(window as unknown as Record<string, unknown>).window_ = { pickMediaFiles };
});

describe("Media page file picker", () => {
	it("enqueues every picked path (audio and video) and leaves the link field empty", async () => {
		const audio =
			"C:\\Users\\me\\Downloads\\How To Build a Clean Gaming Laptop Setup_(MP3_160K).mp3";
		const video =
			"C:\\Users\\me\\Downloads\\How To Build a Clean Gaming Laptop Setup.mp4";
		pickMediaFiles.mockResolvedValue({
			canceled: false,
			paths: [audio, video],
		});

		const { default: MediaPage } = await import("@/pages/Media");
		const { getAllByText, getByPlaceholderText, getByText } =
			renderWithProviders(<MediaPage />);

		fireEvent.click(getByText(/browse/i).closest("button") as HTMLElement);
		await waitFor(() => {
			const starts = callMock.mock.calls.filter(
				([cmd]) => cmd === "media_transcribe_start",
			);
			expect(
				starts.map(([, data]) => (data as { source: string }).source),
			).toEqual([audio, video]);
		});
		expect(pickMediaFiles).toHaveBeenCalledTimes(1);
		// Both files have their own row…
		expect(getAllByText(/Gaming Laptop Setup/)).toHaveLength(2);
		// …and the field stays empty, so Transcribe cannot re-submit either.
		const field = getByPlaceholderText(/example\.com/) as HTMLInputElement;
		expect(field.value).toBe("");
	});

	it("leaves the source untouched when the picker is canceled", async () => {
		pickMediaFiles.mockResolvedValue({ canceled: true, paths: [] });

		const { default: MediaPage } = await import("@/pages/Media");
		const { getByPlaceholderText, getByText } = renderWithProviders(
			<MediaPage />,
		);

		fireEvent.click(getByText(/browse/i).closest("button") as HTMLElement);
		await waitFor(() => expect(pickMediaFiles).toHaveBeenCalled());
		const field = getByPlaceholderText(/example\.com/) as HTMLInputElement;
		expect(field.value).toBe("");
		expect(
			callMock.mock.calls.filter(([cmd]) => cmd === "media_transcribe_start"),
		).toHaveLength(0);
	});

	it("clears the link field once the pasted link is accepted", async () => {
		const { default: MediaPage } = await import("@/pages/Media");
		const { getByPlaceholderText, getByRole } = renderWithProviders(
			<MediaPage />,
		);

		const field = getByPlaceholderText(/example\.com/) as HTMLInputElement;
		fireEvent.change(field, { target: { value: "https://example.com/v" } });
		fireEvent.click(getByRole("button", { name: /transcribe/i }));

		await waitFor(() => expect(field.value).toBe(""));
		expect(getByRole("button", { name: /transcribe/i })).toBeDisabled();
	});

	it("disables the drop zone and the link field at the backend cap", async () => {
		callMock.mockImplementation((cmd: string) => {
			if (cmd === "media_transcribe_status") {
				return Promise.resolve({
					jobs: [
						{ job_id: "j1", source: "a.mp3", status: "running", progress: 0.2 },
					],
					max_jobs: 1,
				});
			}
			return Promise.resolve({});
		});

		const { default: MediaPage } = await import("@/pages/Media");
		const { getByPlaceholderText, getByRole, getByTestId, getByText } =
			renderWithProviders(<MediaPage />);

		await waitFor(() => expect(getByTestId("media-capacity")).toBeTruthy());
		expect(getByPlaceholderText(/example\.com/)).toBeDisabled();
		expect(getByText(/browse/i).closest("button")).toHaveAttribute(
			"aria-disabled",
			"true",
		);
		expect(getByRole("button", { name: /transcribe/i })).toBeDisabled();
	});
});
