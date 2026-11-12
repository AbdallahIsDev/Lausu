// GeneralSettingsSection, the General section of the Settings surface.
// SettingsSection block: "General" (Launch at Login, Fast Startup,
// Offline Engine Pack, App Language, Notifications, Tray Click).
// component (OverlaySettingsSection.tsx) and its own section page
// (settingsOverlay). Behaviour is identical to the previous combined
// implementation, including the per-row search-filter visibility via the
// `isVisible` prop and the section-level "hide if no items match" check.

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
import { ToggleGroup } from "@/components/ui/toggle-group";
import {
	getLocale,
	getLocaleLabel,
	type Locale,
	pushLocaleToPythonBackend,
	SUPPORTED_LOCALES,
	setLocale,
	useT,
} from "@/i18n/i18n";
import {
	MODEL_IDLE_UNLOAD_OPTIONS,
	normalizeModelIdleUnloadMinutes,
} from "@/lib/utils/modelIdleUnload";

import type { SettingsSectionSharedProps } from "./types";

type GeneralSettingsSectionProps = SettingsSectionSharedProps;

const TRAY_CLICK_OPTIONS = [
	{ value: "toggle_dictation", labelKey: "settings.trayClickToggleDictation" },
	{ value: "open_app", labelKey: "settings.trayClickOpenApp" },
] as const;

// Locale selector options, derived from SUPPORTED_LOCALES so adding a
// new locale in i18n.ts automatically appears here. The labels are
// locale-name strings ("English", "العربية", …) which don't go through
// t(), they're the same in every UI language.
const LOCALE_OPTIONS = SUPPORTED_LOCALES.map((locale) => ({
	value: locale,
	label: getLocaleLabel(locale),
}));

// live at module scope. Because ``t()`` is a plain function that reads a
// module-level ``_currentLocale`` variable, evaluating them at import time
// FROZE the strings to whatever locale was active on first import.
// They are now computed INSIDE the component body, so each render
// re-resolves them against the CURRENT locale. The locale switcher no
// longer calls ``window.location.reload()``: ``setLocale`` (i18n.ts)
// notifies subscribers via ``subscribeLocale``, and ``useT()``
// (useSyncExternalStore) re-renders this section, and every other
// subscribed component, in place when the locale changes. The App root
// subscribes so the whole tree cascades a re-render; memoized sections
// (like this one) subscribe directly via ``useT()``. Covered by
// GeneralSettingsSection.test.tsx.

