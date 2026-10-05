import {
	Add01Icon,
	Alert02Icon,
	RefreshIcon,
} from "@hugeicons/core-free-icons";
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
	/** Optional, overrides the variant's default action glyph (RefreshIcon for error, Add01Icon for info) */
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
	const isError = variant === "error";
	// Error CTAs are retries, so they carry the reload glyph — the same one
	// every other Retry button in the app uses (ConnectionStatusScreen).
	const actionGlyph = actionIcon ?? (isError ? RefreshIcon : Add01Icon);
	return (
		<div
			role={isError ? "alert" : "status"}
			className={cn(
				"flex w-full flex-col items-center justify-center rounded-lg border text-center",
				isError
					? // Calm app-theme failure card: neutral surface, destructive
						// accent confined to the icon disc. A full-card red wash
						// reads as an alarm, not as a load failure.
						"gap-4 border-border/8 bg-surface px-6 py-10"
					: "gap-5 border-border/8 bg-surface-subtle px-8 py-16",
			)}
		>
			{isError ? (
				<div
					data-slot="empty-state-error-icon"
					className="flex items-center justify-center rounded-full bg-destructive/10 p-3"
				>
					<HugeiconsIcon
						icon={Alert02Icon}
						strokeWidth={2}
						className="h-10 w-10 text-destructive"
					/>
				</div>
			) : (
				<HugeiconsIcon
					icon={icon}
					strokeWidth={2}
					className="h-10 w-10 text-muted-foreground"
				/>
			)}
			{/* Title is an <h3> (not a <p>) so screen-reader users can navigate
			    empty-state cards by heading; the level sits below the page h1/h2. */}
			<h3
				className={cn(
					"text-center",
					isError
						? "text-lg font-semibold text-foreground"
						: "text-sm text-muted-foreground",
				)}
			>
				{title}
			</h3>
			{/* No stacked opacity on text-muted-foreground — it is already a
			    low-contrast token, and opacity on top drops below WCAG AA. */}
			{description && (
				<p
					className={cn(
						"max-w-lg text-center leading-relaxed text-muted-foreground",
						isError ? "text-sm" : "text-xs",
					)}
				>
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
