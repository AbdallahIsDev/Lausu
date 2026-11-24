// The Settings landing page: ONE card of rows, each with an icon, a
// title and a chevron. Current values and descriptions are deliberately
// NOT rendered; their translated text stays in the search label set so
// "Search settings…" still finds every row.

import { ArrowRight01Icon, Search01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useMemo } from "react";
import { APP_NAME } from "@/branding";
import { EmptyState } from "@/components/feedback/EmptyState";
import {
	SETTINGS_HUB_ROWS,
	type SettingsHubPage,
} from "@/components/settings/settingsSections";
import { getSectionLabels } from "@/components/settings/settingsTabLabels";
import { fuzzyContains } from "@/hooks/useFuzzySearch";
import { useT } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import { useGlobalSearch } from "@/stores/useGlobalSearch";

export interface SettingsHubProps {
	/** Navigate to a section page or an appended page (Chat/Providers). */
	onNavigateSection: (page: SettingsHubPage) => void;
}

export function SettingsHub({ onNavigateSection }: SettingsHubProps) {
	const t = useT();
	const query = useGlobalSearch((s) => s.query);
	const clearQuery = useGlobalSearch((s) => s.clearQuery);
	const q = query.trim();

	const rows = useMemo(() => {
		const labelsByPage = getSectionLabels();
		return SETTINGS_HUB_ROWS.flatMap((row) => {
			const title = t(row.titleKey);
			const keywords = [
				title,
				t(row.descriptionKey, { appName: APP_NAME }),
				...(labelsByPage[row.page] ?? []),
			];
			if (!q) return [{ row, title }];
			const matched = [...new Set(keywords)].filter((label) =>
				fuzzyContains(label, q),
			);
			return matched.length > 0 ? [{ row, title }] : [];
		});
	}, [q, t]);

	if (q && rows.length === 0) {
		return (
			<EmptyState
				variant="info"
				icon={Search01Icon}
				title={t("settings.searchNoMatch", { query: q })}
				description={t("settings.noResultsMessage")}
				actionLabel={t("a11y.clearSearch")}
				onAction={clearQuery}
			/>
		);
	}

	return (
		<section aria-label={t("settings.title")}>
			<div className="overflow-hidden rounded-lg border border-border/8 bg-surface-subtle divide-y divide-border/8">
				{rows.map(({ row, title }) => (
					<button
						key={row.page}
						type="button"
						data-testid={`settings-hub-row-${row.page}`}
						className={cn(
							"flex w-full items-center gap-4 p-4 text-start",
							"transition-colors duration-150 hover:bg-foreground/5",
							"focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none",
						)}
						onClick={() => onNavigateSection(row.page)}
					>
						<HugeiconsIcon
							icon={row.icon}
							strokeWidth={2}
							aria-hidden="true"
							className="h-5 w-5 shrink-0 text-muted-foreground"
						/>
						<span className="min-w-0 flex-1 text-sm font-medium text-foreground">
							{title}
						</span>
						<HugeiconsIcon
							icon={ArrowRight01Icon}
							strokeWidth={2}
							aria-hidden="true"
							className="nav-directional-icon h-4 w-4 shrink-0 text-muted-foreground"
						/>
					</button>
				))}
			</div>
		</section>
	);
}