export const GeneralSettingsSection = memo(function GeneralSettingsSection({
	config,
	updateConfig,
	isVisible,
}: GeneralSettingsSectionProps) {
	// F-3: subscribe to locale changes so this section repaints in the
	// new language without a full page reload.
	const t = useT();
	return (
		<Skeleton
			data={config}
			sample={SAMPLE_CONFIG}
			id="settings-general"
			label={skeletonLoadingLabel()}
		>
			{(cfg) => {
				const LAUNCH_AT_LOGIN_LABEL = t("settings.launchAtLogin");
				const LAUNCH_AT_LOGIN_INFO = t("settings.launchAtLoginDescription");
				const NOTIFICATIONS_LABEL = t("settings.notifications");
				const NOTIFICATIONS_INFO = t("settings.notificationsDescription");
				const TRAY_CLICK_LABEL = t("settings.trayClick");
				const TRAY_CLICK_INFO = t("settings.trayClickDescription");
				const APP_LANGUAGE_LABEL = t("settings.appLanguage");
				const APP_LANGUAGE_INFO = t("settings.appLanguageDescription");
				const FAST_STARTUP_LABEL = t("settings.fastStartup");
				const FAST_STARTUP_INFO = t("settings.fastStartupDescription");
				const MODEL_IDLE_UNLOAD_LABEL = t("settings.modelIdleUnload");
				const MODEL_IDLE_UNLOAD_INFO = t("settings.modelIdleUnloadDescription");
				const STREAMING_TRANSCRIPTION_LABEL = t(
					"settings.streamingTranscription",
				);
				const STREAMING_TRANSCRIPTION_INFO = t(
					"settings.streamingTranscriptionDescription",
				);
				const generalSectionTitle = t("settings.general");
				const generalItems = [
					{ label: LAUNCH_AT_LOGIN_LABEL, info: LAUNCH_AT_LOGIN_INFO },
					{ label: APP_LANGUAGE_LABEL, info: APP_LANGUAGE_INFO },
					{ label: NOTIFICATIONS_LABEL, info: NOTIFICATIONS_INFO },
					{ label: TRAY_CLICK_LABEL, info: TRAY_CLICK_INFO },
					{ label: FAST_STARTUP_LABEL, info: FAST_STARTUP_INFO },
					{ label: MODEL_IDLE_UNLOAD_LABEL, info: MODEL_IDLE_UNLOAD_INFO },
					{
						label: STREAMING_TRANSCRIPTION_LABEL,
						info: STREAMING_TRANSCRIPTION_INFO,
					},
				];
				const generalVisible = generalItems.some((item) =>
					isVisible(item.label, item.info, generalSectionTitle),
				);
				const handleAutostartChange = (checked: boolean) =>
					updateConfig({ autostart: checked });
				const handleFastStartupChange = (checked: boolean) =>
					updateConfig({ fast_startup: checked });
				const handleNotificationsChange = (checked: boolean) =>
					updateConfig({ show_notifications: checked });
				const handleTrayClickChange = (v: string) =>
					updateConfig({
						tray_left_click_action: v as "open_app" | "toggle_dictation",
					});
				const handleModelIdleUnloadChange = (v: string) =>
					updateConfig({ model_idle_unload_minutes: Number(v) });
				const handleStreamingTranscriptionChange = (checked: boolean) =>
					updateConfig({ streaming_transcription: checked });
				if (!generalVisible) return null;
				return (
					<SettingsSection
						title={generalSectionTitle}
						description={t("settings.generalDescription")}
					>
						{isVisible(
							LAUNCH_AT_LOGIN_LABEL,
							LAUNCH_AT_LOGIN_INFO,
							generalSectionTitle,
						) && (
							<SettingRow
								label={LAUNCH_AT_LOGIN_LABEL}
								info={LAUNCH_AT_LOGIN_INFO}
							>
								<Switch
									checked={cfg.autostart}
									onCheckedChange={handleAutostartChange}
									aria-label={LAUNCH_AT_LOGIN_LABEL}
								/>
							</SettingRow>
						)}
						{isVisible(
							FAST_STARTUP_LABEL,
							FAST_STARTUP_INFO,
							generalSectionTitle,
						) && (
							<SettingRow label={FAST_STARTUP_LABEL} info={FAST_STARTUP_INFO}>
								<Switch
									checked={cfg.fast_startup ?? true}
									onCheckedChange={handleFastStartupChange}
									aria-label={FAST_STARTUP_LABEL}
								/>
							</SettingRow>
						)}
						{isVisible(
							STREAMING_TRANSCRIPTION_LABEL,
							STREAMING_TRANSCRIPTION_INFO,
							generalSectionTitle,
						) && (
							<SettingRow
								label={STREAMING_TRANSCRIPTION_LABEL}
								info={STREAMING_TRANSCRIPTION_INFO}
							>
								<Switch
									checked={cfg.streaming_transcription ?? true}
									onCheckedChange={handleStreamingTranscriptionChange}
									aria-label={STREAMING_TRANSCRIPTION_LABEL}
								/>
							</SettingRow>
						)}
						{isVisible(
							NOTIFICATIONS_LABEL,
							NOTIFICATIONS_INFO,
							generalSectionTitle,
						) && (
							<SettingRow label={NOTIFICATIONS_LABEL} info={NOTIFICATIONS_INFO}>
								<Switch
									checked={cfg.show_notifications}
									onCheckedChange={handleNotificationsChange}
									aria-label={NOTIFICATIONS_LABEL}
								/>
							</SettingRow>
						)}
						{isVisible(
							MODEL_IDLE_UNLOAD_LABEL,
							MODEL_IDLE_UNLOAD_INFO,
							generalSectionTitle,
						) && (
							<SettingRow
								label={MODEL_IDLE_UNLOAD_LABEL}
								info={MODEL_IDLE_UNLOAD_INFO}
							>
								<Select
									value={String(
										normalizeModelIdleUnloadMinutes(
											cfg.model_idle_unload_minutes,
										),
									)}
									onValueChange={handleModelIdleUnloadChange}
								>
									<SelectTrigger
										className="w-44"
										aria-label={MODEL_IDLE_UNLOAD_LABEL}
									>
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										{MODEL_IDLE_UNLOAD_OPTIONS.map((opt) => (
											<SelectItem key={opt.value} value={String(opt.value)}>
												<span>{t(opt.labelKey)}</span>
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</SettingRow>
						)}
						{isVisible(
							APP_LANGUAGE_LABEL,
							APP_LANGUAGE_INFO,
							generalSectionTitle,
						) && (
							<SettingRow label={APP_LANGUAGE_LABEL} info={APP_LANGUAGE_INFO}>
								<Select
									value={getLocale()}
									onValueChange={(v) => {
										setLocale(v as Locale);
										try {
											localStorage.setItem("lausu-ui-locale", v);
										} catch (e) {
											console.warn(
												"[renderer:GeneralSettingsSection] setItem locale failed:",
												e,
											);
										}
										try {
											pushLocaleToPythonBackend(v as Locale);
										} catch (e) {
											console.warn(
												"[renderer:GeneralSettingsSection] set_tray_locale IPC failed:",
												e,
											);
										}
									}}
								>
									<SelectTrigger
										className="w-44"
										aria-label={APP_LANGUAGE_LABEL}
									>
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										{LOCALE_OPTIONS.map((opt) => (
											<SelectItem key={opt.value} value={opt.value}>
												<span>{opt.label}</span>
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</SettingRow>
						)}
						{isVisible(
							TRAY_CLICK_LABEL,
							TRAY_CLICK_INFO,
							generalSectionTitle,
						) && (
							<SettingRow label={TRAY_CLICK_LABEL} info={TRAY_CLICK_INFO}>
								<ToggleGroup
									options={TRAY_CLICK_OPTIONS.map((opt) => ({
										value: opt.value,
										label: t(opt.labelKey),
									}))}
									value={cfg.tray_left_click_action ?? "open_app"}
									onChange={handleTrayClickChange}
									ariaLabel={TRAY_CLICK_LABEL}
								/>
							</SettingRow>
						)}
					</SettingsSection>
				);
			}}
		</Skeleton>
	);
});
