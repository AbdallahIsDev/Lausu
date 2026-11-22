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
import { Skeleton } from "skullet/react";
import { SettingRow } from "@/components/common/SettingRow";
import { SettingsSection } from "@/components/common/SettingsSection";
import { skeletonLoadingLabel } from "@/components/feedback/skeletons";
import { SAMPLE_CONFIG } from "@/components/skullet/sampleConfig";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { usePython } from "@/hooks/usePython";
import { useT } from "@/i18n/i18n";
import { LANGUAGE_OPTIONS } from "@/lib/utils/languages";
import type { Page } from "@/types/ipc";
import type { SettingsSectionSharedProps } from "./types";

export const PostProcessingSettingsSection = memo(
	function PostProcessingSettingsSection({
		config,
		updateConfig,
		updateConfigDebounced,
		isVisible,
		onNavigate,
	}: SettingsSectionSharedProps & {
		/** Routes to the Text Snippets page (the "Open Text Snippets" button). */
		onNavigate?: (page: Page) => void;
	}) {
		const t = useT();
		const { call } = usePython();

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
		const handleTranslationChange = (checked: boolean) =>
			updateConfig({ translation_enabled: checked });
		const handleTranslationTargetChange = (v: string) =>
			updateConfig({ translation_target_language: v === "same" ? "" : v });
		const handleTranslationGpuChange = (checked: boolean) =>
			updateConfig({ translation_gpu_enabled: checked });
		const handleTranslationDownload = () =>
			void call("download_model", { model: "index-translate-2b-q4-k-m" });

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
				label: t("settings.translationEnable"),
				info: t("settings.translationTargetInfo"),
			},
			{
				label: t("settings.translationTarget"),
				info: t("settings.translationTargetInfo"),
			},
			{
				label: t("settings.translationGpu"),
				info: t("settings.translationGpuInfo"),
			},
			{
				label: t("settings.translationGlossary"),
				info: t("settings.translationGlossaryInfo"),
			},
			{
				label: t("settings.translationDownload"),
				info: t("settings.translationTargetInfo"),
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
			<Skeleton
				data={config}
				sample={SAMPLE_CONFIG}
				id="settings-post-processing"
				label={skeletonLoadingLabel()}
			>
				{(cfg) => (
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
									value={cfg.language || "auto"}
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
							t("settings.translationEnable"),
							t("settings.translationTargetInfo"),
							postProcessingTitle,
						) && (
							<SettingRow
								label={t("settings.translationEnable")}
								info={t("settings.translationTargetInfo")}
							>
								<Switch
									checked={cfg.translation_enabled ?? false}
									onCheckedChange={handleTranslationChange}
									aria-label={t("settings.translationEnable")}
								/>
							</SettingRow>
						)}

						{isVisible(
							t("settings.translationTarget"),
							t("settings.translationTargetInfo"),
							postProcessingTitle,
						) && (
							<SettingRow
								label={t("settings.translationTarget")}
								info={t("settings.translationTargetInfo")}
							>
								<Select
									value={cfg.translation_target_language || "same"}
									onValueChange={handleTranslationTargetChange}
								>
									<SelectTrigger
										className="w-44"
										aria-label={t("settings.translationTarget")}
									>
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="same">
											<span>{t("settings.translationSameAsSpoken")}</span>
										</SelectItem>
										{LANGUAGE_OPTIONS.filter(
											(lang) => lang.value !== "auto",
										).map((lang) => (
											<SelectItem key={lang.value} value={lang.value}>
												<span>{t(lang.labelKey)}</span>
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</SettingRow>
						)}

						{isVisible(
							t("settings.translationGpu"),
							t("settings.translationGpuInfo"),
							postProcessingTitle,
						) && (
							<SettingRow
								label={t("settings.translationGpu")}
								info={t("settings.translationGpuInfo")}
							>
								<Switch
									checked={cfg.translation_gpu_enabled ?? true}
									onCheckedChange={handleTranslationGpuChange}
									aria-label={t("settings.translationGpu")}
								/>
							</SettingRow>
						)}

						{isVisible(
							t("settings.translationGlossary"),
							t("settings.translationGlossaryInfo"),
							postProcessingTitle,
						) && (
							<SettingRow
								label={t("settings.translationGlossary")}
								info={t("settings.translationGlossaryInfo")}
							>
								<textarea
									className="min-h-20 w-72 rounded-md border border-border bg-background px-3 py-2 text-sm"
									value={cfg.translation_glossary ?? ""}
									onChange={(event) =>
										updateConfigDebounced(
											"translation_glossary",
											event.target.value,
										)
									}
									aria-label={t("settings.translationGlossary")}
									placeholder="hero section => الهيرو سكشن"
								/>
							</SettingRow>
						)}

						{isVisible(
							t("settings.translationDownload"),
							t("settings.translationTargetInfo"),
							postProcessingTitle,
						) && (
							<SettingRow
								label={t("settings.translationDownload")}
								info={t("settings.translationTargetInfo")}
							>
								<Button
									variant="outline"
									size="sm"
									onClick={handleTranslationDownload}
									aria-label={t("settings.translationDownload")}
								>
									{t("settings.translationDownload")}
								</Button>
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
									checked={cfg.auto_punctuation ?? false}
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
									checked={cfg.text_cleanup_enabled}
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
										checked={cfg.templates_enabled ?? true}
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
									checked={cfg.vocabulary_automation_enabled ?? false}
									onCheckedChange={handleVocabAutomationChange}
									aria-label={t("settings.vocabAutomation.title")}
								/>
							</SettingRow>
						)}
					</SettingsSection>
				)}
			</Skeleton>
		);
	},
);
