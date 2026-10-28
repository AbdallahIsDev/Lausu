// The renderer mints a `client_id` per media job and the backend echoes it
// on every push for that job, so a token names exactly one row.
//
// A module-level counter cannot promise that. After a reload — or any second
// evaluation of the hook module — the counter restarts at 0 while the job the
// PREVIOUS instance started is still running and still owns `media-row-1`;
// its progress would land on the new instance's first row, and the real row
// would sit in `starting` forever. The fix is a random prefix per instance.
//
// This lives in its own file because `isolate: true` gives every test FILE a
// fresh module registry, so the collision probe needs `vi.resetModules()`
// between two dynamic imports — a pattern that would otherwise leak into
// sibling tests in the same file.

import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const callMock = vi.fn();

vi.mock("sonner", () => ({
	toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}));

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: callMock }),
	usePythonEvent: () => {},
}));

/** Load a fresh copy of the hook module and return the client token its
 *  first `start` hands the backend. */
async function mintFromFreshInstance(): Promise<string> {
	callMock.mockImplementation((cmd: string) => {
		if (cmd === "media_transcribe_status") {
			return Promise.resolve({ jobs: [], max_jobs: 4 });
		}
		return Promise.resolve({ job_id: "job-1", status: "running" });
	});
	const { useMediaJobs } = await import("@/pages/media/hooks/useMediaJobs");
	const { result } = renderHook(() => useMediaJobs());
	await act(async () => {
		await result.current.start("https://example.com/a", false);
	});
	const sent = callMock.mock.calls
		.filter(([cmd]) => cmd === "media_transcribe_start")
		.map(([, data]) => (data as { client_id: string }).client_id);
	cleanup();
	callMock.mockClear();
	const [clientId] = sent;
	if (!clientId) throw new Error("media_transcribe_start was never called");
	return clientId;
}

beforeEach(() => {
	vi.resetModules();
});

afterEach(() => {
	cleanup();
	vi.resetModules();
});

describe("media job client tokens", () => {
	it("never reuses a token across two module instances", async () => {
		const first = await mintFromFreshInstance();
		vi.resetModules();
		const second = await mintFromFreshInstance();

		expect(first).toMatch(/^media-row-/);
		expect(second).toMatch(/^media-row-/);
		expect(second).not.toBe(first);
	});
});
