// Measured-skeleton sample for a Media job row. A job exists (and its source
// is known) from the moment it is enqueued, so the sample carries that job's
// OWN identity and only the not-yet-reported progress values are zeroed: the
// wrap reserves the running row's geometry without painting a source or a
// percentage the user never submitted (C-UI-15).
import type { MediaJobRow } from "../hooks/useMediaJobs";

export function mediaJobSample(job: MediaJobRow): MediaJobRow {
	return {
		...job,
		phase: "starting",
		progress: 0,
		etaSeconds: null,
		chars: null,
		partial: false,
		quality: null,
	};
}
