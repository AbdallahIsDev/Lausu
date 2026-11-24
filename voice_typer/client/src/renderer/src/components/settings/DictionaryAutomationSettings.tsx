// The two persisted toggles that used to live in a Settings section:
// their data model and write path are unchanged, they now sit with the
// collections they govern on the merged Dictionary & Snippets page.

import { memo } from "react";
import { SettingsSection } from "@/components/common/SettingsSection";
import { Switch } from "@/components/ui/switch";
import { useT } from "@/i18n/i18n";
import { GatedSettingRow } from "./settingsRowGating";
import type { SettingsSectionSharedProps } from "./types";

export const DictionaryAutomationSettings = memo(
	function DictionaryAutomationSettings({
		config,
		updateConfig,
		isVisible,
	}: SettingsSectionSharedProps) {
		const t = useT();
		const sectionTitle = t("settings.vocabAutomation.title");
		const snippetLabel = t("settings.textSnippets");
		const vocabularyLabel = t("settings.vocabAutomation.title");

		return (
			<SettingsSection title={sectionTitle}>
				<GatedSettingRow
					isVisible={isVisible}
					sectionTitle={sectionTitle}
					label={snippetLabel}
					info={t("settings.textSnippetsInfo")}
				>
					<Switch
						checked={config?.templates_enabled ?? true}
						onCheckedChange={(checked) =>
							updateConfig({ templates_enabled: checked })
						}
						aria-label={snippetLabel}
						data-testid="text-snippets-enabled"
					/>
				</GatedSettingRow>
				<GatedSettingRow
					isVisible={isVisible}
					sectionTitle={sectionTitle}
					label={vocabularyLabel}
					info={t("settings.vocabAutomation.enableInfo")}
				>
					<Switch
						checked={config?.vocabulary_automation_enabled ?? false}
						onCheckedChange={(checked) =>
							updateConfig({
								vocabulary_automation_enabled: checked,
							})
						}
						aria-label={vocabularyLabel}
						data-testid="vocabulary-automation-enabled"
					/>
				</GatedSettingRow>
			</SettingsSection>
		);
	},
);
