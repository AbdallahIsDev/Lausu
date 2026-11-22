import {
	Copy01Icon,
	Delete01Icon,
	Film01Icon,
	StarIcon,
	Tick02Icon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import {
	Fragment,
	memo,
	type KeyboardEvent as ReactKeyboardEvent,
	useCallback,
	useEffect,
	useLayoutEffect,
	useRef,
	useState,
} from "react";
import { toast } from "sonner";
import { Modal, ModalFooter } from "@/components/common/Modal";
import {
	formatRecordTime,
	groupRecordsByDate,
} from "@/components/dashboard/historyGroups";
import { Button } from "@/components/ui/button";
import { ToggleGroup } from "@/components/ui/toggle-group";
import { getLocale, t } from "@/i18n/i18n";
import {
	countWords,
	formatElapsedShort,
	formatMediaDuration,
} from "@/lib/format";
import { cn } from "@/lib/utils";
import { formatSourceDisplayName } from "@/lib/utils/format";
import type { HistoryRecord } from "@/types/ipc";

/**
 * Which version of a transcription the modal is showing.
 *
 * `final` is the default on every open (and every close resets to it).
 * `original` and `compare` only exist for rows that carry a
 * pre-translation original; the list projection reports that up front
 * (`has_original`), so no row ever offers an empty view.
 */
type TranscriptView = "final" | "original" | "compare";

/** Exit duration before the swap; mirrors `.history-view-out` in index.css. */
const VIEW_EXIT_MS = 160;

/** Transcript content-box clamp, as a fraction of the viewport height. */
const MIN_BOX_VH = 0.25;
const MAX_BOX_VH = 0.55;

function formatTimestamp(ts: string): string {
	try {
		const d = new Date(ts);
		// Use the selected UI locale, not the browser default.
		return (
			d.toLocaleDateString(getLocale(), { month: "short", day: "numeric" }) +
			" · " +
			d.toLocaleTimeString(getLocale(), { hour: "2-digit", minute: "2-digit" })
		);
	} catch {
		return ts;
	}
}

function isMedia(item: HistoryRecord): boolean {
	return item.kind === "media";
}

function sourceLabel(item: HistoryRecord): string | null {
	switch (item.source_type) {
		case "youtube":
			return t("media.metaYoutube");
		case "file":
			return t("media.metaLocalFile");
		case "url":
			return t("media.metaWebsite");
		default:
			return null;
	}
}

function methodLabel(method: string | null | undefined): string | null {
	if (method === "subtitles") return t("media.metaSubtitles");
	if (method === "transcription") return t("media.metaTranscription");
	return null;
}

interface MetaPiece {
	key: string;
	text: string;
}

function metaPieces(item: HistoryRecord, grouped: boolean): MetaPiece[] {
	const pieces: MetaPiece[] = [];
	const push = (key: string, text: string) => pieces.push({ key, text });
	push(
		"time",
		grouped
			? formatRecordTime(item.timestamp)
			: formatTimestamp(item.timestamp),
	);
	const words = item.word_count ?? countWords(item.text);
	if (Number.isFinite(words)) {
		push("words", t("activityList.wordsCount", { count: String(words) }));
	}
	const seconds = isMedia(item)
		? (item.media_duration_seconds ?? item.duration)
		: item.duration;
	if (seconds != null && Number.isFinite(seconds)) {
		push("duration", formatMediaDuration(seconds));
	}
	if (
		item.processing_seconds != null &&
		Number.isFinite(item.processing_seconds)
	) {
		push("processing", formatElapsedShort(item.processing_seconds));
	}
	if (item.model?.trim()) push("model", formatSourceDisplayName(item.model));
	const source = sourceLabel(item);
	if (source) push("source", source);
	const method = methodLabel(item.method);
	if (method) push("method", method);
	return pieces;
}

interface ActivityListProps {
	items: HistoryRecord[];
	lineClamp?: number;
	title?: string;
	showViewAll?: boolean;
	onViewAll?: () => void;
	onDelete?: (id: number) => void;
	onToggleFavorite?: (id: number) => void;
	groupByDate?: boolean;
	onFetchFullText?: (id: number) => Promise<string | null>;
	/** Optional richer fetch that keeps the pre-translation original text. */
	onFetchFullRecord?: (id: number) => Promise<{
		text: string;
		original_text?: string;
	} | null>;
	hideHeader?: boolean;
	/** Row to briefly ring + scroll into view (cross-surface handoff). */
	highlightId?: number | null;
}

interface ActivityListRowProps {
	item: HistoryRecord;
	copied: boolean;
	lineClamp: number;
	grouped: boolean;
	highlighted: boolean;
	onCopy: (item: HistoryRecord) => void;
	onOpen: (item: HistoryRecord) => void;
	onDelete?: (id: number) => void;
	onToggleFavorite?: (id: number) => void;
}

const ActivityListRow = memo(function ActivityListRow({
	item,
	copied,
	lineClamp,
	grouped,
	highlighted,
	onCopy,
	onOpen,
	onDelete,
	onToggleFavorite,
}: ActivityListRowProps) {
	const rowRef = useRef<HTMLDivElement>(null);
	const media = isMedia(item);
	const pieces = metaPieces(item, grouped);
	const sourceTitle = item.source_title?.trim() || item.file_name?.trim() || "";
	const thumbnail = item.thumbnail_url?.trim() || "";
	const clampClass = lineClamp >= 3 ? "line-clamp-3" : "line-clamp-2";

	useEffect(() => {
		if (highlighted) {
			rowRef.current?.scrollIntoView?.({ block: "center", behavior: "smooth" });
		}
	}, [highlighted]);

	const handlePreviewKeyDown = useCallback(
		(e: ReactKeyboardEvent<HTMLDivElement>) => {
			if (e.key === "Enter" || e.key === " ") {
				e.preventDefault();
				onOpen(item);
			}
		},
		[onOpen, item],
	);

	return (
		<div
			ref={rowRef}
			data-history-row-id={item.id}
			className={`flex flex-col gap-2 px-4 py-2.5 transition-colors ${
				highlighted ? "bg-primary/5 ring-1 ring-primary" : ""
			}`}
		>
			<div className="flex min-w-0 flex-col gap-1">
				{/* biome-ignore lint/a11y/useSemanticElements: a native <button> blocks text selection inside the transcript */}
				<div
					dir="auto"
					role="button"
					tabIndex={0}
					aria-label={t("history.viewTranscript")}
					data-testid="activity-row-preview"
					onClick={() => onOpen(item)}
					onKeyDown={handlePreviewKeyDown}
					className={`${clampClass} cursor-pointer whitespace-pre-wrap wrap-break-word text-sm leading-snug text-foreground transition-colors hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-hidden`}
				>
					{item.text}
				</div>
			</div>

			{media && (sourceTitle || thumbnail) && (
				<div className="flex min-w-0 items-center gap-2">
					{thumbnail && (
						<img
							src={thumbnail}
							alt=""
							className="size-10 shrink-0 rounded-lg object-cover"
							onError={(e) => {
								e.currentTarget.hidden = true;
							}}
						/>
					)}
					{sourceTitle && (
						<span
							className="min-w-0 flex-1 truncate text-xs font-medium text-foreground"
							title={sourceTitle}
						>
							{sourceTitle}
						</span>
					)}
				</div>
			)}

			<div className="flex min-w-0 flex-wrap items-center justify-between gap-x-2 gap-y-1">
				<div
					data-testid="activity-row-meta"
					className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-muted-foreground"
				>
					{media && (
						<span className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-border/8 bg-surface px-1.5 py-0.5 text-[10px] font-medium leading-none text-muted-foreground">
							<HugeiconsIcon
								icon={Film01Icon}
								strokeWidth={2}
								className="size-3"
							/>
							{t("history.mediaBadge")}
						</span>
					)}
					{pieces.map((piece, i) => (
						<Fragment key={piece.key}>
							{i > 0 && (
								<span aria-hidden="true" className="shrink-0">
									·
								</span>
							)}
							<span
								className={i === 0 ? "min-w-0 truncate" : "whitespace-nowrap"}
							>
								{piece.text}
							</span>
						</Fragment>
					))}
				</div>
				<div className="flex shrink-0 items-center gap-1">
					<Button
						variant="ghost"
						size="icon-xs"
						onClick={(e) => {
							e.stopPropagation();
							onCopy(item);
						}}
						className="shrink-0 text-muted-foreground hover:text-foreground"
						title={t("history.copyText")}
						aria-label={t("history.copyText")}
					>
						{copied ? (
							<HugeiconsIcon
								icon={Tick02Icon}
								strokeWidth={2.5}
								className="h-4 w-4"
							/>
						) : (
							<HugeiconsIcon
								icon={Copy01Icon}
								strokeWidth={2.5}
								className="h-4 w-4"
							/>
						)}
					</Button>
					{onToggleFavorite && (
						<Button
							variant="ghost"
							size="icon-xs"
							onClick={(e) => {
								e.stopPropagation();
								onToggleFavorite(item.id);
							}}
							className="shrink-0 text-muted-foreground hover:text-warning"
							title={
								item.favorite
									? t("activityList.removeFromFavorites")
									: t("activityList.addToFavorites")
							}
							aria-label={
								item.favorite
									? t("activityList.removeFromFavorites")
									: t("activityList.addToFavorites")
							}
						>
							<HugeiconsIcon
								icon={StarIcon}
								strokeWidth={2.5}
								fill={item.favorite ? "currentColor" : "none"}
								className={`h-4 w-4 ${item.favorite ? "text-warning" : ""}`}
							/>
						</Button>
					)}
					{onDelete && (
						<Button
							variant="ghost"
							size="icon-xs"
							onClick={(e) => {
								e.stopPropagation();
								onDelete(item.id);
							}}
							className="shrink-0 text-muted-foreground hover:text-destructive"
							title={t("common.delete")}
							aria-label={t("history.deleteEntry")}
						>
							<HugeiconsIcon
								icon={Delete01Icon}
								strokeWidth={2.5}
								className="h-4 w-4"
							/>
						</Button>
					)}
				</div>
			</div>
		</div>
	);
});

function ActivityListInner({
	items,
	lineClamp = 2,
	title = t("home.recentActivity"),
	showViewAll = false,
	onViewAll,
	onDelete,
	onToggleFavorite,
	groupByDate = false,
	onFetchFullText,
	onFetchFullRecord,
	hideHeader = false,
	highlightId = null,
}: ActivityListProps) {
	const [copiedId, setCopiedId] = useState<number | null>(null);
	const [viewing, setViewing] = useState<{
		item: HistoryRecord;
		text: string;
		originalText?: string;
	} | null>(null);
	// Displayed version. `view` is the content on screen; `leaving` runs
	// the blur-out before the swap, so the outgoing text is what animates
	// out and the incoming one animates in (no cross-fade, no opacity).
	const [view, setView] = useState<TranscriptView>("final");
	const [leaving, setLeaving] = useState(false);
	// Content-box height in px, clamped to [25vh, 55vh] and animated. A
	// MEASURED pixel height (never `auto`) is what makes it transitionable;
	// `null` means "not measured yet" and the CSS floor/ceiling take over.
	const [boxHeight, setBoxHeight] = useState<number | null>(null);
	const boxRef = useRef<HTMLDivElement | null>(null);
	const pendingViewRef = useRef<TranscriptView | null>(null);
	const swapTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const viewerTokenRef = useRef(0);
	const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	// Track the content's own layout height and clamp it. Runs before paint
	// so opening a row never flashes a wrong height, and a ResizeObserver
	// catches text that arrives late (a cache miss), font swaps and window
	// resizes. The observed node is the CONTENT, not the scroll box, so the
	// height transition can never feed back into the measurement.
	useLayoutEffect(() => {
		// Nothing to measure while the dialog is closed. `viewing` also changes
		// when a late full-record fetch replaces the text, re-running the clamp.
		if (!viewing) return;
		const box = boxRef.current;
		// The content node is keyed by `view`, so it remounts on every mode
		// switch. Re-query it here (instead of holding a stale ref) so both
		// `view` and `viewing` are genuinely read and the observer follows the
		// live node, including late-arriving text (cache miss).
		if (!box) return;
		const content = box.querySelector<HTMLElement>(`[data-view="${view}"]`);
		if (!content) return;
		const apply = (): void => {
			const min = window.innerHeight * MIN_BOX_VH;
			const max = window.innerHeight * MAX_BOX_VH;
			// offsetHeight is layout height: unaffected by the scale/blur
			// transform the switch animation applies. The scroll box carries
			// p-4, so its own height must include that vertical padding or
			// the last text line would be clipped/scrolled unnecessarily.
			const padding =
				parseFloat(getComputedStyle(box).paddingTop) +
				parseFloat(getComputedStyle(box).paddingBottom);
			const natural = content.offsetHeight + (padding || 0);
			const next = Math.min(Math.max(natural, min), max);
			setBoxHeight(Math.round(next));
		};
		apply();
		const observer = new ResizeObserver(apply);
		observer.observe(content);
		window.addEventListener("resize", apply);
		return () => {
			observer.disconnect();
			window.removeEventListener("resize", apply);
		};
	}, [view, viewing]);

	const prefersReducedMotion = useCallback((): boolean => {
		if (
			typeof window === "undefined" ||
			typeof window.matchMedia !== "function"
		)
			return false;
		return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
	}, []);

	const resetView = useCallback(() => {
		if (swapTimerRef.current !== null) {
			clearTimeout(swapTimerRef.current);
			swapTimerRef.current = null;
		}
		pendingViewRef.current = null;
		setLeaving(false);
		setView("final");
	}, []);

	// Swap request. Rapid clicks retarget the pending view instead of
	// stacking a second exit, so the content never goes stale or
	// overlaps two animations.
	const requestView = useCallback(
		(next: TranscriptView) => {
			if (prefersReducedMotion()) {
				if (swapTimerRef.current !== null) {
					clearTimeout(swapTimerRef.current);
					swapTimerRef.current = null;
				}
				pendingViewRef.current = null;
				setLeaving(false);
				setView(next);
				return;
			}
			pendingViewRef.current = next;
			if (leaving) return;
			setLeaving(true);
			swapTimerRef.current = setTimeout(() => {
				swapTimerRef.current = null;
				const target = pendingViewRef.current ?? next;
				pendingViewRef.current = null;
				setView(target);
				setLeaving(false);
			}, VIEW_EXIT_MS);
		},
		[leaving, prefersReducedMotion],
	);

	useEffect(() => {
		return () => {
			if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
			if (swapTimerRef.current !== null) clearTimeout(swapTimerRef.current);
		};
	}, []);

	const handleCopy = useCallback(async (item: HistoryRecord) => {
		try {
			await navigator.clipboard.writeText(item.text);
			setCopiedId(item.id);
			toast.success(t("history.copiedToClipboard"));
			if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
			copyTimeoutRef.current = setTimeout(() => setCopiedId(null), 2000);
		} catch {
			toast.error(t("activityList.failedToCopy"));
		}
	}, []);

	const closeViewer = useCallback(() => {
		viewerTokenRef.current += 1;
		// Every open starts on Final, and every close returns to it.
		resetView();
		setViewing(null);
	}, [resetView]);

	const openViewer = useCallback(
		(item: HistoryRecord) => {
			const token = ++viewerTokenRef.current;
			resetView();
			setViewing({ item, text: item.text });
			// The richer fetch is used when available so a translated row can
			// reveal its raw ASR text. Keep the older string-only callback for
			// callers that never supply it (Dashboard, tests).
			const fetcher = onFetchFullRecord ?? onFetchFullText;
			// A translated row can have a short final text (not truncated) yet
			// still carry a raw original worth revealing. The richer callback
			// always fetches; the legacy string-only one keeps its old
			// truncated-only behaviour for callers/tests that never supply it.
			if (!fetcher) return;
			if (!onFetchFullRecord && item.text_truncated !== true) return;
			void fetcher(item.id)
				.then((full) => {
					if (token !== viewerTokenRef.current) return;
					if (typeof full === "string" ? full === "" : full == null) {
						toast.error(t("activityList.loadTextFailed"));
						return;
					}
					const text = typeof full === "string" ? full : full?.text || "";
					const originalText =
						typeof full === "string" ? undefined : full?.original_text;
					setViewing((current) =>
						current && token === viewerTokenRef.current
							? { ...current, text, originalText }
							: current,
					);
				})
				.catch(() => {
					if (token === viewerTokenRef.current) {
						toast.error(t("activityList.loadTextFailed"));
					}
				});
		},
		[onFetchFullRecord, onFetchFullText, resetView],
	);

	// Copy follows the visible selection: Final copies the processed
	// text, Original the raw one, Compare both with explicit labels.
	const copyViewerText = useCallback(() => {
		if (!viewing) return;
		const finalText = viewing.text;
		const originalText = viewing.originalText ?? "";
		const payload =
			view === "original" && originalText !== ""
				? originalText
				: view === "compare" && originalText !== ""
					? `${t("history.viewFinal")}:\n${finalText}\n\n${t("history.viewOriginal")}:\n${originalText}`
					: finalText;
		void handleCopy({ ...viewing.item, text: payload });
	}, [viewing, view, handleCopy]);

	const viewerTitle = viewing
		? isMedia(viewing.item)
			? viewing.item.source_title?.trim() ||
				viewing.item.file_name?.trim() ||
				formatTimestamp(viewing.item.timestamp)
			: formatTimestamp(viewing.item.timestamp)
		: "";

	// Original/Compare only exist when the row actually carries a raw
	// version. `has_original` comes from the list projection, so the
	// selector never offers an empty view (and a row without one keeps
	// the footer at just Copy).
	const originalText = viewing?.originalText ?? "";
	const viewOptions: { value: TranscriptView; label: string }[] | null =
		originalText === ""
			? null
			: [
					{ value: "final", label: t("history.viewFinal") },
					{ value: "original", label: t("history.viewOriginal") },
					{ value: "compare", label: t("history.viewCompare") },
				];

	// One content tree per mode. Both versions use the SAME
	// `text-foreground` colour in every mode — the version is conveyed by
	// the label and position, never by dimming one of them.
	const transcriptBody =
		view === "compare" ? (
			<div className="flex flex-col gap-4">
				<section>
					<p className="mb-1 text-xs font-medium text-muted-foreground">
						{t("history.viewFinal")}
					</p>
					<div
						dir="auto"
						data-testid="transcript-modal-final"
						className="whitespace-pre-wrap wrap-break-word text-sm leading-relaxed text-foreground [text-wrap:auto]"
					>
						{viewing?.text ?? ""}
					</div>
				</section>
				<section>
					<p className="mb-1 text-xs font-medium text-muted-foreground">
						{t("history.viewOriginal")}
					</p>
					<div
						dir="auto"
						data-testid="transcript-modal-original"
						className="whitespace-pre-wrap wrap-break-word text-sm leading-relaxed text-foreground [text-wrap:auto]"
					>
						{originalText}
					</div>
				</section>
			</div>
		) : (
			<div
				dir="auto"
				data-testid={
					view === "original"
						? "transcript-modal-original"
						: "transcript-modal-final"
				}
				className="whitespace-pre-wrap wrap-break-word text-sm leading-relaxed text-foreground [text-wrap:auto]"
			>
				{view === "original" ? originalText : (viewing?.text ?? "")}
			</div>
		);

	const modal = (
		<Modal
			open={viewing !== null}
			onClose={closeViewer}
			title={viewerTitle}
			size="lg"
		>
			{/* Surface with a content-driven height clamped to [25vh, 55vh]
			    and its OWN scrollbar: the modal header and the footer (toggle
			    + Copy) never move, and Compare shares this same scroll area
			    instead of growing the dialog. The measured px height animates;
			    the outer CSS min/max are the pre-measure fallback. */}
			<div
				ref={boxRef}
				dir="auto"
				data-testid="transcript-modal-text"
				style={boxHeight === null ? undefined : { height: boxHeight }}
				className="history-content-height min-h-[25vh] max-h-[55vh] overflow-y-auto overscroll-contain rounded-lg bg-foreground/8 p-4 [text-wrap:auto]"
			>
				<div
					key={view}
					data-view={view}
					className={cn(
						"origin-center will-change-[filter,transform]",
						leaving ? "history-view-out" : "history-view-in",
					)}
				>
					{transcriptBody}
				</div>
			</div>
			<ModalFooter className="sm:items-center sm:justify-between">
				{viewOptions ? (
					<ToggleGroup<TranscriptView>
						options={viewOptions}
						value={view}
						onChange={requestView}
						ariaLabel={t("history.viewModeAria")}
					/>
				) : (
					<span aria-hidden="true" />
				)}
				<Button
					variant="outline"
					size="sm"
					title={t("history.copyText")}
					onClick={copyViewerText}
					className="gap-2"
				>
					<HugeiconsIcon
						icon={
							viewing && copiedId === viewing.item.id ? Tick02Icon : Copy01Icon
						}
						strokeWidth={2.5}
						className="h-4 w-4"
					/>
					{t("history.copyText")}
				</Button>
			</ModalFooter>
		</Modal>
	);

	if (items.length === 0) {
		return (
			<>
				<div className="flex w-full flex-col gap-3 [text-wrap:auto]">
					{!hideHeader && (
						<div className="flex items-end justify-between w-full">
							<span className="text-xs font-medium text-foreground">
								{title}
							</span>
							{showViewAll && onViewAll && (
								<Button
									onClick={onViewAll}
									variant="link"
									size="xs"
									className="text-xs font-medium text-muted-foreground hover:text-foreground"
								>
									{t("activityList.viewAll")}
								</Button>
							)}
						</div>
					)}
					<div className="rounded-lg border border-border/8 bg-surface-subtle">
						<p className="px-3.5 py-4 text-center text-xs text-muted-foreground">
							{t("activityList.noRecentActivity")}
						</p>
					</div>
				</div>
				{modal}
			</>
		);
	}

	const groups = groupByDate ? groupRecordsByDate(items) : null;

	const renderRow = (item: HistoryRecord, grouped: boolean) => (
		<ActivityListRow
			key={item.id}
			item={item}
			copied={copiedId === item.id}
			lineClamp={lineClamp}
			grouped={grouped}
			highlighted={highlightId === item.id}
			onCopy={handleCopy}
			onOpen={openViewer}
			onDelete={onDelete}
			onToggleFavorite={onToggleFavorite}
		/>
	);

	return (
		<>
			<div className="flex w-full flex-col gap-3 [text-wrap:auto]">
				{!hideHeader && (
					<div className="flex items-end justify-between w-full">
						<span className="text-xs font-medium text-foreground">{title}</span>
						{showViewAll && onViewAll && (
							<Button
								onClick={onViewAll}
								variant="link"
								size="xs"
								className="text-xs font-medium text-muted-foreground hover:text-foreground"
							>
								{t("activityList.viewAll")}
							</Button>
						)}
					</div>
				)}
				{groups ? (
					<div className="flex w-full flex-col gap-4">
						{groups.map((group, gi) => (
							<section
								key={group.key || `unknown-date-${gi}`}
								aria-labelledby={
									group.label ? `history-date-${group.key}` : undefined
								}
								className="rounded-lg border border-border/8 bg-surface-subtle"
							>
								{group.label && (
									<div className="px-4 pt-3 pb-1">
										<h2
											id={`history-date-${group.key}`}
											className="text-xs font-medium tracking-wide text-muted-foreground"
										>
											{group.label}
										</h2>
									</div>
								)}
								<div className="divide-y divide-border/8">
									{group.records.map((record) =>
										renderRow(record, !!group.label),
									)}
								</div>
							</section>
						))}
					</div>
				) : (
					<div className="rounded-lg border border-border/8 bg-surface-subtle divide-y divide-border/8">
						{items.map((item) => renderRow(item, false))}
					</div>
				)}
			</div>
			{modal}
		</>
	);
}

export default memo(ActivityListInner);
