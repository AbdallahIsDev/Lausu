// Media page progress bar reuse: the owner asked for the SAME bar the
// Microphone page uses (2026-10-27), so this pins the shared LevelBar
// markup instead of a bespoke progress div.

import { cleanup, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/__tests__/helpers/render";

const callMock = vi.fn();

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: callMock }),
	usePythonEvent: () => {},
}));

afterEach(() => {
	cleanup();
});

beforeEach(() => {
	callMock.mockReset();
	callMock.mockImplementation((cmd: string) =>
		cmd === "media_transcribe_status"
			? Promise.resolve({ job: null })
			: Promise.resolve({}),
	);
});

describe("Media page progress bar", () => {
	it("renders the shared LevelBar (mic-page bar) while a job runs", async () => {
		const { default: MediaPage } = await import("@/pages/Media");
		const { container, getByPlaceholderText, getByRole } = renderWithProviders(
			<MediaPage />,
		);

		fireEvent.change(getByPlaceholderText(/example\.com/), {
			target: { value: "https://example.com/v" },
		});
		fireEvent.click(getByRole("button", { name: /transcribe/i }));

		const bar = await waitFor(() => {
			const el = container.querySelector('[role="progressbar"]');
			if (!el) throw new Error("progressbar not rendered yet");
			return el as HTMLElement;
		});
		// LevelBar signature: neutral /10 track, transform-driven primary fill.
		expect(bar.className).toContain("bg-border/10");
		const fill = bar.firstElementChild as HTMLElement;
		expect(fill.className).toContain("bg-primary");
		expect(fill.style.transform).toMatch(/^scaleX\(/);
		// Loading state (no progress push yet) → a truly empty fill.
		expect(fill.style.transform).toBe("scaleX(0)");
	});
});
