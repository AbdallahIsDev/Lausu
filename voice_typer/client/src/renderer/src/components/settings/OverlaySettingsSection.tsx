// The bubble card of the merged General & Overlay Settings page.
// One card for behavior, position, startup visibility, drag and related
// controls. The former Bubble Preview card (mock pills + state variants)
// is gone; controls and persistence are unchanged.

import { memo } from "react";
import { SettingsSection } from "@/components/common/SettingsSection";
import { MeasuredSkeleton } from "@/components/feedback/MeasuredSkeleton";
import { skeletonLoadingLabel } from "@/components/feedback/skeletons";
import { SAMPLE_CONFIG } from "@/components/skullet/sampleConfig";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup } from "@/components/ui/toggle-group";
import { useT } from "@/i18n/i18n";
import { anyRowVisible, GatedSettingRow } from "./settingsRowGating";

import type { SettingsSectionSharedProps } from "./types";

const BUBBLE_BEHAVIOR_OPTIONS = [
	{ value: "always_visible", labelKey: "settings.bubbleBehaviorAlwaysVisible" },
	{ value: "show_on_record", labelKey: "settings.bubbleBehaviorShowOnRecord" },
	{ value: "hidden", labelKey: "settings.bubbleBehaviorHidden" },
] as const;

export const OverlaySettingsSection = memo(function OverlaySettingsSection({
	config,
	updateConfig,
	isVisible,
}: SettingsSectionSharedProps) {
	// F-3: subscribe to locale changes so this section repaints in the
	// new language without a full page reload.
	const t = useT();

	//section-level visibility check for the Overlay section. The title
	// constant feeds BOTH the `<SettingsSection title>` prop AND the
	// `isVisible` third parameter, so search matches the heading the
	// user actually sees.
	const overlaySectionTitle = t("settings.bubbleSettings");
	const overlayItems = [
		{
			label: t("settings.bubbleBehaviorLabel"),
			info: t("settings.bubbleBehaviorInfo"),
		},
		{
			label: t("settings.bubblePositionLabel"),
			info: t("settings.bubblePositionInfo"),
		},
		{
			label: t("settings.showOnAppStartup"),
			info: t("settings.showOnAppStartupInfo"),
		},
		{
			label: t("settings.dragToMove"),
			info: t("settings.dragToMoveInfo"),
		},
		{
			label: t("settings.bubbleMicButton"),
			info: t("settings.bubbleMicButtonDescription"),
		},
		{
			label: t("settings.bubbleShowRecordingTimer"),
			info: t("settings.bubbleShowRecordingTimerInfo"),
		},
		{
			label: t("settings.screenshotBeta"),
			info: t("settings.screenshotBetaInfo"),
		},
	];
	const overlayVisible = anyRowVisible(
		isVisible,
		overlaySectionTitle,
		overlayItems,
	);

	// ── Inline handler extraction ─────────────────────────────────
	const handleBubbleBehaviorChange = (v: string) =>
		updateConfig({
			bubble_behavior: v as "show_on_record" | "always_visible" | "hidden",
		});
	const handleBubblePositionChange = (v: string) => {
		updateConfig({ bubble_position: v as "top" | "bottom" });
		window.bubble?.setPosition?.(v as "top" | "bottom");
	};
	const handleBubbleStartupChange = (checked: boolean) =>
		updateConfig({ bubble_show_on_startup: checked });
	const handleDragToMoveChange = (checked: boolean) => {
		updateConfig({ bubble_draggable: checked });
		window.bubble?.setDraggable?.(checked);
	};
	//mic button toggle, only meaningful in always_visible mode.
	const handleBubbleMicButtonChange = (checked: boolean) =>
		updateConfig({ bubble_mic_button: checked });
	const handleRecordingTimerChange = (checked: boolean) =>
		updateConfig({ bubble_show_recording_timer: checked });
	// One-shot screenshot beta, Windows-only, default OFF. While off
	// the bubble annotate button stays hidden and no screenshot IPC
	// fires, so the feature is a zero behavior change until enabled.
	const handleScreenshotBetaChange = (checked: boolean) =>
		updateConfig({ screenshot_beta_enabled: checked });

	if (!overlayVisible) return null;

	return (
		<MeasuredSkeleton
			stackClassName="gap-12"
			data={config}
			sample={SAMPLE_CONFIG}
			id="settings-overlay"
			label={skeletonLoadingLabel()}
		>
			{(cfg) => (
				<>
					<SettingsSection
						title={overlaySectionTitle}
						description={t("settings.bubbleSettingsDescription")}
					>
						{/* ── Dropdowns ──────────────────────────────────────── */}
						<GatedSettingRow
							isVisible={isVisible}
							sectionTitle={overlaySectionTitle}
							label={t("settings.bubbleBehaviorLabel")}
							info={t("settings.bubbleBehaviorInfo")}
						>
							<ToggleGroup
								options={BUBBLE_BEHAVIOR_OPTIONS.map((opt) => ({
									value: opt.value,
									label: t(opt.labelKey),
								}))}
								value={cfg.bubble_behavior ?? "show_on_record"}
								onChange={handleBubbleBehaviorChange}
								ariaLabel={t("settings.bubbleBehaviorLabel")}
							/>
						</GatedSettingRow>{" "}
						{/* Position, drag and timer are meaningless while
				    the bubble itself is hidden, so the rows stay visible but
				    locked instead of disappearing. */}
						<GatedSettingRow
							isVisible={isVisible}
							sectionTitle={overlaySectionTitle}
							label={t("settings.bubblePositionLabel")}
							info={t("settings.bubblePositionInfo")}
						>
							<ToggleGroup
								options={[
									{ value: "top", label: t("settings.bubblePositionTop") },
									{
										value: "bottom",
										label: t("settings.bubblePositionBottom"),
									},
								]}
								value={cfg.bubble_position ?? "bottom"}
								onChange={handleBubblePositionChange}
								ariaLabel={t("settings.bubblePositionLabel")}
								disabled={cfg.bubble_behavior === "hidden"}
							/>
						</GatedSettingRow>
						{/* ── Switches ───────────────────────────────────────── */}
						{/* Show on app startup toggle, only unlockable when Always Visible is selected */}
						<GatedSettingRow
							isVisible={isVisible}
							sectionTitle={overlaySectionTitle}
							label={t("settings.showOnAppStartup")}
							info={t("settings.showOnAppStartupInfo")}
						>
							<Switch
								checked={cfg.bubble_show_on_startup ?? true}
								onCheckedChange={handleBubbleStartupChange}
								aria-label={t("settings.showOnAppStartup")}
								disabled={cfg.bubble_behavior !== "always_visible"}
							/>
						</GatedSettingRow>
						{/*mic button toggle, available for both visible behaviors. It
                	takes effect on the always-visible bubble (the only one
                	with an idle state to host it). */}
						<GatedSettingRow
							isVisible={isVisible}
							sectionTitle={overlaySectionTitle}
							label={t("settings.bubbleMicButton")}
							info={t("settings.bubbleMicButtonDescription")}
						>
							<Switch
								checked={cfg.bubble_mic_button ?? true}
								onCheckedChange={handleBubbleMicButtonChange}
								aria-label={t("settings.bubbleMicButton")}
								disabled={cfg.bubble_behavior === "hidden"}
							/>
						</GatedSettingRow>
						<GatedSettingRow
							isVisible={isVisible}
							sectionTitle={overlaySectionTitle}
							label={t("settings.dragToMove")}
							info={t("settings.dragToMoveInfo")}
						>
							<Switch
								checked={cfg.bubble_draggable ?? true}
								onCheckedChange={handleDragToMoveChange}
								aria-label={t("settings.dragToMove")}
								disabled={cfg.bubble_behavior === "hidden"}
							/>
						</GatedSettingRow>{" "}
						{/* Recording timer toggle, locked only while the bubble itself
			    is hidden. Applied to the live bubble on the next state change. */}
						<GatedSettingRow
							isVisible={isVisible}
							sectionTitle={overlaySectionTitle}
							label={t("settings.bubbleShowRecordingTimer")}
							info={t("settings.bubbleShowRecordingTimerInfo")}
						>
							<Switch
								checked={cfg.bubble_show_recording_timer ?? false}
								onCheckedChange={handleRecordingTimerChange}
								aria-label={t("settings.bubbleShowRecordingTimer")}
								disabled={cfg.bubble_behavior === "hidden"}
							/>
						</GatedSettingRow>
						{/* Screenshot beta toggle, locked while the bubble itself
				    is hidden (the annotate button lives on the bubble). */}
						<GatedSettingRow
							isVisible={isVisible}
							sectionTitle={overlaySectionTitle}
							label={t("settings.screenshotBeta")}
							info={t("settings.screenshotBetaInfo")}
						>
							<Switch
								checked={cfg.screenshot_beta_enabled ?? false}
								onCheckedChange={handleScreenshotBetaChange}
								aria-label={t("settings.screenshotBeta")}
								disabled={cfg.bubble_behavior === "hidden"}
							/>
						</GatedSettingRow>
					</SettingsSection>
				</>
			)}
		</MeasuredSkeleton>
	);
});
