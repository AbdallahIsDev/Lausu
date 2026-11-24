// One collection page for corrections and reusable snippets. Both halves
// keep their existing hooks/components (and therefore their data and
// per-tab selection state); both configure the SAME shared
// CollectionToolbar / CollectionListHeader family, one table visible at
// a time. The header toggle chooses which configuration is shown, and the
// global search placeholder follows that tab's live count.

import { useEffect, useState } from "react";
import PageHeading from "@/components/common/PageHeading";
import { DictionaryAutomationSettings } from "@/components/settings/DictionaryAutomationSettings";
import { useSettingsConfig } from "@/components/settings/useSettingsConfig";
import { ToggleGroup } from "@/components/ui/toggle-group";
import { useNavigation } from "@/hooks/useNavigation";
import { useT } from "@/i18n/i18n";
import type { DictionaryTab } from "@/router/routes";
import TemplatesPage from "./Templates";
import VocabularyPage from "./Vocabulary";

export default function DictionarySnippetsPage() {
	const t = useT();
	const { consumeDictionaryTab } = useNavigation();
	const [tab, setTab] = useState<DictionaryTab>("dictionary");
	const { config, updateConfig, updateConfigDebounced, loadConfigOnMount } =
		useSettingsConfig();

	// Legacy `templates`/`vocabulary` deep links arrive as a one-shot tab
	// intent; consume it once so switching tabs later is never overridden.
	useEffect(() => {
		const pending = consumeDictionaryTab();
		if (pending) setTab(pending);
	}, [consumeDictionaryTab]);

	useEffect(() => {
		void loadConfigOnMount();
	}, [loadConfigOnMount]);

	return (
		<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-4 px-16 pt-20 pb-6">
			<div className="flex items-start justify-between gap-4">
				<PageHeading
					title={t("dictionarySnippets.title")}
					description={t("dictionarySnippets.description")}
				/>
				<div data-testid="dictionary-snippets-tab-toggle" className="shrink-0">
					<ToggleGroup<DictionaryTab>
						options={[
							{
								value: "dictionary",
								label: t("dictionarySnippets.dictionary"),
							},
							{
								value: "snippets",
								label: t("dictionarySnippets.snippets"),
							},
						]}
						value={tab}
						onChange={setTab}
						ariaLabel={t("dictionarySnippets.switcherAria")}
					/>
				</div>
			</div>
			{/* Both collections stay mounted so selection, inline forms
			    and dialogs survive a tab switch. `hidden` also removes the
			    inactive table from the accessibility tree and from
			    role-based queries. */}
			<div hidden={tab !== "dictionary"}>
				<VocabularyPage embedded active={tab === "dictionary"} />
			</div>
			<div hidden={tab !== "snippets"}>
				<TemplatesPage embedded active={tab === "snippets"} />
			</div>
			{config && (
				<DictionaryAutomationSettings
					config={config}
					updateConfig={updateConfig}
					updateConfigDebounced={updateConfigDebounced}
					isVisible={() => true}
				/>
			)}
		</div>
	);
}
