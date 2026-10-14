import type { ComponentProps, ReactNode } from "react";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { cn } from "@/lib/utils";

// ── Group shell ───────────────────────────────────────────────────────

/**
 * The accordion container shared by Local Models + Cloud Models.
 * Matches the pre-overhaul Local Models treatment
 * (rounded-lg border bg-subtle) so both tabs read as the same
 * surface.
 */
export function ModelGroupAccordion({
	className,
	...props
}: ComponentProps<typeof Accordion>) {
	return (
		<Accordion
			className={cn(
				"rounded-lg border border-border/8 bg-surface-subtle",
				className,
			)}
			{...props}
		/>
	);
}

export function ModelGroupItem({
	className,
	...props
}: ComponentProps<typeof AccordionItem>) {
	return (
		<AccordionItem
			className={cn("border-border/8 data-open:bg-transparent", className)}
			{...props}
		/>
	);
}

export function ModelGroupTrigger({
	className,
	children,
	actions,
	...props
}: ComponentProps<typeof AccordionTrigger>) {
	return (
		<AccordionTrigger
			className={cn(
				// `justify-start` + `items-center` override the primitive's
				// `justify-between` + `items-start`. That base pair is kept
				// for consumers that spread TWO groups across the row (the
				// microphone preset selector: label on the left, current
				// value + chevron on the right), but it is wrong here: a
				// model-group header's children are the logo and the name,
				// one unit. The primitive used to neutralise its own
				// `justify-between` by giving the trailing "+" `ms-auto`,
				// which consumed every spare pixel — once the glyph moved
				// out to the sibling span, nothing absorbed the free space
				// and the name was flung to the far edge, away from its
				// logo. These two classes are the replacement, at the layer
				// that knows the header is a single line.
				"justify-start items-center gap-2 px-4 py-2.5 text-sm font-medium text-foreground hover:no-underline hover:bg-foreground/5 data-open:bg-transparent",
				className,
			)}
			// Forwarded through (not spread with the rest) so the slot is
			// declared at this layer too, the Cloud tab's provider-level
			// Configure button uses it to sit on the group's header row
			// while staying outside the trigger `<button>` — immediately
			// LEFT of the disclosure chevron. When it is present the primitive
			// also makes the HEADER the hover group, so the row highlight
			// covers the action instead of stopping at the "+"; the
			// `hover:bg-foreground/5` below still carries the Local tab,
			// which passes no actions and therefore gets no group hover.
			actions={actions}
			{...props}
		>
			{children}
		</AccordionTrigger>
	);
}

/** The expanded-group content wrapper: rows separated by hairline dividers. */
export function ModelGroupContent({
	className,
	children,
	...props
}: ComponentProps<typeof AccordionContent>) {
	return (
		<AccordionContent
			className={cn("px-0 pb-0 divide-y divide-border/8", className)}
			{...props}
		>
			{children}
		</AccordionContent>
	);
}

// ── Single model/plan row ─────────────────────────────────────────────

export interface ModelVariantRowProps {
	/** Row heading (the model/plan display name). Rendered as an <h4>. */
	name: string;
	/** Optional badges rendered inline next to the heading. */
	headingExtra?: ReactNode;
	/** Metadata line: `MetadataPair` values + icon-only metadata chips. */
	meta?: ReactNode;
	/** Right-side actions (e.g. `ModelCardActions`, a Configure button). */
	actions?: ReactNode;
}

export function ModelVariantRow({
	name,
	headingExtra,
	meta,
	actions,
}: ModelVariantRowProps) {
	return (
		<div className="flex items-center gap-3 px-4 py-2.5">
			<div className="flex min-w-0 flex-1 flex-col gap-1">
				<div className="flex items-center gap-2">
					<h4
						className="truncate text-sm font-medium text-foreground"
						title={name}
					>
						{name}
					</h4>
					{headingExtra}
				</div>
				{meta && (
					<div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs">
						{meta}
					</div>
				)}
			</div>
			{actions && (
				<div className="flex shrink-0 items-center gap-2">{actions}</div>
			)}
		</div>
	);
}

// ── Metadata primitives (point 6) ─────────────────────────────────────

/**
 * Label+value pair: the LABEL word renders muted/secondary, then a
 * colon, then the VALUE in the primary text color, visually a
 * "named metric with a measured value" (e.g. "VRAM: ~512 MB",
 * "WER: 5.0%").
 */
export function MetadataPair({
	label,
	value,
}: {
	label: string;
	value: string;
}) {
	return (
		<span className="inline-flex items-baseline gap-1">
			<span className="text-muted-foreground">{label}</span>
			<span className="text-foreground">: {value}</span>
		</span>
	);
}
