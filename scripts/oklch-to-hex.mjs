// oklch-to-hex.mjs — converts the renderer's CSS color tokens
// (voice_typer/client/src/renderer/src/index.css) from oklch() to sRGB
// hex, and reports WCAG contrast ratios for the token pairs the UI
// actually renders.
//
// Usage: node scripts/oklch-to-hex.mjs

const M1 = [
	[1, 0.3963377774, 0.2158037573],
	[1, -0.1055613458, -0.0638541728],
	[1, -0.0894841775, -1.291485548],
];
const M2 = [
	[4.0767416621, -3.3077115913, 0.2309699292],
	[-1.2684380046, 2.6097574011, -0.3413193965],
	[-0.0041960863, -0.7034186147, 1.707614701],
];
const mul = (m, v) => m.map((r) => r[0] * v[0] + r[1] * v[1] + r[2] * v[2]);

function oklchToLinearRgb(L, C, H) {
	const h = (H * Math.PI) / 180;
	const lab = [L, C * Math.cos(h), C * Math.sin(h)];
	const lms = mul(M1, lab).map((x) => x ** 3);
	return mul(M2, lms);
}

const encode = (x) => {
	const c = Math.min(1, Math.max(0, x));
	return c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055;
};

function oklchToHex(L, C, H) {
	const rgb = oklchToLinearRgb(L, C, H).map((x) =>
		Math.round(encode(x) * 255),
	);
	return "#" + rgb.map((n) => n.toString(16).padStart(2, "0")).join("");
}

