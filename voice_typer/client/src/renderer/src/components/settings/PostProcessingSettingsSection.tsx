// PostProcessingSettingsSection, the Post-Processing section of the
// Settings surface.
// Post-Processing and LLM Polishing cards on one page) so each domain
// gets its own focused section page (settingsTranscription for this
// card). Renders one SettingsSection block: "Post-Processing"
// (Transcription Language, Auto Punctuation, Text Cleanup, Text
// Snippets, Vocabulary). Behaviour is identical to the previous combined
// implementation, including the per-row search-filter visibility via the
// `isVisible` prop and the section-level "hide if no items match" check.

import { ArrowRight01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { memo } from "react";
import { SettingRow } from "@/components/common/SettingRow";
import { SettingsSection } from "@/components/common/SettingsSection";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useT } from "@/i18n/i18n";
import { LANGUAGE_OPTIONS } from "@/lib/utils/languages";
import type { Page } from "@/types/ipc";
import { SettingsSkeleton } from "./SettingsSkeleton";
import type { SettingsSectionSharedProps } from "./types";

export const PostProcessingSettingsSection = memo(
	function PostProcessingSettingsSection({
		config,
		updateConfig,
		isVisible,
		onNavigate,
	}: SettingsSectionSharedProps & {
		/** Routes to the Templates page (the "Open Templates" button). */
		onNavigate?: (page: Page) => void;
	}) {
		const t = useT();

		if (!config) return <SettingsSkeleton rows={3} />;

		// ── Inline handler extraction ─────────────────────────────────
		const handleLanguageChange = (v: string) =>
			updateConfig({ language: v === "auto" ? "" : v });
		const handleAutoPunctuationChange = (checked: boolean) =>
			updateConfig({ auto_punctuation: checked });
		const handleTextCleanupChange = (checked: boolean) =>
			updateConfig({ text_cleanup_enabled: checked });
		const handleTextSnippetsChange = (checked: boolean) =>
			updateConfig({ templates_enabled: checked });
		const handleVocabAutomationChange = (checked: boolean) =>
			updateConfig({ vocabulary_automation_enabled: checked });

		//section-level visibility check for the Post-Processing section.
		// The title constant feeds BOTH the `<SettingsSection title>` prop
		// AND the `isVisible` third parameter, so search matches the
		// heading the user actually sees.
		const postProcessingTitle = t("settings.postProcessing");
		const postProcessingItems = [
			{
				label: t("settings.transcriptionLanguage"),
				info: t("settings.transcriptionLanguageDescription"),
			},
			{
				label: t("settings.autoPunctuation"),
				info: t("settings.autoPunctuationInfo"),
			},
			{
				label: t("settings.textCleanupLabel"),
				info: t("settings.textCleanupInfo"),
			},
			{
				label: t("settings.textSnippets"),
				info: t("settings.textSnippetsInfo"),
			},
			{
				label: t("settings.vocabAutomation.title"),
				info: t("settings.vocabAutomation.enableInfo"),
			},
			{
				label: t("settings.openTemplates"),
				info: t("settings.textSnippetsInfo"),
			},
		];
		const postProcessingVisible = postProcessingItems.some((item) =>
			isVisible(item.label, item.info, postProcessingTitle),
		);

		if (!postProcessingVisible) return null;

		return (
			<SettingsSection
				title={postProcessingTitle}
				description={t("settings.postProcessingDescription")}
			>
				{isVisible(
					t("settings.transcriptionLanguage"),
					t("settings.transcriptionLanguageDescription"),
					postProcessingTitle,
				) && (
					<SettingRow
						label={t("settings.transcriptionLanguage")}
						info={t("settings.transcriptionLanguageDescription")}
					>
						<Select
							value={config.language || "auto"}
							onValueChange={handleLanguageChange}
						>
							<SelectTrigger
								className="w-44"
								aria-label={t("settings.transcriptionLanguage")}
							>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{LANGUAGE_OPTIONS.map((lang) => (
									<SelectItem key={lang.value} value={lang.value}>
										<span>{t(lang.labelKey)}</span>
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</SettingRow>
				)}

				{isVisible(
					t("settings.autoPunctuation"),
					t("settings.autoPunctuationInfo"),
					postProcessingTitle,
				) && (
					<SettingRow
						label={t("settings.autoPunctuation")}
						info={t("settings.autoPunctuationInfo")}
					>
						<Switch
							checked={config.auto_punctuation ?? false}
							onCheckedChange={handleAutoPunctuationChange}
							aria-label={t("settings.autoPunctuation")}
						/>
					</SettingRow>
				)}

				{isVisible(
					t("settings.textCleanupLabel"),
					t("settings.textCleanupInfo"),
					postProcessingTitle,
				) && (
					<SettingRow
						label={t("settings.textCleanupLabel")}
						info={t("settings.textCleanupInfo")}
					>
						<Switch
							checked={config.text_cleanup_enabled}
							onCheckedChange={handleTextCleanupChange}
							aria-label={t("settings.textCleanupLabel")}
						/>
					</SettingRow>
				)}

				{isVisible(
					t("settings.textSnippets"),
					t("settings.textSnippetsInfo"),
					postProcessingTitle,
				) && (
					<SettingRow
						label={t("settings.textSnippets")}
						info={t("settings.textSnippetsInfo")}
					>
						<div className="flex items-center gap-2">
							<Button
								variant="outline"
								size="sm"
								className="gap-1.5"
								onClick={() => onNavigate?.("templates")}
								aria-label={t("settings.openTemplates")}
								title={t("settings.textSnippetsInfo")}
								data-testid="open-templates-button"
							>
								<HugeiconsIcon
									icon={ArrowRight01Icon}
									strokeWidth={2}
									className="size-4"
									aria-hidden="true"
								/>
								{t("settings.openTemplates")}
							</Button>
							<Switch
								checked={config.templates_enabled ?? true}
								onCheckedChange={handleTextSnippetsChange}
								aria-label={t("settings.textSnippets")}
							/>
						</div>
					</SettingRow>
				)}

				{isVisible(
					t("settings.vocabAutomation.title"),
					t("settings.vocabAutomation.enableInfo"),
					postProcessingTitle,
				) && (
					<SettingRow
						label={t("settings.vocabAutomation.title")}
						info={t("settings.vocabAutomation.enableInfo")}
					>
						<Switch
							checked={config.vocabulary_automation_enabled ?? false}
							onCheckedChange={handleVocabAutomationChange}
							aria-label={t("settings.vocabAutomation.title")}
						/>
					</SettingRow>
				)}
			</SettingsSection>
		);
	},
);
