// Plugins page entry point (lazy route chunk target): the installed
// plugins as one compact card each, with the activation switch on the card,
// and ONE shared settings block below for the active plugin. Data +
// activation + shared settings all live in `./hooks/usePlugins`.

import { AlertCircleIcon, PuzzleIcon } from "@hugeicons/core-free-icons";
import { useCallback } from "react";
import { Skeleton } from "skullet/react";
import PageHeading from "@/components/common/PageHeading";
import { SettingRow } from "@/components/common/SettingRow";
import { SettingsSection } from "@/components/common/SettingsSection";
import { EmptyState } from "@/components/feedback/EmptyState";
import { MeasuredSkeleton } from "@/components/feedback/MeasuredSkeleton";
import { skeletonLoadingLabel } from "@/components/feedback/skeletons";
import { Switch } from "@/components/ui/switch";
import { useT } from "@/i18n/i18n";
import { PluginCard } from "./components/PluginCard";
import { usePlugins } from "./hooks/usePlugins";
import { SAMPLE_ACTIVE_PLUGIN, SAMPLE_PLUGINS } from "./lib/sample";

export default function PluginsPage() {
	const t = useT();
	const {
		plugins,
		activePluginId,
		shared,
		loading,
		loadError,
		loadPlugins,
		setActivePlugin,
		setSharedSetting,
	} = usePlugins();

	const handleActivate = useCallback(
		(pluginId: string, active: boolean) => {
			// Single owner model: ON selects this plugin, OFF restores the
			// built-in local model (""), exactly as the old detail switch did.
			setActivePlugin(active ? pluginId : "");
		},
		[setActivePlugin],
	);

	const activePlugin = plugins.find((p) => p.id === activePluginId) ?? null;

	if (loadError) {
		return (
			<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-4 px-16 pt-20 pb-6">
				<PageHeading
					title={t("plugins.title")}
					description={t("plugins.description")}
				/>
				<EmptyState
					variant="error"
					icon={AlertCircleIcon}
					title={t("plugins.loadFailedTitle")}
					description={loadError}
					actionLabel={t("plugins.retry")}
					onAction={() => void loadPlugins()}
				/>
			</div>
		);
	}

	return (
		<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-4 px-16 pt-20 pb-6">
			<PageHeading
				title={t("plugins.title")}
				description={t("plugins.description")}
			/>
			<Skeleton
				data={loading ? null : plugins}
				sample={SAMPLE_PLUGINS}
				id="plugins"
				label={skeletonLoadingLabel()}
			>
				{(items) =>
					items.length === 0 ? (
						/* The shipped build has no plugin workspace, so an empty list
				   is the NORMAL state, not a failure (C-UI-2). */
						<EmptyState
							icon={PuzzleIcon}
							title={t("plugins.emptyTitle")}
							description={t("plugins.emptyDescription")}
							actionLabel={t("plugins.retry")}
							onAction={() => void loadPlugins()}
						/>
					) : (
						<div className="grid grid-cols-2 gap-4">
							{items.map((plugin) => (
								<PluginCard
									key={plugin.id}
									plugin={plugin}
									onActivate={handleActivate}
								/>
							))}
						</div>
					)
				}
			</Skeleton>

			{/* ONE shared settings surface for whichever plugin is active.
			    No plugin declares or stores these itself. */}
			<MeasuredSkeleton
				stackClassName="gap-4"
				data={loading ? null : (activePlugin ?? SAMPLE_ACTIVE_PLUGIN)}
				sample={SAMPLE_ACTIVE_PLUGIN}
				id="plugin-shared-settings"
				label={skeletonLoadingLabel()}
			>
				{() =>
					activePlugin === null ? (
						<p className="text-sm text-muted-foreground">
							{t("plugins.noActivePlugin")}
						</p>
					) : (
						<SettingsSection
							title={t("plugins.settingsSection")}
							description={t("plugins.sharedSettingsDescription")}
							descriptionMode="tooltip"
							stackClassName="gap-2"
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
					)
				}
			</MeasuredSkeleton>
		</div>
	);
}
