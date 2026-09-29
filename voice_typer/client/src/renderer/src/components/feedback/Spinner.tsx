import { t } from "@/i18n/i18n";
import { cn } from "@/lib/utils";

interface SpinnerProps {
	/** Diameter in pixels. Default 16. */
	size?: number;
	/** Additional class names appended to the spinner element. */
	className?: string;
	label?: string;
	decorative?: boolean;
}

export function Spinner({
	size = 16,
	className,
	label,
	decorative = false,
}: SpinnerProps) {
	const resolvedClassName = cn(
		"animate-spin rounded-full border-2 border-accent border-t-transparent",
		className,
	);
	const resolvedStyle = { width: size, height: size };
	if (decorative) {
		return (
			<div
				aria-hidden="true"
				className={resolvedClassName}
				style={resolvedStyle}
			/>
		);
	}
	// Use a <span role="img"> with an accessible name
	// instead of <output>. The <output> element has an implicit
	// ARIA role of "status" (i.e. aria-live="polite"), which caused
	// every page that rendered a Spinner to announce "Loading" to
	// screen-reader users, even when the spinner was incidental to
	// the page's primary content. <span role="img"> gives the
	// spinner an accessible name (so AT users hear "Loading" when
	// they focus it) without the implicit live region. Pages that
	// need the live-region announcement (e.g. ConnectionStatusScreen)
	// wrap the Spinner in their own <output aria-live="polite">.
	// When a contextual ``label`` is provided it ALSO renders as
	// visible text next to the glyph, "Loading microphones…" reads
	// better than an anonymous spinner for sighted users too. The
	// glyph span stays the FIRST element (the component's root in the
	// DOM) carrying role/aria-label/size/classes, and the label is a
	// sibling so consumer layouts (flex-centered page containers)
	// place them side by side.
	return (
		<>
			<span
				role="img"
				aria-label={label ?? t("a11y.loading")}
				className={resolvedClassName}
				style={resolvedStyle}
			/>
			{label ? (
				<span className="ms-2 text-xs text-muted-foreground">{label}</span>
			) : null}
		</>
	);
}
