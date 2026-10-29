// useMediaJobs, the Media page's job lifecycle for SEVERAL concurrent
// jobs: start (with the unified consent gate + retry), progress/complete/
// error push subscriptions keyed by the renderer's own client token,
// per-job cancel, the backend's concurrency cap, and mount-time hydration
// via `media_transcribe_status` so running jobs survive page navigation
// (ADR-0023).
//
// Ownership contract: every start mints a `clientId`, sends it as
// `client_id`, and the backend echoes it on every event for that job. A row
// is resolved by clientId first and jobId second, so a push that arrives
// before the start ack still lands on the exact row that asked for it.
// There is deliberately no "adopt the only waiting row" heuristic: with two
// starts in flight it bound events to the wrong row (or dropped them all,
// leaving rows stuck in `starting` forever).
//
// Concurrency contract: the backend runs up to `max_jobs` jobs at once and
// rejects the next start with `job_busy`. `startMany` therefore only starts
// as many sources as there are free slots and reports the rest once, so the
// backend's rejection stays a backstop rather than the normal path.

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useLatestRef } from "@/hooks/useLatestRef";
import { useNavigation } from "@/hooks/useNavigation";
import { usePython, usePythonEvent } from "@/hooks/usePython";
import { t } from "@/i18n/i18n";
import { CONSENT_REQUIRED_CODE, MEDIA_URL_CONSENT_FIELD } from "@/lib/consent";
import { consentBodyKey, openConsentGate } from "@/lib/consentGate";
import type { Page } from "@/types/ipc";
import {
	isMultiItemError,
	isNoModelError,
	mediaErrorKey,
} from "../lib/mediaErrorCopy";

export type MediaJobPhase =
	| "starting"
	| "preparing"
	| "loading_model"
	| "downloading"
	| "transcribing"
	| "done";

/** Engine quality readings for a finished job (absent when unavailable). */
export interface MediaJobQuality {
	avg_logprob?: number;
	no_speech_prob?: number;
	chars_per_second?: number;
}

export interface MediaJobRow {
	/** Renderer-minted correlation token; also the React key. Never empty. */
	clientId: string;
	/** Backend id; empty until the start ack lands. */
	jobId: string;
	source: string;
	phase: MediaJobPhase;
	progress: number;
	etaSeconds: number | null;
	durationSeconds: number | null;
	rowId: number | null;
	chars: number | null;
	partial: boolean;
	/** Ingest path that produced the audio (`null` for local files). */
	tier: "subtitles" | "download" | "stream" | null;
	/** Machine-readable degradation note (`stream_fallback`, `model_changed`). */
	note: string | null;
	quality: MediaJobQuality | null;
}

/** Result of a batch submit: what was enqueued and what was not. */
export interface StartManyResult {
	accepted: number;
	/** The sources that did NOT start, in input order (capacity + refusals). */
	refused: string[];
}

const RUNNING_PHASES: ReadonlySet<MediaJobPhase> = new Set([
	"starting",
	"preparing",
	"loading_model",
	"downloading",
	"transcribing",
]);

/** Low-confidence thresholds for the finished row's tag (C-UI-1 copy). */
const LOW_CONFIDENCE_LOGPROB = -1.0;
const HIGH_NO_SPEECH_PROB = 0.6;

export function isLowConfidence(quality: MediaJobQuality | null): boolean {
	if (!quality) return false;
	const logprob = quality.avg_logprob;
	const noSpeech = quality.no_speech_prob;
	return (
		(typeof logprob === "number" && logprob <= LOW_CONFIDENCE_LOGPROB) ||
		(typeof noSpeech === "number" && noSpeech >= HIGH_NO_SPEECH_PROB)
	);
}

/** Fallback cap until the mount-time status read reports the real one. */
const DEFAULT_MAX_JOBS = 4;

