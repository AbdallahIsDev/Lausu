// One queued/running/finished media job, as a row: the shared LevelBar for
// progress, two user-facing phase labels, and the finished card (title,
// optional inline preview, outcome copy). Presentation only — the job
// lifecycle lives in `media/hooks/useMediaJobs`.

import {
	Cancel01Icon,
	File02Icon,
	Film01Icon,
	HistoryIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useEffect, useRef, useState } from "react";
import { LevelBar } from "@/components/feedback/LevelBar";
import { Button } from "@/components/ui/button";
import { useT } from "@/i18n/i18n";
import {
	countWords,
	formatClockDuration,
	formatElapsedShort,
	formatMediaDuration,
} from "@/lib/format";
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
	const startedAtRef = useRef<number | null>(null);
	const [elapsedSeconds, setElapsedSeconds] = useState(0);
	useEffect(() => {
		if (job.phase === "done") return;
		if (startedAtRef.current === null) startedAtRef.current = Date.now();
		const tick = () => {
			const start = startedAtRef.current ?? Date.now();
			setElapsedSeconds(Math.floor((Date.now() - start) / 1000));
		};
		tick();
		const timer = window.setInterval(tick, 1000);
		return () => window.clearInterval(timer);
	}, [job.phase]);

	const percent = Math.max(0, Math.min(100, Math.round(job.progress * 100)));
	const label = describeMediaSource(job.source);
	// Two user states only: everything before the first window is
	// "Preparing…", everything after it is "Transcribing…". The internal
	// codes stay for the detail line and for support logs, but the label
	// must never read "Loading model…" for a job that already has an engine.
	const phaseLabel =
		job.phase === "transcribing"
			? t("media.phaseTranscribing")
			: job.phase === "downloading"
				? t("media.phaseDownloading")
				: t("media.phasePreparing");
	// Secondary detail: only a model load changes the story mid-prepare.
	const phaseDetail =
		job.phase === "loading_model" ? t("media.phaseLoadingModel") : null;
	const lowConfidence = isLowConfidence(job.quality);
	const isLongMedia =
		job.durationSeconds !== null && job.durationSeconds > LONG_MEDIA_SECONDS;
	// Percent owns the slot above the bar; remaining time + total length
	// read as one caption below it (owner request 2026-10-27).
	const progressMeta = [
		t("media.elapsed", { time: formatClockDuration(elapsedSeconds) }),
		job.etaSeconds !== null
			? t("media.eta", { time: formatClockDuration(job.etaSeconds) })
			: null,
		job.durationSeconds !== null
			? t("media.duration", { time: formatClockDuration(job.durationSeconds) })
			: null,
	].filter((part): part is string => part !== null);

	if (job.phase === "done") {
		const words = job.words ?? countWords(job.title ?? "");
		const heading = job.sourceTitle ?? job.title ?? label;
		const thumbnail = job.thumbnailDataUrl ?? job.thumbnailUrl;
		const isFileSource =
			job.sourceType === "file" ||
			Boolean(job.fileName) ||
			job.sourceType === null;
		const source =
			job.sourceType === "youtube"
				? t("media.metaYoutube")
				: job.sourceType === "file"
					? t("media.metaLocalFile")
					: job.sourceType === "url"
						? label
						: null;
		const method =
			job.method === "subtitles"
				? t("media.metaSubtitles")
				: job.method === "transcription"
					? t("media.metaTranscription")
					: null;
		const metadata = [
			job.mediaDurationSeconds != null
				? formatMediaDuration(job.mediaDurationSeconds)
				: null,
			job.processingSeconds != null
				? t("media.elapsed", {
						time: formatElapsedShort(job.processingSeconds),
					})
				: null,
			source,
			job.modelName ?? null,
			method,
		].filter((part): part is string => part !== null);

		return (
			<div
				className={cn(
					"relative flex flex-wrap items-center gap-3 p-4 pe-10",
					!first && "border-t border-border/10",
				)}
			>
				{thumbnail !== null && thumbnail !== "" ? (
					<img
						src={thumbnail}
						alt=""
						aria-hidden="true"
						className="aspect-video w-20 shrink-0 rounded-md border border-border/8 object-cover"
						data-testid="media-preview-thumbnail"
					/>
				) : (
					<div
						className="flex aspect-video w-20 shrink-0 items-center justify-center rounded-md border border-border/8 bg-border/5 text-muted-foreground"
						data-testid="media-preview-placeholder"
						aria-hidden="true"
					>
						<HugeiconsIcon
							icon={isFileSource ? File02Icon : Film01Icon}
							strokeWidth={1.5}
							className="h-6 w-6"
						/>
					</div>
				)}
				<div className="flex min-w-0 flex-1 flex-col gap-1">
					<span
						className="line-clamp-2 text-sm font-medium leading-snug text-foreground"
						title={job.sourceTitle ?? heading}
						dir="auto"
					>
						{heading}
					</span>
					<p className="text-sm text-muted-foreground" dir="auto">
						{words === 0
							? t("media.noSpeech")
							: words === 1
								? t("media.wordAdded")
								: t("media.wordsAdded", { count: String(words) })}
					</p>
					{metadata.length > 0 && (
						<p className="break-words text-xs text-muted-foreground">
							{metadata.join(" · ")}
						</p>
					)}
					{lowConfidence && (
						<span
							className="w-fit rounded-md border border-border/8 px-1.5 py-0.5 text-xs text-muted-foreground"
							data-testid="media-low-confidence"
						>
							{t("media.lowConfidence")}
						</span>
					)}
					{/* Visible degradation: the row is a success, but not a clean one. */}
					{job.tier === "stream" && (
						<p
							className="text-xs text-muted-foreground"
							data-testid="media-stream-fallback-note"
						>
							{t("media.streamFallbackNote")}
						</p>
					)}
				</div>
				{job.rowId !== null && (
					<Button
						variant="secondary"
						size="sm"
						className="shrink-0"
						onClick={onOpenHistory}
					>
						<HugeiconsIcon
							icon={HistoryIcon}
							strokeWidth={2}
							className="h-4 w-4"
						/>
						{t("media.openHistory")}
					</Button>
				)}
				<Button
					variant="ghost"
					size="icon-xs"
					aria-label={t("media.dismiss")}
					title={t("media.dismiss")}
					onClick={onDismiss}
					className="absolute end-2 top-2 text-muted-foreground hover:text-foreground"
				>
					<HugeiconsIcon
						icon={Cancel01Icon}
						strokeWidth={2}
						className="h-3.5 w-3.5"
					/>
				</Button>
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
