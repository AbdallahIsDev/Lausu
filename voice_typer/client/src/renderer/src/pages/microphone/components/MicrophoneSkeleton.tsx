// Microphone page loading skeleton (full page).
// Mirrors the loaded Microphone layout (`pages/Microphone.tsx`):
// page shell → heading → `gap-4` content group with
//   1. the ActiveMicrophoneCard cluster (`gap-3`): the test card
//      (`rounded-lg border-border/8 bg-surface-subtle`: header row,
//      the h-1.5 LevelBar track, the controls row) followed by the
//      PresetAccordionSelector card (`rounded-lg` card, label + help
//      icon + enable-Switch row),
//   2. the AvailableMicrophonesList section (h2 + a `rounded-lg` radio
//      card of `px-4 py-2.5` rows: mic icon, name + description lines,
//      trailing radio).

import {
	HeadingSkeleton,
	PageShell,
	PillSkeleton,
	RadioSkeleton,
} from "@/components/feedback/skeletons";
import { Skeleton } from "@/components/ui/skeleton";

const DEVICE_ROW_IDS = ["mic-row-0", "mic-row-1", "mic-row-2"];

export function MicrophoneSkeleton() {
	return (
		<PageShell>
			<HeadingSkeleton />
			<div className="flex flex-col gap-4">
				<div className="flex flex-col gap-3">
					<div className="flex flex-col overflow-hidden rounded-lg border border-border/8 bg-surface-subtle">
						<div className="flex items-start justify-center flex-col gap-3 min-w-0">
							<Skeleton className="h-4 w-4 shrink-0" />
							<div className="flex min-w-0 flex-col">
								<Skeleton className="h-5 w-36" />
								<Skeleton className="h-4 w-48" />
							</div>
						</div>
						<div className="px-4 pb-3">
							<Skeleton className="h-1.5 w-full rounded-full" />
						</div>
						<div className="flex items-center gap-3 border-t border-border/8 px-4 py-2.5">
							<PillSkeleton className="w-28" />
							<Skeleton className="ms-auto h-4 w-12" />
						</div>
					</div>
					<div className="overflow-hidden rounded-lg border border-border/8 bg-surface-subtle">
						<div className="flex items-center gap-3 px-4 py-2.5">
							<div className="flex min-w-0 items-center gap-2">
								<Skeleton className="h-4 w-36" />
								<Skeleton className="size-4 rounded-full" />
							</div>
							<Skeleton className="ms-auto h-5 w-11 shrink-0 rounded-full" />
						</div>
					</div>
				</div>
				<div className="flex flex-col gap-2">
					<Skeleton className="h-6 w-40" />
					<div className="rounded-lg border border-border/8 bg-surface-subtle">
						<div className="divide-y divide-border/8">
							{DEVICE_ROW_IDS.map((id) => (
								<div key={id} className="flex items-center gap-3 px-4 py-2.5">
									<Skeleton className="h-4 w-4 shrink-0" />
									<div className="flex min-w-0 flex-1 flex-col gap-1">
										<Skeleton className="h-5 w-40" />
										<Skeleton className="h-4 w-56" />
									</div>
									<RadioSkeleton />
								</div>
							))}
						</div>
					</div>
				</div>
			</div>
		</PageShell>
	);
}
