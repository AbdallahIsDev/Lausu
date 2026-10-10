# Squircle corners: research report + implementation plan

> **Status:** Research report, 2026-10-10. Researched against current browser/spec
> data (MDN, caniuse, chromestatus, Tailwind docs, June-2026 polyfill work) and
> the current renderer code. Nothing in this document is implemented yet — it is
> a decision document plus a mechanical implementation plan.
>
> **Question answered:** what is the best and simplest way to give this app
> squircle (superellipse) corners?

---

## 1. TL;DR — the recommendation

**Use native CSS `corner-shape: squircle`, feature-detected with `@supports`,
applied by ONE design-system rule to the single radius family, with circles and
pills explicitly kept circular.**

Why this is both the *best* and the *simplest*:

- It is **one CSS property** that reuses the `border-radius` the design system
  already has; the radius keeps controlling size, `corner-shape` only changes the
  curve drawn inside each corner.
- **No fallback is needed.** Browsers that do not know the property ignore it and
  render exactly today's circular corner — a pure progressive enhancement. There
  is no flash, no JS, no layout change, no dependency, and nothing to uninstall.
- Every decoration that must follow the corner follows it natively: background,
  borders, **outline (our focus rings)**, **box-shadow (our elevation)**, overflow
  clipping, and `backdrop-filter`. `clip-path` / SVG-mask hacks clip all of those
  away — that difference is the whole reason to prefer the native property.
- Cost: one token + ~12 lines of CSS in `index.css`, the mirrored block in
  `design-system.html` (required by `C-DESIGN-1`), and one CSS contract test.
  No TypeScript change, no Rust change, no new npm dependency.
- Reach today: **Windows** (Tauri WebView2 = Chromium ⇒ supported since 139, and
  WebView2 is evergreen/auto-updating). **macOS (WKWebView) and Linux (WebKitGTK)
  keep today's round corners** until WebKit implements the property — that is the
  only open decision (see §5 and §9).

If cross-platform identical geometry is a hard requirement *today*, the only
practical route is the Hyperellipse polyfill (Option B in §5) — it works, but it
costs a JS runtime, rewrites some CSS to a custom-property carrier, and has
documented limitations against our surfaces. Recommendation: **ship Option A now,
defer Option B**, and let the CSS upgrade automatically when WebKit ships.

---

## 2. Background: what `corner-shape` actually does

Facts from the spec/MDN (fetched 2026-10-10):

- `corner-shape` is a shorthand for `corner-top-left-shape`, `corner-top-right-shape`,
  `corner-bottom-left-shape`, `corner-bottom-right-shape`, accepting 1–4 values.
- **It has no effect without a non-zero `border-radius`** — the radius defines the
  corner box, the shape defines the curve inside it.
- Keyword values and their superellipse equivalents:
  | keyword | `superellipse(K)` | look |
  |---|---|---|
  | `square` | `superellipse(infinity)` | sharp corner |
  | `squircle` | `superellipse(2)` | the "iOS icon" continuous curve |
  | `round` (initial) | `superellipse(1)` | today's circular arc |
  | `bevel` | `superellipse(0)` | straight diagonal cut |
  | `scoop` | `superellipse(-1)` | concave corner |
  | `notch` | `superellipse(-infinity)` | inverted square |
- `superellipse(<number>)` lets you tune between them (e.g. `1.8` = softer than
  `squircle`, `2.4` = squarer).
- **Properties that follow the corner shape** on the container: `background-color`,
  `background-image`, `border`, `outline`, `box-shadow`, `overflow`,
  `backdrop-filter`.
- **Content and hit-testing do not change**: the content box stays rectangular and
  `:hover` still applies where text sticks out past the curve — so this is not a
  pointer-target or layout change.
- The property is **not inherited**, and it is animatable (superellipse interpolation).
- MDN currently labels it **"Limited availability / Experimental — not Baseline"**.

---

## 3. Support matrix (as of 2026-10-10)

`caniuse` (feature `wf-corner-shape`, fetched today): global usage **70.46 %**.

