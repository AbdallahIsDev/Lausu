// PG-1 regression guard: a WARM route chunk must render synchronously.
//
// `React.lazy` suspends on its first render even when the module is
// already in memory, so the Suspense fallback (`RouteSkeleton`) used to
// commit on EVERY navigation — that skeleton was what the user saw after
// hovering Analytics, not a data load. `<RouteChunk>` reads the warm
// registry instead. These tests fail if the fast path is removed, and
// pin that a genuinely cold chunk still gets the fallback.

import { cleanup, render, screen } from "@testing-library/react";
import { type ReactElement, Suspense } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/pages/Home", () => ({
	default: () => <div data-testid="page-home">Home page</div>,
}));
vi.mock("@/pages/History", () => ({
	default: () => <div data-testid="page-history">History page</div>,
}));
vi.mock("@/pages/Dashboard", () => ({
	default: () => <div data-testid="page-analytics">Analytics page</div>,
}));
vi.mock("@/pages/Settings", () => ({
	default: ({ page }: { page: string }) => (
		<div data-testid={`settings-${page}`}>Settings sub-page {page}</div>
	),
}));
vi.mock("@/pages/Onboarding", () => ({
	default: () => <div data-testid="page-onboarding">Onboarding</div>,
}));

import { PageSwitch } from "@/router/PageSwitch";
import {
	__resetResolvedChunksForTests,
	PAGE_LOADERS,
	resolvedChunkComponent,
} from "@/router/pageLoaders";
import { prefetchPage } from "@/router/prefetch";
import { RouteChunk } from "@/router/RouteChunk";

const FALLBACK_TESTID = "route-fallback";

function withFallback(ui: ReactElement) {
	return (
		<Suspense fallback={<div data-testid={FALLBACK_TESTID}>fallback</div>}>
			{ui}
		</Suspense>
	);
}

beforeEach(() => {
	__resetResolvedChunksForTests();
});

afterEach(() => {
	cleanup();
});

describe("RouteChunk warm fast path (PG-1)", () => {
	it("renders a warmed chunk synchronously with no Suspense fallback", async () => {
		await PAGE_LOADERS.analytics();
		render(withFallback(<RouteChunk page="analytics" />));

		// Synchronous: no `findBy`, the page is in the FIRST commit.
		expect(screen.getByTestId("page-analytics")).toBeTruthy();
		expect(screen.queryByTestId(FALLBACK_TESTID)).toBeNull();
	});

	it("still routes a cold chunk through React.lazy and its fallback", async () => {
		render(withFallback(<RouteChunk page="history" />));
		expect(screen.getByTestId(FALLBACK_TESTID)).toBeTruthy();
		expect(await screen.findByTestId("page-history")).toBeTruthy();
	});

	it("forwards the settings section literal to the shared Settings chunk", async () => {
		await PAGE_LOADERS.settings();
		render(withFallback(<RouteChunk page="settingsPrivacy" />));
		expect(screen.getByTestId("settings-settingsPrivacy")).toBeTruthy();
		expect(screen.queryByTestId(FALLBACK_TESTID)).toBeNull();
	});

	it("prefetchPage warms the chunk so the route switch renders with no fallback", async () => {
		prefetchPage("analytics");
		await vi.waitFor(() => {
			expect(resolvedChunkComponent("analytics")).toBeTruthy();
		});
		render(
			withFallback(
				<PageSwitch
					page="analytics"
					navigate={() => {}}
					onOnboardingComplete={() => {}}
				/>,
			),
		);
		expect(screen.getByTestId("page-analytics")).toBeTruthy();
		expect(screen.queryByTestId(FALLBACK_TESTID)).toBeNull();
	});
});
