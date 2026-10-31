// One queued/running/finished media job, as a row: the shared LevelBar for
// progress, two user-facing phase labels, and the finished card (title,
// optional inline preview, outcome copy). Presentation only — the job
// lifecycle lives in `media/hooks/useMediaJobs`.

import {
	Cancel01Icon,
	CheckmarkCircle01Icon,
	HistoryIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { LevelBar } from "@/components/feedback/LevelBar";
import { Button } from "@/components/ui/button";
import { useT } from "@/i18n/i18n";
import { formatClockDuration } from "@/lib/format";
import { cn } from "@/lib/utils";
import { isLowConfidence, type MediaJobRow } from "../hooks/useMediaJobs";
import { describeMediaSource } from "../lib/sourceLabel";

/** ADR-0023 E11: past this length the page warns about the total time. */
export const LONG_MEDIA_SECONDS = 4 * 3600;

interface MediaJobRowViewProps {
	job: MediaJobRow;
	first: boolean;
	onCancel: () => void;
	onDismiss: () => void;
	onOpenHistory: () => void;
}

export function MediaJobRowView({
	job,
	first,
	onCancel,
	onDismiss,
	onOpenHistory,
}: MediaJobRowViewProps) {
	const t = useT();
	const percent = Math.max(0, Math.min(100, Math.round(job.progress * 100)));
	const label = describeMediaSource(job.source);
	// Two user states only: everything before the first window is
	// "Preparing…", everything after it is "Transcribing…". The internal
	// codes stay for the detail line and for support logs, but the label
	// must never read "Loading model…" for a job that already has an engine.
	const phaseLabel =
		job.phase === "transcribing"
			? t("media.phaseTranscribing")
			: t("media.phasePreparing");
	// Secondary detail: what the pre-transcribe stage is actually doing.
	const phaseDetail =
		job.phase === "downloading"
			? t("media.phaseDownloading")
			: job.phase === "loading_model"
				? t("media.phaseLoadingModel")
				: null;
	const lowConfidence = isLowConfidence(job.quality);
	const isLongMedia =
		job.durationSeconds !== null && job.durationSeconds > LONG_MEDIA_SECONDS;
	// Percent owns the slot above the bar; remaining time + total length
	// read as one caption below it (owner request 2026-10-27).
	const progressMeta = [
		job.etaSeconds !== null
			? t("media.eta", { time: formatClockDuration(job.etaSeconds) })
			: null,
		job.durationSeconds !== null
			? t("media.duration", { time: formatClockDuration(job.durationSeconds) })
			: null,
	].filter((part): part is string => part !== null);

	if (job.phase === "done") {
		const chars = job.chars ?? 0;
		// The real media title first: a link's label (`host/status-id`) says
		// nothing about the video the user just transcribed.
		const heading = job.title ?? label;
		return (
			<div
				className={cn(
					"flex flex-col gap-2 p-4",
					!first && "border-t border-border/10",
				)}
			>
				<div className="flex items-center gap-2">
					{job.thumbnailDataUrl !== null && (
						<img
							src={job.thumbnailDataUrl}
							alt=""
							aria-hidden="true"
							className="aspect-video w-24 shrink-0 rounded-md border border-border/8 object-cover"
							data-testid="media-preview-thumbnail"
						/>
					)}
					{/* The semantic success token, not primary: a done job is not an action. */}
					<HugeiconsIcon
						icon={CheckmarkCircle01Icon}
						strokeWidth={2}
						className="h-4 w-4 shrink-0 text-success"
					/>
					<span
						className="min-w-0 flex-1 truncate text-sm font-medium text-foreground"
						title={job.source}
					>
						{heading}
					</span>
					{lowConfidence && (
						<span
							className="shrink-0 rounded-md border border-border/8 px-1.5 py-0.5 text-xs text-muted-foreground"
							data-testid="media-low-confidence"
						>
							{t("media.lowConfidence")}
						</span>
					)}
					<Button
						variant="ghost"
						size="sm"
						aria-label={t("media.dismiss")}
						onClick={onDismiss}
					>
						<HugeiconsIcon
							icon={Cancel01Icon}
							strokeWidth={2}
							className="h-4 w-4"
						/>
					</Button>
				</div>
				<p className="text-sm text-muted-foreground">
					{chars === 0
						? t("media.noSpeech")
						: job.partial
							? t("media.partialDescription", { chars: String(chars) })
							: t("media.completeDescription", { chars: String(chars) })}
				</p>
				{/* Visible degradation: the row is a success, but not a clean one. */}
				{job.tier === "stream" && (
					<p
						className="text-xs text-muted-foreground"
						data-testid="media-stream-fallback-note"
					>
						{t("media.streamFallbackNote")}
					</p>
				)}
				{job.rowId !== null && (
					<div>
						<Button variant="outline" size="sm" onClick={onOpenHistory}>
							<HugeiconsIcon
								icon={HistoryIcon}
								strokeWidth={2}
								className="h-4 w-4"
							/>
							{t("media.openHistory")}
						</Button>
					</div>
				)}
			</div>
		);
	}

	return (
		<div
			className={cn(
				"flex flex-col gap-2 p-4",
				!first && "border-t border-border/10",
			)}
		>
			<div className="flex flex-wrap items-baseline justify-between gap-2">
				<span
					className="min-w-0 flex-1 truncate text-sm font-medium text-foreground"
					title={job.source}
				>
					{label}
				</span>
				<span
					className="text-xs text-muted-foreground tabular-nums"
					data-testid="media-progress-percent"
				>
					{t("media.percent", { percent: String(percent) })}
				</span>
			</div>
			{/* Shared LevelBar (same bar as the Microphone page). */}
			<LevelBar
				level={percent / 100}
				playing={false}
				ariaLabel={t("media.percent", { percent: String(percent) })}
				ariaValueText={t("media.percent", { percent: String(percent) })}
			/>
			<div className="flex flex-wrap items-center justify-between gap-2">
				<span className="text-xs text-muted-foreground">
					{phaseLabel}
					{phaseDetail !== null && (
						<span data-testid="media-phase-detail">{` · ${phaseDetail}`}</span>
					)}
					{progressMeta.length > 0 && (
						<span className="tabular-nums" data-testid="media-progress-meta">
							{" · "}
							{progressMeta.join(" · ")}
						</span>
					)}
				</span>
				{job.jobId !== "" && (
					<Button variant="ghost" size="sm" onClick={onCancel}>
						{t("media.cancel")}
					</Button>
				)}
			</div>
			{isLongMedia && (
				<p className="text-xs text-muted-foreground">
					{t("media.longMediaNotice")}
				</p>
			)}
		</div>
	);
}
