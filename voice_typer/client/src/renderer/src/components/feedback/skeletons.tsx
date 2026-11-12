// Measured-skeleton primitives. Loading states no longer hand-draw
// page-mirroring boxes: each page wraps its REAL content in
// `<Skeleton data sample>` (skullet/react) and Skullet measures it in
// place, so the skeleton matches the content by construction (the
// zero-shift guarantee the old hand-drawn compositions approximated).
// What remains here is the route-chunk fallback (`RouteSkeleton`,
// shown for at most one frame while a lazy chunk streams, chunks are
// prefetched at idle) and the shared loading label every measured
// wrap passes as `label` (read by assistive tech in place of the
// skeleton).

import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/i18n/i18n";

// The accessible name for every loading state: the localized generic
// loading label, shared by the measured wraps (history, vocabulary,
// models, …) and the route fallback below.
export function skeletonLoadingLabel(): string {
	return t("a11y.loading");
}

// The generic route-chunk fallback for PageSwitch's Suspense boundary.
// Deliberately generic: it shows for at most one frame in practice
// (route chunks are prefetched at idle, see router/prefetch.ts) so it
// renders only the neutral page shell + heading, never a fake page
// body. It is already the fallback, so Skullet has nothing to suspend
// on here and its own status/label would never render; the busy status
// region is owned here instead.
export function RouteSkeleton() {
	return (
		<div
			role="status"
			aria-busy="true"
			className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-6 px-16 pt-20 pb-6"
		>
			<span className="sr-only">{skeletonLoadingLabel()}</span>
			<div className="flex min-w-0 flex-col gap-2">
				<Skeleton width="14rem" height="2rem" />
				<Skeleton width="20rem" height="1.25rem" />
			</div>
		</div>
	);
}
