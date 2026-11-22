/**
 * History full-text cache: the hover prefetch that makes the transcript
 * modal open with BOTH versions and zero IPC calls.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import { __resetIpcCacheForTests } from "@/lib/ipcCache";
import { __resetPrefetchFlightsForTests } from "@/lib/snapshotCache";
import {
	clearHistoryTexts,
	forgetHistoryText,
	HISTORY_TEXTS_MAX_ENTRIES,
	peekHistoryText,
	prefetchHistoryTexts,
	pruneHistoryTexts,
	writeHistoryText,
} from "@/pages/history/hooks/useHistoryCache";
import type { HistoryRecord } from "@/types/ipc";

function row(
	id: number,
	overrides: Partial<HistoryRecord> = {},
): HistoryRecord {
	return {
		id,
		text: `preview ${id}`,
		timestamp: "2026-11-22 10:00:00",
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

describe("history text cache", () => {
	beforeEach(() => {
		__resetIpcCacheForTests();
		__resetPrefetchFlightsForTests();
		clearHistoryTexts();
	});

	it("fetches only rows that actually need a full record", async () => {
		const call = vi.fn(
			async (_type: string, data?: Record<string, unknown>) => ({
				id: Number(data?.id),
				text: `full ${data?.id}`,
				original_text: `raw ${data?.id}`,
			}),
		);

		await prefetchHistoryTexts(call as never, [
			row(1, { text_truncated: true }),
			row(2, { has_original: true }),
			// Short and untranslated: the list payload is already complete.
			row(3),
		]);

		expect(call).toHaveBeenCalledTimes(2);
		expect(call).toHaveBeenCalledWith("get_transcription_text", { id: 1 });
		expect(call).toHaveBeenCalledWith("get_transcription_text", { id: 2 });
		expect(peekHistoryText(1)).toEqual({
			text: "full 1",
			original_text: "raw 1",
		});
		expect(peekHistoryText(3)).toBeNull();
	});

	it("does not refetch rows already cached", async () => {
		const call = vi.fn(
			async (_type: string, data?: Record<string, unknown>) => ({
				id: Number(data?.id),
				text: `full ${data?.id}`,
			}),
		);
		await prefetchHistoryTexts(call as never, [row(7, { has_original: true })]);
		expect(call).toHaveBeenCalledTimes(1);

		await prefetchHistoryTexts(call as never, [row(7, { has_original: true })]);
		expect(call).toHaveBeenCalledTimes(1);
	});

	it("collapses concurrent prefetches into one flight", async () => {
		const call = vi.fn(
			async (_type: string, data?: Record<string, unknown>) => ({
				id: Number(data?.id),
				text: `full ${data?.id}`,
			}),
		);
		await Promise.all([
			prefetchHistoryTexts(call as never, [row(9, { text_truncated: true })]),
			prefetchHistoryTexts(call as never, [row(9, { text_truncated: true })]),
		]);
		expect(call).toHaveBeenCalledTimes(1);
	});

	it("evicts the oldest entry past the cap", () => {
		for (let id = 1; id <= HISTORY_TEXTS_MAX_ENTRIES + 1; id += 1) {
			writeHistoryText(id, { text: `t${id}` });
		}
		expect(peekHistoryText(1)).toBeNull();
		expect(peekHistoryText(2)).not.toBeNull();
		expect(peekHistoryText(HISTORY_TEXTS_MAX_ENTRIES + 1)).not.toBeNull();
	});

	it("prunes rows that disappeared from the refreshed window", () => {
		writeHistoryText(1, { text: "a" });
		writeHistoryText(2, { text: "b" });
		pruneHistoryTexts([2, 3]);
		expect(peekHistoryText(1)).toBeNull();
		expect(peekHistoryText(2)).not.toBeNull();
	});

	it("forgets a single deleted row", () => {
		writeHistoryText(5, { text: "a" });
		forgetHistoryText(5);
		expect(peekHistoryText(5)).toBeNull();
	});
});

describe("handleFetchFullRecord", () => {
	beforeEach(() => {
		__resetIpcCacheForTests();
		__resetPrefetchFlightsForTests();
		clearHistoryTexts();
	});

	it("resolves from the prefetched cache without any IPC call", async () => {
		const { renderHook } = await import("@testing-library/react");
		const { useHistoryRecordActions } = await import(
			"@/pages/history/hooks/useHistoryRecordActions"
		);
		writeHistoryText(11, { text: "FULL FINAL", original_text: "RAW ORIGINAL" });
		const call = vi.fn();
		const { result } = renderHook(() =>
			useHistoryRecordActions({
				call: call as never,
				records: [],
				load: vi.fn(),
				setRecords: vi.fn(),
			}),
		);

		const record = await result.current.handleFetchFullRecord(11);
		expect(call).not.toHaveBeenCalled();
		expect(record).toEqual({
			id: 11,
			text: "FULL FINAL",
			original_text: "RAW ORIGINAL",
		});
	});

	it("falls back to one IPC call and writes the result through", async () => {
		const { renderHook } = await import("@testing-library/react");
		const { useHistoryRecordActions } = await import(
			"@/pages/history/hooks/useHistoryRecordActions"
		);
		const call = vi.fn().mockResolvedValue({
			id: 12,
			text: "LIVE FINAL",
			original_text: "LIVE RAW",
		});
		const { result } = renderHook(() =>
			useHistoryRecordActions({
				call: call as never,
				records: [],
				load: vi.fn(),
				setRecords: vi.fn(),
			}),
		);

		const record = await result.current.handleFetchFullRecord(12);
		expect(call).toHaveBeenCalledTimes(1);
		expect(record).toEqual({
			id: 12,
			text: "LIVE FINAL",
			original_text: "LIVE RAW",
		});
		// Second open is a cache hit.
		await result.current.handleFetchFullRecord(12);
		expect(call).toHaveBeenCalledTimes(1);
	});
});
