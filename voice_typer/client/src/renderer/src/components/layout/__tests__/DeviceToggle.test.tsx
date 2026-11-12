import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	pythonMock,
	resetStableMocks,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";
import { DeviceToggle } from "@/components/layout/DeviceToggle";
import { useAppStore } from "@/stores/appStore";

vi.mock("@/hooks/usePython", () =>
	pythonMock({ captureEvents: stableMocks.pythonEventHandlers }),
);

const { mockCall, pythonEventHandlers } = stableMocks;

function setConfigSnapshot(config: Record<string, unknown> | null) {
	useAppStore.setState({ config: config as never });
}

function checkedLabel(): string {
	const radios = screen.getAllByRole("radio");
	const checked = radios.find((radio) => (radio as HTMLInputElement).checked);
	const label = checked?.closest("label")?.textContent ?? "";
	return label.trim();
}

beforeEach(() => {
	resetStableMocks();
	mockCall.mockResolvedValue({ success: true });
});

afterEach(() => {
	cleanup();
	useAppStore.setState({ config: null });
});

describe("DeviceToggle", () => {
	it("renders CPU/GPU with the active device checked", () => {
		setConfigSnapshot({ device: "cuda", gpu_available: true });
		render(<DeviceToggle />);
		const radios = screen.getAllByRole("radio");
		expect(radios).toHaveLength(2);
		expect(radios[1]).toBeChecked();
	});

	it("shows the EFFECTIVE device when the request still says GPU", () => {
		// The regression: config.device is the persisted request ("cuda"),
		// but the loaded engine reports CPU (CPU-only onnxruntime build).
		// The pill must follow the engine, not the request (C-UI-15).
		setConfigSnapshot({
			device: "cuda",
			active_device: "cpu",
			gpu_available: true,
		});
		render(<DeviceToggle />);
		expect(checkedLabel()).toBe("CPU");
	});

	it("shows the effective GPU even when the request says CPU", () => {
		setConfigSnapshot({
			device: "cpu",
			active_device: "cuda",
			gpu_available: true,
		});
		render(<DeviceToggle />);
		expect(checkedLabel()).toBe("GPU");
	});

	it("falls back to the request when no effective device is reported", () => {
		setConfigSnapshot({ device: "cuda", gpu_available: true });
		render(<DeviceToggle />);
		expect(screen.getAllByRole("radio")[1]).toBeChecked();
	});

	it("persists a GPU->CPU switch via set_config", async () => {
		const user = userEvent.setup();
		setConfigSnapshot({ device: "cuda", gpu_available: true });
		render(<DeviceToggle />);
		await user.click(screen.getByText("CPU"));
		expect(mockCall).toHaveBeenCalledWith("set_config", { device: "cpu" });
	});

	it("re-requests the GPU while a CPU fallback is serving it", async () => {
		// request=cuda / effective=cpu: clicking the (unchecked) GPU pill is
		// still a real request, not a no-op against the persisted value.
		const user = userEvent.setup();
		setConfigSnapshot({
			device: "cuda",
			active_device: "cpu",
			gpu_available: true,
		});
		render(<DeviceToggle />);
		await user.click(screen.getByText("GPU"));
		expect(mockCall).toHaveBeenCalledWith("set_config", { device: "cuda" });
	});

	it("stays hidden when no GPU is present", () => {
		setConfigSnapshot({ device: "cpu", gpu_available: false });
		const { container } = render(<DeviceToggle />);
		expect(container).toBeEmptyDOMElement();
	});

	it("stays hidden when the capability flag is absent (legacy sidecar)", () => {
		setConfigSnapshot({ device: "cpu" });
		const { container } = render(<DeviceToggle />);
		expect(container).toBeEmptyDOMElement();
	});

	it("stays hidden in the collapsed rail", () => {
		setConfigSnapshot({ device: "cuda", gpu_available: true });
		const { container } = render(<DeviceToggle collapsed />);
		expect(container).toBeEmptyDOMElement();
	});

	it("follows a backend GPU->CPU fallback through the store", () => {
		setConfigSnapshot({ device: "cuda", gpu_available: true });
		const { rerender } = render(<DeviceToggle />);
		useAppStore.getState().mergeConfig({ device: "cpu" });
		rerender(<DeviceToggle />);
		const radios = screen.getAllByRole("radio");
		expect(radios[0]).toBeChecked();
	});

	it("follows the effective-device push on config_changed", () => {
		setConfigSnapshot({ device: "cuda", gpu_available: true });
		render(<DeviceToggle />);
		expect(screen.getAllByRole("radio")[1]).toBeChecked();

		act(() => {
			pythonEventHandlers.config_changed?.({ active_device: "cpu" });
		});

		expect(checkedLabel()).toBe("CPU");
	});

	it("ignores config_changed pushes without a usable active_device", () => {
		setConfigSnapshot({ device: "cuda", gpu_available: true });
		render(<DeviceToggle />);

		act(() => {
			pythonEventHandlers.config_changed?.({ device: "cpu" });
			pythonEventHandlers.config_changed?.({ active_device: "pack worker" });
		});

		expect(screen.getAllByRole("radio")[1]).toBeChecked();
	});
});

