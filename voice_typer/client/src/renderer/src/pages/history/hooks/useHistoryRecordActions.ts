// History per-row record actions hook.
// per-row event flows, delete-with-undo, favorite toggle, and the
// lazy full-text fetch for expandable rows, are cohesive IPC-backed
// event logic that belongs in a named, testable hook instead of the
// page root. The list rendering (ActivityList wiring) stays in the
// page; this hook owns the handlers it wires up.
// All state mutations go through the passed-in callbacks (`setRecords`
// / `load` from useHistoryCache), so the hook stays a pure handler
// factory, the page keeps owning the data.

import { useCallback } from "react";
import { toast } from "sonner";
import type { usePython } from "@/hooks/usePython";
import { showUndoableToast } from "@/hooks/useSnackbar";
import { t } from "@/i18n/i18n";
import type { HistoryRecord, TranscriptionTextData } from "@/types/ipc";

import {
	forgetHistoryText,
	peekHistoryText,
	writeHistoryText,
} from "./useHistoryCache";

export interface UseHistoryRecordActionsOptions {
	/** The Python bridge call (from usePython). */
	call: ReturnType<typeof usePython>["call"];
	/** The currently loaded records (delete needs the pre-delete row). */
	records: HistoryRecord[];
	/** The cache hook's load (re-fetches after an undo restore). */
	load: (query?: string, favoritesOnly?: boolean) => Promise<unknown>;
	/** The cache hook's records-state setter. */
	setRecords: React.Dispatch<React.SetStateAction<HistoryRecord[]>>;
}

export interface UseHistoryRecordActionsReturn {
	/** Delete a row, offering an undo toast that restores it. */
	handleDelete: (id: number) => Promise<void>;
	/** Toggle a row's favorite flag in the backend + local cache. */
	handleToggleFavorite: (id: number) => Promise<void>;
	/** Lazy full-text fetch for an expandable row (null on failure). */
	handleFetchFullText: (id: number) => Promise<string | null>;
	/** Same IPC call, keeping the optional pre-translation original text. */
	handleFetchFullRecord: (id: number) => Promise<TranscriptionTextData | null>;
}

export function useHistoryRecordActions({
	call,
	records,
	load,
	setRecords,
}: UseHistoryRecordActionsOptions): UseHistoryRecordActionsReturn {
	const handleDelete = useCallback(
		async (id: number) => {
			// Capture the record before delete for Undo. The list projection
			// omits original_text on purpose, so fetch the full row for a
			// translated entry — otherwise Undo would silently lose it.
			const listed = records.find((r) => r.id === id);
			let deleted: HistoryRecord | undefined = listed;
			try {
				const full = await call<TranscriptionTextData | null>(
					"get_transcription_text",
					{
						id,
					},
				);
				if (listed && full)
					deleted = { ...listed, original_text: full.original_text };
			} catch {
				// Best effort: undo still restores the final text.
			}
			try {
				await call("delete_history", { id });
				// The row is gone: drop its cached full text so a stale
				// modal entry can never outlive the record. Undo restores
				// under a NEW id, which refetches on open.
				forgetHistoryText(id);
				setRecords((prev) => prev.filter((r) => r.id !== id));
				if (deleted) {
					showUndoableToast(
						t("history.entryDeleted"),
						async () => {
							try {
								await call("restore_history", {
									record: deleted,
								});
								load();
								toast.success(t("history.entryRestored"));
							} catch {
								toast.error(t("history.restoreFailed"));
							}
						},
						{
							undoLabel: t("history.undo"),
							type: "warning",
							timeoutMs: 6000,
						},
					);
				}
			} catch {
				toast.error(t("history.deleteFailed"));
			}
		},
		[call, records, load, setRecords],
	);

	const handleToggleFavorite = useCallback(
		async (id: number) => {
			try {
				const res = await call<{ favorite: number }>("toggle_favorite", {
					id,
				});
				setRecords((prev) =>
					prev.map((r) => (r.id === id ? { ...r, favorite: res.favorite } : r)),
				);
			} catch {
				toast.error(t("history.favoriteFailed"));
			}
		},
		[call, setRecords],
	);

	// Full-record fetch for the transcript modal. Cache-first: the hover
	// prefetch already stores BOTH versions (see `prefetchHistoryTexts`),
	// so opening a row normally resolves without any IPC round-trip. A
	// miss (direct navigation, prefetch still in flight, evicted entry)
	// falls back to the single-row call and writes through.
	const handleFetchFullRecord = useCallback(
		async (id: number) => {
			const cached = peekHistoryText(id);
			if (cached) {
				return {
					id,
					text: cached.text,
					original_text: cached.original_text,
				} satisfies TranscriptionTextData;
			}
			try {
				const full = await call<TranscriptionTextData>(
					"get_transcription_text",
					{
						id,
					},
				);
				if (full) {
					writeHistoryText(id, {
						text: typeof full.text === "string" ? full.text : "",
						original_text:
							typeof full.original_text === "string"
								? full.original_text
								: undefined,
					});
				}
				return full;
			} catch {
				return null;
			}
		},
		[call],
	);

	const handleFetchFullText = useCallback(
		async (id: number): Promise<string | null> =>
			(await handleFetchFullRecord(id))?.text ?? null,
		[handleFetchFullRecord],
	);

	return {
		handleDelete,
		handleToggleFavorite,
		handleFetchFullText,
		handleFetchFullRecord,
	};
}
