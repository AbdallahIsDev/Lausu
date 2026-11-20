// Owner-only variant switcher. Mounted once in App.tsx; hidden until the owner
// opts in via localStorage. One surface, divided rows, no nested
// cards (C-UI-16), no animation (C-ANIM-3), real Button focus rings (C-FOCUS-1).

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { PluginsBadgeHue } from "@/components/layout/PluginsNewBadge";
import {
	DEBUG_PANEL_VISIBLE_KEY,
	type StatsLayout,
	useDebugPrefs,
} from "@/hooks/useDebugPrefs";
import { t } from "@/i18n/i18n";
import { cn } from "@/lib/utils";

type Choice = { value: string; label: string; testId: string };

function ChoiceRow({
	label,
	choices,
	current,
	onSelect,
}: {
	label: string;
	choices: Choice[];
	current: string;
	onSelect: (value: string) => void;
}) {
	return (
		<div className="px-3 py-2">
			<div className="mb-1 text-[11px] font-medium text-muted-foreground">
				{label}
			</div>
			<div role="group" aria-label={label} className="flex flex-wrap gap-1">
				{choices.map((choice) => (
					<Button
						key={choice.value}
						size="sm"
						variant={current === choice.value ? "secondary" : "ghost"}
						aria-pressed={current === choice.value}
						data-testid={choice.testId}
						onClick={() => onSelect(choice.value)}
						className="h-7 px-2 text-[11px]"
					>
						{choice.label}
					</Button>
				))}
			</div>
		</div>
	);
}

export function DebugPanel() {
	const [open, setOpen] = useState(true);
	const { statsLayout, badgeHue, setStatsLayout, setBadgeHue, reset } =
		useDebugPrefs();

	// Exact visibility rule: the panel stays in the code but renders ONLY when
	// the owner explicitly opts in via localStorage. Neither developer_mode
	// nor a dev build shows it by itself (owner instruction 2026-11-19).
	let optedIn = false;
	try {
		optedIn = localStorage.getItem(DEBUG_PANEL_VISIBLE_KEY) === "1";
	} catch {
		// Storage disabled: stay hidden.
	}
	if (!optedIn) return null;

	return (
		<section
			data-testid="debug-panel"
			role="region"
			aria-label={t("debug.title")}
			className={cn(
				"fixed end-4 bottom-4 z-40 w-60 rounded-lg border border-border/8 bg-surface text-foreground shadow-lg",
			)}
		>
			<div className="flex items-center justify-between gap-2 px-3 py-2">
				<span className="text-xs font-medium">{t("debug.title")}</span>
				<Button
					size="sm"
					variant="ghost"
					aria-label={open ? t("debug.close") : t("debug.open")}
					aria-expanded={open}
					data-testid="debug-toggle"
					onClick={() => setOpen((v) => !v)}
					className="h-7 w-7 p-0"
				>
					{open ? "−" : "+"}
				</Button>
			</div>
			{open && (
				<div className="divide-y divide-border/8 border-t border-border/8">
					<ChoiceRow
						label={t("debug.statsLayout")}
						current={statsLayout}
						onSelect={(v) => setStatsLayout(v as StatsLayout)}
						choices={[
							{
								value: "separated",
								label: t("debug.separated"),
								testId: "debug-stats-separated",
							},
							{
								value: "joined",
								label: t("debug.joined"),
								testId: "debug-stats-joined",
							},
						]}
					/>
					<ChoiceRow
						label={t("debug.badgeColor")}
						current={badgeHue}
						onSelect={(v) => setBadgeHue(v as PluginsBadgeHue)}
						choices={[
							{
								value: "red",
								label: t("debug.red"),
								testId: "debug-badge-red",
							},
							{
								value: "green",
								label: t("debug.green"),
								testId: "debug-badge-green",
							},
							{
								value: "primary",
								label: t("debug.primary"),
								testId: "debug-badge-primary",
							},
						]}
					/>
					<div className="px-3 py-2">
						<Button
							size="sm"
							variant="outline"
							data-testid="debug-reset"
							onClick={reset}
							className="h-7 w-full text-[11px]"
						>
							{t("debug.reset")}
						</Button>
					</div>
				</div>
			)}
		</section>
	);
}
