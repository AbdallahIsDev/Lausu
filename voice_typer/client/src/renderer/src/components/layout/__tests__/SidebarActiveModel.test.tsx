import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SidebarActiveModel } from "@/components/layout/SidebarActiveModel";
import { cloudDefaultModel, cloudModelLabel } from "@/lib/utils/cloudCatalog";
import { useAppStore } from "@/stores/appStore";

function setConfigSnapshot(config: Record<string, unknown> | null) {
	useAppStore.setState({ config: config as never });
}

afterEach(() => {
	cleanup();
	useAppStore.setState({ config: null });
});

describe("SidebarActiveModel", () => {
	it("renders the local active model as a truncated 12px caption", () => {
		setConfigSnapshot({ asr_backend: "whisper", model_size: "large-v3" });
		render(<SidebarActiveModel />);

		const label = screen.getByTestId("sidebar-active-model");
		// Same wording as the Models row for the same variant.
		expect(label.textContent).toBe("Whisper Large V3");
		// 12px is the existing text-xs step, never a literal size.
		expect(label.className).toContain("text-xs");
		expect(label.className).toContain("truncate");
		// The full name stays reachable when a long name is clipped.
		expect(label.getAttribute("title")).toBe("Whisper Large V3");
	});

	it("names a non-whisper local backend by its catalogue entry, not model_size", () => {
		// `model_size` is untouched by non-whisper activations, so the label
		// must follow the backend, not the stale size.
		setConfigSnapshot({ asr_backend: "parakeet", model_size: "large-v3" });
		render(<SidebarActiveModel />);

		expect(screen.getByTestId("sidebar-active-model").textContent).toBe(
			"Parakeet",
		);
	});

	it("names the selected cloud model when the cloud backend is active", () => {
		setConfigSnapshot({
			asr_backend: "cloud",
			cloud_provider: "openai",
			cloud_model: "gpt-4o-transcribe",
		});
		render(<SidebarActiveModel />);

		expect(screen.getByTestId("sidebar-active-model").textContent).toBe(
			cloudModelLabel("openai", "gpt-4o-transcribe"),
		);
	});

	it("names the provider's default model when only the provider is set", () => {
		setConfigSnapshot({
			asr_backend: "cloud",
			cloud_provider: "groq",
			cloud_model: "",
		});
		render(<SidebarActiveModel />);

		expect(screen.getByTestId("sidebar-active-model").textContent).toBe(
			cloudModelLabel("groq", cloudDefaultModel("groq")),
		);
	});

	it("stays hidden when the cloud backend has no provider", () => {
		setConfigSnapshot({ asr_backend: "cloud", cloud_provider: "" });
		const { container } = render(<SidebarActiveModel />);
		expect(container).toBeEmptyDOMElement();
	});

	it("stays hidden when no model is active", () => {
		setConfigSnapshot({ asr_backend: "whisper", model_size: "" });
		const { container } = render(<SidebarActiveModel />);
		expect(container).toBeEmptyDOMElement();
	});

	it("stays hidden in the collapsed icon rail", () => {
		setConfigSnapshot({ asr_backend: "whisper", model_size: "large-v3" });
		const { container } = render(<SidebarActiveModel collapsed />);
		expect(container).toBeEmptyDOMElement();
	});

	it("follows a model switch through the shared config snapshot", () => {
		setConfigSnapshot({ asr_backend: "whisper", model_size: "tiny" });
		render(<SidebarActiveModel />);
		expect(screen.getByTestId("sidebar-active-model").textContent).toBe(
			"Whisper Tiny",
		);

		act(() => {
			useAppStore.getState().mergeConfig({ model_size: "large-v3" });
		});

		expect(screen.getByTestId("sidebar-active-model").textContent).toBe(
			"Whisper Large V3",
		);
	});

	// The caption is the sidebar half of the tray tooltip's "which model is
	// running". Nothing about the compute-device switch may gate it: a
	// CPU-only machine, a missing GPU probe, or a garbage `device` value are
	// all states where DeviceToggle hides, and the model name must survive
	// every one of them.
	it.each([
		[
			"CPU-only machine (gpu_available false)",
			{ device: "cpu", gpu_available: false },
		],
		["GPU probe absent (gpu_available undefined)", { device: "cuda" }],
		["unusable device value", { device: "", gpu_available: true }],
		["mid-toggle garbage", { device: "CUDA", gpu_available: "true" }],
	])(
		"stays visible when the device switch cannot render: %s",
		(_label, deviceCfg) => {
			setConfigSnapshot({
				asr_backend: "whisper",
				model_size: "large-v3",
				...deviceCfg,
			});
			render(<SidebarActiveModel />);

			expect(screen.getByTestId("sidebar-active-model").textContent).toBe(
				"Whisper Large V3",
			);
		},
	);
});
