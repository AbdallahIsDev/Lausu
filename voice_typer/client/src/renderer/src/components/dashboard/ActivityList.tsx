import {
	Copy01Icon,
	Delete01Icon,
	Film01Icon,
	Mic02Icon,
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
import { getLocale, t } from "@/i18n/i18n";
import {
	countWords,
	formatElapsedShort,
	formatMediaDuration,
} from "@/lib/format";
import type { HistoryRecord } from "@/types/ipc";

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
	if (item.model?.trim()) push("model", item.model);
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
	const previewRef = useRef<HTMLDivElement>(null);
	const rowRef = useRef<HTMLDivElement>(null);
	const [truncated, setTruncated] = useState(false);
	const media = isMedia(item);
	const pieces = metaPieces(item, grouped);
	const sourceTitle = item.source_title?.trim() || item.file_name?.trim() || "";
	const thumbnail = item.thumbnail_url?.trim() || "";
	const clampClass = lineClamp >= 3 ? "line-clamp-3" : "line-clamp-2";

	// Line-clamp doesn't expose a "was truncated" flag, measure the rendered
	// block against its clamped box instead. ResizeObserver catches the
	// panel/zoom changes that flip the verdict without a text change.
	// biome-ignore lint/correctness/useExhaustiveDependencies: re-measure on transcript/clamp change
	useEffect(() => {
		const el = previewRef.current;
		if (!el) return;
		const measure = () => setTruncated(el.scrollHeight > el.clientHeight + 1);
		measure();
		if (typeof ResizeObserver === "undefined") return;
		const observer = new ResizeObserver(measure);
		observer.observe(el);
		return () => observer.disconnect();
	}, [item.text, clampClass]);

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
			<div className="flex min-w-0 flex-wrap items-center justify-between gap-x-2 gap-y-1">
				<div
					data-testid="activity-row-meta"
					className="flex min-w-0 flex-1 flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-muted-foreground"
				>
					<span className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-border/8 bg-surface px-1.5 py-0.5 text-[10px] font-medium leading-none text-muted-foreground">
						<HugeiconsIcon
							icon={media ? Film01Icon : Mic02Icon}
							strokeWidth={2}
							className="size-3"
						/>
						{media ? t("history.mediaBadge") : t("history.dictationBadge")}
					</span>
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

			<div className="flex min-w-0 flex-col gap-1">
				{/* biome-ignore lint/a11y/useSemanticElements: a native <button> blocks text selection inside the transcript */}
				<div
					ref={previewRef}
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
				{truncated && (
					<button
						type="button"
						onClick={(e) => {
							e.stopPropagation();
							onOpen(item);
						}}
						className="self-start cursor-pointer rounded-lg whitespace-nowrap text-xs leading-snug text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-hidden"
					>
						{t("home.showMore")}
					</button>
				)}
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
	hideHeader = false,
	highlightId = null,
}: ActivityListProps) {
	const [copiedId, setCopiedId] = useState<number | null>(null);
	const [viewing, setViewing] = useState<{
		item: HistoryRecord;
		text: string;
	} | null>(null);
	const viewerTokenRef = useRef(0);
	const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	useEffect(() => {
		return () => {
			if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
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
		setViewing(null);
	}, []);

	const openViewer = useCallback(
		(item: HistoryRecord) => {
			const token = ++viewerTokenRef.current;
			setViewing({ item, text: item.text });
			if (!onFetchFullText || item.text_truncated !== true) return;
			void onFetchFullText(item.id)
				.then((full) => {
					if (token !== viewerTokenRef.current) return;
					if (full == null || full === "") {
						toast.error(t("activityList.loadTextFailed"));
						return;
					}
					setViewing((current) =>
						current && token === viewerTokenRef.current
							? { ...current, text: full }
							: current,
					);
				})
				.catch(() => {
					if (token === viewerTokenRef.current) {
						toast.error(t("activityList.loadTextFailed"));
					}
				});
		},
		[onFetchFullText],
	);

	const copyViewerText = useCallback(() => {
		if (viewing) void handleCopy({ ...viewing.item, text: viewing.text });
	}, [viewing, handleCopy]);

	const viewerTitle = viewing
		? isMedia(viewing.item)
			? viewing.item.source_title?.trim() ||
				viewing.item.file_name?.trim() ||
				formatTimestamp(viewing.item.timestamp)
			: formatTimestamp(viewing.item.timestamp)
		: "";

	const modal = (
		<Modal
			open={viewing !== null}
			onClose={closeViewer}
			title={viewerTitle}
			size="lg"
		>
			<div
				dir="auto"
				data-testid="transcript-modal-text"
				className="max-h-[55vh] overflow-y-auto whitespace-pre-wrap wrap-break-word text-sm leading-relaxed text-foreground [text-wrap:auto]"
			>
				{viewing?.text ?? ""}
			</div>
			<ModalFooter>
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
