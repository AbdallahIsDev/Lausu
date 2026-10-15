// router/pageLoaders.ts, the SINGLE lazy-import registry for the
// secondary route chunks.
// declared ten `lazy(() => import("@/pages/X"))` components while
// prefetch.ts kept its own ten-entry `PAGE_LOADERS` map of the SAME
// import specifiers, the two lists could (and did) drift silently.
// This module is now the one source of truth:
//   - `PAGE_LOADERS`, the raw chunk loaders (one `import()` per
//     secondary page). `router/prefetch.ts` warms these at idle and
//     on sidebar hover, and every loader records its resolved module
//     in `resolvedChunks` below.
//   - `LAZY_PAGES`, the `React.lazy` components created ONCE at
//     module scope from the same loaders. `router/RouteChunk.tsx`
//     renders these for a genuinely COLD chunk.
//   - `resolvedChunks` + `resolvedChunkComponent(page)`, the warm
//     fast path: React.lazy suspends on its first render even when
//     the module is already in memory (it cannot know), which is why
//     a warmed chunk still flashed the route skeleton. RouteChunk
//     reads this map first and renders the page synchronously, so a
//     hover/idle-warmed route commits in ONE render with no fallback.
// Home stays an EAGER import in PageSwitch.tsx (default landing page —
// lazy-loading it would put a Suspense fallback flash on every app
// launch), so it deliberately has no entry here.
// The ten entries are the pages with their own route chunk. The
// Settings HUB and ALL settings-section literals resolve to the SAME
// Settings chunk (one entry covers them); `chunkKeyForPage` returns
// `undefined` for pages without their own chunk so `prefetchPage`
// can no-op for them.
// Adding a page: add the literal to the `Page` union in
// entry here (if the page gets its own chunk), and add a `case` to
// `PageSwitch`'s switch (component wiring, legitimate routing
// logic, not registry duplication).

import { type ComponentType, lazy } from "react";
import type { Page } from "@/types/ipc";

/** A resolved chunk's default export. Props are erased here and
 *  re-checked at each `<RouteChunk>` call site. */
export type ChunkComponent = ComponentType<Record<string, unknown>>;

/** Chunk modules already loaded this session (idle warm-up, sidebar
 *  hover, or a previous visit). */
const resolvedChunks = new Map<PageWithLazyChunk, ChunkComponent>();

/** Loads in flight, so concurrent warm-ups share one `import()`. */
const chunkFlights = new Map<
	PageWithLazyChunk,
	Promise<{ default: ChunkComponent }>
>();

// Dev-only: Vite's React plugin auto-accepts page modules, so a hot
// edit to e.g. pages/Dashboard.tsx swaps the module WITHOUT a reload.
// A cached component would then keep rendering the previous version,
// so drop the warm entries before each update (the next navigation
// re-imports and suspends once, which is correct).
if (import.meta.hot) {
	import.meta.hot.on("vite:beforeUpdate", () => {
		resolvedChunks.clear();
		chunkFlights.clear();
	});
}

/**
 * Load a route chunk once, recording its component for the warm fast
 * path. Concurrent callers share one import; a FAILED import is never
 * cached (the real navigation retries, per the prefetch contract).
 */
function loadChunk(
	key: PageWithLazyChunk,
	load: () => Promise<unknown>,
): Promise<{ default: ChunkComponent }> {
	const warm = resolvedChunks.get(key);
	if (warm) return Promise.resolve({ default: warm });
	const flight = chunkFlights.get(key);
	if (flight) return flight;
	const pending = load()
		.then((mod) => {
			const component = (mod as { default?: unknown }).default;
			if (typeof component !== "function") {
				throw new Error(`Route chunk "${key}" has no default export`);
			}
			resolvedChunks.set(key, component as ChunkComponent);
			return { default: component as ChunkComponent };
		})
		.finally(() => {
			chunkFlights.delete(key);
		});
	chunkFlights.set(key, pending);
	return pending;
}

export const PAGE_LOADERS = {
	aboutAndPrivacy: () =>
		loadChunk("aboutAndPrivacy", () => import("@/pages/AboutAndPrivacy")),
	analytics: () => loadChunk("analytics", () => import("@/pages/Dashboard")),
	history: () => loadChunk("history", () => import("@/pages/History")),
	media: () => loadChunk("media", () => import("@/pages/Media")),
	microphone: () => loadChunk("microphone", () => import("@/pages/Microphone")),
	models: () => loadChunk("models", () => import("@/pages/Models")),
	onboarding: () => loadChunk("onboarding", () => import("@/pages/Onboarding")),
	plugins: () => loadChunk("plugins", () => import("@/pages/plugins/Plugins")),
	// The settings hub and ALL section-page literals resolve to the
	// SAME Settings chunk, one entry covers them.
	settings: () => loadChunk("settings", () => import("@/pages/Settings")),
	templates: () => loadChunk("templates", () => import("@/pages/Templates")),
	vocabulary: () => loadChunk("vocabulary", () => import("@/pages/Vocabulary")),
} as const;

/** Pages that own a lazy route chunk in {@link PAGE_LOADERS}. */
export type PageWithLazyChunk = keyof typeof PAGE_LOADERS;

export const LAZY_PAGES = {
	aboutAndPrivacy: lazy(PAGE_LOADERS.aboutAndPrivacy),
	analytics: lazy(PAGE_LOADERS.analytics),
	history: lazy(PAGE_LOADERS.history),
	media: lazy(PAGE_LOADERS.media),
	microphone: lazy(PAGE_LOADERS.microphone),
	models: lazy(PAGE_LOADERS.models),
	onboarding: lazy(PAGE_LOADERS.onboarding),
	plugins: lazy(PAGE_LOADERS.plugins),
	settings: lazy(PAGE_LOADERS.settings),
	templates: lazy(PAGE_LOADERS.templates),
	vocabulary: lazy(PAGE_LOADERS.vocabulary),
};

/** The chunk key backing `page` (settings-section literals share the
 *  Settings chunk), or `undefined` when the page has no lazy chunk. */
export function chunkKeyForPage(page: Page): PageWithLazyChunk | undefined {
	const loaders = PAGE_LOADERS as Partial<Record<Page, unknown>>;
	if (loaders[page]) return page as PageWithLazyChunk;
	// Every settings-section literal renders the shared Settings chunk
	// (see PageSwitch), so hover prefetch warms it for those too.
	if (page.startsWith("settings")) return "settings";
	return undefined;
}

export function routeChunkLoader(
	page: Page,
): (() => Promise<unknown>) | undefined {
	const key = chunkKeyForPage(page);
	return key ? PAGE_LOADERS[key] : undefined;
}

/** The chunk's component when its module is already loaded, else
 *  `undefined` (the caller falls back to the `React.lazy` path). */
export function resolvedChunkComponent(page: Page): ChunkComponent | undefined {
	const key = chunkKeyForPage(page);
	return key ? resolvedChunks.get(key) : undefined;
}

/** Test-only reset for the warm-chunk registry. */
export function __resetResolvedChunksForTests(): void {
	resolvedChunks.clear();
	chunkFlights.clear();
}
