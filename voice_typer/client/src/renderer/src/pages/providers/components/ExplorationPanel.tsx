// Page-local exploration switcher, kept as a reusable debug surface. Not a
// user setting and not part of the shared design system: callers pass the
// options they want to compare and it renders a fixed, always-reachable
// bottom-right control group.

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ExplorationOption {
	id: string;
	label: string;
}

export function ExplorationPanel({
	options,
	value,
	onChange,
	label,
}: {
	options: readonly ExplorationOption[];
	value: string;
	onChange: (id: string) => void;
	/** Accessible name for the group and its visible caption. */
	label: string;
}) {
	return (
		<div className="fixed end-6 bottom-6 z-50 flex w-52 flex-col gap-2 rounded-lg border border-border/10 bg-surface p-2">
			<span className="px-1 text-xs font-medium text-muted-foreground">
				{label}
			</span>
			<fieldset aria-label={label} className="flex min-w-0 flex-col gap-1">
				{options.map((option, index) => {
					const active = option.id === value;
					return (
						<Button
							key={option.id}
							size="sm"
							variant="ghost"
							aria-pressed={active}
							onClick={() => onChange(option.id)}
							className={cn(
								"justify-start gap-2",
								active && "bg-border/8 text-foreground",
							)}
						>
							<span className="w-3 shrink-0 text-xs tabular-nums text-muted-foreground">
								{index + 1}
							</span>
							<span className="truncate">{option.label}</span>
						</Button>
					);
				})}
			</fieldset>
		</div>
	);
}
