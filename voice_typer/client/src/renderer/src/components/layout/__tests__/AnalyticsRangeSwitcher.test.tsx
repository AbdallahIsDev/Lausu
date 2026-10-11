/**
 * AnalyticsRangeSwitcher — the Analytics time range in the title bar.
 *
 * The control is the only way to change the range, so what matters is:
 * it mounts on the analytics page and nowhere else, it exposes every
 * PRESET as a labelled radio, it writes through to the shared store (the
 * page reads that same store, which is the whole reason the control can
 * live outside the page's tree), and it follows the store when the
 * value changes from elsewhere.
 *
 * The second half of the file covers the 2026-10-11 split: the custom
 * range is a standalone disclosure BUTTON beside the pill row, not a
 * fifth pill inside it. Two different interactions (select a window vs.
 * open a menu) must not look like the same one, and the highlight rules
 * below only hold because they are separate.
 */

import {
	act,
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AnalyticsRangeSwitcher } from "@/components/layout/AnalyticsRangeSwitcher";
import { t } from "@/i18n/i18n";
import {
	ANALYTICS_RANGES,
	useAnalyticsRange,
} from "@/stores/useAnalyticsRange";
import type { Page } from "@/types/ipc";

/** The standalone calendar disclosure button (a button, NOT a radio). */
const calendarButton = () =>
	screen.getByRole("button", { name: t("analytics.rangeCustomAria") });

/** The custom-range panel, or null when it is closed/unmounted. */
const panel = () =>
	screen.queryByRole("dialog", { name: t("analytics.rangeAria") });

/** Accessible name of a calendar day cell, matching the picker's own format. */
const dayName = (y: number, m: number, day: number) =>
	new Intl.DateTimeFormat("en", {
		weekday: "long",
		month: "long",
		day: "numeric",
		year: "numeric",
	}).format(new Date(y, m, day));

beforeEach(() => {
	sessionStorage.clear();
	useAnalyticsRange.setState({ range: "7d", customWindow: null });
});

afterEach(() => {
	cleanup();
	useAnalyticsRange.setState({ range: "7d", customWindow: null });
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

	it("exposes every preset as a labelled option on the analytics page", () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		const group = screen.getByRole("radiogroup", {
			name: t("analytics.rangeAria"),
		});
		// The strip sits inside the title bar's drag region: without
		// `no-drag` a click would move the window instead of picking a
		// range.
		expect(group.className).toContain("no-drag");

		const radios = screen.getAllByRole("radio");
		// Presets ONLY. The custom range is a sibling button now, so it
		// must not show up here (see the calendar-control suite below).
		expect(radios).toHaveLength(ANALYTICS_RANGES.length);
		for (const range of ANALYTICS_RANGES) {
			expect(
				screen.getByRole("radio", { name: t(`analytics.range.${range}`) }),
			).toBeTruthy();
		}
		expect(
			screen.queryByRole("radio", { name: t("analytics.range.custom") }),
		).toBeNull();
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

describe("AnalyticsRangeSwitcher calendar control", () => {
	it("is a sibling button beside the row, separated by a gap", () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		const group = screen.getByRole("radiogroup", {
			name: t("analytics.rangeAria"),
		});
		const calendar = calendarButton();

		// A plain button: no `role` override, and it is NOT inside the
		// radiogroup (a radio would promise "this changes the page").
		expect(calendar.getAttribute("role")).toBeNull();
		expect(group.contains(calendar)).toBe(false);
		// Both are direct children of the same row, which is what spaces
		// them apart.
		const row = group.parentElement;
		expect(row).toBe(calendar.parentElement);
		expect(row?.className ?? "").toContain("gap-1.5");
	});

	it("declares itself as a dialog disclosure, not a selection", () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		const calendar = calendarButton();
		expect(calendar.getAttribute("aria-haspopup")).toBe("dialog");
		expect(calendar.getAttribute("aria-expanded")).toBe("false");
		// `aria-pressed` is the "custom range is live" state, not
		// "the menu is open".
		expect(calendar.getAttribute("aria-pressed")).toBe("false");
	});

	it("toggles the panel: a click opens it, the next click closes it", async () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		fireEvent.click(calendarButton());
		expect(panel()).toBeTruthy();
		expect(calendarButton().getAttribute("aria-expanded")).toBe("true");

		// A real click is pointerdown THEN click. The pointerdown lands on
		// the row, which the picker's dismissGuard reports as INSIDE — so
		// it cannot dismiss the panel first and leave the click to reopen
		// it. Without that guard this second click would be a no-op.
		fireEvent.pointerDown(calendarButton());
		fireEvent.click(calendarButton());

		// The exit morph holds the panel briefly; it must unmount.
		await waitFor(() => expect(panel()).toBeNull());
		expect(calendarButton().getAttribute("aria-expanded")).toBe("false");
	});

	it("rests muted while a preset is live and takes the raised pill when custom", () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		const restingPill = calendarButton().querySelector("span");
		const resting = restingPill?.getAttribute("class") ?? "";
		expect(resting).toMatch(/text-muted-foreground/);
		expect(resting).not.toMatch(/bg-surface/);

		act(() => {
			useAnalyticsRange.getState().setCustomRange({
				startKey: "2026-09-01",
				endKey: "2026-09-03",
			});
		});

		const activePill = calendarButton().querySelector("span");
		const active = activePill?.getAttribute("class") ?? "";
		// Same raised-surface treatment the group gives its selected
		// option, so "which range is live" reads the same on both.
		expect(active).toMatch(/bg-surface/);
		expect(active).not.toMatch(/text-muted-foreground/);
		expect(calendarButton().getAttribute("aria-pressed")).toBe("true");
	});
});

