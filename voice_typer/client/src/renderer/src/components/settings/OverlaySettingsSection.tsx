// OverlaySettingsSection, the Overlay section of the Settings surface.
// General and Overlay cards on one page) so the Overlay domain gets its
// own focused section page (settingsOverlay). Renders one SettingsSection
// block: "Overlay" (Bubble Behavior, Bubble Position, Show on App Startup,
// Drag to Move, Bubble Mic Button). Behaviour is identical to the previous
// combined implementation, including the per-row search-filter visibility
// via the `isVisible` prop and the section-level "hide if no items match"
// check.

import { memo } from "react";
import { SettingsSection } from "@/components/common/SettingsSection";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup } from "@/components/ui/toggle-group";
import { useT } from "@/i18n/i18n";
import { BubblePreview } from "./BubblePreview";
import { SettingsSkeleton } from "./SettingsSkeleton";
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

	if (!config) return <SettingsSkeleton rows={3} />;

	//section-level visibility check for the Overlay section. The title
	// constant feeds BOTH the `<SettingsSection title>` prop AND the
	// `isVisible` third parameter, so search matches the heading the
	// user actually sees.
	const overlaySectionTitle = t("settings.overlay");
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
			label: t("settings.bubblePreview"),
			info: t("settings.bubblePreviewInfo"),
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

	// The preview gets its own card ("Bubble Preview") instead of
	// living as a last row inside the Overlay card: a mock pill in a
	// list of controls reads as one more control. It is gated by the
	// same search predicate (its own label, so a query that matches
	// one row hides the preview and vice versa) and by the bubble
	// actually being enabled.
	const previewSectionTitle = t("settings.bubblePreview");
	const previewVisible =
		config.bubble_behavior !== "hidden" &&
		isVisible(
			previewSectionTitle,
			t("settings.bubblePreviewInfo"),
			overlaySectionTitle,
		);

	if (!overlayVisible) return null;

	return (
		<>
			<SettingsSection
				title={overlaySectionTitle}
				description={t("settings.overlayDescription")}
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
						value={config.bubble_behavior ?? "show_on_record"}
						onChange={handleBubbleBehaviorChange}
						ariaLabel={t("settings.bubbleBehaviorLabel")}
					/>
				</GatedSettingRow>

				{/* Position, drag, timer, and preview are meaningless while
			    the bubble itself is hidden. */}
				{config.bubble_behavior !== "hidden" && (
					<GatedSettingRow
						isVisible={isVisible}
						sectionTitle={overlaySectionTitle}
						label={t("settings.bubblePositionLabel")}
						info={t("settings.bubblePositionInfo")}
					>
						<ToggleGroup
							options={[
								{ value: "top", label: t("settings.bubblePositionTop") },
								{ value: "bottom", label: t("settings.bubblePositionBottom") },
							]}
							value={config.bubble_position ?? "bottom"}
							onChange={handleBubblePositionChange}
							ariaLabel={t("settings.bubblePositionLabel")}
						/>
					</GatedSettingRow>
				)}

				{/* ── Switches ───────────────────────────────────────── */}
				{/* Show on app startup toggle, only visible when Always Visible is selected */}
				{config.bubble_behavior === "always_visible" && (
					<GatedSettingRow
						isVisible={isVisible}
						sectionTitle={overlaySectionTitle}
						label={t("settings.showOnAppStartup")}
						info={t("settings.showOnAppStartupInfo")}
					>
						<Switch
							checked={config.bubble_show_on_startup ?? true}
							onCheckedChange={handleBubbleStartupChange}
							aria-label={t("settings.showOnAppStartup")}
						/>
					</GatedSettingRow>
				)}

				{/*mic button toggle, shown for both visible behaviors. It
                	takes effect on the always-visible bubble (the only one
                	with an idle state to host it); the preview below shows
                	the difference live. */}
				{config.bubble_behavior !== "hidden" && (
					<GatedSettingRow
						isVisible={isVisible}
						sectionTitle={overlaySectionTitle}
						label={t("settings.bubbleMicButton")}
						info={t("settings.bubbleMicButtonDescription")}
					>
						<Switch
							checked={config.bubble_mic_button ?? true}
							onCheckedChange={handleBubbleMicButtonChange}
							aria-label={t("settings.bubbleMicButton")}
						/>
					</GatedSettingRow>
				)}

				{config.bubble_behavior !== "hidden" && (
					<GatedSettingRow
						isVisible={isVisible}
						sectionTitle={overlaySectionTitle}
						label={t("settings.dragToMove")}
						info={t("settings.dragToMoveInfo")}
					>
						<Switch
							checked={config.bubble_draggable ?? true}
							onCheckedChange={handleDragToMoveChange}
							aria-label={t("settings.dragToMove")}
						/>
					</GatedSettingRow>
				)}

				{/* Recording timer toggle, hidden only when the bubble itself
			    is hidden. Drives the live preview below instantly. */}
				{config.bubble_behavior !== "hidden" && (
					<GatedSettingRow
						isVisible={isVisible}
						sectionTitle={overlaySectionTitle}
						label={t("settings.bubbleShowRecordingTimer")}
						info={t("settings.bubbleShowRecordingTimerInfo")}
					>
						<Switch
							checked={config.bubble_show_recording_timer ?? false}
							onCheckedChange={handleRecordingTimerChange}
							aria-label={t("settings.bubbleShowRecordingTimer")}
						/>
					</GatedSettingRow>
				)}
			</SettingsSection>

			{/* Second card: the preview. Every bubble setting above is
		    mirrored into it, so toggling the mic button, the timer or
		    the behavior repaints it on the same commit. */}
			{previewVisible && (
				<SettingsSection
					title={previewSectionTitle}
					description={t("settings.bubblePreviewInfo")}
					descriptionMode="text"
				>
					<BubblePreview
						timerOn={config.bubble_show_recording_timer ?? false}
						micOn={
							config.bubble_behavior === "always_visible" &&
							config.bubble_mic_button !== false &&
							config.bubble_click_to_toggle !== false
						}
						dismissOn={config.bubble_behavior === "always_visible"}
						position={config.bubble_position ?? "bottom"}
					/>
				</SettingsSection>
			)}
		</>
	);
});
