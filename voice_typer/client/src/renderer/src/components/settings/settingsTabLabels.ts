// settingsTabLabels, the source of truth for "which labels appear on
// which Settings section page?" Used by the search auto-switch (so the
// user's query navigates to the section page whose labels best match)
// and by the hub's query filter (so hub rows hide unless their section
// matches), label-based, not hint-based.
// Hints (settings.searchHints.*) remain in i18n for completeness
// (translated into zh/de/fr/hi/ru) but are NOT used by the
// auto-switch logic; labels are sufficient because every section title
// and row label is already translated and reflects the user's locale.

import { t } from "@/i18n/i18n";
import type { SettingsSectionPage } from "./settingsSections";

export function getSectionLabels(): Record<SettingsSectionPage, string[]> {
	return {
		settingsGeneral: [
			t("settings.general"),
			t("settings.launchAtLogin"),
			t("settings.fastStartup"),
			t("settings.streamingTranscription"),
			t("settings.appLanguage"),
			t("settings.notifications"),
			t("settings.trayClick"),
		],
		settingsOverlay: [
			t("settings.overlay"),
			t("settings.bubbleBehaviorLabel"),
			t("settings.bubblePositionLabel"),
			t("settings.showOnAppStartup"),
			t("settings.dragToMove"),
			t("settings.bubbleMicButton"),
		],
		settingsHotkeys: [
			t("settings.hotkeySection.recordingTitle"),
			t("settings.hotkeySection.dictationKey"),
			t("settings.hotkeySection.repasteKey"),
			t("settings.hotkeySection.recordingMode"),
			t("settings.hotkeySection.stopOnSilence"),
			t("settings.hotkeySection.escToCancel"),
			t("settings.hotkeySection.autoPaste"),
			t("settings.hotkeySection.soundFeedback"),
			t("settings.hotkeySection.soundVolume"),
			t("settings.hotkeySection.testStartSound"),
			t("settings.hotkeySection.testStopSound"),
			t("settings.hotkeySection.unsafePaste"),
			t("settings.hotkeySection.warnElevatedPaste"),
			t("settings.hotkeySection.warnPasswordPaste"),
			t("settings.hotkeySection.silenceWarning"),
			t("settings.hotkeySection.maxRecordingTime"),
		],
		settingsTranscription: [
			t("settings.postProcessing"),
			t("settings.transcriptionLanguage"),
			t("settings.autoPunctuation"),
			t("settings.textCleanupLabel"),
			t("settings.textSnippets"),
			t("settings.openTemplates"),
			t("settings.vocabAutomation.title"),
			t("settings.vocabAutomation.enable"),
		],
		settingsAudio: [
			t("settings.audioEnhancement.title"),
			t("settings.audioEnhancement.volumeBackend"),
			t("settings.audioEnhancement.autoDuckVolume"),
			t("settings.audioEnhancement.duckLevel"),
			t("settings.audioEnhancement.microphoneQuality"),
			t("settings.audioEnhancement.hallucinationFilter"),
			t("settings.audioEnhancement.highPassFilter"),
			t("settings.audioEnhancement.noiseSuppression"),
			t("settings.audioEnhancement.noiseGate"),
			t("settings.audioEnhancement.equalizer"),
			t("settings.audioEnhancement.compressor"),
			t("settings.audioEnhancement.limiter"),
			t("settings.audioEnhancement.notchFilter"),
		],
		settingsAppearance: [
			t("settings.appearance.title"),
			t("settings.appearance.colorScheme"),
			t("settings.appearance.themePreset"),
			t("settings.appearance.customTheme"),
			t("settings.appearance.textSize"),
		],
		settingsPrivacy: [
			t("settings.privacy.privacyTitle"),
			t("settings.privacy.audioRecoveryTitle"),
			t("settings.privacy.crashRecovery"),
			t("settings.privacy.huggingFaceDownloadsLabel"),
			t("settings.privacy.logTranscriptionsLabel"),
			t("settings.privacy.clipboardSaveRestoreLabel"),
			t("settings.privacy.voiceBiometricLabel"),
			t("settings.privacy.openaiCloudAsrLabel"),
			t("settings.privacy.groqCloudAsrLabel"),
			t("settings.privacy.deepgramCloudAsrLabel"),
			t("settings.privacy.llmTextPolishingLabel"),
			t("settings.privacy.exportAllDataLabel"),
		],
		settingsAdvanced: [
			t("settings.hub.advancedTitle"),
			t("settings.llmPolishing"),
			t("settings.llmPolish"),
			t("settings.enable"),
			t("settings.apiKey"),
			t("settings.apiUrl"),
			t("settings.model"),
			t("settings.preset"),
			t("settings.troubleshooting.title"),
			t("settings.troubleshooting.diagnostics"),
			t("settings.troubleshooting.reportBug"),
			// The setup wizard is a dev-only affordance; listing its label
			// in production would route a search to a page with no match.
			...(import.meta.env.DEV
				? [t("settings.troubleshooting.reRunWizard")]
				: []),
			t("settings.troubleshooting.resetAccessibility"),
			t("settings.troubleshooting.resetLinux"),
			t("about.cacheTitle"),
			t("about.updatesTitle"),
		],
	};
}
