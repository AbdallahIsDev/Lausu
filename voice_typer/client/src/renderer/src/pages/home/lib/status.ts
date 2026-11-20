// `statusLabelFor` resolves at render time so the pill honours the
// current locale on every render (not just at module-import time). The
// `RecordingState` union from `@/types/ipc` is the source of truth for
// the input string, the helpers gracefully fall back to the "ready"
// label for any unrecognised state (defensive against future backend
// additions).

import { t } from "@/i18n/i18n";

// The state→key rule moved to the shared status module when the sidebar
// caption started rendering the same dot; re-exported so this module stays
// the Home page's single status entry point.
export { statusKeyFor } from "@/lib/dictationStatus";

export function statusLabelFor(key: string): string {
	switch (key) {
		case "recording":
			return t("home.recording");
		case "transcribing":
			return t("home.transcribing");
		case "loading":
			return t("home.loading");
		case "cancelling":
			return t("home.cancelling");
		case "error":
			return t("home.error");
		default:
			return t("home.ready");
	}
}
