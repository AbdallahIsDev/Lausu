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
	PlayCircleIcon,
	Upload01Icon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import {
	type ClipboardEvent,
	useCallback,
	useEffect,
	useRef,
	useState,
} from "react";
import { Skeleton } from "skullet/react";
import { toast } from "sonner";
import PageHeading from "@/components/common/PageHeading";
import { SettingRow } from "@/components/common/SettingRow";
import { Spinner } from "@/components/feedback/Spinner";
import { skeletonLoadingLabel } from "@/components/feedback/skeletons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useNavigation } from "@/hooks/useNavigation";
import { useT } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import { useMediaSourceStore } from "@/stores/mediaSourceStore";
import { MediaJobRowView } from "./media/components/MediaJobRow";
import { reportBatchLimited, useMediaJobs } from "./media/hooks/useMediaJobs";
import { SAMPLE_MEDIA_JOB } from "./media/lib/sample";
import { splitSources } from "./media/lib/splitSources";

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
	} = useMediaJobs();
	// The field lives in a store (persisted): a value typed here must survive
	// navigation, a refresh and a restart, and only the user clears it.
	const source = useMediaSourceStore((state) => state.source);
	const setSource = useMediaSourceStore((state) => state.setSource);
	const clearSource = useMediaSourceStore((state) => state.clear);
	const inputRef = useRef<HTMLInputElement>(null);
	const [useSubtitles, setUseSubtitles] = useState(true);
	const [dragOver, setDragOver] = useState(false);

	const onClear = useCallback(() => {
		clearSource();
		// Focus stays in the field so the next paste needs no extra click.
		inputRef.current?.focus();
	}, [clearSource]);

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
	}, [canStart, source, setSource, startMany, useSubtitles]);

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
		[atCapacity, maxJobs, setSource, startMany, useSubtitles],
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
						<div className="relative min-w-0 flex-1">
							<Input
								id="media-source"
								ref={inputRef}
								value={source}
								onChange={(e) => setSource(e.target.value)}
								onPaste={onPaste}
								placeholder={t("media.sourcePlaceholder")}
								disabled={atCapacity}
								// Trailing room for the in-field clear button.
								className={cn("min-w-0 w-full", source !== "" && "pe-9")}
								onKeyDown={(e) => {
									if (e.key === "Enter") void handleStart();
								}}
							/>
							{source !== "" && (
								<button
									type="button"
									aria-label={t("media.clearInput")}
									title={t("media.clearInput")}
									onClick={onClear}
									disabled={atCapacity}
									className="absolute inset-y-0 end-2 my-auto flex h-5 w-5 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
									data-testid="media-source-clear"
								>
									<HugeiconsIcon
										icon={Cancel01Icon}
										strokeWidth={2}
										className="h-3.5 w-3.5"
									/>
								</button>
							)}
						</div>
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
						// Measured wrap per row: jobs is always an array (no
						// first-load null), so only the no-progress "starting"
						// phase needs the skeleton; the Start button's Spinner
						// stays, it is an inline action state.
						<Skeleton
							key={job.clientId}
							data={job.phase === "starting" ? null : job}
							sample={SAMPLE_MEDIA_JOB}
							id={`media-job-${job.clientId}`}
							label={skeletonLoadingLabel()}
						>
							{(d) => (
								<MediaJobRowView
									job={d}
									first={index === 0}
									onCancel={() => void cancel(job.jobId)}
									onDismiss={() => dismiss(job.clientId)}
									onOpenHistory={() => navigate("history")}
								/>
							)}
						</Skeleton>
					))}
				</div>
			)}
		</div>
	);
}
