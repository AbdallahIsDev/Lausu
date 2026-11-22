/**
 * ActivityList: date grouping, per-item badges/metadata, the clamped
 * preview + transcript modal, truncation detection, star fill and the
 * cross-surface row highlight.
 *
 * The Home/Dashboard surfaces use the same component flat, so every new
 * field is optional and every test covers both `groupByDate` modes.
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
	resetStableMocks,
	sonnerMock,
} from "@/__tests__/helpers/stableMocks";

vi.mock("@hugeicons/react", () => hugeiconsReactMock({ spreadProps: true }));
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());
vi.mock("sonner", () => sonnerMock());

import { toast } from "sonner";
import ActivityList from "@/components/dashboard/ActivityList";
import { t } from "@/i18n/i18n";
import type { HistoryRecord } from "@/types/ipc";

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

function mediaRec(
	id: number,
	timestamp: string,
	overrides: Partial<HistoryRecord> = {},
): HistoryRecord {
	return rec(id, timestamp, {
		kind: "media",
		source_type: "youtube",
		source_title: "Conference talk",
		thumbnail_url: "https://example.com/thumb.jpg",
		media_duration_seconds: 754,
		processing_seconds: 130,
		method: "subtitles",
		word_count: 320,
		text: "media transcript preview ".repeat(20).trim(),
		...overrides,
	});
}

afterEach(() => {
	cleanup();
	resetStableMocks();
	vi.unstubAllGlobals();
});

describe("ActivityList date grouping", () => {
	it("renders one section per local day with localized headings; rows show time only", () => {
		const items = [
			rec(1, localIso(0, 12)),
			rec(2, localIso(0, 5)),
			rec(3, localIso(1, 8)),
		];
		render(<ActivityList items={items} lineClamp={3} groupByDate />);

		expect(screen.getByText("Today")).toBeTruthy();
		expect(screen.getByText("Yesterday")).toBeTruthy();

		// Grouped rows show only time-of-day, never a repeated full date.
		for (const meta of screen.getAllByTestId("activity-row-meta")) {
			const text = meta.textContent ?? "";
			expect(text).not.toMatch(/[A-Z][a-z]{2}\s+\d/);
			expect(text).toMatch(/\d{1,2}:\d{2}/);
		}
	});

	it("renders one SEPARATE CARD per local day with a visible gap between cards", () => {
		const items = [
			rec(1, localIso(0, 12)),
			rec(2, localIso(0, 5)),
			rec(3, localIso(1, 8)),
		];
		const { container } = render(
			<ActivityList items={items} lineClamp={3} groupByDate />,
		);

		const sections = container.querySelectorAll("section");
		expect(sections).toHaveLength(2);
		for (const section of sections) {
			expect(section.className).toContain("rounded-lg");
			expect(section.className).toContain("border");
			expect(section.className).toContain("bg-surface-subtle");
		}
		expect(sections[0]?.parentElement).toBe(sections[1]?.parentElement);
		expect(sections[0]?.parentElement?.className).toContain("gap-4");
		expect(container.querySelector(".border-t")).toBeNull();

		expect(screen.getByText("Today").closest("section")).toHaveTextContent(
			"entry 1",
		);
		expect(screen.getByText("Yesterday").closest("section")).toHaveTextContent(
			"entry 3",
		);
	});

	it("flat mode keeps the full date+time line and no headers", () => {
		render(<ActivityList items={[rec(1, localIso(0, 12))]} lineClamp={2} />);
		expect(screen.queryByText("Today")).toBeNull();
		expect(screen.queryByText("Yesterday")).toBeNull();
		expect(screen.getByTestId("activity-row-meta").textContent).toMatch(
			/[A-Z][a-z]{2}\s+\d/,
		);
	});

	it("hideHeader suppresses the title row", () => {
		render(<ActivityList items={[rec(1, localIso(0, 12))]} hideHeader />);
		expect(screen.queryByText(t("home.recentActivity"))).toBeNull();
	});

	it("list root opts into text wrapping and carries no margin utilities", () => {
		for (const props of [
			{ items: [rec(1, localIso(0, 12))] },
			{ items: [rec(1, localIso(0, 12))], groupByDate: true },
			{ items: [] as HistoryRecord[] },
		]) {
			const { container, unmount } = render(<ActivityList {...props} />);
			const root = container.firstElementChild;
			expect(root?.className).toContain("[text-wrap:auto]");
			expect(root?.className).not.toMatch(/(^|\s)(m[trblxy]|space-[xy])-/);
			unmount();
		}
	});
});

describe("ActivityList badges and metadata", () => {
	it("shows no badge for normal dictation and a Media badge for media rows", () => {
		const { rerender } = render(
			<ActivityList items={[rec(1, localIso(0, 12))]} />,
		);
		expect(screen.queryByText(t("history.dictationBadge"))).toBeNull();
		expect(screen.queryByText(t("history.mediaBadge"))).toBeNull();

		rerender(<ActivityList items={[mediaRec(2, localIso(0, 12))]} />);
		const mediaBadge = screen.getByText(t("history.mediaBadge"));
		expect(
			mediaBadge.parentElement?.querySelector('[data-name="Film01Icon"]'),
		).toBeTruthy();
	});

	it("renders plugin model ids as user-facing labels", () => {
		render(
			<ActivityList
				items={[rec(1, localIso(0, 12), { model: "google-stt-web" })]}
			/>,
		);
		const meta = screen.getByTestId("activity-row-meta").textContent ?? "";
		expect(meta).toContain("Google STT");
		expect(meta).not.toContain("web");
		expect(meta).not.toContain("google-stt");
	});

	it("puts the transcription before its metadata and action buttons", () => {
		render(
			<ActivityList
				items={[rec(1, localIso(0, 12))]}
				onDelete={vi.fn()}
				onToggleFavorite={vi.fn()}
			/>,
		);
		const preview = screen.getByTestId("activity-row-preview");
		const meta = screen.getByTestId("activity-row-meta");
		expect(
			preview.compareDocumentPosition(meta) & Node.DOCUMENT_POSITION_FOLLOWING,
		).toBeTruthy();
		expect(
			screen.queryByRole("button", { name: t("home.showMore") }),
		).toBeNull();
	});

	it("shows the media source title and thumbnail above the preview", () => {
		const { container } = render(
			<ActivityList items={[mediaRec(2, localIso(0, 12))]} />,
		);
		const title = screen.getByText("Conference talk");
		expect(title.className).toContain("truncate");
		const thumb = container.querySelector('img[alt=""]');
		expect(thumb?.getAttribute("src")).toBe("https://example.com/thumb.jpg");
		expect(thumb?.className).toContain("size-10");
		expect(thumb?.className).toContain("rounded-lg");
		// Media details sit below the transcription, with the metadata.
		const preview = screen.getByTestId("activity-row-preview");
		expect(
			preview.compareDocumentPosition(title) & Node.DOCUMENT_POSITION_FOLLOWING,
		).toBeTruthy();
	});

	it("renders time, words, duration, processing, model and source, never characters", () => {
		render(<ActivityList items={[mediaRec(2, localIso(0, 12))]} groupByDate />);
		const meta = screen.getByTestId("activity-row-meta").textContent ?? "";
		expect(meta).toContain(t("activityList.wordsCount", { count: "320" }));
		expect(meta).toContain("12:34"); // media_duration_seconds = 754
		expect(meta).toContain("2m 10s"); // processing_seconds = 130
		expect(meta).toContain("Tiny");
		expect(meta).toContain(t("media.metaYoutube"));
		expect(meta).toContain(t("media.metaSubtitles"));
		expect(meta).not.toContain("haracter");
	});

	it("falls back to countWords when word_count is missing and hides unavailable pieces", () => {
		render(
			<ActivityList
				items={[
					rec(1, localIso(0, 12), {
						word_count: undefined as unknown as number,
						text: "alpha beta gamma delta",
						model: "",
					}),
				]}
			/>,
		);
		const meta = screen.getByTestId("activity-row-meta").textContent ?? "";
		expect(meta).toContain(t("activityList.wordsCount", { count: "4" }));
		expect(meta).not.toContain("tiny");
		expect(meta).not.toContain(t("media.metaYoutube"));
	});

	it("keeps actions at the right of the meta row", () => {
		render(
			<ActivityList
				items={[rec(1, localIso(0, 12))]}
				onDelete={vi.fn()}
				onToggleFavorite={vi.fn()}
			/>,
		);
		const metaRow = screen.getByTestId("activity-row-meta").parentElement;
		expect(metaRow?.className).toContain("justify-between");
		const copyBtn = screen.getByRole("button", { name: t("history.copyText") });
		expect(metaRow?.lastElementChild?.contains(copyBtn)).toBe(true);
		const preview = screen.getByTestId("activity-row-preview");
		expect(preview.getAttribute("dir")).toBe("auto");
		expect(metaRow?.contains(preview)).toBe(false);
	});
});

describe("ActivityList preview and transcript modal", () => {
	beforeEach(() => {
		Object.defineProperty(navigator, "clipboard", {
			value: { writeText: vi.fn().mockResolvedValue(undefined) },
			configurable: true,
		});
	});

	it("clamps the preview to three lines with no inline expand/mask artifacts", () => {
		const { container } = render(
			<ActivityList items={[rec(1, localIso(0, 12))]} lineClamp={3} />,
		);
		const preview = screen.getByTestId("activity-row-preview");
		expect(preview.className).toContain("line-clamp-3");
		expect(preview.getAttribute("aria-label")).toBe(
			t("history.viewTranscript"),
		);
		expect(preview.className).not.toContain("mask-b-");
		expect(
			container.querySelector('[role="button"][aria-expanded]'),
		).toBeNull();
		expect(container.querySelector(".absolute")).toBeNull();
		expect(screen.queryByText(t("home.showLess"))).toBeNull();
	});

	it("opens the modal with the full transcript and copies it", async () => {
		const fetchFullText = vi.fn().mockResolvedValue("THE COMPLETE TRANSCRIPT");
		render(
			<ActivityList
				items={[mediaRec(7, localIso(0, 12), { text_truncated: true })]}
				lineClamp={3}
				onFetchFullText={fetchFullText}
			/>,
		);
		fireEvent.click(screen.getByTestId("activity-row-preview"));

		const dialog = await screen.findByRole("dialog");
		expect(fetchFullText).toHaveBeenCalledWith(7);
		// Media title is the modal title, not row metadata.
		expect(within(dialog).getByText("Conference talk")).toBeTruthy();
		const text = within(dialog).getByTestId("transcript-modal-text");
		expect(text.textContent).toBe("THE COMPLETE TRANSCRIPT");
		expect(text.getAttribute("dir")).toBe("auto");
		expect(
			dialog.querySelector('[data-testid="activity-row-meta"]'),
		).toBeNull();

		const writeText = navigator.clipboard.writeText as ReturnType<typeof vi.fn>;
		fireEvent.click(
			within(dialog).getByRole("button", { name: t("history.copyText") }),
		);
		await waitFor(() => {
			expect(writeText).toHaveBeenCalledWith("THE COMPLETE TRANSCRIPT");
		});

		fireEvent.click(
			within(dialog).getByRole("button", { name: t("common.close") }),
		);
		await waitFor(() => {
			expect(screen.queryByRole("dialog")).toBeNull();
		});
	});

	it("modal transcript uses auto text wrap, not the global balance", async () => {
		// The global `html, body { text-wrap: balance }` would otherwise be
		// inherited by the modal text. `text-wrap-auto` is NOT a Tailwind
		// utility, so only the bracketed arbitrary form overrides it.
		render(<ActivityList items={[rec(9, localIso(0, 12))]} lineClamp={3} />);
		fireEvent.click(screen.getByTestId("activity-row-preview"));
		const dialog = await screen.findByRole("dialog");
		const text = within(dialog).getByTestId("transcript-modal-text");
		expect(text.className).toContain("[text-wrap:auto]");
		expect(text.className).not.toContain("text-wrap-auto");
	});

	it("uses the formatted time/date as the title for dictation rows", async () => {
		render(<ActivityList items={[rec(1, localIso(0, 12))]} lineClamp={3} />);
		fireEvent.click(screen.getByTestId("activity-row-preview"));
		const dialog = await screen.findByRole("dialog");
		expect(
			within(dialog).getByTestId("transcript-modal-text").textContent,
		).toBe("entry 1");
	});

	it("keyboard activation opens the modal", async () => {
		render(<ActivityList items={[rec(1, localIso(0, 12))]} lineClamp={3} />);
		const preview = screen.getByTestId("activity-row-preview");
		fireEvent.keyDown(preview, { key: "Enter" });
		expect(await screen.findByRole("dialog")).toBeTruthy();
	});

	it("a failed full-text fetch toasts and keeps the preview in the modal", async () => {
		render(
			<ActivityList
				items={[
					rec(3, localIso(0, 12), {
						text_truncated: true,
						text: "available preview",
					}),
				]}
				onFetchFullText={vi.fn().mockRejectedValue(new Error("boom"))}
			/>,
		);
		fireEvent.click(screen.getByTestId("activity-row-preview"));
		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith(
				t("activityList.loadTextFailed"),
			);
		});
		expect(
			within(screen.getByRole("dialog")).getByTestId("transcript-modal-text")
				.textContent,
		).toBe("available preview");
	});

	it("row action buttons never open the modal", () => {
		render(
			<ActivityList
				items={[rec(1, localIso(0, 12))]}
				onDelete={vi.fn()}
				onToggleFavorite={vi.fn()}
			/>,
		);
		fireEvent.click(
			screen.getByRole("button", { name: t("activityList.addToFavorites") }),
		);
		fireEvent.click(
			screen.getByRole("button", { name: t("history.copyText") }),
		);
		expect(screen.queryByRole("dialog")).toBeNull();
	});

	it("the list DOM stays mounted and unchanged while the modal is open", async () => {
		const { container } = render(
			<ActivityList
				items={[
					rec(1, localIso(0, 12)),
					rec(2, localIso(0, 11)),
					rec(3, localIso(1, 9)),
				]}
				lineClamp={3}
				groupByDate
			/>,
		);
		const before = Array.from(
			container.querySelectorAll("[data-history-row-id]"),
		);
		expect(before).toHaveLength(3);
		const firstPreview = screen.getAllByTestId("activity-row-preview")[0];
		expect(firstPreview).toBeDefined();
		fireEvent.click(firstPreview as HTMLElement);
		await screen.findByRole("dialog");
		const after = Array.from(
			container.querySelectorAll("[data-history-row-id]"),
		);
		expect(after).toHaveLength(3);
		after.forEach((row, i) => {
			expect(before.indexOf(row)).toBe(i);
		});
	});
});

describe("ActivityList star fill and highlight", () => {
	it("fills an active star solid amber and leaves an inactive star outlined", () => {
		const { container, rerender } = render(
			<ActivityList
				items={[rec(1, localIso(0, 12), { favorite: 1 })]}
				onToggleFavorite={vi.fn()}
			/>,
		);
		const active = container.querySelector('[data-name="StarIcon"]');
		expect(active?.getAttribute("fill")).toBe("currentColor");
		expect(active?.className).toContain("text-warning");

		rerender(
			<ActivityList
				items={[rec(1, localIso(0, 12), { favorite: 0 })]}
				onToggleFavorite={vi.fn()}
			/>,
		);
		const inactive = container.querySelector('[data-name="StarIcon"]');
		expect(inactive?.getAttribute("fill")).toBe("none");
		expect(inactive?.className).not.toContain("text-warning");
	});

	it("rings and scrolls the highlighted row into view", () => {
		const scrollIntoView = vi.fn();
		Object.defineProperty(Element.prototype, "scrollIntoView", {
			configurable: true,
			value: scrollIntoView,
		});
		const { container, unmount } = render(
			<ActivityList
				items={[rec(7, localIso(0, 12))]}
				lineClamp={3}
				highlightId={7}
			/>,
		);
		const row = container.querySelector('[data-history-row-id="7"]');
		expect(row?.className).toContain("ring-primary");
		expect(scrollIntoView).toHaveBeenCalled();
		unmount();
		delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView;
	});
});
