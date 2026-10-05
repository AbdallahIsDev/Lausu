// Plugins page loading skeleton (full page).
// Mirrors the loaded Plugins layout (`pages/Plugins.tsx`): page shell →
// heading → the 3-per-row square card grid. Each placeholder is a square
// `aspect-square` tile with the same internal stack as the real card
// (icon tile, name line, two description lines, status pill), so the
// loading → loaded transition does not shift.

import {
	HeadingSkeleton,
	PageShell,
	PillSkeleton,
} from "@/components/feedback/skeletons";
import { Skeleton } from "@/components/ui/skeleton";

const CARD_IDS = ["plugin-card-0", "plugin-card-1", "plugin-card-2"];

export function PluginsSkeleton() {
	return (
		<PageShell>
			<HeadingSkeleton />
			<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
				{CARD_IDS.map((id) => (
					<div
						key={id}
						className="flex aspect-square flex-col gap-3 rounded-lg border border-border/8 bg-surface-subtle p-4"
					>
						<Skeleton className="size-10 shrink-0 rounded-lg" />
						<div className="flex flex-col gap-2">
							<Skeleton className="h-5 w-32" />
							<Skeleton className="h-4 w-full" />
							<Skeleton className="h-4 w-3/4" />
						</div>
						<div className="flex items-center gap-2">
							<PillSkeleton className="h-6 w-20" />
						</div>
					</div>
				))}
			</div>
		</PageShell>
	);
}
