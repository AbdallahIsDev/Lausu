import { ArrowRight01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { Accordion as AccordionPrimitive } from "radix-ui";
import type * as React from "react";
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
	 * Optional trailing slot, rendered INSIDE the trigger button at the
	 * far right (e.g. the Cloud tab's provider-level Configure action,
	 * which sits on the same row as the provider name, immediately LEFT
	 * of the disclosure chevron).
	 *
	 * The slot lives inside the trigger's `<button>` so the row is ONE
	 * hover surface: the trigger alone owns `hover:bg-foreground/5`.
	 * Clicks on an action button do NOT toggle the panel — the slot
	 * wrapper stops propagation before it reaches the trigger.
	 *
	 * Rendered as a `<div>` (not a `<span>`) per the Models-row DOM
	 * contract: left content group + right trailing group, both divs
	 * inside the full-width trigger button.
	 */
	actions?: React.ReactNode;
	/**
	 * Render the disclosure chevron at the end of the row. `false` for
	 * instances that supply their own expand affordance (the microphone
	 * preset selector's rotating chevron).
	 */
	disclosure?: boolean;
}) {
	const hasActions = actions != null;
	// The trailing group exists only when it has something to hold. An
	// empty one would still steal inset from the label side, so a
	// `disclosure={false}` instance with no actions (the microphone
	// preset selector) renders no trailing group at all.
	const hasTrailing = hasActions || disclosure;

	return (
		// The header is layout only: the trigger button is the row. It
		// spans the full width (`flex-1` in this flex header) and owns
		// the single hover surface — there is no sibling half painting
		// a second tint.
		<AccordionPrimitive.Header className="flex">
			<AccordionPrimitive.Trigger
				data-slot="accordion-trigger"
				className={cn(
					"group/accordion-trigger relative flex w-full flex-1 items-center justify-between gap-6 border border-transparent p-4 text-start text-sm font-medium transition-all outline-hidden hover:bg-foreground/5 hover:underline focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:pointer-events-none disabled:opacity-50",
					className,
				)}
				{...props}
			>
				{children}
				{hasTrailing ? (
					// biome-ignore lint/a11y/noStaticElementInteractions: the div is not a control — it only stops an action button's click reaching the trigger <button> beside it, which is the accessible control.
					// biome-ignore lint/a11y/useKeyWithClickEvents: keyboard users activate the action button directly, so a keydown mirror here would double-fire.
					<div
						data-slot="accordion-trigger-trailing"
						className="flex shrink-0 items-center gap-2"
						// An action (e.g. Configure) inside the trigger must
						// not toggle the panel: stop its click reaching the
						// trigger button. Chevron/padding clicks fall through
						// and toggle normally — the whole button is the hit
						// area.
						onClick={(event) => {
							const target = event.target;
							if (target instanceof Element && target.closest("button"))
								event.stopPropagation();
						}}
					>
						{actions}
						{disclosure ? (
							/* A RIGHT chevron that rotates to point DOWN when the
							   group is open. Rendered AFTER the actions slot,
							   so a row-level action reads as "…action, then
							   the disclosure". Driven from the TRIGGER's
							   `data-state`: the glyph is a descendant of the
							   trigger, so the trigger group selector reaches
							   it. */
							<HugeiconsIcon
								icon={ArrowRight01Icon}
								strokeWidth={2}
								data-slot="accordion-trigger-icon"
								aria-hidden="true"
								className="pointer-events-none size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]/accordion-trigger:rotate-90"
							/>
						) : null}
					</div>
				) : null}
			</AccordionPrimitive.Trigger>
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
