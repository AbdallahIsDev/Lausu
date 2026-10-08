/**
 * SevenDayActivityChart — the Analytics page's Activity card.
 *
 * The chart is presentational: it receives bars that are already
 * bucketed (see `../../lib/streaks`, covered by `lib/__tests__/
 * streaks.test.ts`) and owns the bar RENDER contract, which is what
 * this file pins:
 *
 *   1. A slot with dictations draws a bar, filled at full strength.
 *   2. A covered slot with NO dictations draws nothing at all, so a
 *      quiet day reads as an empty column rather than as a bar of
 *      height zero.
 *   3. A slot the sample does not cover keeps its dashed tick, because
 *      "outside the sample" is a different claim from "nothing
 *      happened".
 *   4. The header is text only — no icon.
 *   5. The header is ONE line: title leading, range/unit trailing on
 *      the same baseline (same shape as the heatmap card's header).
 *
 * Marks are located by their `title` (the per-bar tooltip), the only
 * attribute a mark carries, which keeps these assertions independent of
 * the classes the fill happens to use.
 */

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
} from "@/__tests__/helpers/stableMocks";

vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());

import { t, tChoice } from "@/i18n/i18n";
import type { ActivityBar, ActivityChartData } from "../../lib/streaks";
import { ActivityChart } from "../SevenDayActivityChart";

function chart(bars: ActivityBar[]): ActivityChartData {
	return { bars, kind: "daily", coveredFromKey: null, daySpan: bars.length };
}

// Mon has dictations, Tue is a covered day with none, Wed predates the
// history sample.
const ACTIVITY = chart([
	{ key: "mon", label: "Mon", count: 3, isMissing: false },
	{ key: "tue", label: "Tue", count: 0, isMissing: false },
	{ key: "wed", label: "Wed", count: 0, isMissing: true },
]);

function renderChart() {
	return render(<ActivityChart range="7d" activity={ACTIVITY} />);
}

/** Every mark in the plot, in bar order (a slot may contribute none). */
function marks(container: HTMLElement): HTMLElement[] {
	return Array.from(container.querySelectorAll<HTMLElement>("[title]"));
}

/** The nth mark — fails loudly when a slot drew nothing. */
function mark(container: HTMLElement, index: number): HTMLElement {
	const found = marks(container)[index];
	if (!found) throw new Error(`no mark at index ${index}`);
	return found;
}

afterEach(cleanup);

describe("ActivityChart bar rendering", () => {
	it("marks a day with dictations and leaves a quiet day unmarked", () => {
		// Only Mon (3 dictations) and Wed (no data) have anything to
		// say; Tue renders no element at all, so the plot holds two
		// marks rather than three.
		expect(marks(renderChart().container).map((m) => m.title)).toEqual([
			tChoice("analytics.dayCountTooltip", 3, { label: "Mon" }),
			t("analytics.noDataBar", { label: "Wed" }),
		]);
	});

	it("fills the bar at full opacity, with no hover state", () => {
		// The bar is a read-out, not a control.
		const bar = mark(renderChart().container, 0);
		expect(bar.className).toContain("bg-accent");
		expect(bar.className).not.toMatch(/bg-accent\//);
		expect(bar.className).not.toMatch(/hover:/);
	});

	it("keeps the dashed tick only for slots outside the sample", () => {
		const { container } = renderChart();
		expect(mark(container, 0).className).not.toContain("border-dashed");
		expect(mark(container, 1).className).toContain("border-dashed");
	});

	it("renders no icon in the card header", () => {
		expect(
			renderChart().container.querySelector('[data-testid="hugeicon"]'),
		).toBeNull();
	});

	it("puts the range/unit line on the title's row, trailing it", () => {
		// Title and window share one baseline row; a stacked column
		// would make the card a row taller for no added information.
		const { container } = renderChart();
		const title = container.querySelector("h2");
		const header = title?.parentElement;
		expect(header?.className).not.toContain("flex-col");
		expect(header?.className).toContain("items-baseline");
		expect(header?.className).toContain("justify-between");
		const sub = header?.querySelector("p");
		expect(sub?.textContent).toBe(
			`${t("analytics.range.7d")} · ${t("analytics.byDay")}`,
		);
		expect(sub?.className).toContain("shrink-0");
	});
});