describe("AnalyticsRangeSwitcher highlight contract", () => {
	it("leaves the highlight on the current preset while the panel is open", () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		const preset = screen.getByRole("radio", {
			name: t("analytics.range.7d"),
		});
		expect(preset).toBeChecked();

		fireEvent.click(calendarButton());
		expect(panel()).toBeTruthy();

		// Opening a menu is not a selection: no tab changed, so the
		// indicator must not travel to the calendar.
		expect(preset).toBeChecked();
		expect(calendarButton().getAttribute("aria-pressed")).toBe("false");
		expect(useAnalyticsRange.getState().range).toBe("7d");
	});

	it("drops the tab highlight once a custom window is committed", () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date(2026, 9, 15, 12, 0, 0));
		try {
			render(<AnalyticsRangeSwitcher currentPage="analytics" />);
			fireEvent.click(calendarButton());

			fireEvent.click(
				screen.getByRole("button", { name: dayName(2026, 9, 10) }),
			);
			fireEvent.click(
				screen.getByRole("button", { name: dayName(2026, 9, 12) }),
			);

			expect(useAnalyticsRange.getState().range).toBe("custom");
			expect(useAnalyticsRange.getState().customWindow).toEqual({
				startKey: "2026-10-10",
				endKey: "2026-10-12",
			});

			// No preset pill is the truth any more — the custom window is
			// what the page shows, so nothing stays lit.
			for (const radio of screen.getAllByRole("radio")) {
				expect(radio).not.toBeChecked();
			}
			// ...and the calendar owns the active state instead, so the
			// row still answers "which range is live".
			expect(calendarButton().getAttribute("aria-pressed")).toBe("true");
		} finally {
			vi.useRealTimers();
		}
	});

	it("hands the highlight back when the picked window matches a preset", () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date(2026, 9, 15, 12, 0, 0));
		try {
			render(<AnalyticsRangeSwitcher currentPage="analytics" />);
			fireEvent.click(calendarButton());

			// 2026-10-09 .. 2026-10-15 is exactly "7 Days" anchored on
			// today, so the picker must land back on that pill rather than
			// leaving the row with nothing lit.
			fireEvent.click(
				screen.getByRole("button", { name: dayName(2026, 9, 9) }),
			);
			fireEvent.click(
				screen.getByRole("button", { name: dayName(2026, 9, 15) }),
			);

			expect(useAnalyticsRange.getState().range).toBe("7d");
			expect(
				screen.getByRole("radio", { name: t("analytics.range.7d") }),
			).toBeChecked();
			expect(calendarButton().getAttribute("aria-pressed")).toBe("false");
		} finally {
			vi.useRealTimers();
		}
	});

	it("renders no pill lit when a custom window is already committed", () => {
		useAnalyticsRange.setState({
			range: "custom",
			customWindow: { startKey: "2026-09-01", endKey: "2026-09-03" },
		});
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		for (const radio of screen.getAllByRole("radio")) {
			expect(radio).not.toBeChecked();
		}
		expect(calendarButton().getAttribute("aria-pressed")).toBe("true");
		// Committed ≠ open: the panel stays shut until the button asks.
		expect(panel()).toBeNull();

		fireEvent.click(calendarButton());
		expect(panel()).toBeTruthy();
		// Reopening must not disturb the committed selection.
		expect(useAnalyticsRange.getState().range).toBe("custom");
	});
});

