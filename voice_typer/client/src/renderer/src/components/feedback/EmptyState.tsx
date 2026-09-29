import { Add01Icon, Alert02Icon } from "@hugeicons/core-free-icons";
import type { IconSvgElement } from "@hugeicons/react";
import { HugeiconsIcon } from "@hugeicons/react";
import type { ReactNode, RefObject } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type EmptyStateVariant = "info" | "error";

interface EmptyStateProps {
	icon: IconSvgElement;
	title: string;
	/** Plain text, or a node when the copy embeds inline elements (e.g. hotkey chips). */
	description?: ReactNode;
	/** Optional action button label */
	actionLabel?: string;
	/** Optional action button click handler */
	onAction?: () => void;
	/** Optional, overrides the default Add01Icon for the action button */
	actionIcon?: IconSvgElement;
	actionRef?: RefObject<HTMLButtonElement | null>;
	/** Optional extra content below the description */
	children?: ReactNode;
	variant?: EmptyStateVariant;
}

export function EmptyState({
	icon,
	title,
	description,
	actionLabel,
	onAction,
	actionIcon,
	actionRef,
	children,
	variant = "info",
}: EmptyStateProps) {
	const displayIcon = actionIcon ?? Add01Icon;
	const isError = variant === "error";
	// For the action button: when the empty state represents a failure,
	// the CTA is typically "Retry" / "Refresh", surface that with the
	// Alert02Icon instead of the default Add01Icon so the affordance
	// matches the context.
	const actionGlyph = isError ? Alert02Icon : displayIcon;
	return (
		<div
			role={isError ? "alert" : "status"}
			className={cn(
				// Match data-page cards (Media/Settings): rounded surface
				// panel + generous vertical rhythm so empty states breathe
				// like the rest of the page instead of floating in a void.
				"flex w-full flex-col items-center justify-center gap-5 rounded-lg border px-8 py-16",
				isError
					? // Error variant: tinted ring + soft destructive wash so
						// load failures don't masquerade as "no data yet".
						"border-destructive/40 bg-destructive/5"
					: "border-border/10 bg-surface-subtle",
			)}
		>
			<HugeiconsIcon
				icon={isError ? Alert02Icon : icon}
				strokeWidth={2}
				className={cn(
					"h-10 w-10",
					isError
						? // No opacity wash for the error variant —
							// destructive token already carries enough
							// contrast, and stacking opacity on top
							// pushes the icon below WCAG 1.4.11.
							"text-destructive"
						: // No opacity wash for the info variant either —
							// text-muted-foreground alone carries the visual
							// hierarchy. Stacking opacity on top of the
							// already-muted token pushed the icon below the
							// WCAG 1.4.11 non-text contrast minimum (3:1)
							// (same rationale as the description below).
							"text-muted-foreground",
				)}
			/>
			{/* Title is rendered as an <h3> (not a <p>) so screen-reader
			    users can navigate empty-state cards by heading. The heading
			    level (h3) is chosen to sit below the typical page <h1>/<h2>
			    hierarchy used across the app. */}
			<h3 className="text-center text-sm text-muted-foreground">{title}</h3>
			{/* Dropped opacity-70, text-muted-foreground is already a
			    low-contrast token, and stacking opacity on top pushed the
			    effective contrast below WCAG AA for body text. */}
			{description && (
				<p className="max-w-lg text-center text-xs leading-relaxed text-muted-foreground">
					{description}
				</p>
			)}
			{children}
			{actionLabel && onAction && (
				<Button
					ref={actionRef}
					variant="default"
					className="gap-2"
					onClick={onAction}
				>
					<HugeiconsIcon
						icon={actionGlyph}
						strokeWidth={2}
						className="h-4 w-4"
					/>
					{actionLabel}
				</Button>
			)}
		</div>
	);
}