// ── GPU switch + CUDA install flow ────────────────────────────────────
//
// Visibility and readiness are separate: an NVIDIA adapter makes the
// control reachable even when the CUDA runtime is missing, and clicking
// GPU in that state opens the request modal instead of persisting a
// `cuda` request no backend can serve.

function capability(overrides: Record<string, unknown> = {}) {
	return {
		state: "gpu_present_cuda_missing",
		hardware_present: true,
		driver_present: true,
		gpu_names: ["NVIDIA GeForce RTX 4070"],
		cuda_ready: false,
		backends: [],
		download: {
			supported: true,
			reason: null,
			total_bytes: 1_677_000_000,
			python: "3.13",
			installed: false,
			progress: {
				status: "idle",
				artifact: null,
				artifact_index: 0,
				artifact_count: 0,
				bytes_done: 0,
				bytes_total: 0,
				percent: 0,
				speed_bps: 0,
				eta_seconds: null,
				error: null,
			},
		},
		activation: null,
		driver_url: "https://www.nvidia.com/en-us/drivers/",
		...overrides,
	};
}

describe("DeviceToggle, GPU switch + CUDA install flow", () => {
	it("stays hidden when the capability reports no NVIDIA adapter", () => {
		setConfigSnapshot({
			device: "cpu",
			gpu_available: false,
			gpu_hardware_present: false,
			gpu_capability: capability({
				state: "no_nvidia_gpu",
				hardware_present: false,
				driver_present: false,
				gpu_names: [],
			}),
		});
		const { container } = render(<DeviceToggle />);
		expect(container).toBeEmptyDOMElement();
	});

	it("is reachable when an NVIDIA adapter exists but CUDA is missing", () => {
		setConfigSnapshot({
			device: "cpu",
			gpu_available: false,
			gpu_hardware_present: true,
			gpu_capability: capability(),
		});
		render(<DeviceToggle />);
		expect(screen.getAllByRole("radio")).toHaveLength(2);
		// The pill must not claim GPU is serving: CPU stays checked.
		expect(checkedLabel()).toBe("CPU");
	});

	it("is reachable on a driver-only machine", () => {
		setConfigSnapshot({
			device: "cpu",
			gpu_available: false,
			gpu_hardware_present: true,
			gpu_capability: capability({
				state: "driver_missing",
				driver_present: false,
				cuda_ready: false,
			}),
		});
		render(<DeviceToggle />);
		expect(screen.getAllByRole("radio")).toHaveLength(2);
	});

	it("opens the request modal instead of writing set_config", async () => {
		const user = userEvent.setup();
		setConfigSnapshot({
			device: "cpu",
			gpu_available: false,
			gpu_hardware_present: true,
			gpu_capability: capability(),
		});
		render(<DeviceToggle />);
		await user.click(screen.getByText("GPU"));
		expect(mockCall).not.toHaveBeenCalled();
		expect(await screen.findByRole("dialog")).toBeInTheDocument();
		// Nothing was persisted: CPU is still the request.
		expect(useAppStore.getState().config?.device).toBe("cpu");
	});

	it("writes set_config when the ACTIVE backend is already ready", async () => {
		const user = userEvent.setup();
		setConfigSnapshot({
			device: "cpu",
			active_device: "cpu",
			gpu_available: true,
			gpu_hardware_present: true,
			gpu_capability: capability({
				state: "gpu_ready",
				cuda_ready: true,
				stack_complete: true,
				active_backend: "whisper",
				active_backend_gpu_ready: true,
				backends: [
					{
						name: "whisper",
						local: true,
						gpu_capable: true,
						gpu_ready: true,
						detail: "ready",
					},
				],
			}),
		});
		render(<DeviceToggle />);
		await user.click(screen.getByText("GPU"));
		expect(mockCall).toHaveBeenCalledWith("set_config", { device: "cuda" });
		expect(screen.queryByRole("dialog")).toBeNull();
	});

	it("opens the dialog in the MIXED state (whisper ready, parakeet not)", async () => {
		// The live bug: `state` is gpu_ready because CTranslate2 works, so the
		// old global gate wrote `cuda` for a Parakeet user who can only fall
		// back to CPU — with no route to the CUDA download.
		const user = userEvent.setup();
		setConfigSnapshot({
			device: "cpu",
			active_device: "cpu",
			gpu_available: true,
			gpu_hardware_present: true,
			gpu_capability: capability({
				state: "gpu_ready",
				cuda_ready: true,
				stack_complete: false,
				active_backend: "parakeet",
				active_backend_gpu_ready: false,
				backends: [
					{
						name: "whisper",
						local: true,
						gpu_capable: true,
						gpu_ready: true,
						detail: "ready",
					},
					{
						name: "parakeet",
						local: true,
						gpu_capable: true,
						gpu_ready: false,
						detail: "cuda_missing",
					},
				],
			}),
		});
		render(<DeviceToggle />);
		await user.click(screen.getByText("GPU"));
		expect(mockCall).not.toHaveBeenCalled();
		expect(await screen.findByRole("dialog")).toBeInTheDocument();
		expect(useAppStore.getState().config?.device).toBe("cpu");
	});

	it("writes set_config for a READY active backend in the mixed state", async () => {
		// Same machine, Whisper selected: the switch is legitimate.
		const user = userEvent.setup();
		setConfigSnapshot({
			device: "cpu",
			active_device: "cpu",
			gpu_available: true,
			gpu_hardware_present: true,
			gpu_capability: capability({
				state: "gpu_ready",
				cuda_ready: true,
				stack_complete: false,
				active_backend: "whisper",
				active_backend_gpu_ready: true,
				backends: [
					{
						name: "whisper",
						local: true,
						gpu_capable: true,
						gpu_ready: true,
						detail: "ready",
					},
					{
						name: "parakeet",
						local: true,
						gpu_capable: true,
						gpu_ready: false,
						detail: "cuda_missing",
					},
				],
			}),
		});
		render(<DeviceToggle />);
		await user.click(screen.getByText("GPU"));
		expect(mockCall).toHaveBeenCalledWith("set_config", { device: "cuda" });
		expect(screen.queryByRole("dialog")).toBeNull();
	});

	it("does not offer CUDA for a CPU-only backend (qwen)", async () => {
		const user = userEvent.setup();
		setConfigSnapshot({
			device: "cpu",
			active_device: "cpu",
			gpu_available: true,
			gpu_hardware_present: true,
			gpu_capability: capability({
				state: "gpu_ready",
				cuda_ready: true,
				active_backend: "qwen",
				active_backend_gpu_ready: false,
				backends: [
					{
						name: "qwen",
						local: true,
						gpu_capable: false,
						gpu_ready: false,
						detail: "cpu_only_backend",
					},
				],
			}),
		});
		render(<DeviceToggle />);
		await user.click(screen.getByText("GPU"));
		// `device` is a global preference for a CPU-only engine, not a claim
		// about Qwen: no CUDA modal, and the request still goes through.
		expect(screen.queryByRole("dialog")).toBeNull();
		expect(mockCall).toHaveBeenCalledWith("set_config", { device: "cuda" });
	});

	it("ignores a GPU click while the install job is running", async () => {
		const user = userEvent.setup();
		const running = capability();
		running.download.progress.status = "downloading";
		setConfigSnapshot({
			device: "cpu",
			gpu_available: false,
			gpu_hardware_present: true,
			gpu_capability: running,
		});
		render(<DeviceToggle />);
		await user.click(screen.getByText("GPU"));
		expect(mockCall).not.toHaveBeenCalled();
		expect(screen.queryByRole("dialog")).toBeNull();
	});
});

describe("DeviceToggle, plugin owns dictation", () => {
	it("is hidden while a plugin is active", () => {
		// The plugin drives its own browser and its own audio path; the local
		// model is not running, so a CPU/GPU switch would be meaningless.
		setConfigSnapshot({
			device: "cpu",
			gpu_available: true,
			gpu_hardware_present: true,
			active_plugin: "anthropic_stt",
			active_plugin_name: "Anthropic STT",
		});
		const { container } = render(<DeviceToggle />);
		expect(container).toBeEmptyDOMElement();
	});

	it("comes back when the plugin is cleared", () => {
		setConfigSnapshot({
			device: "cpu",
			gpu_available: true,
			gpu_hardware_present: true,
			active_plugin: "",
		});
		render(<DeviceToggle />);
		expect(screen.getAllByRole("radio")).toHaveLength(2);
	});
});
