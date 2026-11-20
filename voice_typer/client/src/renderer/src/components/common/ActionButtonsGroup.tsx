// Joined icon actions (refresh + share) as ONE control: the group owns the
// surface and radius, members are bare, and the divider comes from the group's
// child rule (`divide-*` sits in `:where()` and loses to a member's `border-0`).
// NOTE: see DESIGN-SYSTEM.md#ActionButtonsGroup.

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Bare member styling for a button living inside `ActionButtonsGroup`. */
export const SEGMENTED_ACTION_BUTTON =
	"rounded-none border-0 bg-transparent hover:bg-border/8";

export interface ActionButtonsGroupProps {
	children: ReactNode;
	className?: string;
}

export function ActionButtonsGroup({
	children,
	className,
}: ActionButtonsGroupProps) {
	return (
		// biome-ignore lint/a11y/useSemanticElements: a pair of icon buttons is a plain group, not a landmark.
		<div
			role="group"
			data-testid="action-buttons-group"
			className={cn(
				// The surface the members used to carry, moved to the group: the
				// outline Button's fill + hairline border, rounded once.
				"flex items-stretch overflow-hidden rounded-lg border border-border/8 bg-border/5",
				// Every member after the first is separated by a hairline.
				"[&>*:not(:first-child)]:border-l [&>*:not(:first-child)]:border-border/8",
				className,
			)}
		>
			{children}
		</div>
	);
}
