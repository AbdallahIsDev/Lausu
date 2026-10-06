/**
 * ActivityHeatmap — the Analytics page's dictation heatmap card.
 *
 * The chart itself is a vendored Bklit component whose <svg> is
 * `aria-hidden`, and in jsdom `@visx/responsive` reports a width of 0 so
 * the grid renders nothing at all. What is worth pinning here is
 * therefore the CARD's contract, which is what this project owns:
 *
 *   1. The card is a labelled region, and the chart body is exposed to
 *      assistive tech as ONE `role="img"` whose label carries the totals
 *      — not 180 unlabelled hover targets, and not nothing at all (the
 *      `aria-hidden` svg alone would leave the card mute).
 *   2. Title / subtitle / legend labels come from the translation
 *      catalog (C-I18N-1), so the Arabic UI is not half English.
 *   3. The subtitle states the range the card covers, because the card
 *      ignores the page's TimeRangeSelector.
 *   4. The truncation note appears only when the grid is capped, so it
 *      cannot cry wolf on a short history.
 *   5. Rendering survives an empty history (the chart's own zero-width
 *      bail-out must not take the card down with it).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
	resetStableMocks,
} from "@/__tests__/helpers/stableMocks";

vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());

import { t } from "@/i18n/i18n";
import type { HistoryRecord } from "@/types/ipc";
import { buildDictationHeatmap } from "../../lib/heatmap";
import { ActivityHeatmap } from "../ActivityHeatmap";

const NOW = new Date(2026, 9, 6, 15, 0, 0);

function recordOn(date: Date, id: number): HistoryRecord {
	return {
		id,
		text: "",
		timestamp: new Date(
			date.getFullYear(),
			date.getMonth(),
			date.getDate(),
			12,
			0,
			0,
		)
			.toISOString()
			.slice(0, 19)
			.replace("T", " "),
		duration: 1,
		model: "",
		device: "",
		word_count: 1,
		char_count: 1,
		favorite: 0,
		language: "en",
	};
}

function renderHeatmap(records: HistoryRecord[]) {
	const heatmap = buildDictationHeatmap(records, NOW);
	return {
		heatmap,
		...render(<ActivityHeatmap heatmap={heatmap} />),
	};
}

afterEach(() => {
	cleanup();
	resetStableMocks();
});

describe("ActivityHeatmap", () => {
	it("is a labelled region whose chart body carries a totals summary", () => {
		const { heatmap } = renderHeatmap([
			recordOn(new Date(2026, 9, 6), 1),
			recordOn(new Date(2026, 9, 6), 2),
			recordOn(new Date(2026, 9, 5), 3),
		]);

		expect(
			screen.getByRole("region", { name: t("analytics.heatmap.title") }),
		).toBeTruthy();
		expect(
			screen.getByRole("heading", { name: t("analytics.heatmap.title") }),
		).toBeTruthy();

		// The summary must report the SAME numbers the cells encode.
		const summary = screen.getByRole("img");
		expect(summary.getAttribute("aria-label")).toBe(
			t("analytics.heatmap.aria", {
				total: String(heatmap.total),
				days: String(heatmap.activeDays),
			}),
		);
		expect(summary.getAttribute("aria-label")).toContain("3");
	});

	it("renders its title, range subtitle and legend labels from the catalog", () => {
		renderHeatmap([recordOn(new Date(2026, 9, 6), 1)]);

		expect(
			screen.getByRole("heading", { name: t("analytics.heatmap.title") }),
		).toBeTruthy();
		// Subtitle = "<range> · per day" (the card ignores the page's
		// range selector, so it must state its own window).
		expect(screen.getByText(new RegExp(t("analytics.byDay")))).toBeTruthy();
		expect(screen.getByText(t("analytics.heatmap.less"))).toBeTruthy();
		expect(screen.getByText(t("analytics.heatmap.more"))).toBeTruthy();
	});

	it("does not claim a truncated window when the history fits", () => {
		const { heatmap } = renderHeatmap([recordOn(new Date(2026, 9, 6), 1)]);

		expect(heatmap.truncated).toBe(false);
		// Regex, not a bare string: the note lives inside the subtitle <p>
		// alongside the range and "per day", and `getByText(string)` only
		// matches an element whose WHOLE text is that string — a bare
		// string here would match nothing whether or not the note
		// rendered, i.e. the assertion would be vacuous.
		expect(
			screen.queryByText(new RegExp(t("analytics.heatmap.truncated"))),
		).toBeNull();
	});

	it("says the window is capped when the history reaches past a year", () => {
		const { heatmap } = renderHeatmap([
			recordOn(new Date(2023, 4, 2), 1),
			recordOn(new Date(2026, 9, 6), 2),
		]);

		expect(heatmap.truncated).toBe(true);
		expect(
			screen.getByText(new RegExp(t("analytics.heatmap.truncated"))),
		).toBeTruthy();
	});

	it("survives an empty history without taking the card down", () => {
		const { heatmap } = renderHeatmap([]);

		expect(heatmap.total).toBe(0);
		expect(
			screen.getByRole("region", { name: t("analytics.heatmap.title") }),
		).toBeTruthy();
		expect(screen.getByRole("img").getAttribute("aria-label")).toBe(
			t("analytics.heatmap.aria", { total: "0", days: "0" }),
		);
	});
});
