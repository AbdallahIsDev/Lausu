import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
	PLUGINS_BADGE_SEEN_KEY,
	usePluginsNewBadge,
} from "@/hooks/usePluginsNewBadge";

beforeEach(() => {
	localStorage.removeItem(PLUGINS_BADGE_SEEN_KEY);
});

afterEach(() => {
	cleanup();
	localStorage.removeItem(PLUGINS_BADGE_SEEN_KEY);
});

describe("usePluginsNewBadge", () => {
	it("is due on a fresh install", () => {
		const { result } = renderHook(() => usePluginsNewBadge("home"));
		expect(result.current).toBe(true);
	});

	it("latches off for good once the Plugins page is opened", () => {
		const { result, rerender } = renderHook(
			({ page }: { page: string }) => usePluginsNewBadge(page),
			{ initialProps: { page: "home" } },
		);
		expect(result.current).toBe(true);
		rerender({ page: "plugins" });
		expect(result.current).toBe(false);
		expect(localStorage.getItem(PLUGINS_BADGE_SEEN_KEY)).toBe("1");

		// Leaving the page and coming back must not resurrect it.
		act(() => rerender({ page: "home" }));
		expect(result.current).toBe(false);
	});

	it("stays off across a remount once seen", () => {
		localStorage.setItem(PLUGINS_BADGE_SEEN_KEY, "1");
		const { result } = renderHook(() => usePluginsNewBadge("home"));
		expect(result.current).toBe(false);
	});
});
