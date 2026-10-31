// The Media page's field has to survive a refresh and a restart, and a
// disabled storage (private mode, quota, policy) must never break the page.
// Both directions are pinned here; the page-level behavior lives in
// `pages/__tests__/Media-file-picker.test.tsx`.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MEDIA_SOURCE_STORAGE_KEY } from "./mediaSourceStore";

beforeEach(() => {
	localStorage.clear();
	vi.resetModules();
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.resetModules();
});

describe("mediaSourceStore", () => {
	it("rehydrates the persisted value on first use", async () => {
		localStorage.setItem(MEDIA_SOURCE_STORAGE_KEY, "https://example.com/v");
		const { useMediaSourceStore } = await import("./mediaSourceStore");
		expect(useMediaSourceStore.getState().source).toBe("https://example.com/v");
	});

	it("writes on change and removes the key when cleared", async () => {
		const { useMediaSourceStore } = await import("./mediaSourceStore");
		useMediaSourceStore.getState().setSource("https://example.com/a");
		expect(localStorage.getItem(MEDIA_SOURCE_STORAGE_KEY)).toBe(
			"https://example.com/a",
		);
		useMediaSourceStore.getState().clear();
		expect(useMediaSourceStore.getState().source).toBe("");
		expect(localStorage.getItem(MEDIA_SOURCE_STORAGE_KEY)).toBeNull();
	});

	it("starts empty when the storage read throws", async () => {
		vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
			throw new Error("storage disabled");
		});
		const { useMediaSourceStore } = await import("./mediaSourceStore");
		expect(useMediaSourceStore.getState().source).toBe("");
	});

	it("keeps the in-memory value when the storage write throws", async () => {
		const { useMediaSourceStore } = await import("./mediaSourceStore");
		vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
			throw new Error("quota exceeded");
		});
		expect(() =>
			useMediaSourceStore.getState().setSource("https://example.com/b"),
		).not.toThrow();
		expect(useMediaSourceStore.getState().source).toBe("https://example.com/b");
	});
});
