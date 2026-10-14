import { cleanup, render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: (
		props: Record<string, unknown> & { icon?: { name?: string } },
	) => {
		// Mimic the real HugeiconsIcon: render an SVG-like element that
		// forwards DOM attributes (data-slot, aria-hidden, className, etc.)
		// so tests can assert on them. The real component renders an <svg>;
		// we use a <span> with the same attributes for jsdom assertions.
		const { icon, strokeWidth, ...rest } = props;
		return <span data-testid="hugeicon" data-name={icon?.name} {...rest} />;
	},
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import {
	AlertDialog,
	AlertDialogContent,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { NumberInputStepper } from "@/components/ui/number-input-stepper";

vi.mock("@/i18n/i18n", () => ({
	t: (key: string) => key,
	getLocale: () => "en",
	isRtlLocale: () => false,
}));

afterEach(() => {
	cleanup();
});

describe("NumberInputStepper, aria-live region", () => {
	it("renders a visually-hidden aria-live=polite sibling next to the input", () => {
		render(
			<NumberInputStepper value="5" onChange={() => {}} aria-label="count" />,
		);
		const liveRegion = document.querySelector('[aria-live="polite"]');
		expect(liveRegion).toBeTruthy();
		expect(liveRegion?.getAttribute("aria-atomic")).toBe("true");
		// Visually-hidden, Tailwind .sr-only utility.
		expect(liveRegion?.className).toContain("sr-only");
	});

	it("echoes the new value into the live region on step-up", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<NumberInputStepper value="5" onChange={onChange} aria-label="count" />,
		);
		const liveRegion = document.querySelector(
			'[aria-live="polite"]',
		) as HTMLElement;
		expect(liveRegion).toBeTruthy();
		// The live region starts empty (only mutated when a step fires).
		expect(liveRegion.textContent).toBe("");

		const upBtn = document.querySelector(
			'button[aria-label="a11y.increase"]',
		) as HTMLButtonElement;
		expect(upBtn).toBeTruthy();
		await user.click(upBtn);

		// After the click, the synthetic change event fires (verifying
		// the onChange path) AND the live region is populated with the
		// new value.
		expect(onChange).toHaveBeenCalledTimes(1);
		expect(liveRegion.textContent).toBe("6");
	});

	it("echoes the new value into the live region on step-down", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(
			<NumberInputStepper value="5" onChange={onChange} aria-label="count" />,
		);
		const liveRegion = document.querySelector(
			'[aria-live="polite"]',
		) as HTMLElement;
		const downBtn = document.querySelector(
			'button[aria-label="a11y.decrease"]',
		) as HTMLButtonElement;
		await user.click(downBtn);
		expect(onChange).toHaveBeenCalledTimes(1);
		expect(liveRegion.textContent).toBe("4");
	});
});

describe("NumberInputStepper, errorId / aria-errormessage forwarding", () => {
	it("forwards errorId as aria-errormessage on the underlying input", () => {
		render(
			<NumberInputStepper
				value="5"
				onChange={() => {}}
				aria-label="count"
				errorId="count-error"
			/>,
		);
		const input = document.querySelector(
			'input[type="number"]',
		) as HTMLInputElement;
		expect(input).toBeTruthy();
		expect(input.getAttribute("aria-errormessage")).toBe("count-error");
	});

	it("forwards a directly-passed aria-errormessage when errorId is omitted", () => {
		render(
			<NumberInputStepper
				value="5"
				onChange={() => {}}
				aria-label="count"
				aria-errormessage="inline-error"
			/>,
		);
		const input = document.querySelector(
			'input[type="number"]',
		) as HTMLInputElement;
		expect(input.getAttribute("aria-errormessage")).toBe("inline-error");
	});

	it("omits aria-errormessage when neither errorId nor aria-errormessage is provided", () => {
		render(
			<NumberInputStepper value="5" onChange={() => {}} aria-label="count" />,
		);
		const input = document.querySelector(
			'input[type="number"]',
		) as HTMLInputElement;
		expect(input.hasAttribute("aria-errormessage")).toBe(false);
	});

	it("errorId takes precedence over aria-errormessage", () => {
		render(
			<NumberInputStepper
				value="5"
				onChange={() => {}}
				aria-label="count"
				errorId="primary"
				aria-errormessage="secondary"
			/>,
		);
		const input = document.querySelector(
			'input[type="number"]',
		) as HTMLInputElement;
		expect(input.getAttribute("aria-errormessage")).toBe("primary");
	});
});

