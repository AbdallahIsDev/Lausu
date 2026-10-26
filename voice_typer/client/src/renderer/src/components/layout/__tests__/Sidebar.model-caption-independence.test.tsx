/**
 * The sidebar's model caption must be independent of the CPU/GPU switch.
 *
 * The caption is the sidebar half of what the tray tooltip already reports:
 * which model is running. The device switch is an optional control that can
 * be absent (no GPU), lagging (set_config round-trip), or outright broken.
 * None of those states says anything about the active model, so none of them
 * may take the caption down.
 *
 * The concrete failure mode this pins: `DeviceToggle` sits directly below the
 * caption, and before the isolation boundary a throw inside it propagated to
 * the ROOT ErrorBoundary in main.tsx, replacing the entire renderer with the
 * crash fallback — caption included. Now the switch has its own boundary with
 * `fallback={null}`, so a broken toggle degrades to "no switch".
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: ({
		children,
		icon,
	}: {
		children?: React.ReactNode;
		icon?: { name?: string };
	}) => (
		<span data-testid="hugeicon" data-name={icon?.name}>
			{children}
		</span>
	),
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

vi.mock("@/hooks/usePluginCatalog", () => ({
	usePluginsAvailable: () => true,
}));

// The switch is the thing under test's blast radius: let each test decide
// whether it renders, throws, or is absent.
const toggleState = vi.hoisted(() => ({ mode: "ok" as "ok" | "throw" }));

vi.mock("@/components/layout/DeviceToggle", () => ({
	DeviceToggle: () => {
		if (toggleState.mode === "throw") {
			throw new Error("CPU/GPU toggle exploded");
		}
		return <div data-testid="fake-device-toggle" />;
	},
}));

import { Sidebar } from "@/components/layout/Sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useAppStore } from "@/stores/appStore";

function renderSidebar() {
	return render(
		<TooltipProvider delayDuration={200} skipDelayDuration={500}>
			<Sidebar currentPage="home" onNavigate={vi.fn()} />
		</TooltipProvider>,
	);
}

const CONFIG = {
	asr_backend: "whisper",
	model_size: "large-v3",
	device: "cuda",
	gpu_available: true,
} as never;

describe("Sidebar model caption independence", () => {
	let errorSpy: ReturnType<typeof vi.spyOn>;

	beforeEach(() => {
		toggleState.mode = "ok";
		useAppStore.setState({ config: CONFIG });
		// The boundary deliberately logs the caught error; keep the
		// suite output readable without hiding the assertion.
		errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
	});

	afterEach(() => {
		cleanup();
		errorSpy.mockRestore();
		useAppStore.setState({ config: null });
	});

	it("keeps the model name when the CPU/GPU switch throws", () => {
		toggleState.mode = "throw";

		renderSidebar();

		// The caption survives the sibling's crash...
		const caption = screen.getByTestId("sidebar-active-model");
		expect(caption.textContent).toBe("Whisper Large V3");
		// ...the switch itself is gone (fallback={null}), and...
		expect(screen.queryByTestId("fake-device-toggle")).toBeNull();
		// ...the rest of the sidebar is untouched, which is the point:
		// pre-fix this throw reached the root boundary and replaced the
		// whole renderer with the crash fallback.
		expect(screen.getByRole("button", { name: /^Home(\s|$)/ })).toBeTruthy();
		// The boundary did catch it, exactly once.
		expect(errorSpy).toHaveBeenCalled();
	});

	it("renders both when the switch is healthy", () => {
		renderSidebar();

		expect(screen.getByTestId("sidebar-active-model").textContent).toBe(
			"Whisper Large V3",
		);
		expect(screen.getByTestId("fake-device-toggle")).toBeTruthy();
	});

	it("keeps the model name when the switch renders nothing at all (no GPU)", () => {
		// The real DeviceToggle returns null when `gpu_available !== true`;
		// model it as an empty render, which is the CPU-only shape.
		toggleState.mode = "throw";

		useAppStore.setState({
			config: {
				asr_backend: "whisper",
				model_size: "large-v3",
				device: "cpu",
				gpu_available: false,
			} as never,
		});
		renderSidebar();

		expect(screen.getByTestId("sidebar-active-model").textContent).toBe(
			"Whisper Large V3",
		);
	});
});
