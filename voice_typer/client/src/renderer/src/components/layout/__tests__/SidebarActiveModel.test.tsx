import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SidebarActiveModel } from "@/components/layout/SidebarActiveModel";
import { applyStatusWithReason } from "@/hooks/connectionStatus";
import { DEFAULT_STATUS_COLOR, STATUS_COLORS } from "@/lib/dictationStatus";
import { cloudDefaultModel, cloudModelLabel } from "@/lib/utils/cloudCatalog";
import { useAppStore } from "@/stores/appStore";

function setConfigSnapshot(config: Record<string, unknown> | null) {
	useAppStore.setState({ config: config as never });
}

afterEach(() => {
	cleanup();
	// `recordingState` is process-wide: a test that drives the status dot
	// must not leave the next test's caption coloured for the wrong state.
	useAppStore.setState({
		config: null,
		recordingState: "idle",
		lastError: null,
	});
});

/** The status dot's rendered colour (the caption's only state readout). */
function dotColor(): string | undefined {
	const dot = screen.getByTestId("sidebar-active-model-dot");
	return (dot as HTMLElement).style.backgroundColor;
}

describe("SidebarActiveModel", () => {
	it("names the active PLUGIN instead of the local model", () => {
		// A selected plugin owns dictation: the model is not transcribing, so
		// showing "Parakeet Ultra" would be a lie about what is running.
		setConfigSnapshot({
			asr_backend: "parakeet",
			model_size: "large-v3",
			active_plugin: "anthropic_stt",
			active_plugin_name: "Anthropic STT",
		});
		render(<SidebarActiveModel />);

		const label = screen.getByTestId("sidebar-active-model");
		expect(label.textContent).toContain("Anthropic STT");
	});

	it("shows the live state as a DOT beside the name, never as a word", () => {
		setConfigSnapshot({
			asr_backend: "parakeet",
			active_plugin: "anthropic_stt",
			active_plugin_name: "Anthropic STT",
		});
		useAppStore.setState({ recordingState: "recording" });
		render(<SidebarActiveModel />);

		// The visible row is the dot + the engine name only.
		const row = screen.getByTestId("sidebar-active-model");
		expect(row.textContent).toBe("Anthropic STTrecording");
		expect(row.querySelector("[data-testid]")?.textContent).toBe("");
		expect(dotColor()).toBe(STATUS_COLORS.recording);
	});

	it("follows the status_change writer for a plugin cycle", () => {
		// The canonical writer is fed by status_change/state_changed/get_status.
		// Plugin sessions now drive that same authority via app.tray.set_state.
		setConfigSnapshot({
			asr_backend: "whisper",
			active_plugin: "anthropic_stt",
			active_plugin_name: "Anthropic STT",
		});
		render(<SidebarActiveModel />);

		const push = (status: "recording" | "transcribing" | "idle") => {
			act(() =>
				applyStatusWithReason(
					status,
					"",
					(recordingState) => useAppStore.setState({ recordingState }),
					(lastError) => useAppStore.setState({ lastError }),
				),
			);
		};
		push("recording");
		expect(dotColor()).toBe(STATUS_COLORS.recording);
		push("transcribing");
		expect(dotColor()).toBe(STATUS_COLORS.transcribing);
		push("idle");
		expect(dotColor()).toBe(STATUS_COLORS.idle);
	});

	it("colours the dot from the shared status palette on every state", () => {
		setConfigSnapshot({ asr_backend: "whisper", model_size: "large-v3" });
		const cases = [
			["idle", null, STATUS_COLORS.idle],
			["loading", null, STATUS_COLORS.loading],
			["transcribing", null, STATUS_COLORS.transcribing],
			["error", "Model failed", STATUS_COLORS.error],
			// An error state with nothing to explain falls back to idle, the
			// same rule Home's pill follows (C-HOME-1).
			["error", null, STATUS_COLORS.idle],
		] as const;

		for (const [state, lastError, expected] of cases) {
			useAppStore.setState({ recordingState: state, lastError });
			const { unmount } = render(<SidebarActiveModel />);
			expect(dotColor()).toBe(expected);
			unmount();
		}
	});

	it("uses the idle colour for an unrecognised state", () => {
		setConfigSnapshot({ asr_backend: "whisper", model_size: "large-v3" });
		useAppStore.setState({ recordingState: "bogus" as never });
		render(<SidebarActiveModel />);

		expect(dotColor()).toBe(DEFAULT_STATUS_COLOR);
	});

	it("renders the local active model as a truncated 12px caption", () => {
		setConfigSnapshot({ asr_backend: "whisper", model_size: "large-v3" });
		render(<SidebarActiveModel />);

		const label = screen.getByTestId("sidebar-active-model");
		// Same wording as the Models row for the same variant.
		expect(label.textContent).toContain("Whisper Large V3");
		// 12px is the existing text-xs step, never a literal size.
		const name = label.querySelector("span.truncate") as HTMLElement;
		expect(name.className).toContain("text-xs");
		expect(name.className).toContain("truncate");
		// The full name stays reachable when a long name is clipped.
		expect(label.getAttribute("title")).toBe("Whisper Large V3 · idle");
	});

	it("names a non-whisper local backend by its catalogue entry, not model_size", () => {
		// `model_size` is untouched by non-whisper activations, so the label
		// must follow the backend, not the stale size.
		setConfigSnapshot({ asr_backend: "parakeet", model_size: "large-v3" });
		render(<SidebarActiveModel />);

		expect(screen.getByTestId("sidebar-active-model").textContent).toContain(
			"Parakeet Ultra",
		);
	});

	it("names the selected cloud model when the cloud backend is active", () => {
		setConfigSnapshot({
			asr_backend: "cloud",
			cloud_provider: "openai",
			cloud_model: "gpt-4o-transcribe",
		});
		render(<SidebarActiveModel />);

		expect(screen.getByTestId("sidebar-active-model").textContent).toContain(
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

		expect(screen.getByTestId("sidebar-active-model").textContent).toContain(
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
		expect(screen.getByTestId("sidebar-active-model").textContent).toContain(
			"Whisper Tiny",
		);

		act(() => {
			useAppStore.getState().mergeConfig({ model_size: "large-v3" });
		});

		expect(screen.getByTestId("sidebar-active-model").textContent).toContain(
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

			expect(screen.getByTestId("sidebar-active-model").textContent).toContain(
				"Whisper Large V3",
			);
		},
	);
});
