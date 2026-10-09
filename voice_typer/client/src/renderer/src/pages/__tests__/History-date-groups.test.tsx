/**
 * History page, date-grouped list integration.
 *
 * Pins the page-level contract of the grouped list revamp:
 *   - chronological sorts (newest/oldest) render grouped sections;
 *   - alphabetical sorts (az/za) render FLAT (no date headers —
 *     grouping would interleave date sections into A→Z order);
 *   - expanding a truncated row issues ``get_transcription_text`` with
 *     the record id (the page's onFetchFullText bridge);
 *   - the refresh control rides the page heading's action slot, the
 *     section label is gone, and the controls block keeps a 4px gap to
 *     the list while the page root keeps 6px to the heading.
 */

import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// jsdom lacks PointerEvent capture APIs; Radix Select's trigger needs
// them to open + commit an option (same polyfill as Onboarding.test.tsx).
if (
	typeof Element !== "undefined" &&
	typeof Element.prototype.hasPointerCapture !== "function"
) {
	Element.prototype.hasPointerCapture = function hasPointerCapture() {
		return false;
	};
	Element.prototype.setPointerCapture = function setPointerCapture() {};
	Element.prototype.releasePointerCapture = function releasePointerCapture() {};
}

import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
	lastUpdatedMock,
	navigationMock,
	nextThemesMock,
	pythonMock,
	resetStableMocks,
	snackbarMock,
	sonnerMock,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";

const { mockCall } = stableMocks;

vi.mock("@/hooks/usePython", () => pythonMock());
vi.mock("@/hooks/useSnackbar", () => snackbarMock());
vi.mock("@/hooks/useLastUpdated", () => lastUpdatedMock({ withRefresh: true }));
vi.mock("@/hooks/useNavigation", () => navigationMock());
vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());
vi.mock("sonner", () => sonnerMock());
vi.mock("next-themes", () => nextThemesMock());

import { t } from "@/i18n/i18n";
import { useGlobalSearch } from "@/stores/useGlobalSearch";
import type { HistoryRecord, TodayStats } from "@/types/ipc";

const zeroStats: TodayStats = {
	count: 0,
	chars: 0,
	word_count: 0,
	duration: 0,
};

function rec(
	id: number,
	timestamp: string,
	overrides: Partial<HistoryRecord> = {},
): HistoryRecord {
	return {
		id,
		text: `entry ${id}`,
		timestamp,
		duration: 1,
		model: "tiny",
		device: "cpu",
		word_count: 2,
		char_count: 9,
		favorite: 0,
		language: "en",
		...overrides,
	};
}

function localIso(offsetDays: number, hour: number): string {
	const d = new Date();
	d.setDate(d.getDate() - offsetDays);
	d.setHours(hour, 0, 0, 0);
	return d.toISOString();
}

beforeEach(() => {
	resetStableMocks();
	localStorage.clear();
	useGlobalSearch.setState({ query: "" });
	vi.resetModules();
});

afterEach(() => {
	cleanup();
});

