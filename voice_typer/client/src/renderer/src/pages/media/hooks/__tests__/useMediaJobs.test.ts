// useMediaJobs lifecycle: several concurrent jobs, start ack / consent-gate
// retry / error mapping / push-event routing BY JOB ID / status hydration /
// capacity gating / per-job cancel (ADR-0023).

import { act, renderHook, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/i18n";
import { useConsentGateStore } from "@/lib/consentGate";
import { type UseMediaJobsResult, useMediaJobs } from "../useMediaJobs";

const registered = new Map<string, (data?: unknown) => unknown>();
const callMock = vi.fn();

vi.mock("sonner", () => ({
	toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}));

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: callMock }),
	usePythonEvent: (type: string, handler: (data?: unknown) => unknown) => {
		registered.set(type, handler);
	},
}));

function fire(type: string, data?: unknown): void {
	const handler = registered.get(type);
	if (!handler) throw new Error(`${type} handler not registered`);
	act(() => {
		handler(data);
	});
}

/** Start one source and wait for its ack to land on the row. */
async function actStart(
	result: { current: UseMediaJobsResult },
	source = "https://example.com/v",
	jobId = "j1",
): Promise<void> {
	callMock.mockImplementation((cmd: string) => {
		if (cmd === "media_transcribe_status") {
			return Promise.resolve({ jobs: [], max_jobs: 4 });
		}
		return Promise.resolve({ job_id: jobId, status: "running" });
	});
	await act(async () => {
		await result.current.start(source, false);
	});
	await waitFor(() =>
		expect(result.current.jobs.some((row) => row.jobId === jobId)).toBe(true),
	);
}

beforeEach(() => {
	registered.clear();
	vi.clearAllMocks();
	useConsentGateStore.setState({ request: null });
	// Default: status probe sees an idle backend; start acks cleanly.
	callMock.mockImplementation((cmd: string) => {
		if (cmd === "media_transcribe_status") {
			return Promise.resolve({ jobs: [], max_jobs: 4 });
		}
		return Promise.resolve({ job_id: "j1", status: "running" });
	});
});

