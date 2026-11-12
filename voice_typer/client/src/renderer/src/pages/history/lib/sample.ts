// Measured-skeleton sample for the History list. EIGHT rows across
// three days: one viewport of the 50-row first page
// (`HISTORY_PAGE_SIZE`), so the loading state reserves the list a user
// sees before scrolling. Reserving all 50 would draw a
// multi-thousand-pixel skeleton for a history with three rows;
// reserving fewer under-reserves every populated first paint.
import { dateKey } from "@/lib/format";
import type { HistoryRecord, TodayStats } from "@/types/ipc";

export interface HistoryListPayload {
	records: HistoryRecord[];
	stats: TodayStats;
}

function utcStamp(daysAgo: number, hour: number): string {
	const d = new Date();
	d.setUTCDate(d.getUTCDate() - daysAgo);
	d.setUTCHours(hour, 0, 0, 0);
	const pad = (n: number) => String(n).padStart(2, "0");
	return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}

function makeRecord(
	id: number,
	daysAgo: number,
	hour: number,
	text: string,
	duration: number,
	favorite = 0,
): HistoryRecord {
	return {
		id,
		text,
		timestamp: utcStamp(daysAgo, hour),
		duration,
		model: "tiny",
		device: "cpu",
		word_count: text.trim().split(/\s+/).length,
		char_count: text.length,
		favorite,
		language: "en",
	};
}

const SAMPLE_RECORDS: HistoryRecord[] = [
	makeRecord(
		302,
		0,
		11,
		"The meeting notes from this morning need to go to the whole team right away, thanks.",
		38,
	),
	makeRecord(
		303,
		0,
		9,
		"Remind me to book the dentist for next Tuesday and move the stand-up to ten.",
		12,
	),
	makeRecord(
		304,
		0,
		8,
		"Quick note before I forget: the staging server is back up and the deploy went out clean.",
		21,
	),
	makeRecord(
		301,
		1,
		10,
		"Let me think through the project plan carefully before we commit to a launch date. We should review the budget, confirm the staffing, and check the dependencies first.",
		71,
		1,
	),
	makeRecord(
		305,
		1,
		16,
		"Draft reply to the client: the first milestone is on track and the design review lands Thursday.",
		24,
	),
	makeRecord(
		306,
		1,
		12,
		"Add oat milk, coffee beans, and those small notebooks to the shopping list for the weekend.",
		14,
	),
	makeRecord(
		300,
		2,
		15,
		"Please send the invoice to the client before Friday.",
		19,
	),
	makeRecord(
		307,
		2,
		9,
		"The standup summary goes in the shared doc, three bullet points maximum, no action items.",
		17,
	),
];

const todayKey = dateKey(new Date().toISOString());
let statsCount = 0;
let statsChars = 0;
let statsWords = 0;
let statsDuration = 0;
for (const r of SAMPLE_RECORDS) {
	if (dateKey(r.timestamp) === todayKey) {
		statsCount += 1;
		statsChars += r.char_count;
		statsWords += r.word_count;
		statsDuration += r.duration;
	}
}

export const SAMPLE_HISTORY_LIST: HistoryListPayload = {
	records: SAMPLE_RECORDS,
	stats: {
		count: statsCount,
		chars: statsChars,
		word_count: statsWords,
		duration: statsDuration,
	},
};
