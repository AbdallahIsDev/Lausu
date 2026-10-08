// Dashboard loading skeleton.
// Mirrors the loaded Dashboard layout (`pages/Dashboard.tsx`): shell
// (gap-6) → PageHeading with an action row (share + refresh icon
// buttons) → the merged stat card (ONE bordered surface, three
// `min-h-24` p-3 cells divided by rules, icon+label row on top, value
// pinned bottom via mt-auto) → the activity chart card (one-line
// title/range header, h-36 plot with y-axis + 7 bars + x-label row) → the
// derived-metrics QuickInfo row (`sm:grid-cols-3`).
// The range selector is NOT mirrored here: it lives in the app title
// bar, which renders immediately and is outside this page's tree. The
// heatmap card below the activity chart is not mirrored either — it has
// never been part of this skeleton.
// The root stays a `<section aria-busy>` (NOT a live region): the
// live-region guard test (`data-pages-live-region-guards.test.tsx`)
// pins the first-paint skeleton at ZERO live regions, the hydrated
// page owns the announcements.

import { HeadingSkeleton } from "@/components/feedback/skeletons";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n/i18n";

const STAT_IDS = ["dash-stat-0", "dash-stat-1", "dash-stat-2"];
const BAR_HEIGHTS = ["h-16", "h-28", "h-20", "h-24", "h-32", "h-12", "h-20"];
const CHART_LABEL_IDS = [
	"dash-x-0",
	"dash-x-1",
	"dash-x-2",
	"dash-x-3",
	"dash-x-4",
	"dash-x-5",
	"dash-x-6",
];
const DERIVED_IDS = ["dash-derived-0", "dash-derived-1", "dash-derived-2"];

function StatCardSkeleton() {
	// Chrome-less: the cell sits inside the merged group below, which
	// owns the radius/border/background, so only the padding lives here.
	return (
		<div className="flex min-h-24 flex-col gap-2 p-3">
			<div className="flex min-w-0 items-center gap-2">
				<Skeleton className="h-5 w-5 shrink-0" />
				<Skeleton className="h-4 w-16" />
			</div>
			<div className="mt-auto flex items-end justify-between gap-2">
				<Skeleton className="h-8 w-16" />
				<Skeleton className="h-3 w-8 shrink-0" />
			</div>
		</div>
	);
}

function QuickInfoCardSkeleton() {
	return (
		<div className="flex items-stretch gap-3 rounded-lg border border-border/8 bg-surface-subtle p-4">
			<Skeleton className="h-5 w-5 shrink-0" />
			<div className="flex min-w-0 flex-1 flex-col gap-2">
				<Skeleton className="h-3 w-14" />
				<Skeleton className="mt-auto h-5 w-20" />
			</div>
		</div>
	);
}

export function DashboardSkeleton() {
	return (
		<section
			aria-label={t("analytics.loadingAria")}
			aria-busy="true"
			className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-6 px-16 pt-20 pb-6"
		>
			{/* The heading's action row: the share trigger and the refresh
			    button, both `size="icon"` (36px) squares. Reserving them
			    here keeps the stat card from jumping up when the heading
			    hydrates with its actions. */}
			<HeadingSkeleton
				action={
					<>
						<Skeleton className="h-9 w-9 rounded-lg" />
						<Skeleton className="h-9 w-9 rounded-lg" />
					</>
				}
			/>
			<div className="grid grid-cols-1 divide-y divide-border/8 overflow-hidden rounded-lg border border-border/8 bg-surface-subtle md:grid-cols-3 md:divide-x md:divide-y-0">
				{STAT_IDS.map((id) => (
					<StatCardSkeleton key={id} />
				))}
			</div>
			<div className="flex flex-col gap-4 rounded-lg border border-border/8 bg-surface-subtle p-4">
				{/* Header mirrors the activity card's: title and range/unit on
			    ONE baseline, no icon chip — the chip this block used to
			    reserve was removed from the card, and a skeleton taller
			    than the thing it stands in for is a layout shift on
			    hydration. */}
				<div className="flex items-baseline justify-between gap-3">
					<Skeleton className="h-5 w-20" />
					<Skeleton className="h-4 w-24 shrink-0" />
				</div>
				<div className="flex items-end gap-3">
					<Skeleton className="h-36 w-7" />
					<div className="flex flex-1 items-end gap-2">
						{BAR_HEIGHTS.map((height, i) => (
							<Skeleton
								// biome-ignore lint/suspicious/noArrayIndexKey: static bar-height list, order never changes
								key={`dash-bar-${i}`}
								className={`w-full max-w-8 rounded-t-[4px] ${height}`}
							/>
						))}
					</div>
				</div>
				<div className="flex gap-2">
					{CHART_LABEL_IDS.map((id) => (
						<Skeleton key={id} className="mx-auto h-3 w-8" />
					))}
				</div>
			</div>
			<div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
				{DERIVED_IDS.map((id) => (
					<QuickInfoCardSkeleton key={id} />
				))}
			</div>
		</section>
	);
}
