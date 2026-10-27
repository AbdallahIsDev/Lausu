// The Media page's "Browse files" must hand the backend an ABSOLUTE path.
// A webview `<input type="file">` exposes only `file.name`, so the sidecar
// received a bare filename and reported `decode_failed` ("The media could
// not be decoded") for a perfectly good file (owner report 2026-10-27).

import { cleanup, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/__tests__/helpers/render";

const callMock = vi.fn();
const pickMediaFile = vi.fn();

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: callMock }),
	usePythonEvent: () => {},
}));

afterEach(() => {
	cleanup();
});

beforeEach(() => {
	callMock.mockReset();
	pickMediaFile.mockReset();
	callMock.mockImplementation((cmd: string) =>
		cmd === "media_transcribe_status"
			? Promise.resolve({ job: null })
			: Promise.resolve({}),
	);
	(window as unknown as Record<string, unknown>).window_ = { pickMediaFile };
});

describe("Media page file picker", () => {
	it("stores the host-picked absolute path and starts the job with it", async () => {
		const path =
			"C:\\Users\\me\\Downloads\\How To Build a Clean Gaming Laptop Setup_(MP3_160K).mp3";
		pickMediaFile.mockResolvedValue({ canceled: false, path });

		const { default: MediaPage } = await import("@/pages/Media");
		const { getByPlaceholderText, getByRole, getByText } = renderWithProviders(
			<MediaPage />,
		);

		fireEvent.click(getByText(/browse/i).closest("button") as HTMLElement);
		await waitFor(() => {
			const field = getByPlaceholderText(/example\.com/) as HTMLInputElement;
			expect(field.value).toBe(path);
		});
		expect(pickMediaFile).toHaveBeenCalledTimes(1);

		fireEvent.click(getByRole("button", { name: /transcribe/i }));
		await waitFor(() => {
			const startCall = callMock.mock.calls.find(
				([cmd]) => cmd === "media_transcribe_start",
			);
			expect(startCall?.[1]).toMatchObject({ source: path });
		});
	});

	it("leaves the source untouched when the picker is canceled", async () => {
		pickMediaFile.mockResolvedValue({ canceled: true });

		const { default: MediaPage } = await import("@/pages/Media");
		const { getByPlaceholderText, getByText } = renderWithProviders(
			<MediaPage />,
		);

		fireEvent.click(getByText(/browse/i).closest("button") as HTMLElement);
		await waitFor(() => expect(pickMediaFile).toHaveBeenCalled());
		const field = getByPlaceholderText(/example\.com/) as HTMLInputElement;
		expect(field.value).toBe("");
	});
});
