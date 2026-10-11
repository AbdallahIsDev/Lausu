/**
 * ModelsTabSwitcher — Local / Cloud segmented control in the title bar.
 *
 * Same pattern as GlobalSearchBar: the control lives in the title-bar
 * middle strip while `currentPage === "models"` and unmounts elsewhere.
 * Tab selection is shared via `useFilterState("models", "activeTab")` so
 * the Models page and the title bar stay in sync (sessionStorage).
 *
 * Wears the DEFAULT (recessed-track) variant, the same one the sidebar's
 * CPU/GPU switch renders (2026-10-11, user decision). It used to be the
 * `tabs` variant — a transparent strip with 13px options — which meant
 * one component showed two different controls depending on where it was
 * mounted. Both instances now share one visual language: `rounded-lg`
 * recessed track with a `#000000`/10 hairline ring, `p-0.5`, and 11px
 * `tracking-wider` options on a raised `bg-surface` pill. Only the
 * labels differ.
 *
 * The page-side panels in `pages/Models.tsx` are therefore labelled
 * REGIONS, not `role="tabpanel"`: the default variant is a radiogroup
 * (the primitive's documented job — "one setting with mutually
 * exclusive values"), so there is no tablist for a tabpanel to belong
 * to and no `getTabId` / `getPanelId` ids to point `aria-labelledby`
 * at.
 */

import { memo } from "react";
import {
	ToggleGroup,
	type ToggleGroupOption,
} from "@/components/ui/toggle-group";
import { t } from "@/i18n/i18n";
import { type ModelsTab, useModelsTab } from "@/stores/useModelsTab";
import type { Page } from "@/types/ipc";

interface ModelsTabSwitcherProps {
	currentPage: Page;
}

export const ModelsTabSwitcher = memo(function ModelsTabSwitcher({
	currentPage,
}: ModelsTabSwitcherProps) {
	const activeTab = useModelsTab((s) => s.activeTab);
	const setActiveTab = useModelsTab((s) => s.setActiveTab);

	if (currentPage !== "models") return null;

	const tabOptions: ToggleGroupOption<string>[] = [
		{ value: "local", label: t("models.localModels") },
		{ value: "cloud", label: t("models.cloudModels") },
	];

	return (
		<ToggleGroup
			options={tabOptions}
			value={activeTab}
			onChange={(v) => setActiveTab(v as ModelsTab)}
			ariaLabel={t("models.title")}
			// `no-drag` only: the control keeps the primitive's own
			// auto width so it reads exactly like the sidebar instance.
			// The former `h-full` stretched the track to the title bar's
			// full inner height, which no other instance of this
			// component does.
			className="no-drag"
		/>
	);
});