describe("useMediaJobs", () => {
	it("registers handlers for the three media push events", () => {
		renderHook(() => useMediaJobs());
		expect(registered.has("media_transcribe_progress")).toBe(true);
		expect(registered.has("media_transcribe_complete")).toBe(true);
		expect(registered.has("media_transcribe_error")).toBe(true);
	});

	it("acks a start into one row and counts it against the cap", async () => {
		const { result } = renderHook(() => useMediaJobs());
		await actStart(result);
		expect(result.current.jobs).toHaveLength(1);
		expect(result.current.jobs[0]?.jobId).toBe("j1");
		expect(result.current.activeCount).toBe(1);
		expect(result.current.atCapacity).toBe(false);
		expect(callMock).toHaveBeenCalledWith("media_transcribe_start", {
			source: "https://example.com/v",
			use_subtitles: false,
		});
	});

	it("runs several jobs at once and routes each push by job id", async () => {
		const { result } = renderHook(() => useMediaJobs());
		await actStart(result, "https://example.com/a", "j1");
		await actStart(result, "C:\\media\\b.mp4", "j2");
		expect(result.current.jobs.map((row) => row.jobId)).toEqual(["j1", "j2"]);
		expect(result.current.activeCount).toBe(2);

		fire("media_transcribe_progress", {
			job_id: "j2",
			progress: 0.5,
			phase: "downloading",
			eta_seconds: 30,
			duration_seconds: 120,
		});
		const rows = result.current.jobs;
		expect(rows.find((row) => row.jobId === "j1")?.phase).toBe("starting");
		const second = rows.find((row) => row.jobId === "j2");
		expect(second?.phase).toBe("downloading");
		expect(second?.progress).toBe(0.5);
		expect(second?.etaSeconds).toBe(30);

		fire("media_transcribe_complete", {
			job_id: "j2",
			row_id: 7,
			chars: 99,
			partial: false,
		});
		const after = result.current.jobs;
		expect(after.find((row) => row.jobId === "j2")?.phase).toBe("done");
		expect(after.find((row) => row.jobId === "j1")?.phase).toBe("starting");
		// A finished job frees its slot immediately.
		expect(result.current.activeCount).toBe(1);
	});

	it("refuses to enqueue the same source twice while it runs", async () => {
		const { result } = renderHook(() => useMediaJobs());
		await actStart(result);
		callMock.mockClear();
		await act(async () => {
			await result.current.start("https://example.com/v", false);
		});
		expect(
			callMock.mock.calls.filter(([cmd]) => cmd === "media_transcribe_start"),
		).toHaveLength(0);
		expect(result.current.jobs).toHaveLength(1);
		expect(toast.info).toHaveBeenCalledWith(
			t("media.duplicateTitle"),
			expect.objectContaining({ description: t("media.duplicateDescription") }),
		);
	});

	it("disables at the backend-reported cap and re-enables when a slot frees", async () => {
		callMock.mockImplementation((cmd: string) => {
			if (cmd === "media_transcribe_status") {
				return Promise.resolve({ jobs: [], max_jobs: 2 });
			}
			return Promise.resolve({ job_id: `job-${callMock.mock.calls.length}` });
		});
		const { result } = renderHook(() => useMediaJobs());
		await waitFor(() => expect(result.current.maxJobs).toBe(2));
		await act(async () => {
			await result.current.startMany(["a.mp3", "b.mp4"], false);
		});
		expect(result.current.activeCount).toBe(2);
		expect(result.current.atCapacity).toBe(true);

		const first = result.current.jobs[0];
		fire("media_transcribe_complete", {
			job_id: first?.jobId,
			row_id: 1,
			chars: 5,
			partial: false,
		});
		expect(result.current.atCapacity).toBe(false);
	});

	it("opens the consent gate on client.consent_required and Allow retries", async () => {
		callMock.mockImplementation((cmd: string) => {
			if (cmd === "media_transcribe_status")
				return Promise.resolve({ jobs: [], max_jobs: 4 });
			const err = new Error("consent required") as Error & {
				code?: string;
				consent_field?: string;
			};
			err.code = "client.consent_required";
			err.consent_field = "media_url_consent";
			return Promise.reject(err);
		});
		const { result } = renderHook(() => useMediaJobs());
		await result.current.start("https://example.com/v", true);

		const req = useConsentGateStore.getState().request;
		expect(req).toEqual(
			expect.objectContaining({
				consentField: "media_url_consent",
				bodyKey: "consentDialog.field.media_url_consent",
				onAllow: expect.any(Function),
			}),
		);
		// A refused start leaves no ghost row behind.
		expect(result.current.jobs).toHaveLength(0);

		callMock.mockImplementation((cmd: string) =>
			cmd === "media_transcribe_status"
				? Promise.resolve({ jobs: [], max_jobs: 4 })
				: Promise.resolve({ job_id: "j1" }),
		);
		await req?.onAllow?.();
		await waitFor(() => expect(result.current.jobs).toHaveLength(1));
		expect(callMock).toHaveBeenLastCalledWith("media_transcribe_start", {
			source: "https://example.com/v",
			use_subtitles: true,
		});
	});

	it("surfaces start-time server.no_model as a toast carrying the Open Models action", async () => {
		callMock.mockImplementation((cmd: string) => {
			if (cmd === "media_transcribe_status")
				return Promise.resolve({ jobs: [], max_jobs: 4 });
			const err = new Error("no model") as Error & { code?: string };
			err.code = "server.no_model";
			return Promise.reject(err);
		});
		const { result } = renderHook(() => useMediaJobs());
		await act(async () => {
			await result.current.start("/tmp/clip.wav", false);
		});
		expect(result.current.jobs).toHaveLength(0);
		expect(toast.error).toHaveBeenCalledWith(
			t("media.errorTitle"),
			expect.objectContaining({
				description: expect.stringContaining(t("media.errorNoModel")),
				action: expect.objectContaining({ label: t("media.noModelAction") }),
			}),
		);
		// The affordance the inline card used to carry now lives on the toast.
		const calls = vi.mocked(toast.error).mock.calls;
		const options = calls[calls.length - 1]?.[1] as {
			action?: { onClick?: () => void };
		};
		act(() => {
			options.action?.onClick?.();
		});
		expect(localStorage.getItem("vt_nav_state")).toContain("models");
	});

	it("drops a failed job's row and names it in the toast", async () => {
		const { result } = renderHook(() => useMediaJobs());
		await actStart(result, "C:\\media\\broken.mp4", "j4");
		fire("media_transcribe_error", {
			job_id: "j4",
			code: "drm_refused",
			message: "DRM content refused",
		});
		expect(result.current.jobs).toHaveLength(0);
		// The raw backend message never reaches the UI surface, and with
		// several jobs in flight the toast says WHICH one failed.
		expect(toast.error).toHaveBeenCalledWith(
			t("media.errorTitle"),
			expect.objectContaining({
				description: `C:\\media\\broken.mp4 — ${t("media.errorDrm")}`,
			}),
		);
		const calls = vi.mocked(toast.error).mock.calls;
		const options = calls[calls.length - 1]?.[1] as { action?: unknown };
		expect(options.action).toBeUndefined();
	});

	it("hydrates every running job plus the cap after navigation", async () => {
		callMock.mockImplementation((cmd: string) =>
			cmd === "media_transcribe_status"
				? Promise.resolve({
						jobs: [
							{
								job_id: "j9",
								source: "a.mp3",
								status: "running",
								progress: 0.4,
							},
							{
								job_id: "j10",
								source: "b.mp4",
								status: "running",
								progress: 0.1,
							},
						],
						max_jobs: 3,
					})
				: Promise.resolve({}),
		);
		const { result } = renderHook(() => useMediaJobs());
		await waitFor(() => expect(result.current.jobs).toHaveLength(2));
		expect(result.current.maxJobs).toBe(3);
		expect(result.current.jobs.map((row) => row.jobId)).toEqual(["j9", "j10"]);
		expect(result.current.jobs[0]?.progress).toBe(0.4);
		expect(result.current.jobs[0]?.source).toBe("a.mp3");
	});

	it("cancels one job by id, or all of them", async () => {
		const { result } = renderHook(() => useMediaJobs());
		await actStart(result, "a.mp3", "j1");
		await actStart(result, "b.mp4", "j2");
		await result.current.cancel("j2");
		expect(callMock).toHaveBeenCalledWith("media_transcribe_cancel", {
			job_id: "j2",
		});
		await result.current.cancelAll();
		expect(callMock).toHaveBeenLastCalledWith("media_transcribe_cancel");
	});

	it("clearFinished keeps only the jobs that are still running", async () => {
		const { result } = renderHook(() => useMediaJobs());
		await actStart(result, "a.mp3", "j1");
		await actStart(result, "b.mp4", "j2");
		fire("media_transcribe_complete", {
			job_id: "j1",
			row_id: 3,
			chars: 10,
			partial: false,
		});
		act(() => {
			result.current.clearFinished();
		});
		expect(result.current.jobs.map((row) => row.jobId)).toEqual(["j2"]);
	});
});
