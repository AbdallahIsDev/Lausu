// Measured-skeleton samples for the Home sections. While stats/recent are
// null the <Skeleton> measures these samples, so they carry typical today
// totals plus three realistic recent records (layout only, no user text).
import type { HistoryRecord, TodayStats } from "@/types/ipc";

export const SAMPLE_TODAY_STATS: TodayStats = {
	count: 8,
	chars: 1240,
	word_count: 214,
	duration: 420,
};

function stampHoursAgo(hoursAgo: number): string {
	const d = new Date(Date.now() - hoursAgo * 60 * 60 * 1000);
	const pad = (n: number) => String(n).padStart(2, "0");
	return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}

function makeRecord(
	id: number,
	hoursAgo: number,
	text: string,
	duration: number,
): HistoryRecord {
	return {
		id,
		text,
		timestamp: stampHoursAgo(hoursAgo),
		duration,
		model: "tiny",
		device: "cpu",
		word_count: text.trim().split(/\s+/).length,
		char_count: text.length,
		favorite: 0,
		language: "en",
	};
}

export const SAMPLE_HOME_RECENT: HistoryRecord[] = [
	makeRecord(
		104,
		1,
		"Please send the invoice to the client before Friday.",
		18,
	),
	makeRecord(
		103,
		3,
		"The meeting notes from this morning need to go to the whole team right away, thanks.",
		48,
	),
	makeRecord(102, 5, "The report is ready for review on my desk.", 12),
	// The initial load fetches `limit: 4`, so the sample carries four rows.
	makeRecord(
		101,
		7,
		"Can we move the call to later this afternoon when everyone is back from lunch?",
		27,
	),
];
