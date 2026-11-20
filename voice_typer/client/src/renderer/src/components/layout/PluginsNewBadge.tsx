import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type PluginsBadgeHue = "primary" | "red" | "green";

// All three hues are design tokens, so they survive every light/dark/custom
// preset: destructive = brand red, success = emerald-family green, primary =
// the active accent. The label is the FULL-opacity hue; only the wash and the
// border are transparent. Never add `opacity-*` to the chip itself.
const HUE_CLASSES: Record<PluginsBadgeHue, string> = {
	primary: "border-primary/30 bg-primary/15 text-primary",
	red: "border-destructive/30 bg-destructive/15 text-destructive",
	green: "border-success/30 bg-success/15 text-success",
};

export interface PluginsNewBadgeProps {
	label: ReactNode;
	collapsed: boolean;
	/** The sidebar's own label motion classes, passed in from its owner. */
	motionClass: string;
	hue?: PluginsBadgeHue;
}

export function PluginsNewBadge({
	label,
	collapsed,
	motionClass,
	hue = "primary",
}: PluginsNewBadgeProps) {
	return (
		<span
			data-testid="nav-new-badge"
			className={cn(
				"ms-auto shrink-0 overflow-hidden whitespace-nowrap",
				"transition-[max-width,opacity,translate,filter] duration-200 ease-out",
				collapsed ? "max-w-0" : "max-w-16",
				motionClass,
			)}
		>
			<span
				className={cn(
					"inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium leading-none",
					HUE_CLASSES[hue],
				)}
			>
				{label}
			</span>
		</span>
	);
}
