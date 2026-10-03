/**
 * ModelsTabSwitcher — Local / Cloud segmented control in the title bar.
 *
 * Same pattern as GlobalSearchBar: the control lives in the title-bar
 * middle strip while `currentPage === "models"` and unmounts elsewhere.
 * Tab selection is shared via `useFilterState("models", "activeTab")` so
 * the Models page and the title bar stay in sync (sessionStorage).
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
			variant="tabs"
			options={tabOptions}
			value={activeTab}
			onChange={(v) => setActiveTab(v as ModelsTab)}
			ariaLabel={t("models.title")}
			indicatorClassName="bg-surface border border-0 inset-0"
			labelClassName="flex-1 text-center"
			className="no-drag w-auto rounded-lg border border-border/8 bg-background p-0 h-full"
			getTabId={(v) => `models-tab-${v}`}
			getPanelId={(v) => `models-panel-${v}`}
		/>
	);
});