describe("Dialog, aria-modal={true}", () => {
	it("the DialogContent declares aria-modal=true explicitly", () => {
		render(
			<Dialog open={true}>
				<DialogContent>
					<DialogHeader>
						<DialogTitle>Test</DialogTitle>
					</DialogHeader>
				</DialogContent>
			</Dialog>,
		);
		const content = document.querySelector(
			'[data-slot="dialog-content"]',
		) as HTMLElement;
		expect(content).toBeTruthy();
		expect(content.getAttribute("aria-modal")).toBe("true");
	});
});

describe("AlertDialog, aria-modal={true}", () => {
	it("the AlertDialogContent declares aria-modal=true explicitly", () => {
		render(
			<AlertDialog open={true}>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Confirm</AlertDialogTitle>
					</AlertDialogHeader>
				</AlertDialogContent>
			</AlertDialog>,
		);
		const content = document.querySelector(
			'[data-slot="alert-dialog-content"]',
		) as HTMLElement;
		expect(content).toBeTruthy();
		expect(content.getAttribute("aria-modal")).toBe("true");
	});
});

describe("Accordion, decorative disclosure glyph", () => {
	it("the disclosure chevron is marked aria-hidden=true", () => {
		render(
			<Accordion type="single">
				<AccordionItem value="item-1">
					<AccordionTrigger>Section</AccordionTrigger>
					<AccordionContent>Panel</AccordionContent>
				</AccordionItem>
			</Accordion>,
		);
		const icons = document.querySelectorAll(
			'[data-slot="accordion-trigger-icon"]',
		);
		// One decorative glyph per trigger, aria-hidden: the trigger's
		// `aria-expanded` is the accessible state, so the chevron must not
		// be announced (and must not be a second tab stop).
		expect(icons.length).toBe(1);
		for (const icon of icons) {
			expect(icon.getAttribute("aria-hidden")).toBe("true");
		}
	});

	it("the chevron rotates off the TRIGGER's data-state", () => {
		// The glyph lives inside the trigger button, so the trigger's
		// own `group-data-[state=open]/accordion-trigger:` selector
		// reaches it. Assert the contract so a Radix change that drops
		// `data-state` from the trigger fails here instead of silently
		// leaving a chevron stuck pointing right.
		render(
			<Accordion type="single" collapsible>
				<AccordionItem value="item-1">
					<AccordionTrigger>Section</AccordionTrigger>
					<AccordionContent>Panel</AccordionContent>
				</AccordionItem>
			</Accordion>,
		);
		const trigger = document.querySelector(
			'[data-slot="accordion-trigger"]',
		) as HTMLElement;
		const icon = document.querySelector(
			'[data-slot="accordion-trigger-icon"]',
		) as HTMLElement;

		expect(trigger.className).toContain("group/accordion-trigger");
		expect(icon.className).toContain(
			"group-data-[state=open]/accordion-trigger:rotate-90",
		);
		// Collapsed: a right chevron, pointing at the content it reveals.
		expect(trigger.getAttribute("data-state")).toBe("closed");
	});

	it("the header's data-state actually flips, so the rotation fires", async () => {
		// The class contract is only half the story — the rotation needs
		// `data-state` to really change on the header when the panel
		// opens. Driven through the real trigger, so a Radix change that
		// stopped updating the header fails here rather than silently
		// leaving the chevron stuck pointing right.
		const user = userEvent.setup();
		render(
			<Accordion type="single" collapsible>
				<AccordionItem value="item-1">
					<AccordionTrigger>Section</AccordionTrigger>
					<AccordionContent>Panel</AccordionContent>
				</AccordionItem>
			</Accordion>,
		);
		const trigger = document.querySelector(
			'[data-slot="accordion-trigger"]',
		) as HTMLElement;
		const header = trigger.parentElement as HTMLElement;
		expect(header.getAttribute("data-state")).toBe("closed");

		await user.click(trigger);
		expect(header.getAttribute("data-state")).toBe("open");

		await user.click(trigger);
		expect(header.getAttribute("data-state")).toBe("closed");
	});

	it("the chevron is a CHILD of the trigger button inside the trailing div", () => {
		// The row is one button: the trailing div (actions + chevron)
		// lives inside the trigger, so the whole row is a single hover
		// surface owned by the trigger.
		render(
			<Accordion type="single">
				<AccordionItem value="item-1">
					<AccordionTrigger>Section</AccordionTrigger>
					<AccordionContent>Panel</AccordionContent>
				</AccordionItem>
			</Accordion>,
		);
		const trigger = document.querySelector(
			'[data-slot="accordion-trigger"]',
		) as HTMLElement;
		const trailing = document.querySelector(
			'[data-slot="accordion-trigger-trailing"]',
		) as HTMLElement;
		const icon = document.querySelector(
			'[data-slot="accordion-trigger-icon"]',
		) as HTMLElement;

		expect(trailing).toBeTruthy();
		expect(trailing.tagName).toBe("DIV");
		expect(trigger.contains(trailing)).toBe(true);
		expect(trigger.contains(icon)).toBe(true);
		expect(trailing.contains(icon)).toBe(true);
	});

	it("the trigger alone owns the row hover, no sibling half", () => {
		// One button, one hover surface: the trigger carries
		// `hover:bg-foreground/5` and there is no second half painting
		// a group hover beside it.
		render(
			<Accordion type="single">
				<AccordionItem value="item-1">
					<AccordionTrigger actions={<button type="button">Act</button>}>
						Section
					</AccordionTrigger>
					<AccordionContent>Panel</AccordionContent>
				</AccordionItem>
			</Accordion>,
		);
		const trigger = document.querySelector(
			'[data-slot="accordion-trigger"]',
		) as HTMLElement;
		const trailing = document.querySelector(
			'[data-slot="accordion-trigger-trailing"]',
		) as HTMLElement;
		expect(trigger.className).toContain("hover:bg-foreground/5");
		expect(trailing.className).not.toContain("group-hover");
		expect(trigger.contains(trailing)).toBe(true);
	});

	it("disclosure={false} with no actions renders NO trailing div at all", () => {
		// An empty trailing div would steal inset from the label side. The
		// microphone preset selector is exactly this shape (it supplies
		// its own chevron and no action), so the group must not exist.
		render(
			<Accordion type="single">
				<AccordionItem value="item-1">
					<AccordionTrigger disclosure={false}>Section</AccordionTrigger>
					<AccordionContent>Panel</AccordionContent>
				</AccordionItem>
			</Accordion>,
		);
		expect(
			document.querySelector('[data-slot="accordion-trigger-trailing"]'),
		).toBeNull();
		expect(
			document.querySelector('[data-slot="accordion-trigger-icon"]'),
		).toBeNull();
		// …and the trigger is therefore the only hover surface: there is
		// no second half to keep visually attached to it.
		expect(
			(document.querySelector('[data-slot="accordion-trigger"]') as HTMLElement)
				.className,
		).toContain("hover:bg-foreground/5");
	});

	it("disclosure={false} WITH actions keeps the slot, minus the glyph", () => {
		render(
			<Accordion type="single">
				<AccordionItem value="item-1">
					<AccordionTrigger
						disclosure={false}
						actions={<button type="button">Configure</button>}
					>
						Section
					</AccordionTrigger>
					<AccordionContent>Panel</AccordionContent>
				</AccordionItem>
			</Accordion>,
		);
		const trailing = document.querySelector(
			'[data-slot="accordion-trigger-trailing"]',
		) as HTMLElement;
		expect(trailing).toBeTruthy();
		expect(trailing.tagName).toBe("DIV");
		expect(trailing.textContent).toBe("Configure");
		// Inside the trigger button, not beside it.
		expect(
			(
				document.querySelector('[data-slot="accordion-trigger"]') as HTMLElement
			).contains(trailing),
		).toBe(true);
		expect(
			document.querySelector('[data-slot="accordion-trigger-icon"]'),
		).toBeNull();
	});
});