describe("AnalyticsRangeSwitcher picker panel", () => {
	it("opens a single-month panel with no preset rail or footer actions", () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		fireEvent.click(calendarButton());

		// Panel dialog present; the rail (outer pills own those presets)
		// and the footer actions (dates auto-apply) are gone.
		expect(panel()).toBeTruthy();
		expect(
			screen.queryByRole("button", {
				name: t("analytics.rangePicker.apply"),
			}),
		).toBeNull();
		// Pills stay mounted behind the panel.
		expect(screen.getAllByRole("radio")).toHaveLength(ANALYTICS_RANGES.length);
	});

	it("hangs the panel from an anchor directly below the row", () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		fireEvent.click(calendarButton());
		const dialog = screen.getByRole("dialog", {
			name: t("analytics.rangeAria"),
		});

		// Trigger-less: the panel IS the floating container, with no
		// surface wrapper between it and the picker's root.
		const root = dialog.parentElement;
		expect(root?.getAttribute("class") ?? "").toContain("_root");
		expect(root?.getAttribute("class") ?? "").not.toContain("surface");

		// The anchor is a PLAIN div, so its positioning utilities actually
		// apply. The picker's own root is `position: relative` from its
		// stylesheet, which silently beats a layered `absolute` utility —
		// the old markup put these classes on the root and the panel
		// ended up hanging off the end of the row instead of under it.
		const anchor = root?.parentElement;
		const anchorClass = anchor?.getAttribute("class") ?? "";
		expect(anchorClass).toContain("absolute");
		expect(anchorClass).toContain("right-0");
		expect(anchorClass).toContain("top-[calc(100%+8px)]");
		// ...and the row is what it is positioned against.
		expect(anchor?.parentElement?.getAttribute("class") ?? "").toContain(
			"relative",
		);

		// align="end": the panel grows leftward from the anchor, so its
		// right edge stays under the calendar button rather than opening
		// off the right of the window.
		expect(dialog.getAttribute("style") ?? "").toContain("top right");
	});

	it("Escape closes the panel and leaves the preset highlighted", async () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		const preset = screen.getByRole("radio", {
			name: t("analytics.range.7d"),
		});
		fireEvent.click(calendarButton());
		expect(panel()).toBeTruthy();

		fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

		// The exit morph holds the panel briefly; it must unmount.
		await waitFor(() => expect(panel()).toBeNull());
		expect(preset).toBeChecked();
		expect(calendarButton().getAttribute("aria-pressed")).toBe("false");
	});

	it("outside dismiss unmounts the panel and leaves no hollow box", async () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		fireEvent.click(calendarButton());
		const dialog = screen.getByRole("dialog", {
			name: t("analytics.rangeAria"),
		});
		// Trigger-less: nothing sizes a surface, so there is no wrapper to
		// strand at the panel's old size once it closes.
		const root = dialog.parentElement;
		expect(root?.getAttribute("class") ?? "").not.toContain("surface");

		fireEvent.pointerDown(document.body);

		await waitFor(() => expect(panel()).toBeNull());
		expect(
			screen.getByRole("radio", { name: t("analytics.range.7d") }),
		).toBeChecked();
	});

	it("picking a preset while the panel is open closes it and applies", async () => {
		render(<AnalyticsRangeSwitcher currentPage="analytics" />);

		fireEvent.click(calendarButton());
		expect(panel()).toBeTruthy();

		fireEvent.click(
			screen.getByRole("radio", { name: t("analytics.range.30d") }),
		);

		expect(useAnalyticsRange.getState().range).toBe("30d");
		// The exit morph holds the panel briefly; it must unmount.
		await waitFor(() => expect(panel()).toBeNull());
		expect(
			screen.getByRole("radio", { name: t("analytics.range.30d") }),
		).toBeChecked();
	});
});
