// Measured-skeleton sample for a Media job row. While a row is in the
// "starting" phase (no progress data yet) the <Skeleton> measures this
// sample, so it carries the full running-row shape (layout only).
import type { MediaJobRow } from "../hooks/useMediaJobs";

export const SAMPLE_MEDIA_JOB: MediaJobRow = {
	clientId: "media-row-sample",
	jobId: "sample-job",
	source: "https://example.com/media/intro-video",
	phase: "transcribing",
	progress: 0.35,
	etaSeconds: 42,
	durationSeconds: 600,
	rowId: null,
	chars: null,
	partial: false,
	tier: "download",
	note: null,
	quality: null,
	title: null,
	thumbnailDataUrl: null,
};
