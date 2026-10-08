import { beforeEach, describe, expect, it, vi } from "vitest";

import {
	ANALYTICS_RANGES,
	useAnalyticsRange,
} from "@/stores/useAnalyticsRange";

const STORAGE_KEY = "vt:filters:analytics.range";

/** Load a FRESH copy of the module so its storage initializer re-runs. */
async function importFreshStore() {
	vi.resetModules();
	return import("@/stores/useAnalyticsRange");
}

describe("useAnalyticsRange", () => {
	beforeEach(() => {
		sessionStorage.clear();
		useAnalyticsRange.setState({ range: "7d" });
	});

	it("defaults to the 7-day window", () => {
		expect(useAnalyticsRange.getState().range).toBe("7d");
	});

	it("exposes every selectable range in display order", () => {
		// The title-bar control renders exactly this list, so its order
		// and membership are the control's contract.
		expect([...ANALYTICS_RANGES]).toEqual(["today", "7d", "30d", "all"]);
	});

	it("stores the selection and persists it for the next session", () => {
		useAnalyticsRange.getState().setRange("30d");
		expect(useAnalyticsRange.getState().range).toBe("30d");
		expect(sessionStorage.getItem(STORAGE_KEY)).toBe(JSON.stringify("30d"));
	});

	it("rehydrates a previously persisted range", async () => {
		sessionStorage.setItem(STORAGE_KEY, JSON.stringify("all"));
		const fresh = await importFreshStore();
		expect(fresh.useAnalyticsRange.getState().range).toBe("all");
	});

	it("falls back to the default when the persisted value is not a range", async () => {
		// A stale key from an older build must not put the page into a
		// window no branch handles.
		sessionStorage.setItem(STORAGE_KEY, JSON.stringify("last-90-days"));
		const fresh = await importFreshStore();
		expect(fresh.useAnalyticsRange.getState().range).toBe("7d");
	});

	it("survives a persisted value that is not even valid JSON", async () => {
		sessionStorage.setItem(STORAGE_KEY, "{not json");
		const fresh = await importFreshStore();
		expect(fresh.useAnalyticsRange.getState().range).toBe("7d");
	});
});
