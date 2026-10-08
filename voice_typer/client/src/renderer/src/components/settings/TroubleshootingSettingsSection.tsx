// Settings → Advanced tab: the Troubleshooting section.
//
// Owns the support actions that must stay in-app: the keyboard-shortcut
// reference, the bug-report composer, and the platform-specific stale
// permission resets. Anything that would hand the user off to a browser
// (help pages, issue trackers, changelogs) lives behind an in-app modal
// instead, so the product reads as a shipped application rather than a
// repository front-end.

import {
	ArrowTurnBackwardIcon,
	Bug02Icon,
	KeyboardIcon,
	ShieldBanIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { memo, useEffect, useState } from "react";
import { SettingsSection } from "@/components/common/SettingsSection";
import { Button } from "@/components/ui/button";
import { useLatestRef } from "@/hooks/useLatestRef";
import { usePython } from "@/hooks/usePython";
import { useSnackbar } from "@/hooks/useSnackbar";
import { t } from "@/i18n/i18n";
import type { LausuConfig } from "@/types/config";
import type { Page } from "@/types/ipc";
import { anyRowVisible } from "./settingsRowGating";
import type { IsVisibleFn } from "./types";

interface TroubleshootingSettingsSectionProps {
	/** Search-filter predicate, same shape as the page-level helper. */
	isVisible: IsVisibleFn;
	/** Used by the "Re-run setup wizard" button to flip
	 *  `onboarding_completed` to false before navigating. */
	updateConfig: (updates: Partial<LausuConfig>) => void;
	/** Routes the user to the Onboarding wizard (re-run setup). */
	onNavigate?: (page: Page) => void;
	/** Opens the parent-owned HelpOverlay (keyboard-shortcut +
	 *  punctuation-cheat-sheet reference). The overlay instance itself
	 *  lives in Settings.tsx, the section only requests it. */
	onOpenHelp: () => void;
	/** Opens the parent-owned bug-report composer. The modal instance
	 *  lives in Settings.tsx so it survives this section unmounting. */
	onOpenBugReport: () => void;
}

export const TroubleshootingSettingsSection = memo(
	function TroubleshootingSettingsSection({
		isVisible,
		updateConfig,
		onNavigate,
		onOpenHelp,
		onOpenBugReport,
	}: TroubleshootingSettingsSectionProps) {
		const { call } = usePython();
		const { showSnack } = useSnackbar();

		// Ref mirror of `call` so the mount probe effect depends only on
		// `isMac`. Test mocks may return a fresh `call` per render, an
		// effect dep on it would re-fire the probe (check_accessibility →
		// setStaleResetCommand → re-render → new call → loop). Same
		// pattern as useVocabulary.ts.
		const callRef = useLatestRef(call);

		// Resolve translated strings once per render so the search-visible
		// predicate and the rendered labels share the same values.
		const title = t("settings.troubleshooting.title");
		const description = t("settings.troubleshooting.description");
		const reportBugLabel = t("settings.troubleshooting.reportBug");
		const reRunWizardLabel = t("settings.troubleshooting.reRunWizard");
		// Keyboard Shortcuts button, opens the shared HelpOverlay
		// existing `help.title` key ("Keyboard Shortcuts").
		const keyboardShortcutsLabel = t("help.title");
		const resetAccessibilityLabel = t(
			"settings.troubleshooting.resetAccessibility",
		);
		const resetLinuxLabel = t("settings.troubleshooting.resetLinux");

		// macOS-only: the stale-TCC-entry reset (``tccutil reset
		// Accessibility <bundle-id>``) is meaningless on Windows / Linux.
		// Linux-only: the stale-polkit-authorization reset is meaningless
		// elsewhere. Same UA probe as KeyboardPermissionBanner.
		const ua =
			typeof navigator === "undefined" ? "" : navigator.userAgent.toLowerCase();
		const isMac = ua.includes("mac");
		const isLinux = ua.includes("linux");

		// The setup wizard is a developer affordance: it exists so the
		// first-run flow can be replayed while developing. Shipping it
		// invites users to re-run onboarding and lose their configuration.
		const isDev = import.meta.env.DEV;

		// Finding #919 part b: on a CONFIRMED stale Accessibility grant
		// (``AXIsProcessTrusted()`` returned False) the backend echoes
		// command still being decommissioned on an older backend) must
		// silently mean "no suggestion".
		const [staleResetCommand, setStaleResetCommand] = useState<string | null>(
			null,
		);
		useEffect(() => {
			if (!isMac) return;
			let cancelled = false;
			(async () => {
				try {
					const result = (await callRef.current("check_accessibility")) as {
						suggest_reset?: boolean;
						reset_command?: string;
					};
					if (
						!cancelled &&
						result?.suggest_reset === true &&
						typeof result.reset_command === "string"
					) {
						setStaleResetCommand(result.reset_command);
					}
				} catch (err) {
					console.warn(
						"[renderer:TroubleshootingSettingsSection] check_accessibility probe failed (non-fatal):",
						err,
					);
				}
			})();
			return () => {
				cancelled = true;
			};
		}, [isMac, callRef]);

		// title OR at least one button label matches the active search query.
		const sectionVisible =
			isVisible(title, description, title) ||
			anyRowVisible(isVisible, title, [
				{ label: keyboardShortcutsLabel },
				{ label: reportBugLabel },
				...(isDev ? [{ label: reRunWizardLabel }] : []),
				...(isMac ? [{ label: resetAccessibilityLabel }] : []),
				...(isLinux ? [{ label: resetLinuxLabel }] : []),
			]);

		if (!sectionVisible) return null;

		// Re-run the onboarding wizard: synchronously flip
		// user land on the wizard page) then navigate. The toast confirms
		//
		//also call the `onboarding_reset` IPC so the backend clears
		// its `.onboarding_started` marker (otherwise the auto-heal in
		// `startup_sequence.py` would treat onboarding as already-complete
		// `reset_onboarding_complete` Python function were dead code.
		const handleReRunWizard = async () => {
			try {
				await call("onboarding_reset");
			} catch (err) {
				console.warn(
					"[renderer:TroubleshootingSettingsSection] onboarding_reset IPC failed (non-fatal):",
					err,
				);
			}
			await updateConfig({ onboarding_completed: false });
			showSnack(t("settings.troubleshooting.reRunWizardToast"), "success");
			onNavigate?.("onboarding");
		};

		// Reset a stale macOS Accessibility TCC entry: the backend runs
		// `tccutil reset Accessibility <bundle-id>` (bundle ID resolved at
		// predecessor or Tauri) and re-opens System Settings so the user can
		// re-grant. The success toast surfaces the RUNTIME-RESOLVED
		// command the backend actually ran (finding #127 part b /
		// #919 part a) when the backend returned one.
		const handleResetAccessibility = async () => {
			try {
				const result = (await call("reset_macos_accessibility")) as {
					ok?: boolean;
					command?: string | null;
					error?: string | null;
				};
				if (result?.ok) {
					showSnack(
						result.command
							? t(
									"settings.troubleshooting.resetAccessibilityToastWithCommand",
									{
										command: result.command,
									},
								)
							: t("settings.troubleshooting.resetAccessibilityToast"),
						"success",
					);
				} else {
					showSnack(
						result?.error ||
							t("settings.troubleshooting.resetAccessibilityFailed"),
						"error",
					);
				}
			} catch (err) {
				console.error(
					"[renderer:TroubleshootingSettingsSection] reset_macos_accessibility failed:",
					err,
				);
				showSnack(
					t("settings.troubleshooting.resetAccessibilityFailed"),
					"error",
				);
			}
		};

		// Reset a stale Linux polkit authorization: the backend restarts
		const handleResetLinuxPermissions = async () => {
			try {
				const result = (await call("reset_linux_permissions")) as {
					ok?: boolean;
					command?: string | null;
					error?: string | null;
				};
				if (result?.ok) {
					showSnack(
						result.command
							? t("settings.troubleshooting.resetLinuxToastWithCommand", {
									command: result.command,
								})
							: t("settings.troubleshooting.resetLinuxToast"),
						"success",
					);
				} else {
					showSnack(
						result?.error || t("settings.troubleshooting.resetLinuxFailed"),
						"error",
					);
				}
			} catch (err) {
				console.error(
					"[renderer:TroubleshootingSettingsSection] reset_linux_permissions failed:",
					err,
				);
				showSnack(t("settings.troubleshooting.resetLinuxFailed"), "error");
			}
		};

		return (
			<SettingsSection title={title} description={description}>
				<div className="flex flex-wrap gap-3 px-4 py-2">
					{isVisible(keyboardShortcutsLabel, undefined, title) && (
						<Button
							variant="outline"
							className="gap-2"
							onClick={onOpenHelp}
							aria-label={t("help.title")}
							title={t("help.description")}
							data-testid="keyboard-shortcuts-button"
						>
							<HugeiconsIcon
								icon={KeyboardIcon}
								strokeWidth={2}
								className="h-4 w-4"
							/>
							{keyboardShortcutsLabel}
						</Button>
					)}
					{isVisible(reportBugLabel, undefined, title) && (
						<Button
							variant="outline"
							className="gap-2"
							onClick={onOpenBugReport}
							aria-label={t("settings.troubleshooting.reportBugAria")}
							title={t("settings.troubleshooting.reportBugHint")}
							data-testid="report-bug-button"
						>
							<HugeiconsIcon
								icon={Bug02Icon}
								strokeWidth={2}
								className="h-4 w-4"
							/>
							{reportBugLabel}
						</Button>
					)}
					{isDev && isVisible(reRunWizardLabel, undefined, title) && (
						<Button
							variant="outline"
							className="gap-2"
							onClick={handleReRunWizard}
							aria-label={t("settings.troubleshooting.reRunWizardAria")}
							title={t("settings.troubleshooting.reRunWizardHint")}
						>
							<HugeiconsIcon
								icon={ArrowTurnBackwardIcon}
								strokeWidth={2}
								className="h-4 w-4"
							/>
							{reRunWizardLabel}
						</Button>
					)}
					{isDev && isVisible(reRunWizardLabel, undefined, title) && (
						<p className="text-xs text-muted-foreground">
							{t("settings.troubleshooting.reRunWizardHint")}
						</p>
					)}
					{isMac && isVisible(resetAccessibilityLabel, undefined, title) && (
						<div className="flex flex-col gap-1">
							<Button
								variant="outline"
								className="gap-2 self-start"
								onClick={handleResetAccessibility}
								aria-label={t(
									"settings.troubleshooting.resetAccessibilityAria",
								)}
								title={t("settings.troubleshooting.resetAccessibilityHint")}
							>
								<HugeiconsIcon
									icon={ShieldBanIcon}
									strokeWidth={2}
									className="h-4 w-4"
								/>
								{resetAccessibilityLabel}
							</Button>
							{staleResetCommand && (
								<p className="text-xs text-muted-foreground">
									{t("settings.troubleshooting.resetAccessibilitySuggestion")}
									<code className="ms-1 rounded-lg bg-muted px-1 py-0.5 font-mono text-xs">
										{staleResetCommand}
									</code>
								</p>
							)}
						</div>
					)}
					{isLinux && isVisible(resetLinuxLabel, undefined, title) && (
						<Button
							variant="outline"
							className="gap-2"
							onClick={handleResetLinuxPermissions}
							aria-label={t("settings.troubleshooting.resetLinuxAria")}
							title={t("settings.troubleshooting.resetLinuxHint")}
						>
							<HugeiconsIcon
								icon={ShieldBanIcon}
								strokeWidth={2}
								className="h-4 w-4"
							/>
							{resetLinuxLabel}
						</Button>
					)}
				</div>
			</SettingsSection>
		);
	},
);
