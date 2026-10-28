// useMediaJobs lifecycle: several concurrent jobs, start ack / consent-gate
// retry / error mapping / push-event routing BY CLIENT TOKEN / status
// hydration / capacity-aware batches / per-job cancel (ADR-0023).
//
// The ownership tests are the regression pins for the "stuck row" class: a
// renderer that guesses which row an event belongs to either dropped events
// (rows pinned in `starting`, UI permanently at capacity) or bound a late
// event to an unrelated fresh row.

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

/** The client tokens the hook minted, in call order. */
function sentClientIds(): string[] {
	return callMock.mock.calls
		.filter(([cmd]) => cmd === "media_transcribe_start")
		.map(([, data]) => (data as { client_id: string }).client_id);
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
		// The start carries the renderer's own correlation token.
		expect(callMock).toHaveBeenCalledWith(
			"media_transcribe_start",
			expect.objectContaining({
				source: "https://example.com/v",
				use_subtitles: false,
				client_id: expect.any(String),
			}),
		);
		expect(result.current.jobs[0]?.clientId).toBe(sentClientIds()[0]);
	});

	it("runs several jobs at once and routes each push by job id", async () => {
		const { result } = renderHook(() => useMediaJobs());
		await actStart(result, "https://example.com/a", "j1");
		await actStart(result, "C:\\media\\b.mp4", "j2");
		expect(result.current.jobs.map((row) => row.jobId)).toEqual(["j1", "j2"]);
		expect(result.current.activeCount).toBe(2);

		fire("media_transcribe_progress", {
			job_id: "j2",
			client_id: null,
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
			client_id: null,
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

	it("routes two in-flight starts' pushes to the right rows by client token", async () => {
		// Both starts are in flight at once: neither row has a job id yet.
		const deferred: Array<(value: unknown) => void> = [];
		callMock.mockImplementation((cmd: string) => {
			if (cmd === "media_transcribe_status") {
				return Promise.resolve({ jobs: [], max_jobs: 4 });
			}
			return new Promise((resolve) => deferred.push(resolve));
		});
		const { result } = renderHook(() => useMediaJobs());

		act(() => {
			void result.current.start("https://example.com/a", false);
			void result.current.start("https://example.com/b", false);
		});
		await waitFor(() => expect(result.current.jobs).toHaveLength(2));
		expect(result.current.jobs.every((row) => row.jobId === "")).toBe(true);

		const [firstToken, secondToken] = sentClientIds();
		expect(firstToken).not.toBe(secondToken);

		// A progress push for each, keyed only by the client token: the
		// second one lands on the second row even though both are "waiting".
		fire("media_transcribe_progress", {
			job_id: "job-b",
			client_id: secondToken,
			progress: 0.25,
			phase: "transcribing",
			eta_seconds: null,
			duration_seconds: null,
		});
		fire("media_transcribe_progress", {
			job_id: "job-a",
			client_id: firstToken,
			progress: 0.75,
			phase: "downloading",
			eta_seconds: null,
			duration_seconds: null,
		});

		const rows = result.current.jobs;
		expect(rows[0]?.source).toBe("https://example.com/a");
		expect(rows[0]?.jobId).toBe("job-a");
		expect(rows[0]?.phase).toBe("downloading");
		expect(rows[0]?.progress).toBe(0.75);
		expect(rows[1]?.source).toBe("https://example.com/b");
		expect(rows[1]?.jobId).toBe("job-b");
		expect(rows[1]?.phase).toBe("transcribing");
		expect(rows[1]?.progress).toBe(0.25);

		// The acks now land on rows that already adopted the id — no dupes.
		act(() => {
			for (const resolve of deferred) {
				resolve({ job_id: "job-a", client_id: firstToken, status: "running" });
			}
		});
		expect(result.current.jobs).toHaveLength(2);
	});

	it("removes the row when an error push beats the start ack", async () => {
		let resolveStart: (value: unknown) => void = () => {};
		callMock.mockImplementation((cmd: string) => {
			if (cmd === "media_transcribe_status") {
				return Promise.resolve({ jobs: [], max_jobs: 4 });
			}
			return new Promise((resolve) => {
				resolveStart = resolve;
			});
		});
		const { result } = renderHook(() => useMediaJobs());

		let started: Promise<boolean> | undefined;
		act(() => {
			started = result.current.start("C:\\media\\broken.mp4", false);
		});
		await waitFor(() => expect(result.current.jobs).toHaveLength(1));
		const clientId = sentClientIds()[0];

		// The failure arrives before the ack: the row must still be found
		// (by client token), removed, and named in the toast.
		fire("media_transcribe_error", {
			job_id: "job-x",
			client_id: clientId,
			code: "drm_refused",
			message: "DRM content refused",
		});
		expect(result.current.jobs).toHaveLength(0);
		expect(toast.error).toHaveBeenCalledWith(
			t("media.errorTitle"),
			expect.objectContaining({
				description: `C:\\media\\broken.mp4 — ${t("media.errorDrm")}`,
			}),
		);

		// The late ack does not resurrect the row.
		act(() => {
			resolveStart({ job_id: "job-x", client_id: clientId, status: "running" });
		});
		await started;
		expect(result.current.jobs).toHaveLength(0);
	});

	it("removes the row and reports failure when the ack carries no job id", async () => {
		callMock.mockImplementation((cmd: string) => {
			if (cmd === "media_transcribe_status") {
				return Promise.resolve({ jobs: [], max_jobs: 4 });
			}
			return Promise.resolve({ status: "running" });
		});
		const { result } = renderHook(() => useMediaJobs());
		let accepted = true;
		await act(async () => {
			accepted = await result.current.start("https://example.com/a", false);
		});
		expect(accepted).toBe(false);
		expect(result.current.jobs).toHaveLength(0);
		expect(toast.error).toHaveBeenCalledWith(
			t("media.errorTitle"),
			expect.objectContaining({
				description: `https://example.com/a — ${t("media.errorGeneric")}`,
			}),
		);
	});

	it("ignores an event whose client token and job id match no row", async () => {
		const { result } = renderHook(() => useMediaJobs());
		await actStart(result, "https://example.com/a", "j1");
		fire("media_transcribe_progress", {
			job_id: "ghost-job",
			client_id: "ghost-client",
			progress: 0.4,
			phase: "transcribing",
			eta_seconds: null,
			duration_seconds: null,
		});
		fire("media_transcribe_complete", {
			job_id: "ghost-job",
			client_id: "ghost-client",
			row_id: 1,
			chars: 4,
			partial: false,
		});
		expect(result.current.jobs).toHaveLength(1);
		expect(result.current.jobs[0]?.jobId).toBe("j1");
		expect(result.current.jobs[0]?.phase).toBe("starting");
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
			client_id: null,
			row_id: 1,
			chars: 5,
			partial: false,
		});
		expect(result.current.atCapacity).toBe(false);
	});

	it("starts only the free slots of an oversized batch and says so once", async () => {
		callMock.mockImplementation((cmd: string) => {
			if (cmd === "media_transcribe_status") {
				return Promise.resolve({ jobs: [], max_jobs: 2 });
			}
			return Promise.resolve({ job_id: `job-${callMock.mock.calls.length}` });
		});
		const { result } = renderHook(() => useMediaJobs());
		await waitFor(() => expect(result.current.maxJobs).toBe(2));

		let outcome = { accepted: -1, refused: [] as string[] };
		await act(async () => {
			outcome = await result.current.startMany(
				["a.mp3", "b.mp4", "c.wav", "d.mkv", "e.ogg"],
				false,
			);
		});

		expect(
			callMock.mock.calls.filter(([cmd]) => cmd === "media_transcribe_start"),
		).toHaveLength(2);
		expect(outcome.accepted).toBe(2);
		expect(outcome.refused).toEqual(["c.wav", "d.mkv", "e.ogg"]);
		expect(result.current.jobs).toHaveLength(2);
		// Exactly ONE info toast for the whole batch.
		expect(vi.mocked(toast.info).mock.calls).toHaveLength(1);
		expect(toast.info).toHaveBeenCalledWith(
			t("media.batchLimited", { accepted: "2", total: "5", max: "2" }),
			expect.objectContaining({ id: "media-batch-limited" }),
		);
		// No per-file error toast was emitted.
		expect(toast.error).not.toHaveBeenCalled();
	});

	it("starts nothing when the batch arrives at a full backend", async () => {
		callMock.mockImplementation((cmd: string) => {
			if (cmd === "media_transcribe_status") {
				return Promise.resolve({ jobs: [], max_jobs: 1 });
			}
			return Promise.resolve({ job_id: `job-${callMock.mock.calls.length}` });
		});
		const { result } = renderHook(() => useMediaJobs());
		await waitFor(() => expect(result.current.maxJobs).toBe(1));
		await act(async () => {
			await result.current.startMany(["a.mp3"], false);
		});
		expect(result.current.atCapacity).toBe(true);
		callMock.mockClear();

		let outcome = { accepted: -1, refused: [] as string[] };
		await act(async () => {
			outcome = await result.current.startMany(["b.mp4", "c.wav"], false);
		});
		expect(
			callMock.mock.calls.filter(([cmd]) => cmd === "media_transcribe_start"),
		).toHaveLength(0);
		expect(outcome.accepted).toBe(0);
		expect(outcome.refused).toEqual(["b.mp4", "c.wav"]);
		expect(toast.info).toHaveBeenCalledWith(
			t("media.batchLimited", { accepted: "0", total: "2", max: "1" }),
			expect.objectContaining({ id: "media-batch-limited" }),
		);
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
		expect(callMock).toHaveBeenLastCalledWith(
			"media_transcribe_start",
			expect.objectContaining({
				source: "https://example.com/v",
				use_subtitles: true,
			}),
		);
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
			client_id: null,
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

	it("reports a failure whose row is already gone without an empty label", async () => {
		const { result } = renderHook(() => useMediaJobs());
		await actStart(result, "C:\\media\\broken.mp4", "j4");
		act(() => {
			result.current.dismiss(result.current.jobs[0]?.clientId as string);
		});
		expect(result.current.jobs).toHaveLength(0);
		fire("media_transcribe_error", {
			job_id: "j4",
			client_id: null,
			code: "drm_refused",
			message: "DRM content refused",
		});
		// The reason stands alone — never " — reason" with no source.
		expect(toast.error).toHaveBeenCalledWith(
			t("media.errorTitle"),
			expect.objectContaining({ description: t("media.errorDrm") }),
		);
	});

	it("hydrates every running job plus the cap after navigation", async () => {
		callMock.mockImplementation((cmd: string) =>
			cmd === "media_transcribe_status"
				? Promise.resolve({
						jobs: [
							{
								job_id: "j9",
								client_id: "media-row-9",
								source: "a.mp3",
								status: "running",
								progress: 0.4,
							},
							{
								job_id: "j10",
								client_id: "media-row-10",
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
		expect(result.current.jobs.map((row) => row.clientId)).toEqual([
			"media-row-9",
			"media-row-10",
		]);
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
});
