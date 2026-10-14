/**
 * Title-bar button primitives: the Windows/Linux caption button shell
 * (TitleBarButton), the shared toolbar button, and the Back/Forward
 * chevron button.
 *
 * Split out of `TitleBar.tsx` (pure move, no behavior change).
 */

import { HotkeyTooltip } from "@/components/hotkey/HotkeyTooltip";
import { IS_LINUX } from "@/components/hotkey/hotkey-utils";
import { Button } from "@/components/ui/button";
import { cn, focusRing } from "@/lib/utils";

interface TitleBarButtonProps {
	onClick: () => void;
	ariaLabel: string;
	variant?: "default" | "close";
	/** Linux-only shell style: GNOME/Yaru-style always-visible circle
	 *  (default) or KDE/Breeze-style flat square with a hover-only wash. */
	shape?: "circle" | "square";
	children: React.ReactNode;
}

export function TitleBarButton({
	onClick,
	ariaLabel,
	variant = "default",
	shape = "circle",
	children,
}: TitleBarButtonProps) {
	// Red close hover is a WINDOWS convention (the native Windows
	// close button turns solid red on hover). GNOME/KDE draw a
	// neutral hover for the close button, so on Linux the close
	// button must NOT go red, it uses the same neutral hover as
	// minimize/maximize. The caller passes the resolved variant
	// (`IS_WIN ? "close" : "default"`); this component just applies
	// the styling for whichever variant it receives.
	const isClose = variant === "close";
	//migrate from raw <button> to the shared <Button> component
	// so the design-system contract (focus ring, cva variant tokens,
	// active:translate-y-px) is applied uniformly. The cva default
	// (rounded-lg, outline-hidden, border-transparent) is overridden
	// via className to match the title-bar's edge-to-edge framing —
	// no rounded corners, no visible border, fixed 8x11.5 sizing.
	// NOTE: deliberately NOT `asChild`, the children are bare SVG icon
	// components, and `Slot.Root` would merge the click handler +
	// aria-label onto the <svg> itself, replacing the <button> element
	// entirely (breaking keyboard activation, screen-reader semantics,
	// and `getByRole("button")`). A real <button> wrapping the icon is
	// required.
	// The close button uses the `ghost` base + a native-Windows-red
	// HOVER (matching platform convention: neutral at rest, red on
	// hover/focus) rather than the `destructive` cva variant, whose
	// resting state paints a `bg-destructive/10` red tint over the
	// whole hit target.
	return (
		<Button
			type="button"
			variant="ghost"
			size="icon-sm"
			onClick={onClick}
			aria-label={ariaLabel}
			className={cn(
				"no-drag",
				"border-0",
				// Window-control glyphs are PURE WHITE in dark mode and
				// near-black in light mode, mirroring native title bars.
				// `text-foreground` alone is NOT enough: in dark
				// mode --foreground aliases --foreground, which the
				// theme presets (Nord/Dracula/Tokyo Night/...) tint
				// off-white (L 0.90-0.92), so the glyphs rendered gray
				// instead of white. `dark:text-white` pins the dark-mode
				// glyph to true #fff regardless of preset/custom theme.
				// NOTE: the unfocused-window DIM does NOT live here, it's
				// applied as container opacity on the whole bar (see
				// TitleBarInner), which dims every element uniformly and
				// cannot clash with theme colors.
				"text-foreground dark:text-white transition-colors duration-150",
				// Linux shell styles. GNOME/Ubuntu (Yaru): circular buttons
				// with an ALWAYS-VISIBLE subtle circle background, the
				// gray circle is the button's resting state, NOT a hover
				// effect (matches the native Ubuntu header bar). KDE
				// Plasma (Breeze): flat SQUARES with a transparent rest
				// and a hover-only wash. Both share the same
				// deepen-on-interaction ladder. No red close on Linux —
				// the `variant` call-site already passes "default" when
				// IS_WIN is false, so all three buttons use the neutral
				// treatment. `shape` comes from the resolved window-button
				// layout (KDE detection lives in the sidecar snapshot).
				IS_LINUX
					? cn(
							// Linux buttons are SMALLER than the bar (h-7/w-7 =
							// 28px in the 36px bar → space around them) and
							// spaced gap-2 apart (see the cluster wrapper).
							shape === "square"
								? cn("h-7 w-7 rounded-none", "bg-transparent")
								: cn("h-7 w-7 rounded-full", "bg-foreground/5"),
							"hover:bg-foreground/10 dark:hover:bg-foreground/10",
							"focus-visible:bg-foreground/10 dark:focus-visible:bg-foreground/10",
							"active:bg-foreground/15 dark:active:bg-foreground/15",
						)
					: cn(
							"h-9 w-11.5 rounded-none",
							isClose
								? cn(
										// Native Windows close-button hover: solid red
										// background + pure-white glyph, in EVERY theme
										// (the OS close button ignores the app palette).
										// #e81123 is the canonical Windows accent red;
										// pinned here deliberately instead of the
										// theme-tinted --destructive token (which is a
										// lighter orange-red and can be overridden by
										// custom themes). Neutral at rest; press
										// darkens to #c42b1c like the OS button.
										// The dark: twins are REQUIRED: the shared
										// Button `ghost` variant adds
										// `dark:hover:bg-muted/50`, whose rule
										// (`.dark .dark\:hover\:bg-muted\/50:hover`,
										// specificity 0-3-0) beats the plain
										// `hover:bg-[#e81123]` (0-2-0) in dark mode —
										// the close button hovered GRAY instead of red.
										// Adding the same `dark:` modifier lets twMerge
										// dedupe ghost's gray hover away entirely.
										"hover:bg-[#e81123] hover:text-white",
										"dark:hover:bg-[#e81123] dark:hover:text-white",
										"focus-visible:bg-[#e81123] focus-visible:text-white",
										"dark:focus-visible:bg-[#e81123] dark:focus-visible:text-white",
										"active:bg-[#c42b1c] active:text-white",
										"dark:active:bg-[#c42b1c] dark:active:text-white",
									)
								: "hover:bg-foreground/5 dark:hover:bg-foreground/5",
						),
			)}
		>
			{children}
		</Button>
	);
}

