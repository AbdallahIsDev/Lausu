import { RefreshIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n/i18n";
import { cn } from "@/lib/utils";

interface LastUpdatedIndicatorProps {
	/** Localized relative label, e.g. "5s ago" or "Just now" (from useLastUpdated). */
	agoLabel: string;
	/** Refresh callback, calls the page's `load*` function. */
	onRefresh: () => void;
	/** True while the refresh is in-flight (disables the button + shows a spinner). */
	refreshing?: boolean;
	/** Optional className override for the wrapping container. */
	className?: string;
}

export function LastUpdatedIndicator({
	agoLabel,
	onRefresh,
	refreshing = false,
	className,
}: LastUpdatedIndicatorProps) {
	return (
		<div
			className={cn(
				"flex items-center text-xs text-muted-foreground",
				className,
			)}
			data-testid="last-updated-indicator"
		>
			{/* No visible text: the elapsed time is redundant next to the data
			    it describes, and the label made this control read as a
			    status line rather than the refresh action it is. The
			    relative time is still announced to assistive tech (and
			    still exposed in the title) so the freshness information is
			    not lost, only de-emphasised visually.
			    While a refresh is in flight the SAME icon spins in place
			    (animate-spin on the unchanged glyph). Swapping in a
			    different element here (e.g. a border-2 Spinner at a
			    different box size) reads as a size/color jump on every
			    click; rotating the mounted icon keeps the box, stroke,
			    and color identical so the only motion is the rotation.
			    The button stays disabled while refreshing (muted +
			    pointer-events-none per the Button base), and its
			    aria-label/title are untouched. */}
			<span aria-live="polite" className="sr-only">
				{t("common.lastUpdatedWithValue", { value: agoLabel })}
			</span>
			{/* Same box + treatment as the adjacent share trigger
			    (`variant="outline" size="icon"`), so the two controls in
			    this cluster read as one row instead of two different
			    sized boxes. */}
			<Button
				variant="outline"
				size="icon"
				onClick={onRefresh}
				disabled={refreshing}
				aria-label={t("common.refreshAria")}
				title={`${t("common.lastUpdatedWithValue", { value: agoLabel })} · ${t("common.refreshAria")}`}
				className="text-muted-foreground hover:text-foreground"
			>
				<HugeiconsIcon
					icon={RefreshIcon}
					strokeWidth={1.625}
					aria-hidden="true"
					className={cn("h-4 w-4 shrink-0", refreshing && "animate-spin")}
				/>
			</Button>
		</div>
	);
}