| Engine / browser | Support |
|---|---|
| Chrome / Edge | ✅ since **139** (up to 157 in the table) |
| Opera | ✅ 123+ |
| Samsung Internet | ✅ 30+ |
| **Firefox** | ❌ up to 160, still unsupported |
| **Safari / iOS Safari** | ❌ up to 27.1 / TP, still unsupported |

Mapping onto this app's three desktop targets:

| Platform | Webview | `corner-shape` today |
|---|---|---|
| Windows | WebView2 (Chromium, evergreen, auto-updating) | ✅ (runtime ≥ 139; current runtimes are far past that) |
| macOS | WKWebView (Safari/WebKit engine) | ❌ → falls back to today's round corners |
| Linux | WebKitGTK | ❌ → falls back to today's round corners |

Practical consequence: **Option A changes the Windows look only.** That must be an
explicit owner decision (§9), because it is a cross-platform visual difference.
No public WebKit ship date exists as of today (June-2026 sources say the same).

Anything that *requires* one geometry everywhere today needs a JS fallback (§5).

---

## 4. What this app looks like today (grounding)

Everything below is measured in the current renderer tree.

- **One radius scale step.** `index.css` defines the design system's single corner
  radius: `--radius: 0.625rem` (10 px) and `--radius-lg: var(--radius)`; the file
  says as much ("Single radius scale step: every non-circular control/panel
  uses…"). Themes (`themes/*.ts`) do not override it. Tailwind is v4.3.2.
- **Radius-carrying surfaces (class usage counts):**

  | utility | count |
  |---|---|
  | `rounded-lg` (10 px) | 191 |
  | `rounded-full` (circles/pills) | 88 |
  | `rounded-none` | 7 |
  | `rounded-t-lg`, `rounded-l-lg` | 6 + 2 |
  | `rounded-sm`, `rounded-md` | 5 + 2 |

  So ~200 surfaces carry the token radius; 88 are circles/pills that must stay
  circular.
- **Non-class radius users:** the scrollbar thumb (`border-radius: var(--radius-lg)`
  in `index.css`), component CSS files, and the mic button's glow `::after`
  (`border-radius: inherit` over a `rounded-full` parent). The window corner radius
  is owned by the Tauri shell, not by the DOM (comment in `index.css`), so it is out
  of scope here.
- **Circles/pills live mostly in the always-on-top bubble** (`bubble/*.tsx`:
  recording dot, visualizer bars, transcribing dots, overlay pill) plus avatars,
  badges, toggles and the mic button — all `rounded-full`. `superellipse(2)` on a
  pill flattens its end caps, so these must opt out (see §6).
- **Decoration surface (relevant to how corners clip):** no `shadow-inner` (inset
  shadows), no gradient utilities, no `bg-[url(...)]`, `backdrop-blur` in four
  component places (`ui/dialog.tsx`, `ui/alert-dialog.tsx`, the chart tooltip
  box, `CollectionListHeader`), and six
  `border-dashed` "mock/inactive" frames. That means the native property's
  "everything follows the shape" behaviour has very little to break here.
- **Design system must stay in sync:** `design-system.html` is the standalone
  showcase and is required by `C-DESIGN-1` to mirror every design-system change in
  the same commit. It already mirrors the tokens (`--radius:0.625rem`) and has a
  dedicated "Radius & borders" section (`renderRadius()`, `.radius-grid`,
  `.radius-box`, `.border-swatch`).
- **Precedent for the regression test:** `__tests__/index-css-sidebar-rail-token.test.ts`
  (plus `index-css-chart-tokens-follow-theme`, `index-css-glow-pulse`,
  `index-css-dark-contrast-tokens`) — CSS-level contracts are already pinned with
  source-reading tests in this repo, so a corner-shape pin fits the existing style.

---

## 5. Options considered

| | A. Native `corner-shape` (recommended) | B. Native + Hyperellipse polyfill | C. Hand-rolled clip-path / SVG mask | D. Do nothing |
|---|---|---|---|---|
| Geometry on Windows | real squircle | real squircle | approximate (must match spec by hand) | round |
| Geometry on macOS/Linux | round (graceful) | real squircle | approximate | round |
| Cost | ~12 CSS lines + 1 test | ~12 CSS lines + npm dependency + bootstrap call + CSS carrier property | large: per-element measurement, path maths, resize/RTL handling | 0 |
| Runtime cost | **0** (paint-time only, no JS) | Windows: ~0 (native CSS bridge, no observers). WebKit: one shared `ResizeObserver` + `MutationObserver` + `IntersectionObserver`, batched rAF read/write phases, keyed caching | same class as B but unmaintained by us | 0 |
| Risk to shadows / focus rings / borders | **none** — they follow the shape | fallback engine paints borders/shadows/outline as SVG layers; documented gaps | high: `clip-path` clips `box-shadow`/`outline`; border/rounded-border combos need SVG rings | none |
| A11y | unchanged (content box + hit-testing unchanged) | unchanged per its docs (`:hover`/`:focus` handled) | risk: hit-testing follows the clip in most engines | none |
| Future | WebKit ships → same CSS applies automatically | polyfill becomes a no-op in supporting engines | throw-away work | — |
| Verdict | **do this** | optional Phase 2 if parity is required | reject (reinvents a maintained library — `W2`) | legitimate baseline |

### Option B details (so the decision is fully informed)

`hyperellipse` (npm, **v1.0.5**, published ~June 2026; the June-2026 write-up is
"native-first: Chromium uses native rendering, Safari/Firefox use the fallback".
Maturity signal: npm lists **no other packages depending on it** — it is four
months old at the time of writing, so treat it as young infrastructure):

- Authoring model: put the value on a **custom property carrier** next to the
  radius (`--corner-shape: squircle`) and call `registerHyperellipse()` once on the
  client. In supporting engines it installs a zero-specificity bridge
  (`corner-shape: var(--corner-shape, round)`) and **runs no observers**, so
  Windows pays nothing.
- In non-supporting engines it renders via `clip-path: path(...)` on the element,
  an SVG ring as a background layer for borders, a pre-rendered blurred SVG on
  `::before` for shadows, and an `::after` SVG ring for outlines. It scans the
  stylesheets for selectors that declare `--corner-shape`.
- Documented limitations that map onto our surfaces: **inset shadows are dropped**
  (we have none), **dashed/dotted borders render as a uniform solid ring** (we have
  six `border-dashed` frames), in "layer mode" a background *image* is not shaped
  (we have none), child content is not clipped to the shape when layer mode is on,
  the element's own `::before`/`::after` must be free (several of our components
  use both), and radius/shadow/outline transitions update on state change rather
  than frame-by-frame.
