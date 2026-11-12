// Measured-skeleton sample for the Dashboard body. The sample carries
// the same payload shape the page assembles from the hook return
// (data + period + activity + heatmap + corrections + range), built
// from fake records so no component reads an undefined field while
// its shape is measured.
import { SAMPLE_CONFIG } from "@/components/skullet/sampleConfig";
import { dateKey, localDateKey } from "@/lib/format";
import type { LausuConfig } from "@/types/config";
import type { HistoryRecord } from "@/types/ipc";
import { buildDictationHeatmap, type DictationHeatmap } from "./heatmap";
import {
	type ActivityChartData,
	buildActivityBars,
	type CorrectionStats,
	type CorrectionUsageSnapshot,
	computeCorrectionStats,
	computePeriodStats,
	computeStreaks,
	type DashboardData,
	type PeriodStats,
	type RangeId,
} from "./streaks";

export interface DashboardBodyPayload {
	data: DashboardData;
	period: PeriodStats;
	activity: ActivityChartData;
	heatmap: DictationHeatmap;
	correctionStats: CorrectionStats;
	range: RangeId;
	customCapped: boolean;
	customWindowLabel?: string;
	configRaw: LausuConfig;
}

// Fake sentences with typical dictation lengths (short / medium / long).
// No real user text: layout only.
const SAMPLE_TEXTS = [
	"Please send the invoice to the client before Friday.",
	"The meeting notes from this morning need to go to the whole team right away, thanks.",
	"Let me think through the project plan carefully before we commit to a launch date. We should review the budget, confirm the staffing, and check the dependencies first.",
	"The report is ready for review on my desk.",
	"Can we move the call to later this afternoon when everyone is back from lunch?",
	"I will draft the announcement post today and share it for feedback before it goes live tomorrow morning at nine.",
	"Remember to lock the office on your way out tonight.",
];

function utcStamp(daysAgo: number, hour: number, minute = 0): string {
	const d = new Date();
	d.setUTCDate(d.getUTCDate() - daysAgo);
	d.setUTCHours(hour, minute, 0, 0);
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

// Records across 14 days (current + previous 7-day windows) so period
// trends have a baseline and the chart has varied bars.
const SAMPLE_RECORDS: HistoryRecord[] = [
	makeRecord(114, 0, 9, SAMPLE_TEXTS[1]!, 48),
	makeRecord(113, 0, 14, SAMPLE_TEXTS[0]!, 18),
	makeRecord(112, 0, 19, SAMPLE_TEXTS[2]!, 74),
	makeRecord(111, 1, 10, SAMPLE_TEXTS[4]!, 36),
	makeRecord(110, 1, 15, SAMPLE_TEXTS[3]!, 22),
	makeRecord(109, 2, 11, SAMPLE_TEXTS[5]!, 62, 1),
	makeRecord(108, 3, 9, SAMPLE_TEXTS[6]!, 15),
	makeRecord(107, 3, 16, SAMPLE_TEXTS[0]!, 20),
	makeRecord(106, 4, 13, SAMPLE_TEXTS[1]!, 44),
	makeRecord(105, 5, 10, SAMPLE_TEXTS[2]!, 80),
	makeRecord(104, 6, 14, SAMPLE_TEXTS[4]!, 31),
	makeRecord(103, 7, 9, SAMPLE_TEXTS[3]!, 19),
	makeRecord(102, 8, 15, SAMPLE_TEXTS[5]!, 58, 1),
	makeRecord(101, 10, 11, SAMPLE_TEXTS[6]!, 12),
	makeRecord(100, 12, 10, SAMPLE_TEXTS[1]!, 41),
	makeRecord(99, 13, 16, SAMPLE_TEXTS[0]!, 17),
];

const todayKey = dateKey(new Date().toISOString());
let todayCount = 0;
let todayChars = 0;
let todayWordCount = 0;
let todayDuration = 0;
let totalWords = 0;
let totalDuration = 0;
for (const r of SAMPLE_RECORDS) {
	totalWords += r.word_count;
	totalDuration += r.duration;
	if (dateKey(r.timestamp) === todayKey) {
		todayCount += 1;
		todayChars += r.char_count;
		todayWordCount += r.word_count;
		todayDuration += r.duration;
	}
}
const streaks = computeStreaks(SAMPLE_RECORDS);

// Correction usage covering the same 14 days. Keys are local day keys
// (the sheet `computeCorrectionStats` joins on).
const correctionsByDay: Record<string, number> = {};
const dictationsByDay: Record<string, number> = {};
for (let i = 0; i < 14; i++) {
	const d = new Date();
	d.setDate(d.getDate() - i);
	const key = localDateKey(d);
	dictationsByDay[key] = 1 + ((i * 7) % 3);
	correctionsByDay[key] = i % 3;
}
const sampleCorrectionUsage: CorrectionUsageSnapshot = {
	version: 1,
	corrections_by_day: correctionsByDay,
	dictations_by_day: dictationsByDay,
};

// Sample range is a preset so the chart renders its weekly bars.
const SAMPLE_RANGE: RangeId = "7d";

export const SAMPLE_DASHBOARD: DashboardBodyPayload = {
	data: {
		todayCount,
		todayChars,
		todayWordCount,
		todayDuration,
		totalCount: 42,
		totalWords,
		totalDuration,
		favoritesCount: SAMPLE_RECORDS.filter((r) => r.favorite > 0).length,
		model: "tiny",
		device: "cpu",
		language: "en",
		currentStreak: streaks.current,
		maxStreak: streaks.max,
		activeDays: streaks.activeDays,
		sampleSize: SAMPLE_RECORDS.length,
	},
	period: computePeriodStats(SAMPLE_RECORDS, SAMPLE_RANGE),
	activity: buildActivityBars(SAMPLE_RECORDS, SAMPLE_RANGE),
	heatmap: buildDictationHeatmap(SAMPLE_RECORDS),
	correctionStats: computeCorrectionStats(sampleCorrectionUsage, SAMPLE_RANGE),
	range: SAMPLE_RANGE,
	customCapped: false,
	customWindowLabel: undefined,
	configRaw: { ...SAMPLE_CONFIG },
};
