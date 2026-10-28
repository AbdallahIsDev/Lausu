// Media page (ADR-0023): links or local files → a queue of concurrent
// transcription jobs, each with its own phased progress (same shared
// LevelBar as the Microphone page). Job lifecycle lives in
// `media/hooks/useMediaJobs`; this file is the view.
//
// Capacity: the backend runs a bounded number of jobs at once and reports
// that cap in `media_transcribe_status`. At the cap the drop zone, the file
// picker and the link field are disabled, so the user cannot enqueue past
// it; a finished job frees its slot immediately.

import {
	Cancel01Icon,
	CheckmarkCircle01Icon,
	HistoryIcon,
	PlayCircleIcon,
	Upload01Icon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { type ClipboardEvent, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import PageHeading from "@/components/common/PageHeading";
import { SettingRow } from "@/components/common/SettingRow";
import { LevelBar } from "@/components/feedback/LevelBar";
import { Spinner } from "@/components/feedback/Spinner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useNavigation } from "@/hooks/useNavigation";
import { useT } from "@/i18n/i18n";
import { formatClockDuration } from "@/lib/format";
import { cn } from "@/lib/utils";
import {
	type MediaJobRow,
	reportBatchLimited,
	useMediaJobs,
} from "./media/hooks/useMediaJobs";
import { describeMediaSource } from "./media/lib/sourceLabel";
import { splitSources } from "./media/lib/splitSources";

/** ADR-0023 E11: past this length the page warns about the total time. */
const LONG_MEDIA_SECONDS = 4 * 3600;

export default function MediaPage() {
	const t = useT();
	const { navigate } = useNavigation();
	const {
		jobs,
		maxJobs,
		activeCount,
		atCapacity,
		starting,
		startMany,
		cancel,
		cancelAll,
		dismiss,
		clearFinished,
	} = useMediaJobs();
	const [source, setSource] = useState("");
	const [useSubtitles, setUseSubtitles] = useState(true);
	const [dragOver, setDragOver] = useState(false);

	// Native drop: absolute paths (web File objects hide them). Several
	// dropped files are enqueued together; at the cap nothing is attempted
	// and the batch is reported once (no silent drop, no per-file error).
	useEffect(() => {
		const api = window.window_;
		if (!api?.onDragDropFiles) return;
		return api.onDragDropFiles((paths) => {
			if (!Array.isArray(paths)) return;
			const usable = paths.filter((p): p is string => Boolean(p));
			if (usable.length === 0) return;
			if (atCapacity) {
				reportBatchLimited(0, usable.length, maxJobs);
				return;
			}
			void startMany(usable, useSubtitles);
		});
	}, [atCapacity, maxJobs, startMany, useSubtitles]);

	const trimmed = source.trim();
	const canStart = trimmed.length > 0 && !atCapacity && !starting;
	const hasFinished = jobs.some((row) => row.phase === "done");

	const handleStart = useCallback(async () => {
		if (!canStart) return;
		// One field can name several sources: a pasted list of links becomes
		// one job per link, while a local path with spaces stays ONE source.
		const sources = splitSources(source);
		if (sources.length === 0) return;
		const { accepted, refused } = await startMany(sources, useSubtitles);
		if (accepted === 0) {
			// Nothing started (at the cap, or every source failed): keep the
			// text so a retry is one click.
			return;
		}
		// Clear the field the moment the sources are accepted: the rows carry
		// them from here, and an empty field is what keeps Transcribe
		// disabled instead of re-submitting the same work on the next click.
		// Only what was REFUSED stays, so the user can retry just that.
		// Space-separated, not newline: a single-line input drops LF, so
		// joining with "\n" would glue the refused list into one string that
		// neither the field nor the next split can tell apart.
		setSource(refused.length > 0 ? refused.join(" ") : "");
	}, [canStart, source, startMany, useSubtitles]);

	// Browse goes through the HOST picker: a webview file input hands the
	// renderer only `file.name`, which the backend cannot open (drag-drop is
	// the only web path that carries an absolute path). The host dialog is
	// multi-select and opens with audio AND video visible. There is no
	// `<input type="file">` fallback — submitting bare file names was the
	// `decode_failed` bug this picker exists to fix.
	const onPickFiles = useCallback(async () => {
		if (atCapacity) return;
		const api = window.window_;
		if (!api?.pickMediaFiles) {
			toast.info(t("media.pickerUnavailable"), {
				id: "media-picker-unavailable",
			});
			return;
		}
		const picked = await api.pickMediaFiles();
		if (!picked.canceled && picked.paths && picked.paths.length > 0) {
			await startMany(picked.paths, useSubtitles);
		}
	}, [atCapacity, startMany, t, useSubtitles]);

	// A single-line `<input>` STRIPS newlines, so a one-link-per-line paste
	// arrives glued together ("…/aaahttps://…/bbb") and resolves as one bogus
	// URL. Read the clipboard text itself: a multi-link paste is submitted as
	// a batch, while a single link or a path stays in the field to edit.
	const onPaste = useCallback(
		(event: ClipboardEvent<HTMLInputElement>) => {
			const text = event.clipboardData?.getData("text") ?? "";
			const sources = splitSources(text);
			if (sources.length < 2) return;
			event.preventDefault();
			if (atCapacity) {
				reportBatchLimited(0, sources.length, maxJobs);
				return;
			}
			void (async () => {
				const { accepted, refused } = await startMany(sources, useSubtitles);
				if (accepted === 0) {
					// Nothing started (at the cap, or every link failed): put
					// the paste back so a retry is one click. Re-joined with
					// SPACES: a single-line input drops LF on write, which
					// would glue the links into one bogus token.
					setSource(sources.join(" "));
					return;
				}
				setSource(refused.length > 0 ? refused.join(" ") : "");
			})();
		},
		[atCapacity, maxJobs, startMany, useSubtitles],
	);

	return (
		<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-4 px-16 pt-20 pb-6">
			<PageHeading
				title={t("media.title")}
				description={t("media.description")}
			/>

			<div className="flex flex-col rounded-lg border border-border/10 bg-surface-subtle">
				{/* Drop zone + link field share one clean row stack. */}
				<div className="flex flex-col gap-3 p-4">
					<button
						type="button"
						aria-label={t("media.dropZoneAria")}
						aria-disabled={atCapacity}
						onClick={() => void onPickFiles()}
						onDragOver={(e) => {
							e.preventDefault();
							if (!atCapacity) setDragOver(true);
						}}
						onDragLeave={() => setDragOver(false)}
						onDrop={(e) => {
							e.preventDefault();
							setDragOver(false);
							if (atCapacity) return;
							const path =
								e.dataTransfer.getData("text/uri-list") ||
								e.dataTransfer.getData("text/plain");
							if (path) setSource(path.replace(/^file:\/\//, ""));
						}}
						className={cn(
							"flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-12 transition-colors",
							"border-border/10 bg-background focus-visible:ring-1 focus-visible:ring-ring",
							dragOver && "border-primary/40 bg-primary/5",
							atCapacity && "cursor-not-allowed opacity-50",
						)}
					>
						<HugeiconsIcon
							icon={Upload01Icon}
							strokeWidth={1.5}
							className="h-8 w-8 text-muted-foreground"
						/>
						<span className="text-sm text-foreground">
							{t("media.dropZoneTitle")}
						</span>
						<span className="text-xs text-muted-foreground">
							{t("media.browseFile")}
						</span>
					</button>

					<div className="flex items-center gap-3">
						<div className="h-px flex-1 bg-border/10" />
						<span className="text-[11px] uppercase tracking-wide text-muted-foreground">
							{t("media.orLink")}
						</span>
						<div className="h-px flex-1 bg-border/10" />
					</div>

					<div className="flex flex-wrap items-center gap-2">
						<Input
							id="media-source"
							value={source}
							onChange={(e) => setSource(e.target.value)}
							onPaste={onPaste}
							placeholder={t("media.sourcePlaceholder")}
							disabled={atCapacity}
							className="min-w-0 flex-1"
							onKeyDown={(e) => {
								if (e.key === "Enter") void handleStart();
							}}
						/>
						<Button onClick={() => void handleStart()} disabled={!canStart}>
							{starting ? (
								<Spinner className="border-current" decorative />
							) : (
								<HugeiconsIcon
									icon={PlayCircleIcon}
									strokeWidth={2}
									className="h-4 w-4"
								/>
							)}
							{t("media.start")}
						</Button>
						{activeCount > 1 && (
							<Button variant="outline" onClick={() => void cancelAll()}>
								{t("media.cancelAll")}
							</Button>
						)}
					</div>

					{jobs.length > 0 && (
						<div className="flex flex-wrap items-center justify-between gap-2">
							<span
								className="text-xs text-muted-foreground tabular-nums"
								data-testid="media-slots"
							>
								{t("media.slots", {
									running: String(activeCount),
									max: String(maxJobs),
								})}
							</span>
							{hasFinished && (
								<Button variant="ghost" size="sm" onClick={clearFinished}>
									{t("media.clearFinished")}
								</Button>
							)}
						</div>
					)}
					{atCapacity && (
						<p
							className="text-xs text-muted-foreground"
							data-testid="media-capacity"
						>
							{t("media.atCapacity", { max: String(maxJobs) })}
						</p>
					)}
				</div>
				<div className="border-t border-border/10">
					<SettingRow
						label={t("media.useSubtitlesLabel")}
						info={t("media.useSubtitlesInfo")}
					>
						<Switch
							checked={useSubtitles}
							onCheckedChange={setUseSubtitles}
							aria-label={t("media.useSubtitlesLabel")}
						/>
					</SettingRow>
				</div>
			</div>

			{/* One row per job: same progress card for link and local sources. */}
			{jobs.length > 0 && (
				<div className="flex flex-col rounded-lg border border-border/10 bg-surface-subtle">
					{jobs.map((job, index) => (
						<JobRow
							key={job.clientId}
							job={job}
							first={index === 0}
							onCancel={() => void cancel(job.jobId)}
							onDismiss={() => dismiss(job.clientId)}
							onOpenHistory={() => navigate("history")}
						/>
					))}
				</div>
			)}
		</div>
	);
}

interface JobRowProps {
	job: MediaJobRow;
	first: boolean;
	onCancel: () => void;
	onDismiss: () => void;
	onOpenHistory: () => void;
}

function JobRow({
	job,
	first,
	onCancel,
	onDismiss,
	onOpenHistory,
}: JobRowProps) {
	const t = useT();
	const percent = Math.max(0, Math.min(100, Math.round(job.progress * 100)));
	const label = describeMediaSource(job.source);
	const phaseLabel =
		job.phase === "downloading"
			? t("media.phaseDownloading")
			: job.phase === "transcribing"
				? t("media.phaseTranscribing")
				: t("media.phaseLoadingModel");
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
		return (
			<div
				className={cn(
					"flex flex-col gap-2 p-4",
					!first && "border-t border-border/10",
				)}
			>
				<div className="flex items-center gap-2">
					<HugeiconsIcon
						icon={CheckmarkCircle01Icon}
						strokeWidth={2}
						className="h-4 w-4 shrink-0 text-primary"
					/>
					<span
						className="min-w-0 flex-1 truncate text-sm font-medium text-foreground"
						title={job.source}
					>
						{label}
					</span>
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