- It also documents the perceptual-equivalence trick (`--corner-scale: 0.6` inside
  `@supports not (corner-shape: squircle)`) to avoid the "too round before JS
  loads" flash — in a packaged desktop app the pre-JS window is one frame, so this
  matters much less than on the web.

If we ever adopt it, keep our token name `--corner-shape` — that is exactly the
polyfill's carrier, making it a drop-in without touching component CSS.

---

## 6. Recommended implementation (exact, mechanical)

### 6.1 Token (one place to flip it off)

In `voice_typer/client/src/renderer/src/index.css`, beside the existing radius
tokens (`--radius` / `--radius-lg`):

```css
/* Corner curve for the --radius family. Chromium 139+ renders a real
   superellipse; other engines ignore the property and keep today's circular
   arcs, so this is pure progressive enhancement. Set to `round` to disable
   app-wide. */
--corner-shape: squircle;
```

### 6.2 The rule (base layer, feature-detected)

```css
/* Design system: superellipse corners on every surface that uses the shared
   radius token. Circles and pills opt out — superellipse(2) flattens the caps
   of a `rounded-full` element. The exception rule MUST stay after the family
   rule (equal `:where()` specificity, later rule wins). */
@supports (corner-shape: squircle) {
	:where(.rounded-lg, .rounded-t-lg, .rounded-l-lg, .rounded-md, .rounded-sm) {
		corner-shape: var(--corner-shape, squircle);
	}

	/* Circles, pills, avatars, dots: keep circular end caps. */
	:where(.rounded-full) {
		corner-shape: round;
	}
}
```

