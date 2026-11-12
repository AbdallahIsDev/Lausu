// Plugins page entry point (lazy route chunk target): the installed
// plugins, one compact card per plugin in a 2-per-row grid. Data +
// activation live in `./hooks/usePlugins`; this file is the view
// (heading, grid, loading / empty / error states).

import { AlertCircleIcon, PuzzleIcon } from "@hugeicons/core-free-icons";
import { useCallback } from "react";
import { Skeleton } from "skullet/react";
import PageHeading from "@/components/common/PageHeading";
import { EmptyState } from "@/components/feedback/EmptyState";
import { skeletonLoadingLabel } from "@/components/feedback/skeletons";
import { useT } from "@/i18n/i18n";
import { PluginCard } from "./components/PluginCard";
import { usePlugins } from "./hooks/usePlugins";
import { SAMPLE_PLUGINS } from "./lib/sample";
import { usePluginSelection } from "./lib/usePluginSelection";
import PluginDetail from "./PluginDetail";

export default function PluginsPage() {
	const t = useT();
	const { plugins, loading, loadError, loadPlugins } = usePlugins();
	const selectedPluginId = usePluginSelection((s) => s.selectedPluginId);
	const selectPlugin = usePluginSelection((s) => s.selectPlugin);

	const openPlugin = useCallback(
		(pluginId: string) => selectPlugin(pluginId),
		[selectPlugin],
	);

	// A selected plugin swaps this route's view for the detail view; the
	// detail page owns its own "Back to plugins" affordance.
	if (selectedPluginId !== null) return <PluginDetail />;

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
				   is the NORMAL state, not a failure: the copy states exactly
				   that no plugins are installed (C-UI-2). */
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
									onOpen={openPlugin}
								/>
							))}
						</div>
					)
				}
			</Skeleton>
		</div>
	);
}
