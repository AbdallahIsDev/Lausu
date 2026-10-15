// Route-chunk + data prefetching (vercel-react-best-practices:
// bundle-preload; TanStack prefetchQuery / Next.js hover-prefetch).
// The secondary routes are React.lazy chunks (see PageSwitch.tsx).
// Without prefetching, the FIRST navigation to each page waits on a
// dynamic import before anything renders. This module closes that gap:
//   1. `prefetchRouteChunks()`, called once from App after mount, on
//      `requestIdleCallback`, warms every route chunk. The app is a
//      desktop shell (local files, small chunks), so warming all of
//      them at idle is effectively free. Warming RECORDS the resolved
//      module (`pageLoaders.resolvedChunks`), which `<RouteChunk>`
//      renders synchronously — React.lazy on its own still suspends on
//      its first render even when the module is in memory, so the
//      fallback used to flash on every route switch regardless.
//   2. `prefetchPage(page)`, intent-based backup for the idle pass:
//      the Sidebar calls it on nav-item hover/focus so the chunk is
//      already loaded (and recorded) before the click lands, and the
//      page's DATA cache is warmed too, so the click lands on a page
//      that renders its content on the first paint.
// Fire-and-forget: a failed prefetch (dev HMR race, crash) must never
// surface, the normal lazy import path still handles the load.

import type { PrefetchCall } from "@/lib/snapshotCache";
import type { Page } from "@/types/ipc";

import { PAGE_LOADERS, routeChunkLoader } from "./pageLoaders";

let idlePrefetchStarted = false;

type IdleWindow = Window & {
	requestIdleCallback?: (cb: () => void, opts?: { timeout?: number }) => number;
};

export function prefetchRouteChunks(): void {
	if (idlePrefetchStarted) return;
	idlePrefetchStarted = true;
	const run = () => {
		for (const load of Object.values(PAGE_LOADERS)) {
			load().catch(() => {
				// Swallow: the real navigation's lazy import retries.
			});
		}
	};
	const idleWindow = window as IdleWindow;
	if (typeof idleWindow.requestIdleCallback === "function") {
		// Timeout bounds how long "busy" can starve the prefetch —
		// 3s after mount the app is interactive and chunks are small.
		idleWindow.requestIdleCallback(run, { timeout: 3000 });
	} else {
		setTimeout(run, 1500);
	}
}

export function prefetchPage(page: Page): void {
	routeChunkLoader(page)?.().catch(() => {
		// Swallow: the real navigation's lazy import retries.
	});
	prefetchPageData(page);
}

// Data prefetch per page (C-CACHE-4). Dynamic import keeps each page's
// query code out of the main chunk; the callee's own TTL + in-flight
// guards make repeated hovers free, and the mount fetch piggybacks an
// in-flight prefetch instead of duplicating it.
function bridgePrefetchCall(): PrefetchCall | null {
	const bridge = (
		window as unknown as {
			python?: {
				call: (req: {
					type: string;
					data?: Record<string, unknown>;
				}) => Promise<unknown>;
			};
		}
	).python;
	if (!bridge) return null;
	return (type: string, data?: Record<string, unknown>) =>
		bridge.call({ type, data });
}

/** A page's warm-up routine, loaded lazily with its own module. */
type DataPrefetcher = (call: PrefetchCall) => Promise<unknown>;

/** `() => import(module)` thunk that resolves the page's prefetcher. */
type PrefetcherLoader = () => Promise<DataPrefetcher>;

// Pages whose content gates the first paint behind a fetch. A page that
// has no such gate (Media, AboutAndPrivacy, Onboarding) has no entry:
// its chunk is warmed, nothing else is needed.
const PAGE_DATA_PREFETCHERS: Partial<Record<Page, PrefetcherLoader[]>> = {
	analytics: [
		() =>
			import("@/pages/dashboard/hooks/useDashboardData").then(
				(m) => m.prefetchDashboardData,
			),
	],
	history: [
		() =>
			import("@/pages/history/hooks/useHistoryCache").then(
				(m) => m.prefetchHistoryData,
			),
	],
	microphone: [
		() =>
			import("@/pages/microphone/hooks/useMicrophoneData").then(
				(m) => m.prefetchMicrophoneData,
			),
	],
	models: [
		// The disk stat is the expensive leg of the Models page.
		() =>
			import("@/hooks/models/modelStatusCache").then(
				(m) => m.prefetchModelsStatus,
			),
		// …and the config gates the page's first paint (`!config`).
		() =>
			import("@/hooks/models/useModelConfig").then(
				(m) => m.prefetchModelsConfig,
			),
	],
	plugins: [
		() =>
			import("@/pages/plugins/hooks/usePlugins").then(
				(m) => m.prefetchPluginsData,
			),
	],
	settings: [
		() =>
			import("@/components/settings/useSettingsConfig").then(
				(m) => m.prefetchSettingsConfig,
			),
	],
	templates: [
		() =>
			import("@/pages/templates/hooks/useTemplates").then(
				(m) => m.prefetchTemplatesData,
			),
	],
	vocabulary: [
		() =>
			import("@/pages/vocabulary/hooks/useVocabulary").then(
				(m) => m.prefetchVocabularyData,
			),
	],
};

/** The prefetchers backing `page` (every settings-section literal shares
 *  the Settings page's config warm-up). */
function prefetchersFor(page: Page): PrefetcherLoader[] | undefined {
	const direct = PAGE_DATA_PREFETCHERS[page];
	if (direct) return direct;
	if (page.startsWith("settings")) return PAGE_DATA_PREFETCHERS.settings;
	return undefined;
}

function prefetchPageData(page: Page): void {
	const loaders = prefetchersFor(page);
	if (!loaders || loaders.length === 0) return;
	const call = bridgePrefetchCall();
	if (!call) return;
	for (const load of loaders) {
		load()
			.then((run) => run(call))
			.catch(() => {
				// Swallow: the mount fetch stays authoritative.
			});
	}
}
