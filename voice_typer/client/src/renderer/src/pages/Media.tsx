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
	ClipboardListIcon,
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
import { Spinner } from "@/components/feedback/Spinner";
import { skeletonLoadingLabel } from "@/components/feedback/skeletons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useNavigation } from "@/hooks/useNavigation";
import { useT } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import { useMediaSourceStore } from "@/stores/mediaSourceStore";
import { MediaJobRowView } from "./media/components/MediaJobRow";
import { reportBatchLimited, useMediaJobs } from "./media/hooks/useMediaJobs";
import { mediaJobSample } from "./media/lib/sample";
import { splitSources } from "./media/lib/splitSources";

const _URL_RE = /^https?:\/\/\S+$/i;
const _WIN_PATH_RE = /^[a-z]:[\\/]/i;
const _UNC_PATH_RE = /^\\\\/;
const _POSIX_PATH_RE = /^\//;

function _looksLikeSource(value: string): boolean {
	return (
		_URL_RE.test(value) ||
		_WIN_PATH_RE.test(value) ||
		_UNC_PATH_RE.test(value) ||
		_POSIX_PATH_RE.test(value)
	);
}

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
	const [dragOver, setDragOver] = useState(false);
	const [showInvalid, setShowInvalid] = useState(false);
	const running = activeCount > 0;

	const onClear = useCallback(() => {
		clearSource();
		setShowInvalid(false);
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
			if (atCapacity || running) {
				reportBatchLimited(0, usable.length, maxJobs);
				return;
			}
			void startMany(usable, true);
		});
	}, [atCapacity, running, maxJobs, startMany]);

	const trimmed = source.trim();
	const inputInvalid = trimmed.length > 0 && !_looksLikeSource(trimmed);
	const canStart = trimmed.length > 0 && !atCapacity && !starting && !running;

	const onPasteFromClipboard = useCallback(async () => {
		try {
			const text = await navigator.clipboard.readText();
			if (text) setSource(text.trim());
			setShowInvalid(false);
			inputRef.current?.focus();
		} catch {
			// The webview can deny clipboard reads; leave the field focused so
			// the user can paste with the keyboard instead.
			inputRef.current?.focus();
		}
	}, [setSource]);

	const handleStart = useCallback(async () => {
		if (!canStart) return;
		// Validate on submit only: typing or pasting never nags the user.
		if (inputInvalid) {
			setShowInvalid(true);
			toast.error(t("media.invalidSource"));
			return;
		}
		setShowInvalid(false);
		// One field can name several sources: a pasted list of links becomes
		// one job per link, while a local path with spaces stays ONE source.
		const sources = splitSources(source);
		if (sources.length === 0) return;
		// Subtitles are always preferred now; the backend contract is unchanged.
		const { accepted, refused } = await startMany(sources, true);
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
	}, [canStart, inputInvalid, source, setSource, startMany, t]);

	// Browse goes through the HOST picker: a webview file input hands the
	// renderer only `file.name`, which the backend cannot open (drag-drop is
	// the only web path that carries an absolute path). The host dialog is
	// multi-select and opens with audio AND video visible. There is no
	// `<input type="file">` fallback — submitting bare file names was the
	// `decode_failed` bug this picker exists to fix.
	const onPickFiles = useCallback(async () => {
		if (atCapacity || running) return;
		const api = window.window_;
		if (!api?.pickMediaFiles) {
			toast.info(t("media.pickerUnavailable"), {
				id: "media-picker-unavailable",
			});
			return;
		}
		const picked = await api.pickMediaFiles();
		if (!picked.canceled && picked.paths && picked.paths.length > 0) {
			await startMany(picked.paths, true);
		}
	}, [atCapacity, running, startMany, t]);

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
				const { accepted, refused } = await startMany(sources, true);
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
		[atCapacity, maxJobs, setSource, startMany],
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
						aria-disabled={atCapacity || running}
						onClick={() => void onPickFiles()}
						onDragOver={(e) => {
							e.preventDefault();
							if (!atCapacity && !running) setDragOver(true);
						}}
						onDragLeave={() => setDragOver(false)}
						onDrop={(e) => {
							e.preventDefault();
							setDragOver(false);
							if (atCapacity || running) return;
							const path =
								e.dataTransfer.getData("text/uri-list") ||
								e.dataTransfer.getData("text/plain");
							if (path) setSource(path.replace(/^file:\/\//, ""));
						}}
						className={cn(
							"flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-12 transition-colors",
							"border-border/10 bg-background focus-visible:ring-1 focus-visible:ring-ring",
							dragOver && "border-primary bg-primary/10",
							(atCapacity || running) && "cursor-not-allowed opacity-50",
						)}
					>
						<HugeiconsIcon
							icon={Upload01Icon}
							strokeWidth={1.5}
							className="h-8 w-8 text-muted-foreground"
						/>
						<span className="text-sm text-foreground">
							{dragOver ? t("media.dropRelease") : t("media.dropZoneTitle")}
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
						<div className="min-w-0 flex-1">
							<div className="relative">
								<Input
									id="media-source"
									name="mediaSourceField"
									type="text"
									ref={inputRef}
									value={source}
									onChange={(e) => {
										setSource(e.target.value);
										setShowInvalid(false);
									}}
									onPaste={onPaste}
									placeholder={t("media.sourcePlaceholder")}
									disabled={atCapacity || running}
									aria-invalid={showInvalid}
									// WebView autofill ignores autocomplete=off on some
									// platforms; manager hints and CSS are the cross-platform backstop.
									autoComplete="off"
									autoCorrect="off"
									autoCapitalize="off"
									spellCheck={false}
									data-lpignore="true"
									data-1p-ignore="true"
									data-form-type="other"
									// Only one trailing control is shown at a time.
									className="min-w-0 w-full pe-9"
									onKeyDown={(e) => {
										if (e.key === "Enter") void handleStart();
									}}
								/>
								{source === "" ? (
									<button
										type="button"
										aria-label={t("media.paste")}
										title={t("media.paste")}
										onClick={() => void onPasteFromClipboard()}
										disabled={atCapacity || running}
										className="absolute inset-y-0 end-2 my-auto flex h-5 w-5 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
										data-testid="media-source-paste"
									>
										<HugeiconsIcon
											icon={ClipboardListIcon}
											strokeWidth={2}
											className="h-3.5 w-3.5"
										/>
									</button>
								) : (
									<button
										type="button"
										aria-label={t("media.clearInput")}
										title={t("media.clearInput")}
										onClick={onClear}
										disabled={atCapacity || running}
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
			</div>

			{/* One row per job: same progress card for link and local sources. */}
			{jobs.length > 0 && (
				<div className="flex flex-col rounded-lg border border-border/10 bg-surface-subtle">
					{jobs.map((job, index) => (
						// Measured wrap per row: the fallback reserves the running
						// row's geometry from the job's own identity, so nothing
						// invented (source/percent) is ever painted in place of the
						// link the user just pasted.
						<Skeleton
							key={job.clientId}
							data={job.phase === "starting" ? null : job}
							sample={mediaJobSample(job)}
							id={`media-job-${job.clientId}`}
							label={skeletonLoadingLabel()}
						>
							{(d) => (
								<MediaJobRowView
									job={d}
									first={index === 0}
									onCancel={() => void cancel(job.jobId)}
									onDismiss={() => dismiss(job.clientId)}
									onOpenHistory={() => {
										if (job.rowId !== null) {
											sessionStorage.setItem(
												"lausu.history.highlight",
												String(job.rowId),
											);
										}
										navigate("history");
									}}
								/>
							)}
						</Skeleton>
					))}
				</div>
			)}
		</div>
	);
}
