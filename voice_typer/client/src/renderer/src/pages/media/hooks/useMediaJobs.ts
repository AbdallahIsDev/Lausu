// useMediaJobs, the Media page's job lifecycle for SEVERAL concurrent
// jobs: start (with the unified consent gate + retry), progress/complete/
// error push subscriptions keyed by job id, per-job cancel, the backend's
// concurrency cap, and mount-time hydration via `media_transcribe_status`
// so running jobs survive page navigation (ADR-0023).
//
// Concurrency contract: the backend runs up to `max_jobs` jobs at once and
// rejects the next start with `job_busy`. The page disables its inputs at
// the cap so that rejection stays a backstop, never the normal path.

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useLatestRef } from "@/hooks/useLatestRef";
import { useNavigation } from "@/hooks/useNavigation";
import { usePython, usePythonEvent } from "@/hooks/usePython";
import { t } from "@/i18n/i18n";
import { CONSENT_REQUIRED_CODE, MEDIA_URL_CONSENT_FIELD } from "@/lib/consent";
import { consentBodyKey, openConsentGate } from "@/lib/consentGate";
import type { Page } from "@/types/ipc";
import { isNoModelError, mediaErrorKey } from "../lib/mediaErrorCopy";

export type MediaJobPhase =
	| "starting"
	| "loading_model"
	| "downloading"
	| "transcribing"
	| "done";

export interface MediaJobRow {
	/** Stable React key; `jobId` is empty until the start ack lands. */
	key: string;
	jobId: string;
	source: string;
	phase: MediaJobPhase;
	progress: number;
	etaSeconds: number | null;
	durationSeconds: number | null;
	rowId: number | null;
	chars: number | null;
	partial: boolean;
}

const RUNNING_PHASES: ReadonlySet<MediaJobPhase> = new Set([
	"starting",
	"loading_model",
	"downloading",
	"transcribing",
]);

/** Fallback cap until the mount-time status read reports the real one. */
const DEFAULT_MAX_JOBS = 4;

let rowSeq = 0;
function nextKey(): string {
	rowSeq += 1;
	return `media-row-${rowSeq}`;
}

function makeRow(source: string, jobId = ""): MediaJobRow {
	return {
		key: nextKey(),
		jobId,
		source,
		phase: "starting",
		progress: 0,
		etaSeconds: null,
		durationSeconds: null,
		rowId: null,
		chars: null,
		partial: false,
	};
}

function isFinished(phase: MediaJobPhase): boolean {
	return phase === "done";
}

/** Localized failure toast (ADR-0023 E13): the raw backend message stays
 * diagnostics, the user gets the copy mapped from the failure code. A
 * stable id makes a newer failure REPLACE the previous toast (the
 * global error handler's dedupe convention) instead of stacking. */
function showErrorToast(
	errorCode: string | null | undefined,
	navigate: (page: Page) => void,
	label: string,
): void {
	const noModel = isNoModelError(errorCode);
	const reason = t(
		noModel
			? "media.errorNoModel"
			: (mediaErrorKey(errorCode) ?? "media.errorGeneric"),
	);
	toast.error(t("media.errorTitle"), {
		id: "media-transcribe-error",
		// With several jobs in flight the copy alone does not say WHICH one
		// died, so the row label leads the description.
		description: `${label} — ${reason}`,
		...(noModel
			? {
					action: {
						label: t("media.noModelAction"),
						onClick: () => navigate("models"),
					},
				}
			: {}),
	});
}

interface StatusSnapshot {
	jobs:
		| {
				job_id: string;
				source?: string;
				status: string;
				phase?: string;
				progress?: number;
		  }[]
		| null;
	max_jobs?: number | null;
}

export interface UseMediaJobsResult {
	jobs: MediaJobRow[];
	/** Backend concurrency cap (authoritative; the UI never guesses). */
	maxJobs: number;
	/** Jobs holding a slot: starting + running. */
	activeCount: number;
	atCapacity: boolean;
	/** True while at least one start round-trip is in flight. */
	starting: boolean;
	/** Enqueue one source. False when it was refused (duplicate, cap, error). */
	start: (source: string, useSubtitles: boolean) => Promise<boolean>;
	/** Enqueue several sources; returns how many were accepted. */
	startMany: (sources: string[], useSubtitles: boolean) => Promise<number>;
	cancel: (jobId: string) => Promise<void>;
	cancelAll: () => Promise<void>;
	dismiss: (key: string) => void;
	clearFinished: () => void;
}

