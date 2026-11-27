// PostProcessingSettingsSection, the text enhancement controls on the
// Settings surface. Dictionary and snippet controls live on their own
// Settings section page.

import { memo } from "react";
import { Skeleton } from "skullet/react";
import { SettingRow } from "@/components/common/SettingRow";
import { SettingsSection } from "@/components/common/SettingsSection";
import { skeletonLoadingLabel } from "@/components/feedback/skeletons";
import { SAMPLE_CONFIG } from "@/components/skullet/sampleConfig";
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
import { TranslationModelDownloadRow } from "./TranslationModelDownloadRow";
import type { SettingsSectionSharedProps } from "./types";

// ADR-0021 scope lock: the translator only supports the 8 core locales.
// LANGUAGE_OPTIONS has 28 ASR codes; offering the extras here lets the UI
// choose a target the backend validator silently rejects.
const TRANSLATION_TARGET_CODES = new Set([
	"en",
	"zh",
	"hi",
	"es",
	"ar",
	"fr",
	"ru",
	"de",
]);

export const PostProcessingSettingsSection = memo(
	function PostProcessingSettingsSection({
		config,
		updateConfig,
		updateConfigDebounced,
		isVisible,
	}: SettingsSectionSharedProps) {
		const t = useT();

		// ── Inline handler extraction ─────────────────────────────────
		const handleLanguageChange = (v: string) =>
			updateConfig({ language: v === "auto" ? "" : v });
		const handleAutoPunctuationChange = (checked: boolean) =>
			updateConfig({ auto_punctuation: checked });
		const handleTextCleanupChange = (checked: boolean) =>
			updateConfig({ text_cleanup_enabled: checked });
		const handleTranslationChange = (checked: boolean) =>
			updateConfig({ translation_enabled: checked });
		const handleTranslationTargetChange = (v: string) =>
			updateConfig({ translation_target_language: v === "same" ? "" : v });
		const handleTranslationGpuChange = (checked: boolean) =>
			updateConfig({ translation_gpu_enabled: checked });

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
				info: t("settings.translationEnableInfo"),
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
							t("settings.translationEnableInfo"),
							postProcessingTitle,
						) && (
							<SettingRow
								label={t("settings.translationEnable")}
								info={t("settings.translationEnableInfo")}
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
										{LANGUAGE_OPTIONS.filter((lang) =>
											TRANSLATION_TARGET_CODES.has(lang.value),
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
								<TranslationModelDownloadRow
									config={cfg}
									downloadLabel={t("settings.translationDownload")}
									sizeLabel={t("settings.translationDownload")}
								/>
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
					</SettingsSection>
				)}
			</Skeleton>
		);
	},
);
