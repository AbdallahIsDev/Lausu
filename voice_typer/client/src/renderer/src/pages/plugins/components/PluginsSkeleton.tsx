// Plugins page loading skeleton (full page).
// Mirrors the loaded Plugins layout (`pages/Plugins.tsx`): page shell →
// heading → the 2-per-row compact card grid. Each placeholder is a
// horizontal row card with the same internal structure as the real card
// (initial tile, name line, status line), so the loading → loaded
// transition does not shift.

import { HeadingSkeleton, PageShell } from "@/components/feedback/skeletons";
import { Skeleton } from "@/components/ui/skeleton";

const CARD_IDS = [
	"plugin-card-0",
	"plugin-card-1",
	"plugin-card-2",
	"plugin-card-3",
];

export function PluginsSkeleton() {
	return (
		<PageShell>
			<HeadingSkeleton />
			<div className="grid grid-cols-2 gap-4">
				{CARD_IDS.map((id) => (
					<div
						key={id}
						className="flex items-center gap-3 rounded-lg border border-border/8 bg-surface-subtle p-2"
					>
						<Skeleton className="size-10 shrink-0 rounded-lg" />
						<div className="flex min-w-0 flex-1 flex-col gap-1">
							<Skeleton className="h-4 w-24" />
							<Skeleton className="h-3 w-16" />
						</div>
					</div>
				))}
			</div>
		</PageShell>
	);
}