export function useMediaJobs(): UseMediaJobsResult {
	const { call } = usePython();
	const { navigate } = useNavigation();
	const callRef = useLatestRef(call);
	const [jobs, setJobs] = useState<MediaJobRow[]>([]);
	const [maxJobs, setMaxJobs] = useState(DEFAULT_MAX_JOBS);
	const [pending, setPending] = useState(0);
	// Synchronous mirror: the duplicate check runs in an event handler,
	// where a passive-effect ref would still hold the previous commit.
	const jobsRef = useRef<MediaJobRow[]>([]);
	// Latest `start` identity for the consent gate's `onAllow` retry:
	// the gate stores the callback long after this render, so it must
	// re-invoke the CURRENT function, not a stale closure.
	const startRef = useRef<
		(source: string, useSubtitles: boolean) => Promise<boolean>
	>(async () => false);

	const updateJobs = useCallback(
		(fn: (prev: MediaJobRow[]) => MediaJobRow[]) => {
			setJobs((prev) => {
				const next = fn(prev);
				jobsRef.current = next;
				return next;
			});
		},
		[],
	);

	/** Apply a push event to the row with `jobId`.
	 *
	 * A job's first progress push can beat the start ack, so when no row
	 * carries the id yet and exactly ONE row is still waiting for its ack,
	 * that row adopts the id. `startMany` awaits each start before the next,
	 * so "exactly one" is a fact, not a guess.
	 */
	const applyEvent = useCallback(
		(jobId: string, patch: (row: MediaJobRow) => Partial<MediaJobRow>) => {
			updateJobs((prev) => {
				if (!prev.some((row) => row.jobId === jobId)) {
					const waiting = prev.filter((row) => row.jobId === "");
					const adopt = waiting.length === 1 ? waiting[0] : undefined;
					if (!adopt) return prev;
					return prev.map((row) =>
						row.key === adopt.key
							? { ...row, jobId, ...patch({ ...row, jobId }) }
							: row,
					);
				}
				return prev.map((row) =>
					row.jobId === jobId ? { ...row, ...patch(row) } : row,
				);
			});
		},
		[updateJobs],
	);

	const start = useCallback(
		async (source: string, useSubtitles: boolean): Promise<boolean> => {
			const trimmed = source.trim();
			if (!trimmed) return false;
			// Same source already running: enqueueing it again would burn a
			// second slot on identical work (the repeat-transcribe bug).
			const duplicate = jobsRef.current.some(
				(row) => RUNNING_PHASES.has(row.phase) && row.source === trimmed,
			);
			if (duplicate) {
				toast.info(t("media.duplicateTitle"), {
					id: "media-duplicate",
					description: t("media.duplicateDescription"),
				});
				return false;
			}
			setPending((n) => n + 1);
			const optimistic = makeRow(trimmed);
			updateJobs((prev) => [...prev, optimistic]);
			try {
				const result = await call<{ job_id?: string }>(
					"media_transcribe_start",
					{ source: trimmed, use_subtitles: useSubtitles },
				);
				const jobId = typeof result?.job_id === "string" ? result.job_id : "";
				updateJobs((prev) =>
					prev.map((row) =>
						row.key === optimistic.key && !row.jobId ? { ...row, jobId } : row,
					),
				);
				return true;
			} catch (err) {
				const e = err as { code?: string; consent_field?: string };
				// Nothing is running for this source: drop the optimistic row.
				updateJobs((prev) => prev.filter((row) => row.key !== optimistic.key));
				if (e.code === CONSENT_REQUIRED_CODE) {
					// C-MIC-3 just-in-time gate: grant + retry the SAME action.
					const field = e.consent_field ?? MEDIA_URL_CONSENT_FIELD;
					openConsentGate({
						consentField: field,
						bodyKey: consentBodyKey(field),
						onAllow: () => void startRef.current(trimmed, useSubtitles),
					});
					return false;
				}
				showErrorToast(e.code, navigate, trimmed);
				return false;
			} finally {
				setPending((n) => Math.max(0, n - 1));
			}
		},
		[call, navigate, updateJobs],
	);
	startRef.current = start;

	const startMany = useCallback(
		async (sources: string[], useSubtitles: boolean): Promise<number> => {
			let accepted = 0;
			for (const source of sources) {
				// Sequential on purpose: each ack is fast (URL resolution and
				// downloads live in the job thread), and one-at-a-time keeps the
				// optimistic-row ↔ job_id handshake unambiguous.
				if (await start(source, useSubtitles)) accepted += 1;
			}
			return accepted;
		},
		[start],
	);

	const cancel = useCallback(
		async (jobId: string) => {
			if (!jobId) return;
			try {
				await call("media_transcribe_cancel", { job_id: jobId });
			} catch (err) {
				console.warn("[renderer:media] cancel failed:", err);
			}
		},
		[call],
	);

	const cancelAll = useCallback(async () => {
		try {
			await call("media_transcribe_cancel");
		} catch (err) {
			console.warn("[renderer:media] cancel all failed:", err);
		}
	}, [call]);

	const dismiss = useCallback(
		(key: string) => {
			updateJobs((prev) => prev.filter((row) => row.key !== key));
		},
		[updateJobs],
	);

	const clearFinished = useCallback(() => {
		updateJobs((prev) => prev.filter((row) => RUNNING_PHASES.has(row.phase)));
	}, [updateJobs]);

	// Progress pushes (phase + fraction + measured ETA + total duration).
	usePythonEvent("media_transcribe_progress", (data) => {
		if (!data?.job_id) return;
		applyEvent(data.job_id, (row) =>
			isFinished(row.phase)
				? {}
				: {
						phase: data.phase,
						progress:
							typeof data.progress === "number" ? data.progress : row.progress,
						etaSeconds: data.eta_seconds ?? null,
						durationSeconds: data.duration_seconds ?? row.durationSeconds,
					},
		);
	});

	// Completion (also fired for cancelled jobs carrying a partial).
	usePythonEvent("media_transcribe_complete", (data) => {
		if (!data?.job_id) return;
		applyEvent(data.job_id, () => ({
			phase: "done",
			progress: 1,
			rowId: data.row_id,
			chars: data.chars,
			partial: data.partial,
			etaSeconds: null,
		}));
	});

	// Failure pushed from the backend job thread (raw message is
	// diagnostics only; the copy comes from the code map).
	usePythonEvent("media_transcribe_error", (data) => {
		if (!data?.job_id) return;
		const failed = jobsRef.current.find((row) => row.jobId === data.job_id);
		// C-UI-11: a failure is reported by the toast, not by a row left
		// sitting under the drop zone. The row goes away; the toast names it.
		updateJobs((prev) => prev.filter((row) => row.jobId !== data.job_id));
		showErrorToast(data.code, navigate, failed?.source ?? "");
	});

	// Hydrate running jobs after navigation back to the page. One-shot
	// mount read through the callRef mirror (NOT a `[call]` dep: the
	// OOM-loop class — see `useLatestRef` + the dep-guard test).
	// biome-ignore lint/correctness/useExhaustiveDependencies: callRef is a useLatestRef mirror: reading .current in a stale closure is the hook's documented contract, .current must NOT become a dep
	useEffect(() => {
		let cancelled = false;
		void callRef
			.current<StatusSnapshot>("media_transcribe_status")
			.then((result) => {
				if (cancelled) return;
				if (typeof result?.max_jobs === "number" && result.max_jobs > 0) {
					setMaxJobs(result.max_jobs);
				}
				const running = (result?.jobs ?? []).filter(
					(job) => job.status === "running",
				);
				if (running.length === 0) return;
				updateJobs((prev) => {
					const known = new Set(prev.map((row) => row.jobId));
					const restored = running
						.filter((job) => !known.has(job.job_id))
						.map((job) => ({
							...makeRow(job.source ?? "", job.job_id),
							phase: (job.phase as MediaJobPhase) ?? "transcribing",
							progress: typeof job.progress === "number" ? job.progress : 0,
						}));
					return restored.length > 0 ? [...restored, ...prev] : prev;
				});
			})
			.catch(() => {
				/* hydration is best-effort */
			});
		return () => {
			cancelled = true;
		};
	}, []);

	const activeCount = jobs.filter((row) =>
		RUNNING_PHASES.has(row.phase),
	).length;

	return {
		jobs,
		maxJobs,
		activeCount,
		atCapacity: activeCount >= maxJobs,
		starting: pending > 0,
		start,
		startMany,
		cancel,
		cancelAll,
		dismiss,
		clearFinished,
	};
}
