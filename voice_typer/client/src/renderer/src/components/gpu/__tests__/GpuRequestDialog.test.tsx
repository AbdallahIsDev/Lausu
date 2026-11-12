/**
 * Unit tests for the GPU-request modal (`GpuRequestDialog`).
 *
 * Contract under test (owner requirement: "show a model popup explaining
 * that CUDA files or drivers are needed, with buttons Download / Stay on
 * CPU"):
 *
 *   - `gpu_present_cuda_missing` → explains the CUDA runtime, offers
 *     exactly two real buttons: Download (starts the install job) and
 *     Stay on CPU (writes nothing, starts nothing).
 *   - `driver_missing` → explains the driver gap, links out, and has NO
 *     Download button: the app cannot install a kernel driver.
 *   - `gpu_ready` / `no_nvidia_gpu` → renders nothing; the modal is
 *     meaningless in both states.
 *   - A failed `start_cuda_download` keeps the dialog open and surfaces an
 *     error instead of pretending the job started.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	pythonMock,
	resetStableMocks,
	snackbarMock,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";
import { useAppStore } from "@/stores/appStore";

const { mockCall, showSnack: mockShowSnack } = stableMocks;

vi.mock("@/hooks/usePython", () => pythonMock());
vi.mock("@/hooks/useSnackbar", () => snackbarMock());
vi.mock("@/i18n/i18n", () => ({
	t: (key: string) => key,
	useT: () => (key: string, params?: Record<string, string>) =>
		params ? `${key}:${JSON.stringify(params)}` : key,
	// `lib/format` resolves the number/byte locale through this.
	getLocale: () => "en",
}));

const mockOpenExternalUrl = vi.fn();
vi.mock("@/lib/external-links", () => ({
	openExternalUrl: (url: string) => mockOpenExternalUrl(url),
}));

import { GpuRequestDialog } from "../GpuRequestDialog";

type Capability = Record<string, unknown>;

function capability(overrides: Capability = {}): Capability {
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

function setCapability(next: Capability | null) {
	useAppStore.setState({
		config: { device: "cpu", gpu_capability: next } as never,
	});
}

const onOpenChange = vi.fn();

beforeEach(() => {
	resetStableMocks();
	mockCall.mockResolvedValue({});
	mockOpenExternalUrl.mockReset();
	onOpenChange.mockReset();
});

afterEach(() => {
	useAppStore.setState({ config: null });
});

describe("GpuRequestDialog", () => {
	it("offers Download and Stay on CPU when the CUDA runtime is missing", () => {
		setCapability(capability());
		render(<GpuRequestDialog open onOpenChange={onOpenChange} />);
		expect(screen.getByText("gpuSwitch.dialogTitle")).toBeInTheDocument();
		expect(screen.getByText(/gpuSwitch\.cudaMissingBody/)).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "gpuSwitch.download" }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "gpuSwitch.stayOnCpu" }),
		).toBeInTheDocument();
	});

	it("starts the real install job and closes on Download", async () => {
		const user = userEvent.setup();
		setCapability(capability());
		render(<GpuRequestDialog open onOpenChange={onOpenChange} />);
		await user.click(
			screen.getByRole("button", { name: "gpuSwitch.download" }),
		);
		expect(mockCall).toHaveBeenCalledWith("start_cuda_download");
		expect(onOpenChange).toHaveBeenCalledWith(false);
	});

	it("writes nothing and starts nothing on Stay on CPU", async () => {
		const user = userEvent.setup();
		setCapability(capability());
		render(<GpuRequestDialog open onOpenChange={onOpenChange} />);
		await user.click(
			screen.getByRole("button", { name: "gpuSwitch.stayOnCpu" }),
		);
		expect(onOpenChange).toHaveBeenCalledWith(false);
		expect(mockCall).not.toHaveBeenCalled();
	});

	it("shows a driver link and NO Download button on driver_missing", () => {
		setCapability(
			capability({ state: "driver_missing", driver_present: false }),
		);
		render(<GpuRequestDialog open onOpenChange={onOpenChange} />);
		expect(
			screen.getByText("gpuSwitch.driverMissingTitle"),
		).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "gpuSwitch.driverMissingAction" }),
		).toBeInTheDocument();
		expect(
			screen.queryByRole("button", { name: "gpuSwitch.download" }),
		).toBeNull();
		// Stay on CPU is still the only decision available.
		expect(
			screen.getByRole("button", { name: "gpuSwitch.stayOnCpu" }),
		).toBeInTheDocument();
	});

	it("opens the vendor driver page from the driver branch", async () => {
		const user = userEvent.setup();
		setCapability(
			capability({ state: "driver_missing", driver_present: false }),
		);
		render(<GpuRequestDialog open onOpenChange={onOpenChange} />);
		await user.click(
			screen.getByRole("button", { name: "gpuSwitch.driverMissingAction" }),
		);
		expect(mockOpenExternalUrl).toHaveBeenCalledWith(
			"https://www.nvidia.com/en-us/drivers/",
		);
	});

	it("renders nothing when the active backend can already serve", () => {
		setCapability(
			capability({
				state: "gpu_ready",
				cuda_ready: true,
				stack_complete: true,
				active_backend: "parakeet",
				active_backend_gpu_ready: true,
				backends: [
					{
						name: "parakeet",
						local: true,
						gpu_capable: true,
						gpu_ready: true,
						detail: "ready",
					},
				],
			}),
		);
		const { container } = render(
			<GpuRequestDialog open onOpenChange={onOpenChange} />,
		);
		expect(container).toBeEmptyDOMElement();
	});

	it("renders the Download button in the mixed state", () => {
		// Live case: `state` is gpu_ready and `cuda_ready` is true because
		// CTranslate2 works, but the ACTIVE Parakeet backend cannot serve.
		setCapability(
			capability({
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
		);
		render(<GpuRequestDialog open onOpenChange={onOpenChange} />);
		expect(screen.getByText("gpuSwitch.dialogTitle")).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "gpuSwitch.download" }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "gpuSwitch.stayOnCpu" }),
		).toBeInTheDocument();
	});

	it("does not offer a CUDA download for a CPU-only backend", () => {
		// Qwen is pinned to CPU by design; installing CUDA would not help.
		setCapability(
			capability({
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
		);
		const { container } = render(
			<GpuRequestDialog open onOpenChange={onOpenChange} />,
		);
		expect(container).toBeEmptyDOMElement();
	});

	it("renders nothing on a machine with no NVIDIA adapter", () => {
		setCapability(
			capability({ state: "no_nvidia_gpu", hardware_present: false }),
		);
		const { container } = render(
			<GpuRequestDialog open onOpenChange={onOpenChange} />,
		);
		expect(container).toBeEmptyDOMElement();
	});

	it("keeps the dialog open and reports an error when the job cannot start", async () => {
		const user = userEvent.setup();
		mockCall.mockRejectedValueOnce(new Error("bridge down"));
		setCapability(capability());
		render(<GpuRequestDialog open onOpenChange={onOpenChange} />);
		await user.click(
			screen.getByRole("button", { name: "gpuSwitch.download" }),
		);
		await waitFor(() => {
			expect(mockShowSnack).toHaveBeenCalledWith(
				"gpuSwitch.errorInternal",
				"error",
			);
		});
		expect(onOpenChange).not.toHaveBeenCalledWith(false);
	});
});