Notes:

- `:where()` keeps specificity at 0, so any future utility/override still wins —
  no specificity war with the utilities layer (`@utility` output) or component CSS.
- `rounded-none` needs no entry: with radius 0 the property is inert.
- Do **not** use `*` / pseudo-elements. The scrollbar thumb and the mic-button glow
  (`border-radius: inherit` on `::after`) are visual outliers that should get a
  separate, reviewed decision if they are ever included.
- Optional one-off escape hatch, if a single surface should opt in while the global
  token is off:

  ```css
  @utility squircle {
  	corner-shape: squircle;
  }
  ```

  (Tailwind v4's documented custom-utility syntax; it lands in the utilities layer.)
- A third-party plugin (`@toolwind/corner-shape`, Nov 2025) exists for
  `corner-squircle`-style classes. Skip it: two declarations already do the job, and
  a dependency for that is not justified.

### 6.3 Showcase sync (required by `C-DESIGN-1`)

In `design-system.html`:

1. add `--corner-shape:squircle` to the token block (next to `--radius`), so the
   showcase and the app stay one design system;
2. add the same `@supports` block for `.radius-box`, `.radius-item`,
   `.border-swatch`, `.btn*`, `.input`, `.select`, `.card`-like specimens;
3. extend the "Radius & borders" section copy with one line: corners use the
   superellipse curve on engines that support `corner-shape`, circular corners
   elsewhere — plus a side-by-side swatch (round vs squircle) so the difference is
   reviewable in one screenshot.

### 6.4 Regression test (source-level, mirroring the existing CSS contract tests)

New renderer test (e.g. `__tests__/index-css-corner-shape.test.ts`) asserting:

1. the `--corner-shape` token exists in `index.css`;
2. a `@supports (corner-shape: squircle)` gate wraps every `corner-shape`
   declaration (no ungated uses);
3. the radius-family rule consumes `var(--corner-shape`;
4. `.rounded-full` is explicitly reset to `round`;
5. the exception rule is **ordered after** the family rule (the specificity/order
   contract above);
6. `design-system.html` mirrors the token (guards `C-DESIGN-1`).

This is one of the few *structural* pins `C-TEST-7` allows: it enforces a documented
design decision, and it is the only automated way to catch a silent drift in a
declaration that jsdom cannot render.

### 6.5 Explicitly out of scope / do not touch

- `--radius` and any border-weight tokens (`C-DESIGN-2` / `C-DESIGN-3` unchanged).
- The `rounded-full` geometry of bubble dots, mic button, avatars, toggles.
- The window corner radius (owned by the Tauri shell, not the DOM).
- No `corner-shape` on `*`, `::before`, `::after`.

---

## 7. Rollout & verification plan

1. **Automated:** `npm run typecheck:ci` (no TS touched → sanity only), targeted
   `npx vitest run` for the new CSS contract test + the existing CSS-token tests,
   `npm run lint`.
2. **Windows visual proof (required before keeping it):**
   - `cd voice_typer/client && npm run tauri:dev`;
   - in the webview console: `CSS.supports("corner-shape", "squircle")` → expect
     `true`;
   - capture ready-to-compare screenshots (same window size, same theme, same
     scroll position) of Home, Models (cards + accordions), Settings, a Dialog and
     the sidebar with `--corner-shape: round` and with `squircle`;
   - walk the checklist: focus rings still fully visible (`C-FOCUS-*`), elevation
     shadows still paint, `overflow-hidden` lists/images still clip to the corner,
     dialogs' `backdrop-blur` still looks right, the 88 pills are unchanged.
3. **Fallback proof (macOS/Linux):** open `design-system.html` in Safari/Firefox
   (i.e. a non-supporting engine) and confirm the page is exactly today's round
   rendering — that is the no-op guarantee for WKWebView/WebKitGTK.
4. **Tuning:** at the current radius (10 px) the squircle is a subtle, "designed"
   curve; if the owner wants it stronger/softer, change only the token to
   `superellipse(1.8)` … `superellipse(2.4)` and re-screenshot. No component edits.
5. **Rollback:** set `--corner-shape: round` (or delete the `@supports` block).
   One line, no migration.

---

## 8. Design notes / tuning guidance

- The visual difference grows with `radius ÷ shorter side`: at 10 px on a 32–40 px
  control (≈25–30 %) it reads clearly; at 4–6 px (`rounded-sm`) it is
  near-invisible, so no special-casing is needed.
- Icon buttons and skeleton blocks are the tightest cases (e.g. a 32 px square with
  a 10 px radius). Review those screenshots specifically — a squircle there reads
  "squarer" than a circle, which is the intended look but is worth one explicit
  owner sign-off.
- Because `outline` follows the corner shape, the focus ring automatically adopts
  the squircle too — no change needed for `C-FOCUS-*`, and no double-ring artefact.
- Don't mix shapes within one family: all `--radius` surfaces should use the same
  token value, so cards, controls, dialogs and chips stay geometrically coherent.

---

## 9. Risks and open questions (owner decisions)

1. **Cross-platform drift (the main one).** After Option A, Windows corners are
   squircles and macOS/Linux are circles until WebKit ships `corner-shape`.
   Options: accept it (recommended — it is graceful, invisible in every non-Windows
   build, and upgrades itself later), or adopt the polyfill (Option B) for exact
   parity, or skip the feature entirely (Option D). **Needs an owner call.**
2. **Perceptual, not functional:** nothing about layout, hit targets, a11y or
   performance changes; the risk is purely "does the owner like the look at 10 px".
3. **Outliers:** tiny icon-sized elements and dashed "mock" frames are the two
   places to eyeball; dashed frames are only an issue for Option B (its fallback
   renders dashed borders as a solid ring), not for Option A.
4. **If the polyfill is ever added:** it must be verified in a non-supporting
   engine (Safari on macOS) with the same checklist, and the app's `::before`/
   `::after`-heavy components (glow pulse, skeletons, chart tooltips) checked for
   the "pseudo-elements must be free" limitation.

---

## 10. Sources (all fetched 2026-10-10)

- MDN — `corner-shape` property and `<corner-shape-value>`:
  <https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/corner-shape>
  (limited availability; keyword↔`superellipse()` equivalence; properties that
  follow the shape; content/hover behaviour) ·
  <https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/corner-shape-value>
- caniuse — `corner-shape` support table, global usage 70.46 %:
  <https://caniuse.com/wf-corner-shape>
- Microsoft — "Distribute your app and the WebView2 Runtime" (the Evergreen
  Runtime "updates automatically without requiring any action from you", same
  update cadence as Edge Stable; basis for the Windows row in §3):
  <https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution>
- Chrome Platform Status — "Corner shaping (corner-shape, superellipse, squircle)":
  <https://chromestatus.com/feature/5357329815699456>
- Squircle.js — "corner-shape, superellipse() and Browser Support (2026)",
  June 2026: <https://squircle.js.org/blog/squircles-in-css>
- Smashing Magazine — "Beyond border-radius: What the CSS corner-shape property
  changes for UI", March 2026 (baseline should look intentional; support status):
  <https://www.smashingmagazine.com/2026/03/beyond-border-radius-css-corner-shape-property-ui/>
- CSS-Tricks — "What can we actually do with corner-shape?", September 2025:
  <https://css-tricks.com/what-can-we-actually-do-with-corner-shape/>
- Hyperellipse polyfill — announcement (June 2026):
  <https://dev.to/mikhailmogilnikov/how-i-brought-css-corner-shape-to-safari-and-firefox-cka> ·
  package + full limitation list: <https://www.npmjs.com/package/hyperellipse>
- Tailwind CSS — "Adding custom styles" (`@utility`, `@layer components`,
  arbitrary properties): <https://tailwindcss.com/docs/adding-custom-styles>
- `@toolwind/corner-shape` Tailwind plugin (November 2025, not used):
  <https://www.npmjs.com/package/@toolwind/corner-shape>