/** Random per-instance token prefix.
 *
 * The backend echoes `client_id` on every push, so two live rows must never
 * share one. A module-level counter alone cannot promise that: a page reload
 * gets a fresh module registry, the counter restarts at 0, and the job that
 * the previous instance started is still running with `media-row-1` — its
 * progress would land on the new instance's row. A random prefix per mount
 * makes that collision impossible instead of unlikely-per-sequence.
 */
function newClientIdPrefix(): string {
	return Math.random().toString(36).slice(2, 10);
}

function makeRow(source: string, clientId: string, jobId = ""): MediaJobRow {
	return {
		clientId,
		jobId,
		source,
		phase: "starting",
		progress: 0,
		etaSeconds: null,
		durationSeconds: null,
		rowId: null,
		chars: null,
		partial: false,
		tier: null,
		note: null,
		quality: null,
	};
}

function isFinished(phase: MediaJobPhase): boolean {
	return phase === "done";
}

/** Index of the row a push belongs to: client token first, then job id.
 *
 * The client token is authoritative because the renderer minted it; the job
 * id is the fallback for a push that arrives after the ack (or for a job
 * hydrated from `media_transcribe_status`, which carries both). Neither
 * matching means the event belongs to a row that is gone — ignore it
 * rather than inventing one.
 */
function findRowIndex(
	rows: MediaJobRow[],
	clientId: string,
	jobId: string,
): number {
	if (clientId) {
		const byClient = rows.findIndex((row) => row.clientId === clientId);
		if (byClient !== -1) return byClient;
	}
	if (jobId) {
		return rows.findIndex((row) => row.jobId === jobId);
	}
	return -1;
}

/** One info toast for a batch that outran the free slots.
 *
 * Shared by the hook and the page's drag-drop path so a batch is reported
 * exactly once, never as one error per refused file.
 */
export function reportBatchLimited(
	accepted: number,
	total: number,
	max: number,
): void {
	toast.info(
		t("media.batchLimited", {
			accepted: String(accepted),
			total: String(total),
			max: String(max),
		}),
		{ id: "media-batch-limited" },
	);
}

/** Localized failure toast (ADR-0023 E13): the raw backend message stays
 * diagnostics, the user gets the copy mapped from the failure code. A
 * stable id makes a newer failure REPLACE the previous toast (the
 * global error handler's dedupe convention) instead of stacking.
 *
 * `label` is the failing source. It can be empty — an error that arrives
 * after its row was dismissed has no label left — and the description then
 * carries the reason alone instead of a dangling " — reason". */
