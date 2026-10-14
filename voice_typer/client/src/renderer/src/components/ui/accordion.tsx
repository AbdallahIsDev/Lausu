import { ArrowRight01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { Accordion as AccordionPrimitive } from "radix-ui";
import * as React from "react";
import { cn } from "#utils";

function Accordion({
	className,
	...props
}: React.ComponentProps<typeof AccordionPrimitive.Root>) {
	return (
		<AccordionPrimitive.Root
			data-slot="accordion"
			className={cn(
				"flex w-full flex-col overflow-hidden rounded-lg border",
				className,
			)}
			{...props}
		/>
	);
}

function AccordionItem({
	className,
	...props
}: React.ComponentProps<typeof AccordionPrimitive.Item>) {
	return (
		<AccordionPrimitive.Item
			data-slot="accordion-item"
			className={cn("not-last:border-b data-open:bg-muted/50", className)}
			{...props}
		/>
	);
}

function AccordionTrigger({
	className,
	children,
	actions,
	disclosure = true,
	...props
}: React.ComponentProps<typeof AccordionPrimitive.Trigger> & {
	/**
	 * Optional trailing slot, rendered INSIDE the header but OUTSIDE the
	 * trigger button (e.g. the Cloud tab's provider-level Configure
	 * action, which must sit on the same row as the provider name).
	 *
	 * It cannot live inside the trigger's children: the trigger IS a
	 * `<button>`, so nesting another one is invalid HTML and axe flags
	 * it as `nested-interactive`. A sibling also means clicking the
	 * action cannot toggle the panel.
	 *
	 * Rendered as a `<span>` (not a `<div>`) because the header is an
	 * `<h3>`, whose content model is phrasing content.
	 *
	 * WHEN PRESENT, the header — not the trigger — is the row: the
	 * trigger stops spanning it, so the row highlight is painted by BOTH
	 * halves through `group-hover/accordion-row` (two adjacent,
	 * non-overlapping boxes at 5% alpha read as one continuous row; a
	 * single box carrying it twice would double-stack to ~10% and seam).
	 */
	actions?: React.ReactNode;
	/**
	 * Render the disclosure chevron at the end of the row. `false` for
	 * instances that supply their own expand affordance (the microphone
	 * preset selector's rotating chevron). Replaces the old
	 * `**:data-[slot=accordion-trigger-icon]:hidden` hack, which only
	 * worked while the glyph was a descendant of the trigger.
	 */
	disclosure?: boolean;
}) {
	// The disclosure glyph lives in the trailing slot, OUTSIDE the
	// trigger <button>, so a click on it (or on the padding around it)
	// would be inert — it used to sit inside the button and toggle the
	// panel. Forward every click in that slot that did NOT land on an
	// action button back to the trigger, which preserves the hit area
	// the row had before.
	const triggerRef = React.useRef<HTMLButtonElement | null>(null);
	const forwardClickToTrigger = (event: React.MouseEvent<HTMLSpanElement>) => {
		const target = event.target;
		if (target instanceof Element && target.closest("button")) return;
		triggerRef.current?.click();
	};

	const hasActions = actions != null;
	// The trailing slot exists only when it has something to hold. An
	// empty one would still contribute its `pe-4` and steal 16px from the
	// trigger — the pre-`disclosure` primitive rendered it only when
	// `actions` was truthy, so a `disclosure={false}` instance with no
	// actions (the microphone preset selector) keeps that DOM exactly.
	const hasTrailing = hasActions || disclosure;

	return (
		// `items-stretch`, NOT `items-center`. The two halves of this row
		// paint the same hover colour, so they only read as ONE band if
		// they are also the same HEIGHT. They are not naturally: the
		// trigger is `py-2.5` around a 20px line box (40px), while the
		// trailing span is only as tall as the action button it wraps
		// (~32px). Centred, that difference shows up as a step between
		// the two tints — the row looked like two hover regions with a
		// seam. Stretching both to the line's cross size makes the tint
		// continuous; each half centres its own content independently.
		// `group/accordion-header` exists so the chevron can read the
		// OPEN/CLOSED state. Radix puts `data-state` on this `<h3>` (and
		// on the trigger), but the chevron is a sibling of the trigger,
		// not a descendant — `group-data-[state=open]/accordion-trigger:`
		// cannot reach it from here. The header wraps both, so it can.
		<AccordionPrimitive.Header
			className={cn(
				"group/accordion-header flex items-stretch",
				hasActions && "group/accordion-row",
			)}
		>
			<AccordionPrimitive.Trigger
				ref={triggerRef}
				data-slot="accordion-trigger"
				className={cn(
					"group/accordion-trigger relative flex flex-1 items-start justify-between gap-6 border border-transparent p-4 text-start text-sm font-medium transition-all outline-hidden hover:underline focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:pointer-events-none disabled:opacity-50",
					hasActions && "group-hover/accordion-row:bg-foreground/5",
					className,
				)}
				{...props}
			>
				{children}
			</AccordionPrimitive.Trigger>
			{hasTrailing ? (
				<>
					{/* biome-ignore lint/a11y/noStaticElementInteractions: the span is not a control — it forwards a pointer click to the trigger <button> beside it, which is the accessible control (same pattern as SelectableRow). */}
					{/* biome-ignore lint/a11y/useKeyWithClickEvents: keyboard users activate the trigger button directly, so a keydown mirror here would double-fire the toggle. */}
					<span
						data-slot="accordion-trigger-trailing"
						className={cn(
							"flex shrink-0 items-center gap-2 pe-4",
							hasActions && "group-hover/accordion-row:bg-foreground/5",
						)}
						onClick={forwardClickToTrigger}
					>
						{actions}
						{disclosure ? (
							/* A RIGHT chevron that rotates to point DOWN when the
							   group is open (user decision 2026-10-14, reversing
							   the 2026-08-21 static-plus decision; the rule that
							   forbade it, C-MODELS-3, was retired). Rendered
							   AFTER the actions slot, so a row-level action
							   reads as "…action, then the disclosure".

							   The rotation is driven from the HEADER's
							   `data-state`, not the trigger's: the glyph is a
							   sibling of the trigger, so a
							   `group-data-[state=open]/accordion-trigger:`
							   selector cannot reach it. Same reason
							   `group/accordion-header` exists at all. */
							<HugeiconsIcon
								icon={ArrowRight01Icon}
								strokeWidth={2}
								data-slot="accordion-trigger-icon"
								aria-hidden="true"
								className="pointer-events-none size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]/accordion-header:rotate-90"
							/>
						) : null}
					</span>
				</>
			) : null}
		</AccordionPrimitive.Header>
	);
}

function AccordionContent({
	className,
	children,
	...props
}: React.ComponentProps<typeof AccordionPrimitive.Content>) {
	return (
		<AccordionPrimitive.Content
			data-slot="accordion-content"
			className="overflow-hidden text-sm data-open:animate-accordion-down data-closed:animate-accordion-up"
			{...props}
		>
			<div
				className={cn(
					// No fixed height: open/close animations drive outer height via
					// --radix-accordion-content-height; a fixed height freezes the
					// open-time measurement and leaves a trailing void when content shrinks.
					"pt-0 pb-4 [&_a]:underline [&_a]:underline-offset-3 [&_a]:hover:text-foreground [&_p:not(:last-child)]:mb-4",
					className,
				)}
			>
				{children}
			</div>
		</AccordionPrimitive.Content>
	);
}

export { Accordion, AccordionContent, AccordionItem, AccordionTrigger };
