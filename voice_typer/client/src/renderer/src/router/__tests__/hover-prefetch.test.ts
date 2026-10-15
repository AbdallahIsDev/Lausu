// PG-1: hovering a sidebar item must warm BOTH the route chunk and the
// page's data cache, so the click lands on a page that paints its content
// in the first commit. This pins the per-page wiring in
// `router/prefetch.ts` — a page whose prefetcher is missing (or whose
// loader thunk names the wrong export) silently reintroduces the
// skeleton, which is exactly how the original defect presented.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
	__resetSettingsConfigPrefetchForTests,
	isSettingsConfigPrefetchFresh,
} from "@/components/settings/useSettingsConfig";
import { __resetModelsConfigPrefetchForTests } from "@/hooks/models/useModelConfig";
import { resetPluginCatalogCache } from "@/hooks/usePluginCatalog";
import { __resetIpcCacheForTests } from "@/lib/ipcCache";
import { __resetPrefetchFlightsForTests } from "@/lib/snapshotCache";
import {
	__resetMicrophonePrefetchForTests,
	isMicrophonePrefetchFresh,
} from "@/pages/microphone/hooks/useMicrophoneData";
import { __resetPluginsPrefetchForTests } from "@/pages/plugins/hooks/usePlugins";
import { __resetResolvedChunksForTests } from "@/router/pageLoaders";
import { prefetchPage } from "@/router/prefetch";
import type { Page } from "@/types/ipc";

const callMock = vi.fn();

function stubBackend(): void {
	callMock.mockImplementation((req: { type: string }) => {
		switch (req.type) {
			case "get_config":
				return Promise.resolve({ model_size: "tiny", device: "cpu" });
			case "get_history":
			case "get_history_count":
			case "get_correction_usage":
			case "get_model_status":
			case "get_today_stats":
			case "get_vocabulary":
			case "get_templates":
			case "get_microphones":
			case "get_plugins":
				return Promise.resolve(
					req.type === "get_history" || req.type === "get_microphones"
						? []
						: req.type === "get_history_count"
							? { count: 0 }
							: {},
				);
			default:
				return Promise.resolve(null);
		}
	});
}

function commandsIssued(): string[] {
	return callMock.mock.calls.map((c) => (c[0] as { type: string }).type);
}

/** Wait until every expected command has been issued. The budget is
 *  generous on purpose: the first `prefetchPage` in this file pays the
 *  on-demand transform of that page's whole module graph (measured at
 *  ~1s here, and CI is slower), which is unrelated to the wiring under
 *  test — a 1s default would fail on the cold import, not on a missing
 *  prefetcher. */
async function waitForCommands(expected: string[]): Promise<void> {
	await vi.waitFor(
		() => {
			const issued = commandsIssued();
			for (const cmd of expected) {
				expect(issued, `expected ${cmd} to be issued`).toContain(cmd);
			}
		},
		{ timeout: 15_000 },
	);
}

beforeEach(() => {
	callMock.mockReset();
	stubBackend();
	(
		window as unknown as {
			python: { call: typeof callMock };
		}
	).python = { call: callMock };
	__resetIpcCacheForTests();
	__resetPrefetchFlightsForTests();
	__resetResolvedChunksForTests();
	resetPluginCatalogCache();
	// The per-page prefetch stamps are MODULE state: without these the
	// second hover of a page short-circuits and issues no IPC, which is
	// correct behaviour but would leak across cases here.
	__resetSettingsConfigPrefetchForTests();
	__resetMicrophonePrefetchForTests();
	__resetPluginsPrefetchForTests();
	__resetModelsConfigPrefetchForTests();
});

afterEach(() => {
	(window as unknown as { python?: unknown }).python = undefined;
});

describe("prefetchPage data warm-up (PG-1 / C-CACHE-4)", () => {
	const CASES: ReadonlyArray<readonly [Page, string[]]> = [
		["analytics", ["get_config", "get_history", "get_history_count"]],
		["history", ["get_history", "get_today_stats"]],
		["vocabulary", ["get_vocabulary"]],
		["templates", ["get_templates"]],
		["settings", ["get_config"]],
		["microphone", ["get_microphones", "get_config"]],
		["plugins", ["get_plugins"]],
		["models", ["get_model_status", "get_config"]],
	];

	it.each(CASES)(
		"warms the %s page's data on hover",
		async (page, expected) => {
			prefetchPage(page);
			await waitForCommands(expected);
		},
	);

	it("warms the Settings config for every settings-section literal", async () => {
		prefetchPage("settingsPrivacy");
		await waitForCommands(["get_config"]);
		expect(isSettingsConfigPrefetchFresh()).toBe(true);
	});

	it("keeps a page with no data gate chunk-only (Media issues no IPC)", async () => {
		prefetchPage("media");
		// Give the fire-and-forget chain a chance to run.
		await vi.waitFor(() => {
			expect(callMock).not.toHaveBeenCalled();
		});
	});

	it("does not re-fetch on a repeated hover inside the TTL", async () => {
		prefetchPage("templates");
		await waitForCommands(["get_templates"]);
		const first = commandsIssued().length;
		prefetchPage("templates");
		prefetchPage("templates");
		// Let any (unwanted) follow-up flight run.
		await Promise.resolve();
		await Promise.resolve();
		expect(commandsIssued().length).toBe(first);
	});

	it("leaves the cache untouched when the prefetch fails", async () => {
		callMock.mockRejectedValue(new Error("backend down"));
		prefetchPage("microphone");
		await vi.waitFor(() => {
			expect(callMock).toHaveBeenCalled();
		});
		expect(isMicrophonePrefetchFresh()).toBe(false);
	});

	it("never surfaces a prefetch failure (fire-and-forget)", async () => {
		callMock.mockRejectedValue(new Error("backend down"));
		expect(() => prefetchPage("analytics")).not.toThrow();
		await vi.waitFor(() => {
			expect(callMock).toHaveBeenCalled();
		});
	});
});
