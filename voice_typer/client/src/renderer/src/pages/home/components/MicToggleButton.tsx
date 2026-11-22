import {
	AlertCircleIcon,
	Mic02Icon,
	StopIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { memo } from "react";
import { cn } from "@/lib/utils";

export interface MicToggleButtonProps {
	isRecording: boolean;
	disabled: boolean;
	onClick: () => void;
	label: string;
	disabledReason?: string;
	error?: boolean;
}

export function MicToggleButton({
	isRecording,
	disabled,
	onClick,
	label,
	disabledReason,
	error = false,
}: MicToggleButtonProps) {
	// When disabled with a reason, surface the reason as the accessible
	// name + tooltip so users understand why the mic can't be toggled
	// right now (the inline `<p>` in Home.tsx mirrors the same text
	// visually, but the button itself must remain self-describing for
	// screen-reader users who focus it directly).
	const effectiveLabel = disabled && disabledReason ? disabledReason : label;

	// LO-22: use `aria-disabled` + a click guard instead of the native
	// `disabled` attribute so the button stays hoverable/focusable, the
	// `title` tooltip (carrying `disabledReason`) must remain readable on
	// a disabled mic, which a native `disabled` attribute suppresses.
	// Screen readers still announce the disabled state via aria-disabled.
	const handleClick = () => {
		if (disabled) return;
		onClick();
	};

	// ── State → colour contract (C-UI-12) ──────────────────────────────
	// Red means "capturing audio right now" and nothing else, which is
	// what the bubble's recording dot already does (C-UI-12). The idle
	// button therefore carries the brand accent -- the app's CTA colour
	// -- and red is reserved for recording, so the two surfaces agree.
	// Error stays a hollow destructive ring: solid-vs-hollow plus the
	// distinct glyph separates it from the solid recording fill.
	const showError = error && !isRecording;

	// The button IS the whole control: no sibling halo, no extra box. The
	// expanding wave that used to sit behind it during a recording is gone by
	// product decision (2026-11-17); the state change is the fill and its
	// glow turning red, nothing else moves.
	return (
		<button
			type="button"
			onClick={handleClick}
			aria-disabled={disabled || undefined}
			aria-label={effectiveLabel}
			aria-pressed={isRecording}
			title={effectiveLabel}
			aria-live={showError ? "polite" : undefined}
			data-testid="mic-toggle-button"
			className={cn(
				"press-scale relative z-10 flex h-21 w-21 items-center justify-center rounded-full",
				"transition-all duration-200 ease-out",
				"focus:outline-none focus-visible:ring-1 focus-visible:ring-ring",
				"hover:scale-105",
				isRecording
					? // Recording: SOLID destructive fill AND the glow in the
						// same red (C-UI-12). The glow keeps its idle rhythm,
						// only its colour changes with the fill.
						"bg-destructive hover:bg-destructive/90 animate-glow-pulse-destructive"
					: showError
						? // Error state: hollow destructive, a distinct
							// "last attempt failed" treatment next to the
							// solid glow of the healthy idle button.
							"bg-destructive/15 ring-1 ring-inset ring-destructive hover:bg-destructive/25"
						: // Idle: the brand accent (the app's CTA colour)
							// with the glow, so red never sits on a
							// non-recording state (C-UI-12).
							"bg-primary animate-glow-pulse hover:bg-primary/90",
			)}
		>
			<HugeiconsIcon
				icon={isRecording ? StopIcon : showError ? AlertCircleIcon : Mic02Icon}
				strokeWidth={1.625}
				// The glyph sits on a SOLID fill in both the idle
				// (bg-primary) and recording (bg-destructive) states, so
				// it uses each fill's paired near-white foreground token
				// (--primary-foreground / --destructive-foreground, both
				// defined in :root AND .dark, backfilled by every theme
				// preset + the custom-theme generator). `text-foreground`
				// turned black in light mode; raw `text-white` ignored
				// custom palettes entirely. The error-state alert glyph
				// sits on the HOLLOW surface, so it uses the destructive
				// TOKEN itself (tracks every theme's destructive red).
				className={cn(
					"h-8 w-8 transition-opacity",
					isRecording
						? "text-(--destructive-foreground)"
						: showError
							? "text-destructive"
							: "text-(--primary-foreground)",
				)}
			/>
		</button>
	);
}

export default memo(MicToggleButton);
