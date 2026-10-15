// router/RouteChunk.tsx, renders a lazy route chunk SYNCHRONOUSLY when
// its module is already in memory.
//
// `React.lazy` cannot tell a warm module from a cold one: its first
// render always throws the pending thenable, so the nearest Suspense
// boundary committed `RouteSkeleton` on EVERY navigation — including
// the ones the idle pass and the sidebar hover had already warmed. The
// skeleton the user saw after hovering Analytics was that fallback, not
// a data load.
//
// This component reads the warm registry first (`resolvedChunks`, filled
// by `router/prefetch.ts`) and renders the page directly, so a warmed
// route commits the real page in one render with no fallback. A
// genuinely cold chunk still goes through `React.lazy` + Suspense
// exactly as before, so the fallback survives for the case it was
// written for.

import { type ComponentType, createElement } from "react";
import type { Page } from "@/types/ipc";
import {
	chunkKeyForPage,
	LAZY_PAGES,
	resolvedChunkComponent,
} from "./pageLoaders";

interface RouteChunkProps {
	/** The route literal (a settings-section literal resolves to the
	 *  shared Settings chunk). */
	page: Page;
	/** Props for the page component (e.g. `page="settingsGeneral"` for
	 *  the Settings surface, `onComplete` for onboarding). */
	[prop: string]: unknown;
}

export function RouteChunk(props: RouteChunkProps) {
	const { page } = props;
	const pageProps = { ...props } as Record<string, unknown>;
	const Warm = resolvedChunkComponent(page);
	if (Warm) return createElement(Warm, pageProps);
	const key = chunkKeyForPage(page);
	if (!key) return null;
	const Lazy = LAZY_PAGES[key] as unknown as ComponentType<
		Record<string, unknown>
	>;
	return createElement(Lazy, pageProps);
}
