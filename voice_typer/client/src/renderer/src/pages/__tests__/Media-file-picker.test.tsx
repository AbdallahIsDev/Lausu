// The Media page's "Browse files" must hand the backend ABSOLUTE paths.
// A webview `<input type="file">` exposes only `file.name`, so the sidecar
// received a bare filename and reported `decode_failed` ("The media could
// not be decoded") for a perfectly good file (owner report 2026-10-27).
//
// Multi-select + capacity are pinned here too: one picker pass can enqueue
// several files (audio and video mixed), and at the backend's cap the drop
// zone and the link field are disabled so nothing else can be enqueued.

import { act, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/__tests__/helpers/render";
import { t } from "@/i18n/i18n";

const callMock = vi.fn();
const pickMediaFiles = vi.fn();

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: callMock }),
	usePythonEvent: () => {},
}));

vi.mock("sonner", () => ({
	toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
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

	it("starts ONE job per pasted link and clears the field", async () => {
		const { default: MediaPage } = await import("@/pages/Media");
		const { getAllByText, getByPlaceholderText } = renderWithProviders(
			<MediaPage />,
		);

		const field = getByPlaceholderText(/example\.com/) as HTMLInputElement;
		// A single-line <input> strips newlines, so the page reads the
		// clipboard payload itself — a one-link-per-line paste is the normal
		// case and must not arrive glued into one bogus URL.
		fireEvent.paste(field, {
			clipboardData: {
				getData: () =>
					"https://www.youtube.com/watch?v=aaa\nhttps://vimeo.com/222",
			},
		});

		await waitFor(() => {
			const starts = callMock.mock.calls.filter(
				([cmd]) => cmd === "media_transcribe_start",
			);
			expect(
				starts.map(([, data]) => (data as { source: string }).source),
			).toEqual([
				"https://www.youtube.com/watch?v=aaa",
				"https://vimeo.com/222",
			]);
		});
		// Two rows, and the field is empty so nothing can be re-submitted.
		expect(getAllByText(/youtube\.com|vimeo\.com/)).toHaveLength(2);
		expect(field.value).toBe("");
	});

	it("keeps the refused links as SEPARATE sources in the field", async () => {
		// Two slots, four pasted links: the two that did not fit must come
		// back as TWO sources. Joining them with "\n" put a string the field
		// sanitizes on write (a single-line <input> drops LF), so the next
		// split saw one glued token and the retry resolved a bogus URL.
		let accepted = 0;
		callMock.mockImplementation((cmd: string) => {
			if (cmd === "media_transcribe_status") {
				return Promise.resolve({ jobs: [], max_jobs: 2 });
			}
			if (cmd === "media_transcribe_start") {
				accepted += 1;
				return Promise.resolve({
					job_id: `job-${accepted}`,
					status: "running",
				});
			}
			return Promise.resolve({});
		});

		const { default: MediaPage } = await import("@/pages/Media");
		const { getByPlaceholderText } = renderWithProviders(<MediaPage />);

		// Let the mount-time status read land: the cap is what refuses the
		// overflow, and a paste before it arrives would see the default cap.
		await act(async () => {});
		const field = getByPlaceholderText(/example\.com/) as HTMLInputElement;
		fireEvent.paste(field, {
			clipboardData: {
				getData: () =>
					"https://e.com/a\nhttps://e.com/b\nhttps://e.com/c\nhttps://e.com/d",
			},
		});

		await waitFor(() => expect(field.value).toContain("e.com/c"));
		// The field is single-line, so a browser's value sanitization strips
		// LF on write. A test that only counts whitespace-separated tokens
		// cannot see that: jsdom KEEPS the "\n", so the old join still looked
		// like two sources here while a real browser glued the retry into one
		// bogus URL. Pin the contract that makes the difference: no line
		// breaks in the field, one space between the refused links.
		expect(field.value).not.toMatch(/[\r\n]/);
		expect(field.value.split(" ").filter(Boolean)).toEqual([
			"https://e.com/c",
			"https://e.com/d",
		]);
	});

	it("puts the pasted links back when nothing could be started", async () => {
		// The paste handler calls preventDefault (a multi-link paste is
		// submitted as a batch, never typed into the field), so a batch that
		// started NOTHING must restore the text by hand — otherwise the user
		// loses what they pasted and has to find it again.
		callMock.mockImplementation((cmd: string) => {
			if (cmd === "media_transcribe_status") {
				return Promise.resolve({ jobs: [], max_jobs: 4 });
			}
			if (cmd === "media_transcribe_start") {
				return Promise.reject(
					Object.assign(new Error("busy"), { code: "media.busy" }),
				);
			}
			return Promise.resolve({});
		});

		const { default: MediaPage } = await import("@/pages/Media");
		const { getByPlaceholderText } = renderWithProviders(<MediaPage />);

		const field = getByPlaceholderText(/example\.com/) as HTMLInputElement;
		fireEvent.paste(field, {
			clipboardData: {
				getData: () => "https://e.com/a\nhttps://e.com/b",
			},
		});

		await waitFor(() => expect(field.value).toContain("e.com/b"));
		// Same contract as the refused-links test: the restored text is two
		// space-separated sources, never an LF-joined string that a
		// single-line input collapses on write.
		expect(field.value).not.toMatch(/[\r\n]/);
		expect(field.value.split(" ").filter(Boolean)).toEqual([
			"https://e.com/a",
			"https://e.com/b",
		]);
	});

	it("leaves a single pasted link in the field to edit", async () => {
		const { default: MediaPage } = await import("@/pages/Media");
		const { getByPlaceholderText } = renderWithProviders(<MediaPage />);

		const field = getByPlaceholderText(/example\.com/) as HTMLInputElement;
		fireEvent.paste(field, {
			clipboardData: { getData: () => "https://example.com/one" },
		});
		expect(
			callMock.mock.calls.filter(([cmd]) => cmd === "media_transcribe_start"),
		).toHaveLength(0);
	});

	it("keeps a local path with spaces as a single source", async () => {
		const { default: MediaPage } = await import("@/pages/Media");
		const { getByPlaceholderText, getByRole } = renderWithProviders(
			<MediaPage />,
		);

		const path = "C:\\Users\\me\\My Videos\\How To Build a Setup.mp4";
		const field = getByPlaceholderText(/example\.com/) as HTMLInputElement;
		fireEvent.change(field, { target: { value: path } });
		fireEvent.click(getByRole("button", { name: /transcribe/i }));

		await waitFor(() => {
			const starts = callMock.mock.calls.filter(
				([cmd]) => cmd === "media_transcribe_start",
			);
			expect(starts).toHaveLength(1);
			const first = starts[0];
			if (!first) throw new Error("media_transcribe_start was never called");
			expect((first[1] as { source: string }).source).toBe(path);
		});
	});

	it("says file picking is unavailable instead of falling back to a web input", async () => {
		// A webview `<input type="file">` yields only `file.name`, which the
		// backend cannot open — that fallback WAS the decode_failed bug.
		(window as unknown as Record<string, unknown>).window_ = {};
		const { default: MediaPage } = await import("@/pages/Media");
		const { container, getByText } = renderWithProviders(<MediaPage />);

		fireEvent.click(getByText(/browse/i).closest("button") as HTMLElement);

		await waitFor(() => expect(toast.info).toHaveBeenCalled());
		expect(toast.info).toHaveBeenCalledWith(
			t("media.pickerUnavailable"),
			expect.objectContaining({ id: "media-picker-unavailable" }),
		);
		expect(container.querySelector('input[type="file"]')).toBeNull();
		expect(
			callMock.mock.calls.filter(([cmd]) => cmd === "media_transcribe_start"),
		).toHaveLength(0);
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
