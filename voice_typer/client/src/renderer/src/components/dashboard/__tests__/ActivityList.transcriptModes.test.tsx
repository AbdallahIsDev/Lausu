/**
 * Transcript modal: Final / Original / Compare.
 *
 * Covers the three-way selector, the cache-first open (no refetch on
 * switching), the reset-to-Final rule, per-mode copy payloads, and the
 * graceful single-view case for rows with no original.
 */
import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
	sonnerMock,
} from "@/__tests__/helpers/stableMocks";

vi.mock("@hugeicons/react", () => hugeiconsReactMock({ spreadProps: true }));
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());
vi.mock("sonner", () => sonnerMock());

import ActivityList from "@/components/dashboard/ActivityList";
import { t } from "@/i18n/i18n";
import type { HistoryRecord } from "@/types/ipc";

const FINAL = "THE FINAL TRANSLATED TEXT";
const ORIGINAL = "النص الأصلي قبل الترجمة";

const writeText = vi.fn().mockResolvedValue(undefined);

function rec(
	id: number,
	overrides: Partial<HistoryRecord> = {},
): HistoryRecord {
	return {
		id,
		text: `entry ${id}`,
		timestamp: new Date().toISOString(),
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

/** Instant swaps: the exit delay is skipped in reduced-motion mode. */
function preferReducedMotion(): void {
	window.matchMedia = ((query: string) => ({
		matches: query.includes("prefers-reduced-motion"),
		media: query,
		onchange: null,
		addListener: () => {},
		removeListener: () => {},
		addEventListener: () => {},
		removeEventListener: () => {},
		dispatchEvent: () => false,
	})) as unknown as typeof window.matchMedia;
}

async function openRow(
	overrides: Partial<HistoryRecord> = {},
	fetchFullRecord = vi.fn().mockResolvedValue({
		id: 1,
		text: FINAL,
		original_text: ORIGINAL,
	}),
) {
	render(
		<ActivityList
			items={[rec(1, overrides)]}
			lineClamp={3}
			onFetchFullRecord={fetchFullRecord}
		/>,
	);
	fireEvent.click(screen.getByTestId("activity-row-preview"));
	const dialog = await screen.findByRole("dialog");
	return { dialog, fetchFullRecord };
}

describe("ActivityList transcript view modes", () => {
	beforeEach(() => {
		preferReducedMotion();
		writeText.mockClear();
		Object.defineProperty(navigator, "clipboard", {
			value: { writeText },
			configurable: true,
		});
	});

	afterEach(() => {
		cleanup();
	});

	it("opens on Final and offers three views when an original exists", async () => {
		const { dialog } = await openRow({ has_original: true });
		await waitFor(() => {
			expect(
				within(dialog).getByTestId("transcript-modal-final").textContent,
			).toBe(FINAL);
		});
		const radios = within(dialog).getAllByRole("radio");
		expect(radios.map((r) => r.getAttribute("aria-label"))).toEqual([
			t("history.viewFinal"),
			t("history.viewOriginal"),
			t("history.viewCompare"),
		]);
		// Default selection is Final.
		expect(
			within(dialog)
				.getByRole("radio", { name: t("history.viewFinal") })
				.getAttribute("aria-checked"),
		).toBeNull(); // radios use the native `checked` property
		expect(
			(
				within(dialog).getByRole("radio", {
					name: t("history.viewFinal"),
				}) as HTMLInputElement
			).checked,
		).toBe(true);
	});

	it("hides the selector for a row without an original", async () => {
		const { dialog } = await openRow(
			{ has_original: false },
			vi.fn().mockResolvedValue({ id: 1, text: FINAL }),
		);
		await waitFor(() => {
			expect(
				within(dialog).getByTestId("transcript-modal-final").textContent,
			).toBe(FINAL);
		});
		expect(within(dialog).queryAllByRole("radio")).toHaveLength(0);
		// Copy still works (Final is the only version).
		fireEvent.click(
			within(dialog).getByRole("button", { name: t("history.copyText") }),
		);
		await waitFor(() => expect(writeText).toHaveBeenCalledWith(FINAL));
	});

	it("switches Final → Original → Compare without refetching", async () => {
		const { dialog, fetchFullRecord } = await openRow({ has_original: true });
		await waitFor(() => {
			expect(within(dialog).getByTestId("transcript-modal-final")).toBeTruthy();
		});
		expect(fetchFullRecord).toHaveBeenCalledTimes(1);

		fireEvent.click(
			within(dialog).getByRole("radio", { name: t("history.viewOriginal") }),
		);
		await waitFor(() => {
			expect(
				within(dialog).getByTestId("transcript-modal-original").textContent,
			).toBe(ORIGINAL);
		});

		fireEvent.click(
			within(dialog).getByRole("radio", { name: t("history.viewCompare") }),
		);
		await waitFor(() => {
			const original = within(dialog).getByTestId("transcript-modal-original");
			const final = within(dialog).getByTestId("transcript-modal-final");
			expect(original.textContent).toBe(ORIGINAL);
			expect(final.textContent).toBe(FINAL);
		});

		fireEvent.click(
			within(dialog).getByRole("radio", { name: t("history.viewFinal") }),
		);
		await waitFor(() => {
			expect(
				within(dialog).getByTestId("transcript-modal-final").textContent,
			).toBe(FINAL);
		});

		// Switching is pure local state: one fetch for the whole session.
		expect(fetchFullRecord).toHaveBeenCalledTimes(1);
	});

	it("uses the same text colour for both versions", async () => {
		const { dialog } = await openRow({ has_original: true });
		fireEvent.click(
			await within(dialog).findByRole("radio", {
				name: t("history.viewCompare"),
			}),
		);
		const final = await within(dialog).findByTestId("transcript-modal-final");
		const original = within(dialog).getByTestId("transcript-modal-original");
		for (const node of [final, original]) {
			expect(node.className).toContain("text-foreground");
			expect(node.className).not.toContain("text-muted-foreground");
		}
	});

	it("resets to Final after close and reopen", async () => {
		const { dialog } = await openRow({ has_original: true });
		fireEvent.click(
			await within(dialog).findByRole("radio", {
				name: t("history.viewOriginal"),
			}),
		);
		await waitFor(() => {
			expect(
				within(dialog).getByTestId("transcript-modal-original").textContent,
			).toBe(ORIGINAL);
		});
		fireEvent.click(
			within(dialog).getByRole("button", { name: t("common.close") }),
		);
		await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

		fireEvent.click(screen.getByTestId("activity-row-preview"));
		const reopened = await screen.findByRole("dialog");
		await waitFor(() => {
			expect(
				within(reopened).getByTestId("transcript-modal-final").textContent,
			).toBe(FINAL);
		});
		expect(
			(
				within(reopened).getByRole("radio", {
					name: t("history.viewFinal"),
				}) as HTMLInputElement
			).checked,
		).toBe(true);
	});

	it("copies only the visible version", async () => {
		const { dialog } = await openRow({ has_original: true });
		const copy = within(dialog).getByRole("button", {
			name: t("history.copyText"),
		});

		fireEvent.click(copy);
		await waitFor(() => expect(writeText).toHaveBeenCalledWith(FINAL));

		fireEvent.click(
			within(dialog).getByRole("radio", { name: t("history.viewOriginal") }),
		);
		await waitFor(() => {
			expect(
				within(dialog).getByTestId("transcript-modal-original").textContent,
			).toBe(ORIGINAL);
		});
		fireEvent.click(copy);
		await waitFor(() => expect(writeText).toHaveBeenLastCalledWith(ORIGINAL));

		fireEvent.click(
			within(dialog).getByRole("radio", { name: t("history.viewCompare") }),
		);
		await waitFor(() => {
			expect(within(dialog).getByTestId("transcript-modal-final")).toBeTruthy();
			expect(
				within(dialog).getByTestId("transcript-modal-original"),
			).toBeTruthy();
		});
		fireEvent.click(copy);
		await waitFor(() =>
			expect(writeText).toHaveBeenLastCalledWith(
				`${t("history.viewFinal")}:\n${FINAL}\n\n${t("history.viewOriginal")}:\n${ORIGINAL}`,
			),
		);
	});

	it("clamps the scroll container height to [25vh, 55vh] while the header and footer stay put", async () => {
		const { dialog } = await openRow({ has_original: true });
		const box = within(dialog).getByTestId("transcript-modal-text");
		expect(box.className).toContain("overflow-y-auto");
		expect(box.className).toContain("min-h-[25vh]");
		expect(box.className).toContain("max-h-[55vh]");
		// No standalone fixed height - only the min/max clamp.
		expect(box.className.split(" ")).not.toContain("h-[55vh]");
		expect(box.className).toContain("history-content-height");
		expect(box.className).toContain("bg-foreground/8");
		expect(box.className).toContain("p-4");
		expect(box.className).toContain("rounded-lg");
		// The dialog itself must not be the scroller.
		expect(dialog.className).not.toContain("overflow-y-auto");
		// Toggle + Copy live in the footer, outside the scroll box.
		expect(
			box.contains(
				within(dialog).getByRole("radio", { name: t("history.viewFinal") }),
			),
		).toBe(false);
	});

	it("sizes the content box naturally between 25vh and 55vh", async () => {
		const { dialog } = await openRow({ has_original: true });
		await waitFor(() => {
			expect(
				within(dialog).getByTestId("transcript-modal-final").textContent,
			).toBe(FINAL);
		});
		const box = within(dialog).getByTestId("transcript-modal-text");
		const content = box.querySelector<HTMLElement>("[data-view]");
		if (!content) throw new Error("transcript content wrapper not found");
		const min = Math.round(window.innerHeight * 0.25);
		const max = Math.round(window.innerHeight * 0.55);

		const setHeightAndRemeasure = (px: number): void => {
			Object.defineProperty(content, "offsetHeight", {
				configurable: true,
				value: px,
			});
			// The layout effect registers a window resize listener that
			// recomputes the clamp from the measured content height.
			window.dispatchEvent(new Event("resize"));
		};

		// Very short text -> clamped UP to the 25vh floor.
		setHeightAndRemeasure(10);
		await waitFor(() => expect(box.style.height).toBe(`${min}px`));

		// Medium text -> natural height, between the two bounds.
		const medium = Math.round((min + max) / 2);
		setHeightAndRemeasure(medium);
		await waitFor(() => expect(box.style.height).toBe(`${medium}px`));

		// Very long text -> clamped DOWN to the 55vh ceiling (internal scroll).
		setHeightAndRemeasure(window.innerHeight * 2);
		await waitFor(() => expect(box.style.height).toBe(`${max}px`));
		expect(box.className).toContain("overflow-y-auto");
	});

	it("re-measures the box when switching between modes", async () => {
		const { dialog } = await openRow({ has_original: true });
		const box = within(dialog).getByTestId("transcript-modal-text");
		const min = Math.round(window.innerHeight * 0.25);
		const max = Math.round(window.innerHeight * 0.55);

		// Final shows a short text -> floor.
		let content = box.querySelector<HTMLElement>(`[data-view="final"]`);
		if (!content) throw new Error("final content wrapper not found");
		Object.defineProperty(content, "offsetHeight", {
			configurable: true,
			value: 10,
		});
		window.dispatchEvent(new Event("resize"));
		await waitFor(() => expect(box.style.height).toBe(`${min}px`));

		// Switch to Original (its data-view node remounts) with a long text.
		fireEvent.click(
			within(dialog).getByRole("radio", { name: t("history.viewOriginal") }),
		);
		await waitFor(() => {
			expect(box.querySelector(`[data-view="original"]`)).not.toBeNull();
		});
		content = box.querySelector<HTMLElement>(`[data-view="original"]`);
		if (!content) throw new Error("original content wrapper not found");
		Object.defineProperty(content, "offsetHeight", {
			configurable: true,
			value: window.innerHeight * 2,
		});
		window.dispatchEvent(new Event("resize"));
		await waitFor(() => expect(box.style.height).toBe(`${max}px`));
	});
});
