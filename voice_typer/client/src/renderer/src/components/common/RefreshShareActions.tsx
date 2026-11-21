// ONE joined refresh + share control. Owned by this shared component so Home,
// Dashboard and any future surface render the same group: the group carries the
// surface and radius, the members stay bare, and the divider comes from the
// group's child rule (see ActionButtonsGroup).

import { ActionButtonsGroup } from "@/components/common/ActionButtonsGroup";
import { LastUpdatedIndicator } from "@/components/common/LastUpdatedIndicator";
import {
	type ShareStatsActions,
	ShareStatsDialog,
} from "@/components/dashboard/ShareStatsDialog";
import type { StatsThemePalette } from "@/lib/theme-palette";
import type { ShareStats } from "@/types/stats";

export interface RefreshShareActionsProps {
	agoLabel: string;
	onRefresh: () => void;
	refreshing?: boolean;
	/** Pages that show freshness only once data exists pass false until then. */
	showRefresh?: boolean;
	actions: ShareStatsActions;
	stats: ShareStats | null;
	palette: StatsThemePalette;
	shareDisabled?: boolean;
	className?: string;
}

export function RefreshShareActions({
	agoLabel,
	onRefresh,
	refreshing = false,
	showRefresh = true,
	actions,
	stats,
	palette,
	shareDisabled = false,
	className,
}: RefreshShareActionsProps) {
	return (
		<ActionButtonsGroup className={className}>
			{showRefresh && (
				<LastUpdatedIndicator
					agoLabel={agoLabel}
					onRefresh={onRefresh}
					refreshing={refreshing}
					segmented
				/>
			)}
			<ShareStatsDialog
				actions={actions}
				stats={stats}
				palette={palette}
				segmented
				disabled={shareDisabled}
			/>
		</ActionButtonsGroup>
	);
}