interface ToolbarButtonProps extends React.ComponentProps<"button"> {
	/** Click handler (optional, the parent may not wire the action). */
	onClick: (() => void) | undefined;
	/** Accessible name (localized). */
	ariaLabel: string;
	ariaKeyshortcuts?: string;
	disabled?: boolean;
	children: React.ReactNode;
}

export function ToolbarButton({
	onClick,
	ariaLabel,
	ariaKeyshortcuts,
	disabled,
	children,
	...triggerProps
}: ToolbarButtonProps) {
	return (
		<button
			type="button"
			onClick={onClick}
			disabled={disabled}
			aria-label={ariaLabel}
			aria-keyshortcuts={ariaKeyshortcuts}
			className={cn(
				// Toolbar buttons are h-6 (24px) inside the p-1 group wrapper —
				// the 4px padding keeps them off the full 36px bar height.
				"no-drag press-scale flex h-6 w-6 items-center justify-center rounded-lg",
				// Theme-aware hover (muted at rest, primary text + subtle wash on
				// hover, works for custom + dark themes, unlike a physical
				// black/white pairing).
				"text-muted-foreground transition-colors duration-150",
				"hover:bg-foreground/5 hover:text-foreground",
				disabled !== undefined &&
					"disabled:opacity-30 disabled:cursor-not-allowed",
				focusRing,
			)}
			{...triggerProps}
		>
			{children}
		</button>
	);
}

interface NavChevronButtonProps {
	tooltipLabel: string;
	/** Shortcut chips string from the SHORTCUTS catalog. */
	shortcutKeys: string;
	/** Accessible name (a11y.goBack / a11y.goForward). */
	ariaLabel: string;
	onClick: (() => void) | undefined;
	disabled: boolean;
	/** Chevron path, "back" points start-ward, "forward" end-ward. */
	path: string;
}

export function NavChevronButton({
	tooltipLabel,
	shortcutKeys,
	ariaLabel,
	onClick,
	disabled,
	path,
}: NavChevronButtonProps) {
	return (
		<HotkeyTooltip label={tooltipLabel} keys={shortcutKeys}>
			<ToolbarButton
				onClick={onClick}
				ariaLabel={ariaLabel}
				disabled={disabled}
			>
				<svg
					width="16"
					height="16"
					viewBox="0 0 16 16"
					fill="none"
					aria-hidden="true"
					// RTL: the chevron points "back"/"forward", mirrored under
					// dir=rtl by the shared index.css rule so it points the
					// semantically correct way for right-to-left locales (the bar
					// root is pinned dir="ltr", but the [dir="rtl"] ancestor
					// selector still matches through it).
					className="nav-directional-icon"
				>
					<path
						d={path}
						stroke="currentColor"
						strokeWidth="1.5"
						strokeLinecap="round"
						strokeLinejoin="round"
					/>
				</svg>
			</ToolbarButton>
		</HotkeyTooltip>
	);
}
