/**
 * Native Windows caption-button glyph artwork: the filled SVG paths for
 * minimize / maximize / restore / close and their icon components.
 *
 * Split out of `TitleBar.tsx` (pure move, no behavior change).
 * Regenerate the path data with `python scripts/gen_caption_glyph_paths.py`.
 */

// Window-control glyphs, native Windows caption icon geometry.
// CLOSE and RESTORE are the TRUE outlines of the glyphs Windows uses
// font that ships with Windows 11 (C:\Windows\Fonts\SegoeIcons.ttf,
// units-per-em 2048): ChromeClose U+E8BB, ChromeRestore U+E923,
// scaled to a 10px em (the size DWM renders them at inside a 46x36
// caption button) and centered in a 10x10 viewBox. Regenerate with
// `python scripts/gen_caption_glyph_paths.py` if ever needed.
// MINIMIZE and MAXIMIZE are deliberate sharp-cornered, integer-pixel
// variants (see the comments on each constant): the native glyphs'
// half-pixel edges / rounded corners read soft at DPR 1.

// WHY FILLED OUTLINES INSTEAD OF STROKED SHAPES: hand-rolled stroked
// SVGs can never match the native icons, a 0.5px stroke is sub-pixel
// at DPR 1 and antialiases to ~50% alpha (the "gray / toned-down"
// look), diagonal strokes land on half-pixel boundaries, and the X
// geometry (span/weight/caps) drifts from Microsoft's design. These
// paths are the font's own filled contours: solid currentColor mass,
// no stroke, no opacity, every covered pixel is pure #fff in dark
// mode, exactly like the OS rendering. The icons are purely
// decorative (the wrapping button carries the aria-label), so
// ``aria-hidden`` with NO child <title> (a <title> inside an
// aria-hidden SVG is dropped by screen readers AND duplicates the
// button's label).
// Platform note: the GLYPHS are identical on Windows and Linux (the
// shapes below match GNOME's caption icons closely enough that no
// branch is needed); what differs is the BUTTON, not the icon
// (Windows square 46×36 hit targets vs Linux circular buttons, see
// TitleBarButton).
const MINIMIZE_GLYPH_PATH =
	// Sharp-cornered bar snapped to WHOLE pixels (y 5→6). The native
	// ChromeMinimize outline spans y 4.50-5.50 with rounded caps, its
	// edges sit ON half-pixel boundaries, so at DPR 1 both edges
	// antialias to ~50% alpha = the same soft/gray bar as the old
	// hand-drawn rect. Snapping to an integer pixel row renders one
	// fully-lit row: solid color, razor-sharp.
	"M0.00 5.00H10.00V6.00H0.00Z";
const MAXIMIZE_GLYPH_PATH =
	// Sharp square outline (1px frame): outer contour clockwise, inner
	// contour counter-clockwise → nonzero fill-rule punches the hole.
	// Deliberately NOT the native ChromeMaximize outline, whose outer
	// corners are rounded (~1.5px radius), product decision: crisp
	// right angles, all edges on integer pixels.
	"M0.00 0.00H10.00V10.00H0.00ZM1.00 1.00V9.00H9.00V1.00Z";

const RESTORE_GLYPH_PATH =
	"M9.00 2.96Q9.00 2.56 8.84 2.20Q8.68 1.84 8.40 1.57Q8.12 1.31 7.76 1.15Q7.40 1.00 7.00 1.00H2.08Q2.16 0.78 2.30 0.59Q2.45 0.41 2.63 0.27Q2.82 0.14 3.04 0.07Q3.26 0.00 3.50 0.00H7.00Q7.62 0.00 8.16 0.24Q8.71 0.47 9.12 0.88Q9.53 1.28 9.76 1.83Q10.00 2.38 10.00 3.00V6.50Q10.00 6.74 9.93 6.96Q9.86 7.18 9.73 7.37Q9.59 7.55 9.41 7.70Q9.22 7.84 9.00 7.92ZM1.47 10.00Q1.18 10.00 0.91 9.88Q0.64 9.76 0.44 9.56Q0.24 9.36 0.12 9.09Q0.00 8.82 0.00 8.53V3.48Q0.00 3.18 0.12 2.91Q0.24 2.65 0.44 2.44Q0.64 2.24 0.91 2.12Q1.18 2.00 1.47 2.00H6.52Q6.82 2.00 7.09 2.12Q7.36 2.24 7.56 2.44Q7.76 2.64 7.88 2.91Q8.00 3.18 8.00 3.48V8.53Q8.00 8.82 7.88 9.09Q7.76 9.36 7.56 9.56Q7.35 9.76 7.09 9.88Q6.82 10.00 6.52 10.00ZM6.50 9.00Q6.60 9.00 6.69 8.96Q6.78 8.92 6.85 8.85Q6.92 8.78 6.96 8.69Q7.00 8.60 7.00 8.50V3.50Q7.00 3.40 6.96 3.31Q6.92 3.21 6.86 3.14Q6.79 3.08 6.69 3.04Q6.60 3.00 6.50 3.00H1.50Q1.40 3.00 1.31 3.04Q1.22 3.08 1.15 3.15Q1.08 3.22 1.04 3.31Q1.00 3.40 1.00 3.50V8.50Q1.00 8.60 1.04 8.69Q1.08 8.78 1.15 8.85Q1.22 8.92 1.31 8.96Q1.40 9.00 1.50 9.00Z";
const CLOSE_GLYPH_PATH =
	"M5.00 5.71 0.85 9.85Q0.71 10.00 0.50 10.00Q0.29 10.00 0.14 9.86Q0.00 9.71 0.00 9.50Q0.00 9.29 0.15 9.15L4.29 5.00L0.15 0.85Q0.00 0.71 0.00 0.50Q0.00 0.40 0.04 0.30Q0.08 0.21 0.15 0.14Q0.21 0.08 0.31 0.04Q0.40 0.00 0.50 0.00Q0.71 0.00 0.85 0.15L5.00 4.29L9.15 0.15Q9.29 0.00 9.50 0.00Q9.60 0.00 9.69 0.04Q9.79 0.08 9.85 0.15Q9.92 0.21 9.96 0.31Q10.00 0.40 10.00 0.50Q10.00 0.71 9.85 0.85L5.71 5.00L9.85 9.15Q10.00 9.29 10.00 9.50Q10.00 9.60 9.96 9.69Q9.92 9.79 9.86 9.85Q9.79 9.92 9.70 9.96Q9.60 10.00 9.50 10.00Q9.29 10.00 9.15 9.85Z";

/** Shared SVG shell for all window-control glyphs: 10px em box, filled
 *  path only (no stroke), full-opacity currentColor. */
function CaptionGlyph({ d }: { d: string }) {
	return (
		<svg
			width="10"
			height="10"
			viewBox="0 0 10 10"
			aria-hidden="true"
			className="size-2.5 fill-current"
		>
			<path d={d} />
		</svg>
	);
}

export function MinimizeIcon() {
	return <CaptionGlyph d={MINIMIZE_GLYPH_PATH} />;
}

export function MaximizeIcon() {
	return <CaptionGlyph d={MAXIMIZE_GLYPH_PATH} />;
}

export function RestoreIcon() {
	return <CaptionGlyph d={RESTORE_GLYPH_PATH} />;
}

export function CloseIcon() {
	return <CaptionGlyph d={CLOSE_GLYPH_PATH} />;
}