function showErrorToast(
	errorCode: string | null | undefined,
	navigate: (page: Page) => void,
	label: string,
	details?: Record<string, string | number> | null,
): void {
	const noModel = isNoModelError(errorCode);
	const rawKey = noModel ? "media.errorNoModel" : mediaErrorKey(errorCode);
	const key = rawKey ?? "media.errorGeneric";
	// The multi-item failure names the count the backend found (a carousel
	// silently yielding one video was the defect this copy exists for).
	const count = details?.count;
	const reason = t(
		key,
		isMultiItemError(errorCode) && typeof count !== "undefined"
			? { count: String(count) }
			: {},
	);
	const trimmedLabel = label.trim();
	toast.error(t("media.errorTitle"), {
		id: "media-transcribe-error",
		// With several jobs in flight the copy alone does not say WHICH one
		// died, so the row label leads the description.
		description: trimmedLabel ? `${trimmedLabel} — ${reason}` : reason,
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
				client_id?: string | null;
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
	/** Enqueue as many sources as there are free slots; reports the rest once. */
	startMany: (
		sources: string[],
		useSubtitles: boolean,
	) => Promise<StartManyResult>;
	cancel: (jobId: string) => Promise<void>;
	cancelAll: () => Promise<void>;
	dismiss: (clientId: string) => void;
}

export function useMediaJobs(): UseMediaJobsResult {
	const { call } = usePython();
	const { navigate } = useNavigation();
	const callRef = useLatestRef(call);
	const [jobs, setJobs] = useState<MediaJobRow[]>([]);
	const [maxJobs, setMaxJobs] = useState(DEFAULT_MAX_JOBS);
	const [pending, setPending] = useState(0);
	// Synchronous mirrors: the duplicate check and the capacity budget run in
	// an event handler, where a passive-effect ref would still hold the
	// previous commit.
	const jobsRef = useRef<MediaJobRow[]>([]);
	const maxJobsRef = useRef(maxJobs);
	maxJobsRef.current = maxJobs;
	// Latest `start` identity for the consent gate's `onAllow` retry:
	// the gate stores the callback long after this render, so it must
	// re-invoke the CURRENT function, not a stale closure.
	const startRef = useRef<
		(source: string, useSubtitles: boolean) => Promise<boolean>
	>(async () => false);
	// One mint per mount: the prefix is random, the sequence lives in a ref.
	const [clientIdPrefix] = useState(newClientIdPrefix);
	const clientSeq = useRef(0);
	const mintClientId = useCallback((): string => {
		clientSeq.current += 1;
		return `media-row-${clientIdPrefix}-${clientSeq.current}`;
	}, [clientIdPrefix]);
	// Same reason as `callRef`: the hydration effect keeps `[]` deps, so it
	// must read the mint through a mirror rather than capture this render.
	const mintClientIdRef = useRef(mintClientId);
	mintClientIdRef.current = mintClientId;

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

	/** Apply a push event to the row that owns it (client token, then job id).
	 *
	 * A job's first progress push can beat the start ack; the row is found by
	 * its client token either way, and the job id is adopted on the spot.
	 */
	const applyEvent = useCallback(
		(
			clientId: string,
			jobId: string,
			patch: (row: MediaJobRow) => Partial<MediaJobRow>,
		) => {
			updateJobs((prev) => {
				const index = findRowIndex(prev, clientId, jobId);
				if (index === -1) return prev;
				return prev.map((row, i) =>
					i === index
						? { ...row, jobId: row.jobId || jobId, ...patch(row) }
						: row,
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
			const clientId = mintClientId();
			const optimistic = makeRow(trimmed, clientId);
			updateJobs((prev) => [...prev, optimistic]);
			try {
				const result = await call<{
					job_id?: string;
					client_id?: string | null;
				}>("media_transcribe_start", {
					source: trimmed,
					use_subtitles: useSubtitles,
					client_id: clientId,
				});
				const jobId = typeof result?.job_id === "string" ? result.job_id : "";
				if (!jobId) {
					// The backend accepted the call but cannot address the job:
					// keeping the row would leave a "starting" ghost that no
					// event can ever finish (and no Cancel can reach).
					updateJobs((prev) => prev.filter((row) => row.clientId !== clientId));
					showErrorToast("internal_error", navigate, trimmed);
					return false;
				}
				const ackClientId =
					typeof result?.client_id === "string" ? result.client_id : "";
				// An older backend echoes no client_id; the row we just created
				// is still the right one, so fall back to our own token.
				const targetClientId = ackClientId || clientId;
				updateJobs((prev) =>
					prev.map((row) =>
						row.clientId === targetClientId && !row.jobId
							? { ...row, jobId }
							: row,
					),
				);
				return true;
			} catch (err) {
				const e = err as { code?: string; consent_field?: string };
				// Nothing is running for this source: drop the optimistic row.
				updateJobs((prev) => prev.filter((row) => row.clientId !== clientId));
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
		[call, mintClientId, navigate, updateJobs],
	);
	startRef.current = start;

	const startMany = useCallback(
		async (
			sources: string[],
			useSubtitles: boolean,
		): Promise<StartManyResult> => {
			if (sources.length === 0) return { accepted: 0, refused: [] };
			// Capacity is read ONCE, up front: starting a batch and letting the
			// backend reject the overflow would toast one error per file.
			const active = jobsRef.current.filter((row) =>
				RUNNING_PHASES.has(row.phase),
			).length;
			const free = Math.max(0, maxJobsRef.current - active);
			if (free === 0) {
				reportBatchLimited(0, sources.length, maxJobsRef.current);
				return { accepted: 0, refused: [...sources] };
			}
			const toStart = sources.slice(0, free);
			const skipped = sources.slice(free);
			let accepted = 0;
			const refused: string[] = [];
			for (const source of toStart) {
				// Sequential on purpose: each ack is fast (URL resolution and
				// downloads live in the job thread), and one-at-a-time keeps
				// the optimistic-row ↔ ack handshake ordered.
				if (await start(source, useSubtitles)) accepted += 1;
				else refused.push(source);
			}
			refused.push(...skipped);
			if (skipped.length > 0) {
				// One toast for the whole batch, never one per refused file.
				reportBatchLimited(accepted, sources.length, maxJobsRef.current);
			}
			return { accepted, refused };
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
		(clientId: string) => {
			updateJobs((prev) => prev.filter((row) => row.clientId !== clientId));
		},
		[updateJobs],
	);

	// Progress pushes (phase + fraction + measured ETA + total duration).
	usePythonEvent("media_transcribe_progress", (data) => {
		if (!data?.job_id) return;
		const clientId = data.client_id ?? "";
		applyEvent(clientId, data.job_id, (row) =>
			isFinished(row.phase)
				? {}
				: {
						phase: data.phase,
						progress:
							typeof data.progress === "number" ? data.progress : row.progress,
						etaSeconds: data.eta_seconds ?? null,
						durationSeconds: data.duration_seconds ?? row.durationSeconds,
						tier: data.tier ?? row.tier,
						note: data.note ?? row.note,
					},
		);
	});

	// Completion (also fired for cancelled jobs carrying a partial).
	usePythonEvent("media_transcribe_complete", (data) => {
		if (!data?.job_id) return;
		applyEvent(data.client_id ?? "", data.job_id, () => ({
			phase: "done",
			progress: 1,
			rowId: data.row_id,
			chars: data.chars,
			partial: data.partial,
			etaSeconds: null,
			tier: data.tier ?? null,
			note: data.note ?? null,
			quality: data.quality ?? null,
		}));
	});

	// A model switch cancelled running jobs (after waiting for them): the
	// cancellation is explained here, not left as a silent vanishing row.
	usePythonEvent("media_jobs_cancelled_for_model_change", (data) => {
		const count = typeof data?.count === "number" ? data.count : 0;
		toast.warning(t("media.modelChangedTitle"), {
			id: "media-model-changed",
			description: t("media.modelChangedDescription", {
				count: String(count),
			}),
		});
	});

	// Failure pushed from the backend job thread (raw message is
	// diagnostics only; the copy comes from the code map).
	usePythonEvent("media_transcribe_error", (data) => {
		if (!data?.job_id) return;
		const clientId = data.client_id ?? "";
		const index = findRowIndex(jobsRef.current, clientId, data.job_id);
		const failed = index === -1 ? undefined : jobsRef.current[index];
		// C-UI-11: a failure is reported by the toast, not by a row left
		// sitting under the drop zone. The row goes away; the toast names it
		// — unless it already went away, in which case the reason stands
		// alone (never an empty label followed by " — ").
		updateJobs((prev) =>
			prev.filter(
				(row) => row.jobId !== data.job_id && row.clientId !== clientId,
			),
		);
		showErrorToast(data.code, navigate, failed?.source ?? "", data.details);
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
							...makeRow(
								job.source ?? "",
								// A job started by an earlier page instance keeps its
								// client token; one started before this field existed
								// gets a fresh local one (its pushes fall back to job id).
								job.client_id || mintClientIdRef.current(),
								job.job_id,
							),
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
	};
}
