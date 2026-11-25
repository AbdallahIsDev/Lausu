/**
 * PluginsPanel — the developer-only Plugins surface, mounted as a Models tab.
 *
 * The content (cards, activation, the two shared settings) comes from the
 * existing `usePlugins` hook and the same `PluginCard` / `SettingRow` building
 * blocks the old standalone page used. The page shell is owned by Models:
 * this panel never renders a PageHeading, and the shell hides the tab unless
 * BOTH the local developer reveal and the backend `get_plugins.available`
 * flag are on. The backend remains the only authority that can run a plugin.
 */

import { PuzzleIcon } from "@hugeicons/core-free-icons";
import { useCallback } from "react";
import { SettingRow } from "@/components/common/SettingRow";
import { SettingsSection } from "@/components/common/SettingsSection";
import { EmptyState } from "@/components/feedback/EmptyState";
import { Switch } from "@/components/ui/switch";
import { useT } from "@/i18n/i18n";
import { PluginCard } from "@/pages/plugins/components/PluginCard";
import { usePlugins } from "@/pages/plugins/hooks/usePlugins";

export function PluginsPanel() {
	const t = useT();
	const {
		plugins,
		activePluginId,
		shared,
		loadError,
		loadPlugins,
		setActivePlugin,
		setSharedSetting,
	} = usePlugins();

	const handleActivate = useCallback(
		(pluginId: string, active: boolean) => {
			setActivePlugin(active ? pluginId : "");
		},
		[setActivePlugin],
	);

	const activePlugin = plugins.find((p) => p.id === activePluginId) ?? null;

	return (
		<section aria-label={t("plugins.title")} className="flex flex-col gap-4">
			{loadError ? (
				<SettingsSection title={t("plugins.title")}>
					<EmptyState
						variant="error"
						icon={PuzzleIcon}
						title={t("plugins.loadFailedTitle")}
						description={loadError}
						actionLabel={t("plugins.retry")}
						onAction={() => void loadPlugins()}
					/>
				</SettingsSection>
			) : plugins.length === 0 ? (
				<EmptyState
					icon={PuzzleIcon}
					title={t("plugins.emptyTitle")}
					description={t("plugins.emptyDescription")}
					actionLabel={t("plugins.retry")}
					onAction={() => void loadPlugins()}
				/>
			) : (
				<>
					<h2 className="font-sans text-lg font-medium text-foreground">
						{t("plugins.title")}
					</h2>
					<div className="grid grid-cols-3 gap-4">
						{plugins.map((plugin) => (
							<PluginCard
								key={plugin.id}
								plugin={plugin}
								onActivate={handleActivate}
							/>
						))}
					</div>
				</>
			)}

			{activePlugin ? (
				<SettingsSection
					title={t("plugins.settingsSection")}
					description={t("plugins.sharedSettingsDescription")}
					descriptionMode="tooltip"
				>
					<SettingRow
						label={t("plugins.visibleLabel")}
						info={t("plugins.visibleDescription")}
					>
						<Switch
							checked={shared.visible}
							onCheckedChange={(value) =>
								void setSharedSetting("visible", value)
							}
							aria-label={t("plugins.visibleLabel")}
							data-testid="plugin-setting-visible"
						/>
					</SettingRow>
					<SettingRow
						label={t("plugins.notifyLabel")}
						info={t("plugins.notifyDescription")}
					>
						<Switch
							checked={shared.notify}
							onCheckedChange={(value) =>
								void setSharedSetting("notify", value)
							}
							aria-label={t("plugins.notifyLabel")}
							data-testid="plugin-setting-notify"
						/>
					</SettingRow>
				</SettingsSection>
			) : (
				<p className="text-sm text-muted-foreground">
					{t("plugins.noActivePlugin")}
				</p>
			)}
		</section>
	);
}
