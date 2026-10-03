import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
} from "@/__tests__/helpers/stableMocks";
import { MicToggleButton } from "@/pages/home/components/MicToggleButton";

// `spreadProps: true` forwards the icon's className onto the stub span so
// the state-to-colour contract below can assert the glyph token.
vi.mock("@hugeicons/react", () => hugeiconsReactMock({ spreadProps: true }));
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());

afterEach(() => {
	cleanup();
});

function renderButton(overrides: Record<string, unknown> = {}) {
	return render(
		<MicToggleButton
			isRecording={false}
			toggling={false}
			disabled={false}
			onClick={() => {}}
			label="Start dictation"
			{...overrides}
		/>,
	);
}

describe("MicToggleButton error state", () => {
	it("idle without error: alert glyph absent, no aria-live, no testid error marker", () => {
		renderButton();
		const btn = screen.getByRole("button", { name: "Start dictation" });
		expect(btn.getAttribute("aria-live")).toBeNull();
		expect(
			screen.queryByTestId("hugeicon")?.getAttribute("data-name"),
		).not.toBe("AlertCircleIcon");
	});

	it("error: alert glyph renders and the button carries aria-live=polite", () => {
		renderButton({ error: true });
		const btn = screen.getByRole("button", { name: "Start dictation" });
		expect(btn.getAttribute("aria-live")).toBe("polite");
		expect(screen.getByTestId("hugeicon").getAttribute("data-name")).toBe(
			"AlertCircleIcon",
		);
	});

	it("error while recording: recording state takes precedence (stop glyph, no aria-live)", () => {
		renderButton({ error: true, isRecording: true, label: "Stop dictation" });
		const btn = screen.getByRole("button", { name: "Stop dictation" });
		expect(btn.getAttribute("aria-live")).toBeNull();
		expect(screen.getByTestId("hugeicon").getAttribute("data-name")).toBe(
			"StopIcon",
		);
	});

	it("click still invokes onClick in the error state", () => {
		const onClick = vi.fn();
		renderButton({ error: true, onClick });
		fireEvent.click(screen.getByRole("button", { name: "Start dictation" }));
		expect(onClick).toHaveBeenCalledTimes(1);
	});
});

// State → colour contract (C-UI-12): red means "capturing now" and
// nothing else. The idle button carries the brand accent (the app's
// CTA colour); the bubble's recording dot already reserves red for
// recording, so the two surfaces must agree.
describe("MicToggleButton state-to-colour contract (C-UI-12)", () => {
	const classes = (props: Record<string, unknown> = {}) => {
		renderButton(props);
		return screen.getByRole("button", { name: /dictation/i }).className;
	};

	it("idle uses the brand accent, never a destructive fill", () => {
		const cls = classes();
		expect(cls).toContain("bg-primary");
		expect(cls).toContain("animate-glow-pulse");
		expect(cls).not.toMatch(/\bbg-destructive\b/);
	});

	it("recording uses a solid destructive fill and keeps the pulse ring", () => {
		renderButton({ isRecording: true, label: "Stop dictation" });
		const btn = screen.getByRole("button", { name: "Stop dictation" });
		// Solid red, NOT the translucent /15 error wash and NOT accent.
		expect(btn.className).toMatch(/\bbg-destructive\b/);
		expect(btn.className).not.toContain("bg-destructive/15");
		expect(btn.className).not.toContain("bg-primary");
		// The halo sibling is painted red so it reads in every theme.
		const ring = document.querySelector(".animate-pulse-ring");
		expect(ring).toBeTruthy();
		expect(ring?.className).toContain("bg-destructive");
	});

	it("error keeps the hollow destructive wash, distinct from recording", () => {
		const cls = classes({ error: true });
		expect(cls).toContain("bg-destructive/15");
		expect(cls).toContain("ring-destructive");
		expect(cls).not.toMatch(/\bbg-destructive\b(?!\/)/);
		expect(cls).not.toContain("animate-glow-pulse");
	});

	it("the mic glyph uses the accent's paired foreground on the idle fill", () => {
		renderButton();
		const glyph = screen.getByTestId("hugeicon");
		// Near-white via the token, so custom themes are honoured (a raw
		// `text-white` would ignore every palette).
		expect(glyph.getAttribute("class")).toContain(
			"text-(--primary-foreground)",
		);
	});

	it("the stop glyph uses the destructive fill's paired foreground", () => {
		renderButton({ isRecording: true, label: "Stop dictation" });
		const glyph = screen.getByTestId("hugeicon");
		expect(glyph.getAttribute("class")).toContain(
			"text-(--destructive-foreground)",
		);
	});
});
