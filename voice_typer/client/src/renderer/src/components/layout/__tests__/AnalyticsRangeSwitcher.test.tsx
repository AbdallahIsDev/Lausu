/**
 * AnalyticsRangeSwitcher — the Analytics time range in the title bar.
 *
 * The control is the only way to change the range, so what matters is:
 * it mounts on the analytics page and nowhere else, it exposes every
 * range as a labelled radio, it writes through to the shared store (the
 * page reads that same store, which is the whole reason the control can
 * live outside the page's tree), and it follows the store when the
 * value changes from elsewhere.
 */

import {
	act,
	cleanup,
	fireEvent,
	render,
	screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AnalyticsRangeSwitcher } from "@/components/layout/AnalyticsRangeSwitcher";
import { t } from "@/i18n/i18n";
import {
	ANALYTICS_RANGES,
	useAnalyticsRange,
} from "@/stores/useAnalyticsRange";
import type { Page } from "@/types/ipc";

beforeEach(() => {
	sessionStorage.clear();
	useAnalyticsRange.setState({ range: "7d" });
});

afterEach(() => {
	cleanup();
});

describe("AnalyticsRangeSwitcher", () => {
	it("renders nothing on every page except analytics", () => {
		const otherPages: Page[] = ["home", "history", "models", "settings"];
		for (const page of otherPages) {
			const { container, unmount } = render(
				<AnalyticsRangeSwitcher currentPage={page} />,
			);
			expect(container.firstChild).toBeNull();
			unmount();
		}
	});

	it("exposes every range as a labelled option on the analytics page", () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		const group = screen.getByRole("radiogroup", {
			name: t("analytics.rangeAria"),
		});
		// The strip sits inside the title bar's drag region: without
		// `no-drag` a click would move the window instead of picking a
		// range.
		expect(group.className).toContain("no-drag");

		const radios = screen.getAllByRole("radio");
		expect(radios).toHaveLength(ANALYTICS_RANGES.length);
		for (const range of ANALYTICS_RANGES) {
			expect(
				screen.getByRole("radio", { name: t(`analytics.range.${range}`) }),
			).toBeTruthy();
		}
		// Radiogroup, NOT the tabs variant: the range picks a data
		// window and has no `role="tabpanel"` to control.
		expect(screen.queryByRole("tablist")).toBeNull();
	});

	it("writes the selection through to the shared store", () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		fireEvent.click(
			screen.getByRole("radio", { name: t("analytics.range.30d") }),
		);

		expect(useAnalyticsRange.getState().range).toBe("30d");
		expect(
			screen.getByRole("radio", { name: t("analytics.range.30d") }),
		).toBeChecked();
	});

	it("follows the store when the range changes from elsewhere", () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		act(() => {
			useAnalyticsRange.getState().setRange("all");
		});

		expect(
			screen.getByRole("radio", { name: t("analytics.range.all") }),
		).toBeChecked();
	});
});
