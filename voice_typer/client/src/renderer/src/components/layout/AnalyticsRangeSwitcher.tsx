/**
 * AnalyticsRangeSwitcher — the Analytics time range (Today / 7 Days /
 * 30 Days / All Time) in the title-bar middle strip.
 *
 * Same PLACEMENT pattern as ModelsTabSwitcher: the control lives in the
 * bar's middle strip while `currentPage === "analytics"` and unmounts
 * elsewhere, so the range is always reachable even once the page has
 * scrolled.
 *
 * Deliberately NOT `variant="tabs"` (which ModelsTabSwitcher uses): that
 * variant renders a WAI-ARIA tablist whose every tab must control a real
 * `role="tabpanel"`. The range picks a data window — there is no panel to
 * point at — so this keeps the radiogroup variant, the primitive's
 * documented job ("one setting with mutually exclusive values"). It
 * therefore wears the recessed-track look rather than the Models
 * switcher's transparent tab strip.
 *
 * State lives in `stores/useAnalyticsRange` (not component state) so the
 * title bar and the page, which are separate component trees, read the
 * same value.
 */

import { memo } from "react";
import {
	ToggleGroup,
	type ToggleGroupOption,
} from "@/components/ui/toggle-group";
import { t } from "@/i18n/i18n";
import type { RangeId } from "@/pages/dashboard/lib/streaks";
import {
	ANALYTICS_RANGES,
	useAnalyticsRange,
} from "@/stores/useAnalyticsRange";
import type { Page } from "@/types/ipc";

interface AnalyticsRangeSwitcherProps {
	currentPage: Page;
}

export const AnalyticsRangeSwitcher = memo(function AnalyticsRangeSwitcher({
	currentPage,
}: AnalyticsRangeSwitcherProps) {
	const range = useAnalyticsRange((s) => s.range);
	const setRange = useAnalyticsRange((s) => s.setRange);

	if (currentPage !== "analytics") return null;

	const options: ToggleGroupOption<RangeId>[] = ANALYTICS_RANGES.map((r) => ({
		value: r,
		label: t(`analytics.range.${r}`),
	}));

	return (
		<ToggleGroup
			options={options}
			value={range}
			onChange={setRange}
			ariaLabel={t("analytics.rangeAria")}
			// `no-drag`: the strip sits inside the title bar's drag region,
			// so without it a click would start a window move instead of
			// selecting a range. `h-full` fills the 36px bar the way the
			// Models switcher does.
			className="no-drag h-full"
		/>
	);
});
