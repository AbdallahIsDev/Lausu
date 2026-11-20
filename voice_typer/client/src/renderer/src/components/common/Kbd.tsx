import type { ComponentProps, ElementType, ReactNode } from "react";
import { cn } from "@/lib/utils";

// The plate is palette-independent on purpose (like the caption buttons):
// neutral-100 reads as a keycap in light, black in dark; text-foreground is
// token-derived so it stays readable across every light/dark/custom preset.
export const KBD_CHIP_CLASSES =
	"rounded-md border border-border/30 bg-neutral-100 px-2 py-0.5 font-mono text-xs text-foreground dark:bg-black";

interface KbdProps {
	children: ReactNode;
	as?: ElementType;
	/** Optional className override / extension. */
	className?: string;
}

export function Kbd({ children, as: Tag = "kbd", className }: KbdProps) {
	return (
		<Tag data-slot="kbd" className={cn(KBD_CHIP_CLASSES, className)}>
			{children}
		</Tag>
	);
}

export function KbdGroup({ className, ...props }: ComponentProps<"kbd">) {
	return (
		<kbd
			data-slot="kbd-group"
			className={cn("inline-flex items-center gap-1", className)}
			{...props}
		/>
	);
}
