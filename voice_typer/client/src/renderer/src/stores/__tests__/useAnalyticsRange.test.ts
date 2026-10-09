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

describe("useAnalyticsRange custom windows", () => {
	function todayKey(): string {
		const d = new Date();
		const pad = (n: number) => String(n).padStart(2, "0");
		return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
	}

	function shiftKey(key: string, delta: number): string {
		const [y = 1970, m = 1, d = 1] = key.split("-").map(Number);
		const shifted = new Date(y, m - 1, d + delta);
		const pad = (n: number) => String(n).padStart(2, "0");
		return `${shifted.getFullYear()}-${pad(shifted.getMonth() + 1)}-${pad(shifted.getDate())}`;
	}

	beforeEach(() => {
		sessionStorage.clear();
		useAnalyticsRange.setState({ range: "7d", customWindow: null });
	});

	it("stores a valid custom window and persists the object shape", () => {
		const today = todayKey();
		const window = { startKey: shiftKey(today, -6), endKey: today };
		useAnalyticsRange.getState().setCustomRange(window);
		expect(useAnalyticsRange.getState().range).toBe("custom");
		expect(useAnalyticsRange.getState().customWindow).toEqual(window);
		expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? "")).toEqual({
			range: "custom",
			customStart: window.startKey,
			customEnd: window.endKey,
		});
	});

	it("keeps presets on the legacy bare-string shape", () => {
		useAnalyticsRange.getState().setRange("30d");
		expect(sessionStorage.getItem(STORAGE_KEY)).toBe(JSON.stringify("30d"));
	});

	it.each([
		["end before start", { startKey: "2026-08-12", endKey: "2026-08-10" }],
		["future end", { startKey: "2026-08-10", endKey: "2999-01-01" }],
		["malformed keys", { startKey: "yesterday", endKey: "today" }],
	])("ignores invalid custom windows (%s)", (_label, window) => {
		useAnalyticsRange.getState().setCustomRange(window);
		expect(useAnalyticsRange.getState().range).toBe("7d");
		expect(useAnalyticsRange.getState().customWindow).toBeNull();
	});

	it("rehydrates a persisted custom object", async () => {
		const today = todayKey();
		sessionStorage.setItem(
			STORAGE_KEY,
			JSON.stringify({
				range: "custom",
				customStart: shiftKey(today, -6),
				customEnd: today,
			}),
		);
		const fresh = await importFreshStore();
		expect(fresh.useAnalyticsRange.getState().range).toBe("custom");
		expect(fresh.useAnalyticsRange.getState().customWindow).toEqual({
			startKey: shiftKey(today, -6),
			endKey: today,
		});
	});

	it("falls back on stale custom payloads (out of span, future end)", async () => {
		sessionStorage.setItem(
			STORAGE_KEY,
			JSON.stringify({
				range: "custom",
				customStart: "2020-01-01",
				customEnd: "2021-06-01",
			}),
		);
		const fresh = await importFreshStore();
		expect(fresh.useAnalyticsRange.getState().range).toBe("7d");
		expect(fresh.useAnalyticsRange.getState().customWindow).toBeNull();
	});
});