describe("History date-grouped list", () => {
	it("groups entries under date headers for the default (newest) sort", async () => {
		mockCall.mockImplementation((type: string) => {
			if (type === "get_history")
				return Promise.resolve([
					rec(1, localIso(0, 12)),
					rec(2, localIso(0, 5)),
					rec(3, localIso(1, 8)),
				]);
			if (type === "get_today_stats") return Promise.resolve(zeroStats);
			return Promise.resolve({});
		});

		const { default: HistoryPage } = await import("@/pages/History");
		render(<HistoryPage />);

		await waitFor(() => {
			expect(screen.getByText("entry 1")).toBeTruthy();
		});

		// Date section headers render; each entry appears exactly once.
		expect(screen.getByText(t("analytics.today"))).toBeTruthy();
		expect(screen.getByText(t("analytics.yesterday"))).toBeTruthy();
		expect(screen.getByText("entry 2")).toBeTruthy();
		expect(screen.getByText("entry 3")).toBeTruthy();
	});

	it("does NOT group for the alphabetical sorts (az), flat list", async () => {
		const user = userEvent.setup();
		mockCall.mockImplementation((type: string) => {
			if (type === "get_history")
				return Promise.resolve([
					rec(1, localIso(0, 12)),
					rec(2, localIso(1, 8)),
				]);
			if (type === "get_today_stats") return Promise.resolve(zeroStats);
			return Promise.resolve({});
		});

		const { default: HistoryPage } = await import("@/pages/History");
		render(<HistoryPage />);

		await waitFor(() => {
			expect(screen.getByText(t("analytics.today"))).toBeTruthy();
		});

		// Switch the sort to A → Z via the shared SortSelect.
		await user.click(
			screen.getByRole("combobox", { name: t("common.sortAria") }),
		);
		await user.click(screen.getByRole("option", { name: t("common.sortAZ") }));

		await waitFor(() => {
			// No date headers in flat mode.
			expect(screen.queryByText(t("analytics.today"))).toBeNull();
			expect(screen.queryByText(t("analytics.yesterday"))).toBeNull();
		});
		// Both rows still render.
		expect(screen.getByText("entry 1")).toBeTruthy();
		expect(screen.getByText("entry 2")).toBeTruthy();
	});

	it("expanding a truncated row calls get_transcription_text with the record id", async () => {
		mockCall.mockImplementation((type: string, data?: unknown) => {
			if (type === "get_history")
				return Promise.resolve([
					rec(42, localIso(0, 12), {
						text: "word ".repeat(100).trim(),
						text_truncated: true,
						text_full_length: 1200,
					}),
				]);
			if (type === "get_today_stats") return Promise.resolve(zeroStats);
			if (type === "get_transcription_text") {
				const payload = data as { id: number };
				return Promise.resolve({
					id: payload.id,
					text: "THE EXPANDED FULL TEXT",
				});
			}
			return Promise.resolve({});
		});

		const { default: HistoryPage } = await import("@/pages/History");
		render(<HistoryPage />);

		await waitFor(() => {
			expect(screen.getByText(/word word/)).toBeTruthy();
		});

		// Click the collapsed disclosure control (the text block).
		fireEvent.click(screen.getByTestId("activity-row-text-toggle"));

		await waitFor(() => {
			expect(mockCall).toHaveBeenCalledWith(
				"get_transcription_text",
				expect.objectContaining({ id: 42 }),
			);
			expect(screen.getByText("THE EXPANDED FULL TEXT")).toBeTruthy();
		});
	});

	it("rides the refresh control on the heading row and drops the section label", async () => {
		mockCall.mockImplementation((type: string) => {
			if (type === "get_history")
				return Promise.resolve([rec(1, localIso(0, 12))]);
			if (type === "get_today_stats") return Promise.resolve(zeroStats);
			return Promise.resolve({});
		});

		const { default: HistoryPage } = await import("@/pages/History");
		render(<HistoryPage />);

		await waitFor(() => {
			expect(screen.getByText("entry 1")).toBeTruthy();
		});

		// The "Recent Activity" section label is gone. The controls above
		// the list already say what the section is, and the label cost a
		// whole row between them and the card.
		expect(screen.queryByText(t("home.recentActivity"))).toBeNull();

		// Freshness + refresh ride the PAGE HEADING's action slot (the
		// same slot the Analytics page uses), so the indicator's cluster
		// is a child of the heading row that also holds the <h1>.
		const indicator = screen.getByTestId("last-updated-indicator");
		const headingRow = indicator.parentElement?.parentElement;
		expect(headingRow?.querySelector("h1")).not.toBeNull();
		expect(headingRow?.className).toContain("justify-between");

		// Page rhythm: the root keeps gap-6 between the heading and the
		// controls block, and the block itself uses gap-4 between the
		// controls and the list card. The indicator is NOT inside that
		// block any more.
		const block = screen
			.getByRole("button", { name: t("history.favorites") })
			.closest(".gap-4");
		expect(block).not.toBeNull();
		expect(block?.textContent).toContain("entry 1");
		expect(
			block?.querySelector('[data-testid="last-updated-indicator"]'),
		).toBeNull();
		const root = block?.parentElement;
		expect(root?.className).toContain("gap-6");
		expect(root?.querySelector("h1")).not.toBeNull();
	});
});
