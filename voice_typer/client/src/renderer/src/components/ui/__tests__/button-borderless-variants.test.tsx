import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Button, buttonVariants } from "@/components/ui/button";

afterEach(() => {
	cleanup();
});

/**
 * Solid-fill / borderless-intent variants must neutralize the Button
 * base's border in BOTH colour schemes.
 *
 * The base contributes `border-border/8 dark:border-border/10`. A bare
 * `border-transparent` loses to the base's `dark:` rule (both compile
 * to equal-specificity rules; the dark `border-transparent` utility
 * must be present or the CTA renders as an outlined box in dark
 * themes), so every borderless variant carries the shared pair.
 */
const BORDERLESS_VARIANTS = ["default", "ghost", "link"] as const;

describe("borderless button variants neutralize the base border", () => {
	it.each(BORDERLESS_VARIANTS)(
		"variant %s opts out of the border in light AND dark",
		(variant) => {
			const cls = buttonVariants({ variant });
			expect(cls).toMatch(/(^|\s)border-transparent(\s|$)/);
			expect(cls).toMatch(/(^|\s)dark:border-transparent(\s|$)/);
		},
	);

	it("still inherits the base border token the neutralizer overrides", () => {
		// Guards the premise of the contract above: the base DOES paint a
		// border, so a variant that drops `dark:border-transparent`
		// silently regresses every dark theme.
		const cls = buttonVariants({ variant: "default" });
		expect(cls).toMatch(/(^|\s)border-border\/8(\s|$)/);
		expect(cls).toMatch(/(^|\s)dark:border-border\/10(\s|$)/);
	});

	it("the blue primary variant stays a blue fill (borderless, not restyled)", () => {
		const cls = buttonVariants({ variant: "default" });
		expect(cls).toMatch(/(^|\s)bg-primary(\s|$)/);
		expect(cls).toMatch(/(^|\s)text-primary-foreground(\s|$)/);
	});

	it("rendered primary Button carries the dark neutralizer", () => {
		const { container } = render(<Button variant="default">OK</Button>);
		const cls = container.querySelector("button")?.className ?? "";
		expect(cls).toMatch(/dark:border-transparent/);
	});
});
