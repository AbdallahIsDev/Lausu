import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Button } from "@/components/ui/button";
import { Select, SelectTrigger } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup } from "@/components/ui/toggle-group";

// Stub the icon library so ToggleGroup's icon-only path can be
// exercised without pulling in the real (heavy) hugeicons renderer.
vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: () => <span data-testid="hugeicon" />,
}));

afterEach(() => {
	cleanup();
});

beforeEach(() => {
	vi.resetModules();
});

describe("Button, dev-mode a11y warn", () => {
	it("warns when there are no children and no aria-label (icon-only without name)", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(<Button />);
		expect(warn).toHaveBeenCalledTimes(1);
		expect(warn.mock.calls[0]?.[0]).toMatch(
			/\[renderer:Button\] no `aria-label`/,
		);
		warn.mockRestore();
	});

	it("does NOT warn when there is visible text content", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(<Button>Save</Button>);
		expect(warn).not.toHaveBeenCalled();
		warn.mockRestore();
	});

	it("does NOT warn when aria-label is provided (icon-only button with name)", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(<Button aria-label="Close" />);
		expect(warn).not.toHaveBeenCalled();
		warn.mockRestore();
	});

	it("does NOT warn when aria-labelledby is provided", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(<Button aria-labelledby="close-label" />);
		expect(warn).not.toHaveBeenCalled();
		warn.mockRestore();
	});
});

describe("Switch, dev-mode a11y warn", () => {
	it("warns when no aria-label / aria-labelledby is provided", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(<Switch />);
		expect(warn).toHaveBeenCalledTimes(1);
		expect(warn.mock.calls[0]?.[0]).toMatch(
			/\[renderer:Switch\] no `aria-label`/,
		);
		warn.mockRestore();
	});

	it("does NOT warn when aria-label is provided", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(<Switch aria-label="Enable captions" />);
		expect(warn).not.toHaveBeenCalled();
		warn.mockRestore();
	});

	it("does NOT warn when aria-labelledby is provided", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(<Switch aria-labelledby="captions-label" />);
		expect(warn).not.toHaveBeenCalled();
		warn.mockRestore();
	});
});

describe("SelectTrigger, dev-mode a11y warn", () => {
	it("warns when no children / aria-label / aria-labelledby is provided", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(
			<Select>
				<SelectTrigger />
			</Select>,
		);
		expect(warn).toHaveBeenCalledTimes(1);
		expect(warn.mock.calls[0]?.[0]).toMatch(
			/\[renderer:select\] SelectTrigger: no `aria-label`/,
		);
		warn.mockRestore();
	});

	it("does NOT warn when aria-label is provided", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(
			<Select>
				<SelectTrigger aria-label="Microphone" />
			</Select>,
		);
		expect(warn).not.toHaveBeenCalled();
		warn.mockRestore();
	});
});

describe("ToggleGroup, dev-mode a11y warn", () => {
	it("warns when ariaLabel is missing", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(
			<ToggleGroup
				options={[
					{ value: "a", label: "Alpha" },
					{ value: "b", label: "Bravo" },
				]}
				value="a"
				onChange={() => {}}
			/>,
		);
		const a11yWarns = warn.mock.calls.filter((c) =>
			String(c[0]).includes("[renderer:ToggleGroup] `ariaLabel`"),
		);
		expect(a11yWarns).toHaveLength(1);
		warn.mockRestore();
	});

	it("does NOT warn when ariaLabel is provided", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(
			<ToggleGroup
				options={[
					{ value: "a", label: "Alpha" },
					{ value: "b", label: "Bravo" },
				]}
				value="a"
				onChange={() => {}}
				ariaLabel="recording-mode"
			/>,
		);
		const a11yWarns = warn.mock.calls.filter((c) =>
			String(c[0]).includes("[renderer:ToggleGroup] `ariaLabel`"),
		);
		expect(a11yWarns).toHaveLength(0);
		warn.mockRestore();
	});

	it("warns when an icon-only option is missing title", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(
			<ToggleGroup
				options={[
					{
						value: "a",
						label: "",
						icon: (() => null) as unknown as never,
					},
				]}
				value="a"
				onChange={() => {}}
				ariaLabel="recording-mode"
			/>,
		);
		const iconWarns = warn.mock.calls.filter((c) =>
			String(c[0]).includes("icon-only"),
		);
		expect(iconWarns).toHaveLength(1);
		warn.mockRestore();
	});

	it("does NOT warn for icon-only option when title is provided", () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		render(
			<ToggleGroup
				options={[
					{
						value: "a",
						label: "",
						icon: (() => null) as unknown as never,
						title: "Alpha",
					},
				]}
				value="a"
				onChange={() => {}}
				ariaLabel="recording-mode"
			/>,
		);
		const iconWarns = warn.mock.calls.filter((c) =>
			String(c[0]).includes("icon-only"),
		);
		expect(iconWarns).toHaveLength(0);
		warn.mockRestore();
	});

	it("uses a stable useId-derived name for radio inputs when ariaLabel is missing", () => {
		render(
			<ToggleGroup
				options={[
					{ value: "a", label: "Alpha" },
					{ value: "b", label: "Bravo" },
				]}
				value="a"
				onChange={() => {}}
			/>,
		);
		const radios = document.querySelectorAll<HTMLInputElement>(
			'input[type="radio"]',
		);
		expect(radios.length).toBeGreaterThanOrEqual(2);
		const names = new Set(Array.from(radios).map((r) => r.name));
		// All radios in the same control share one name (so they toggle
		// as a group), and that name is NOT the legacy collision-prone
		// "toggle-group" literal, it's prefixed with "toggle-group-"
		// followed by the useId-derived base id.
		expect(names.size).toBe(1);
		const theName = names.values().next().value as string;
		expect(theName.startsWith("toggle-group-")).toBe(true);
		expect(theName).not.toBe("toggle-group");
	});
});
