import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
	act,
	cleanup,
	fireEvent,
	render,
	screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DebugPanel } from "@/components/debug/DebugPanel";
import { useDebugPrefs } from "@/hooks/useDebugPrefs";
import { useAppStore } from "@/stores/appStore";

function PrefsProbe() {
	const { statsLayout, badgeHue } = useDebugPrefs();
	return (
		<div
			data-testid="prefs-probe"
			data-layout={statsLayout}
			data-hue={badgeHue}
		/>
	);
}

beforeEach(() => {
	localStorage.clear();
	localStorage.setItem("lausu-ui-debug-panel-visible", "1");
	vi.unstubAllEnvs();
	useAppStore.setState({ config: { developer_mode: true } as never });
});

afterEach(() => {
	cleanup();
	vi.unstubAllEnvs();
});

describe("DebugPanel", () => {
	it("stays hidden by default and renders only after explicit opt-in", () => {
		localStorage.removeItem("lausu-ui-debug-panel-visible");
		useAppStore.setState({ config: { developer_mode: true } as never });
		render(<DebugPanel />);
		expect(screen.queryByTestId("debug-panel")).toBeNull();
		cleanup();

		localStorage.setItem("lausu-ui-debug-panel-visible", "1");
		render(<DebugPanel />);
		expect(screen.getByTestId("debug-panel")).toBeTruthy();
	});

	it("flips the stats layout and persists the choice", () => {
		render(
			<>
				<DebugPanel />
				<PrefsProbe />
			</>,
		);
		expect(screen.getByTestId("prefs-probe").getAttribute("data-layout")).toBe(
			"separated",
		);
		fireEvent.click(screen.getByTestId("debug-stats-joined"));
		expect(screen.getByTestId("prefs-probe").getAttribute("data-layout")).toBe(
			"joined",
		);
		expect(localStorage.getItem("lausu-ui-debug-stats-layout")).toBe("joined");

		const srcRoot = resolve(import.meta.dirname, "../../../");
		const home = readFileSync(resolve(srcRoot, "pages/Home.tsx"), "utf-8");
		expect(home).toContain("<StatCards stats={d} variant={statsLayout} />");
	});

	it("changes the badge hue and persists it", () => {
		render(
			<>
				<DebugPanel />
				<PrefsProbe />
			</>,
		);
		fireEvent.click(screen.getByTestId("debug-badge-red"));
		expect(screen.getByTestId("prefs-probe").getAttribute("data-hue")).toBe(
			"red",
		);
		expect(localStorage.getItem("lausu-ui-debug-badge-hue")).toBe("red");

		const srcRoot = resolve(import.meta.dirname, "../../../");
		const sidebar = readFileSync(
			resolve(srcRoot, "components/layout/Sidebar.tsx"),
			"utf-8",
		);
		expect(sidebar).toContain("hue={badgeHue}");
	});

	it("reset returns both preferences to the shipped defaults", () => {
		render(
			<>
				<DebugPanel />
				<PrefsProbe />
			</>,
		);
		fireEvent.click(screen.getByTestId("debug-stats-joined"));
		fireEvent.click(screen.getByTestId("debug-badge-green"));
		act(() => fireEvent.click(screen.getByTestId("debug-reset")));
		expect(screen.getByTestId("prefs-probe").getAttribute("data-layout")).toBe(
			"separated",
		);
		expect(screen.getByTestId("prefs-probe").getAttribute("data-hue")).toBe(
			"green",
		);
	});
});