function hexToRgb(hex) {
	const n = parseInt(hex.slice(1), 16);
	return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
const lum = (hex) => {
	const [r, g, b] = hexToRgb(hex).map((v) => {
		const s = v / 255;
		return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
	});
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a, b) => {
	const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
	return (x + 0.05) / (y + 0.05);
};

// ── Reverse direction: hex → oklch (for applying a spec'd colour) ─────
// oklab → LMS' forward matrix is M1; invert it numerically instead of
// hard-coding a second constant set (less chance of a typo).
function invert3(m) {
	const [[a, b, c], [d, e, f], [g, h, i]] = m;
	const det =
		a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
	return [
		[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
		[(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
		[(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det],
	];
}
const M1_INV = invert3(M1);
const M2_INV = invert3(M2);

function hexToOklch(hex) {
	const lin = hexToRgb(hex).map((v) => {
		const s = v / 255;
		return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
	});
	const lms = mul(M2_INV, lin).map((x) => Math.cbrt(x));
	const [L, a, b] = mul(M1_INV, lms);
	const C = Math.sqrt(a * a + b * b);
	let H = (Math.atan2(b, a) * 180) / Math.PI;
	if (H < 0) H += 360;
	const r3 = (n) => Number(n.toFixed(3));
	return { L: Number(L.toFixed(4)), C: r3(C), H: r3(H), css: null };
}

// CLI: `node scripts/oklch-to-hex.mjs '#1447e6'` → oklch(...)
const cliArg = process.argv[2];
if (cliArg && cliArg.startsWith("#")) {
	const { L, C, H, css } = hexToOklch(cliArg);
	void css;
	console.log(`${cliArg}  →  oklch(${L} ${C} ${H})`);
	console.log(`round-trip check: ${oklchToHex(L, C, H)}`);
	process.exit(0);
}

// ── Raw scales, verbatim from index.css ──────────────────────────────
const GRAY = {
	50: [1, 0, 0],
	100: [0.967, 0.001, 286.375],
	200: [0.93, 0, 0],
	300: [0.85, 0, 0],
	400: [0.705, 0.015, 286.067],
	500: [0.48, 0.016, 285.938],
	600: [0.274, 0.006, 286.033],
	700: [0.22, 0, 0],
	800: [0.187, 0, 271.152],
	900: [0.168, 0, 0],
	950: [0.141, 0.005, 285.823],
};
const ACCENT = {
	50: [0.97, 0.014, 254.604],
	100: [0.94, 0.05, 264],
	200: [0.87, 0.11, 264],
	300: [0.76, 0.16, 264],
	400: [0.63, 0.21, 264],
	500: [0.488, 0.243, 264.376],
	600: [0.424, 0.199, 265.638],
	700: [0.36, 0.17, 266],
	800: [0.3, 0.14, 266],
	900: [0.25, 0.11, 266],
	950: [0.2, 0.09, 266],
};

const gray = Object.fromEntries(
	Object.entries(GRAY).map(([k, v]) => [k, oklchToHex(...v)]),
);
const accent = Object.fromEntries(
	Object.entries(ACCENT).map(([k, v]) => [k, oklchToHex(...v)]),
);

// ── Semantic tokens ──────────────────────────────────────────────────
// [css value, resolved [L,C,H]] — `ref:gray-500` means var(--gray-500).
const SEM = {
	background: { light: "gray-50", dark: "gray-800" },
	surface: { light: "gray-50", dark: "gray-700" },
	/* Light cards are `transparent` (the canvas shows through), so they
	   composite as gray-50. Dark cards are the FLATTENED #FFFFFF/5 over
	   the gray-800 canvas = #1f1f1f — not gray-900. */
	"surface-subtle": { light: "gray-50", dark: [0.2393, 0, 0] },
	"surface-hover": { light: "gray-200", dark: "gray-700" },
	muted: { light: "gray-100", dark: "gray-600" },
	foreground: { light: "gray-950", dark: "gray-50" },
	"text-secondary": { light: "gray-500", dark: "gray-300" },
	"muted-foreground": { light: "gray-500", dark: "gray-400" },
	primary: { light: "accent-500", dark: "accent-600" },
	"primary-foreground": { light: "accent-50", dark: "accent-50" },
	accent: { light: "accent-500", dark: "accent-600" },
	"accent-foreground": { light: "accent-50", dark: "accent-50" },
	destructive: { light: [0.55, 0.25, 27], dark: [0.55, 0.25, 27] },
	"destructive-foreground": { light: [0.97, 0, 0], dark: [0.97, 0, 0] },
	success: { light: [0.62, 0.17, 149], dark: [0.7, 0.16, 149] },
	warning: { light: [0.7, 0.16, 70], dark: [0.78, 0.15, 70] },
	info: { light: [0.62, 0.14, 240], dark: [0.7, 0.13, 240] },
	border: { light: [0, 0, 0], dark: [1, 0, 0] },
	input: { light: [0.85, 0, 0], dark: [0.25, 0, 0] },
	ring: { light: "accent-500", dark: [0.552, 0.016, 285.938] },
	"chart-1": { light: [0.809, 0.105, 251.813], dark: [0.809, 0.105, 251.813] },
	"chart-2": { light: [0.623, 0.214, 259.815], dark: [0.623, 0.214, 259.815] },
	"chart-3": { light: [0.546, 0.245, 262.881], dark: [0.546, 0.245, 262.881] },
	"chart-4": { light: "accent-500", dark: "accent-500" },
	"chart-5": { light: "accent-600", dark: "accent-600" },
};

const resolve = (v) => {
	if (Array.isArray(v)) return oklchToHex(...v);
	const [scale, step] = v.split("-");
	return (scale === "gray" ? gray : accent)[step];
};

const out = [];
out.push("── gray ──");
for (const [k, v] of Object.entries(gray)) out.push(`gray-${k}\t${v}`);
out.push("── accent ──");
for (const [k, v] of Object.entries(accent)) out.push(`accent-${k}\t${v}`);
out.push("── semantic (light | dark) ──");
const semHex = {};
for (const [k, v] of Object.entries(SEM)) {
	const l = resolve(v.light);
	const d = resolve(v.dark);
	semHex[k] = { light: l, dark: d };
	out.push(`${k}\t${l}\t${d}`);
}
out.push("── alpha tokens ──");
out.push(`accent-soft\t${oklchToHex(0.424, 0.199, 265.638)} @10% L / @15% D`);
out.push(`accent-muted\t${oklchToHex(0.546, 0.245, 262.881)} @40% L / @60% D`);
out.push("── scrollbar ──");
for (const [k, v] of Object.entries({
	"thumb (light)": [0.85, 0, 0],
	"thumb-hover (light)": [0.75, 0, 0],
	"thumb (dark)": [0.35, 0, 0],
	"thumb-hover (dark)": [0.45, 0, 0],
}))
	out.push(`${k}\t${oklchToHex(...v)}`);

out.push("── composited borders (border-border/α painted over a surface) ──");
const blend = (fgHex, bgHex, a) => {
	const f = hexToRgb(fgHex);
	const b = hexToRgb(bgHex);
	const mix = f.map((v, i) => Math.round(v * a + b[i] * (1 - a)));
	return "#" + mix.map((n) => n.toString(16).padStart(2, "0")).join("");
};
for (const scheme of ["light", "dark"]) {
	for (const a of [0.05, 0.08, 0.1, 0.2]) {
		for (const surf of ["surface", "surface-subtle"]) {
			out.push(
				`${scheme} ${surf} @${a * 100}%\t${blend(semHex.border[scheme], semHex[surf][scheme], a)}`,
			);
		}
	}
}

out.push("── contrast (WCAG 2.1) ──");
const pairs = [
	["foreground", "background"],
	["foreground", "surface"],
	["muted-foreground", "background"],
	["muted-foreground", "surface-subtle"],
	["text-secondary", "surface"],
	["primary", "background"],
	["primary", "surface"],
	["primary-foreground", "primary"],
	["destructive", "surface"],
	["success", "surface"],
	["warning", "surface"],
	["info", "surface"],
];
for (const [fg, bg] of pairs) {
	const r = (scheme) =>
		contrast(semHex[fg][scheme], semHex[bg][scheme]).toFixed(2);
	out.push(`${fg} on ${bg}\tlight ${r("light")}\tdark ${r("dark")}`);
}

console.log(out.join("\n"));
