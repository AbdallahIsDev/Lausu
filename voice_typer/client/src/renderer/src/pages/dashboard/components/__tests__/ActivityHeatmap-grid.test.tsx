/**
 * ActivityHeatmap — the GRID itself.
 *
 * The sibling `ActivityHeatmap.test.tsx` pins the card's contract (region,
 * catalog strings, totals) but cannot assert cells: in jsdom
 * `@visx/responsive`'s `ParentSize` measures its parent, gets 0, and
 * `HeatmapChart` bails out before rendering anything. Every "the grid
 * looks right" assertion written against that setup passes vacuously.
 *
 * This file supplies a fixed width instead, which is the only way to pin
 * the card's central visual promise: a COMPLETE rectangle of
 * 53 weeks × 7 days — including the empty days before the first record —
 * whose width does not depend on how much history exists.
 */

import { cleanup, render } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
	resetStableMocks,
} from "@/__tests__/helpers/stableMocks";

vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());

/** Stand-in viewport for the measured chart parent. */
const CHART_WIDTH = 560;

// `ParentSize` renders nothing until it has a size, so without this stub the
// grid is empty and the assertions below would be vacuously true.
vi.mock("@visx/responsive", () => ({
	ParentSize: ({
		children,
	}: {
		children: (size: { width: number; height: number }) => ReactNode;
	}) => children({ width: CHART_WIDTH, height: 200 }),
}));

import type { HistoryRecord } from "@/types/ipc";
import { buildDictationHeatmap, HEATMAP_MAX_WEEKS } from "../../lib/heatmap";
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

function renderGrid(records: HistoryRecord[]) {
	const heatmap = buildDictationHeatmap(records, NOW);
	const { container } = render(<ActivityHeatmap heatmap={heatmap} />);
	return { heatmap, container };
}

/** One `<g>` per cell, inside the cells layer this project owns. */
function countCells(container: HTMLElement): number {
	return container.querySelectorAll(".visx-heatmap-rects > g").length;
}

afterEach(() => {
	cleanup();
	resetStableMocks();
});

describe("ActivityHeatmap grid", () => {
	it("renders every cell of a full year, empty days included", () => {
		// A single dictation today: 370 of the 371 cells have no data.
		const { container } = renderGrid([recordOn(new Date(2026, 9, 6), 1)]);

		expect(countCells(container)).toBe(HEATMAP_MAX_WEEKS * 7);
	});

	it("renders the same full rectangle for a three-year history", () => {
		const { container } = renderGrid([
			recordOn(new Date(2023, 4, 2), 1),
			recordOn(new Date(2026, 9, 6), 2),
		]);

		// Fixed width: history older than the window is truncated, NOT
		// rendered as extra columns.
		expect(countCells(container)).toBe(HEATMAP_MAX_WEEKS * 7);
	});

	it("renders the same full rectangle for an empty history", () => {
		const { container } = renderGrid([]);

		expect(countCells(container)).toBe(HEATMAP_MAX_WEEKS * 7);
	});

	it("does not inflate the totals with the empty cells it draws", () => {
		const { heatmap } = renderGrid([recordOn(new Date(2026, 9, 6), 1)]);

		// 53×7 cells are on screen; only one day actually has a dictation.
		expect(heatmap.total).toBe(1);
		expect(heatmap.activeDays).toBe(1);
	});

	it("labels the x-axis once per month in the active locale", () => {
		const { container } = renderGrid([recordOn(new Date(2026, 9, 6), 1)]);

		// The vendored axis used to hardcode English. Its labels now come
		// from the card, so a full-year grid must show ~13 of them rather
		// than one or two.
		const labels = Array.from(
			container.querySelectorAll("span.text-chart-label"),
		).map((node) => node.textContent ?? "");

		expect(labels.length).toBeGreaterThanOrEqual(12);
		expect(labels.every((label) => label.trim().length > 0)).toBe(true);
	});
});
