/**
 * Unit tests for `useCudaInstallToast`, the sticky GPU-install notification
 * and the automatic switch that follows a completed install.
 *
 * Contract under test (owner requirement: "a persistent app notification
 * that never disappears shows download progress and information until it
 * finishes; then the app immediately switches to GPU; until the download
 * finishes the switch stays on CPU"):
 *
 *   - downloading/verifying/installing → ONE sticky toast with a fixed id
 *     and an infinite duration, carrying artifact name/index/count,
 *     bytes done/total, percent, speed and ETA.
 *   - completed → the sticky toast survives into "Restarting…", the host's
 *     `restart_sidecar` bridge is invoked, `get_gpu_capability` is re-read
 *     and the success toast only fires once the stack reports `cuda_ready`.
 *   - activation.state === "failed" → the reason is shown and the record is
 *     acknowledged exactly once, with CPU retained.
 *   - failed / cancelled → terminal: sticky cleared, normal toast, no
 *     respawn, CPU retained.
 */
import { renderHook } from "@testing-library/react";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAppStore } from "@/stores/appStore";

const registered = new Map<string, (data?: unknown) => unknown>();
const mockCall = vi.fn();
const mockT = vi.fn((key: string, params?: Record<string, string>) =>
	params ? `${key}:${JSON.stringify(params)}` : key,
);

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: mockCall }),
	usePythonEvent: (type: string, handler: (data?: unknown) => unknown) => {
		registered.set(type, handler);
	},
}));

vi.mock("sonner", () => ({
	toast: {
		error: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
		success: vi.fn(),
		dismiss: vi.fn(),
	},
}));

import {
	CUDA_INSTALL_TOAST_ID,
	describeProgress,
	formatEta,
	installErrorKey,
	useCudaInstallToast,
} from "@/hooks/useCudaInstallToast";
import type { CudaInstallStatus } from "@/types/config";

type Progress = {
	status: CudaInstallStatus;
	artifact: string | null;
	artifact_index: number;
	artifact_count: number;
	bytes_done: number;
	bytes_total: number;
	percent: number;
	speed_bps: number;
	eta_seconds: number | null;
	error: string | null;
};

function progress(overrides: Partial<Progress> = {}): Progress {
	return {
		status: "downloading",
		artifact: "cublas",
		artifact_index: 1,
		artifact_count: 5,
		bytes_done: 250_000_000,
		bytes_total: 1_677_000_000,
		percent: 14.9,
		speed_bps: 12_500_000,
		eta_seconds: 114,
		error: null,
		...overrides,
	};
}

function capability(overrides: Record<string, unknown> = {}) {
	return {
		state: "gpu_present_cuda_missing",
		hardware_present: true,
		cuda_ready: false,
		activation: null,
		download: { progress: progress({ status: "idle" }) },
		...overrides,
	};
}

function fire(type: string, data?: unknown) {
	const handler = registered.get(type);
	expect(handler, `no handler registered for ${type}`).toBeTruthy();
	return handler?.(data);
}

const restartBackend = vi.fn();

/**
 * Flip the capability mock to an activation failure so a test that
 * deliberately never reaches success still ends its 20 s poll loop.
 * Without this the loop outlives the test and the NEXT test's mock
 * (which answers `device: "cuda"`) makes it fire a stray success toast.
 */
let activationFailed = false;
async function stopFlowWithActivationFailure() {
	activationFailed = true;
	await vi.waitFor(() => {
		expect(toast.error).toHaveBeenCalled();
	});
}

beforeEach(() => {
	activationFailed = false;
	registered.clear();
	vi.clearAllMocks();
	mockT.mockImplementation((key: string, params?: Record<string, string>) =>
		params ? `${key}:${JSON.stringify(params)}` : key,
	);
	useAppStore.setState({ config: null });
	restartBackend.mockResolvedValue({ ok: true });
	Object.defineProperty(window, "window_", {
		value: { restartBackend },
		configurable: true,
		writable: true,
	});
	// Mount-time reattach read: nothing running, nothing failed.
	mockCall.mockImplementation((type: string) => {
		if (type === "get_gpu_capability") return Promise.resolve(capability());
		if (type === "get_config") {
			return Promise.resolve({ device: "cpu", active_device: "cpu" });
		}
		return Promise.resolve({});
	});
});

describe("useCudaInstallToast, sticky lifecycle", () => {
	it("registers the cuda_progress channel", () => {
		renderHook(() => useCudaInstallToast(mockT));
		expect(registered.has("cuda_progress")).toBe(true);
	});

	it("shows ONE sticky toast with a fixed id and infinite duration", () => {
		renderHook(() => useCudaInstallToast(mockT));
		fire("cuda_progress", progress());
		expect(toast.info).toHaveBeenCalledTimes(1);
		const [, options] = (toast.info as unknown as ReturnType<typeof vi.fn>).mock
			.calls[0] as [string, Record<string, unknown>];
		expect(options.id).toBe(CUDA_INSTALL_TOAST_ID);
		// Never auto-dismisses: `persistent` resolves to Infinity in
		// useSnackbar (sonner's "stay until dismissed" duration).
		expect(options.duration).toBe(Number.POSITIVE_INFINITY);
	});

	it("renders artifact, bytes, percent, speed and ETA in the description", () => {
		renderHook(() => useCudaInstallToast(mockT));
		fire("cuda_progress", progress());
		const [, options] = (toast.info as unknown as ReturnType<typeof vi.fn>).mock
			.calls[0] as [string, Record<string, unknown>];
		const description = String(options.description);
		expect(description).toContain("cublas");
		expect(description).toContain('"index":"2"');
		expect(description).toContain('"count":"5"');
		expect(description).toContain('"percent":"15"');
		expect(description).toContain("gpuSwitch.toastSpeed");
		expect(description).toContain("1m 54s");
	});

	it("replaces the same toast on every progress tick", () => {
		renderHook(() => useCudaInstallToast(mockT));
		fire("cuda_progress", progress({ percent: 10 }));
		fire("cuda_progress", progress({ percent: 40 }));
		fire("cuda_progress", progress({ percent: 90 }));
		expect(toast.info).toHaveBeenCalledTimes(3);
		for (const call of (toast.info as unknown as ReturnType<typeof vi.fn>).mock
			.calls) {
			expect((call[1] as Record<string, unknown>).id).toBe(
				CUDA_INSTALL_TOAST_ID,
			);
		}
	});

	it("keeps the sticky toast across verifying and installing", () => {
		renderHook(() => useCudaInstallToast(mockT));
		fire("cuda_progress", progress({ status: "verifying" }));
		fire("cuda_progress", progress({ status: "installing" }));
		expect(toast.info).toHaveBeenCalledTimes(2);
		const descriptions = (
			toast.info as unknown as ReturnType<typeof vi.fn>
		).mock.calls.map((call) =>
			String((call[1] as Record<string, unknown>).description),
		);
		expect(descriptions[0]).toContain("gpuSwitch.toastVerifying");
		expect(descriptions[1]).toContain("gpuSwitch.toastInstalling");
	});

	it("cancels the job from the sticky toast action", () => {
		renderHook(() => useCudaInstallToast(mockT));
		fire("cuda_progress", progress());
		const [, options] = (toast.info as unknown as ReturnType<typeof vi.fn>).mock
			.calls[0] as [string, Record<string, unknown>];
		const action = options.action as { label: string; onClick: () => void };
		expect(action.label).toBe("gpuSwitch.cancelDownload");
		action.onClick();
		expect(mockCall).toHaveBeenCalledWith("cancel_cuda_download");
	});
});

describe("useCudaInstallToast, automatic switch", () => {
	it("respawns, confirms GPU readiness, then reports success", async () => {
		renderHook(() => useCudaInstallToast(mockT));
		mockCall.mockImplementation((type: string) => {
			if (type === "get_gpu_capability") {
				if (activationFailed) {
					return Promise.resolve(
						capability({
							activation: { state: "failed", reason: "gpu_not_ready" },
						}),
					);
				}
				return Promise.resolve(
					capability({
						state: "gpu_ready",
						cuda_ready: true,
						stack_complete: true,
						active_backend_gpu_ready: true,
					}),
				);
			}
			if (type === "get_config") {
				return Promise.resolve({ device: "cuda", active_device: "cuda" });
			}
			return Promise.resolve({});
		});

		fire("cuda_progress", progress({ status: "completed" }));

		await vi.waitFor(() => {
			expect(toast.success).toHaveBeenCalledWith(
				"gpuSwitch.toastReady",
				expect.anything(),
			);
		});
		expect(restartBackend).toHaveBeenCalledTimes(1);
		expect(mockCall).toHaveBeenCalledWith("get_gpu_capability");
		expect(toast.dismiss).toHaveBeenCalledWith(CUDA_INSTALL_TOAST_ID);
	});

	it("keeps CPU and explains the reason when activation failed", async () => {
		renderHook(() => useCudaInstallToast(mockT));
		mockCall.mockImplementation((type: string) => {
			if (type === "get_gpu_capability") {
				return Promise.resolve(
					capability({
						activation: { state: "failed", reason: "gpu_not_ready" },
					}),
				);
			}
			if (type === "get_config") {
				return Promise.resolve({ device: "cpu", active_device: "cpu" });
			}
			return Promise.resolve({});
		});

		fire("cuda_progress", progress({ status: "completed" }));

		await vi.waitFor(() => {
			expect(toast.error).toHaveBeenCalled();
		});
		const message = String(
			(toast.error as unknown as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] ??
				"",
		);
		expect(message).toContain("gpuSwitch.toastActivationFailed");
		expect(message).toContain("gpu_not_ready");
		// Acknowledged exactly once so the failure is not re-reported.
		expect(mockCall).toHaveBeenCalledWith("ack_cuda_activation");
		expect(toast.success).not.toHaveBeenCalled();
	});

	it("never reports success on the loose `cuda_ready` alone", async () => {
		// Live mixed state: CTranslate2 works (`cuda_ready` true) but the
		// active Parakeet backend cannot serve. Reporting success here is the
		// "silent CPU fallback" the per-backend gate exists to prevent.
		renderHook(() => useCudaInstallToast(mockT));
		mockCall.mockImplementation((type: string) => {
			if (type === "get_gpu_capability") {
				if (activationFailed) {
					return Promise.resolve(
						capability({
							activation: { state: "failed", reason: "gpu_not_ready" },
						}),
					);
				}
				return Promise.resolve(
					capability({
						state: "gpu_ready",
						cuda_ready: true,
						stack_complete: false,
						active_backend: "parakeet",
						active_backend_gpu_ready: false,
					}),
				);
			}
			return Promise.resolve({});
		});

		fire("cuda_progress", progress({ status: "completed" }));

		await vi.waitFor(() => {
			const descriptions = (
				toast.info as unknown as ReturnType<typeof vi.fn>
			).mock.calls.map((call) =>
				String((call[1] as Record<string, unknown>).description),
			);
			expect(descriptions).toContain("gpuSwitch.toastActivating");
		});
		expect(toast.success).not.toHaveBeenCalled();
		await stopFlowWithActivationFailure();
	});

	it("does not report success when only the ACTIVE backend is ready", async () => {
		// Whisper (CTranslate2) sees the GPU, the ORT GPU wheel failed to load:
		// `active_backend_gpu_ready` is true but `stack_complete` is false, and
		// activation refuses to persist `cuda`. Announcing "GPU ready" here is
		// the exact lie this gate exists to prevent.
		renderHook(() => useCudaInstallToast(mockT));
		mockCall.mockImplementation((type: string) => {
			if (type === "get_gpu_capability") {
				if (activationFailed) {
					return Promise.resolve(
						capability({
							activation: { state: "failed", reason: "gpu_not_ready" },
						}),
					);
				}
				return Promise.resolve(
					capability({
						state: "gpu_ready",
						cuda_ready: true,
						stack_complete: false,
						active_backend: "whisper",
						active_backend_gpu_ready: true,
					}),
				);
			}
			if (type === "get_config") {
				return Promise.resolve({ device: "cpu", active_device: "cpu" });
			}
			return Promise.resolve({});
		});

		fire("cuda_progress", progress({ status: "completed" }));

		await vi.waitFor(() => {
			const descriptions = (
				toast.info as unknown as ReturnType<typeof vi.fn>
			).mock.calls.map((call) =>
				String((call[1] as Record<string, unknown>).description),
			);
			expect(descriptions).toContain("gpuSwitch.toastActivating");
		});
		expect(toast.success).not.toHaveBeenCalled();
		await stopFlowWithActivationFailure();
	});

	it("keeps polling when the stack is complete but the device is still cpu", async () => {
		// The poll can win a race against `apply_pending_activation`: a
		// complete stack with `device: "cpu"` means activation has not run
		// yet, so success must wait for the persisted decision.
		renderHook(() => useCudaInstallToast(mockT));
		mockCall.mockImplementation((type: string) => {
			if (type === "get_gpu_capability") {
				if (activationFailed) {
					return Promise.resolve(
						capability({
							activation: { state: "failed", reason: "gpu_not_ready" },
						}),
					);
				}
				return Promise.resolve(
					capability({
						state: "gpu_ready",
						cuda_ready: true,
						stack_complete: true,
						active_backend_gpu_ready: true,
					}),
				);
			}
			if (type === "get_config") {
				return Promise.resolve({ device: "cpu", active_device: "cpu" });
			}
			return Promise.resolve({});
		});

		fire("cuda_progress", progress({ status: "completed" }));

		await vi.waitFor(() => {
			expect(toast.info).toHaveBeenCalled();
		});
		// Two confirm rounds: t=0 and the 500 ms retry.
		await new Promise((resolve) => setTimeout(resolve, 700));
		expect(toast.success).not.toHaveBeenCalled();
		const configReads = mockCall.mock.calls.filter(
			(call) => call[0] === "get_config",
		).length;
		expect(configReads).toBeGreaterThanOrEqual(2);
		await stopFlowWithActivationFailure();
	});

	it("reports success exactly once when the stack is complete AND device is cuda", async () => {
		renderHook(() => useCudaInstallToast(mockT));
		mockCall.mockImplementation((type: string) => {
			if (type === "get_gpu_capability") {
				if (activationFailed) {
					return Promise.resolve(
						capability({
							activation: { state: "failed", reason: "gpu_not_ready" },
						}),
					);
				}
				return Promise.resolve(
					capability({
						state: "gpu_ready",
						cuda_ready: true,
						stack_complete: true,
						active_backend_gpu_ready: true,
					}),
				);
			}
			if (type === "get_config") {
				return Promise.resolve({ device: "cuda", active_device: "cuda" });
			}
			return Promise.resolve({});
		});

		fire("cuda_progress", progress({ status: "completed" }));

		await vi.waitFor(() => {
			expect(toast.success).toHaveBeenCalledWith(
				"gpuSwitch.toastReady",
				expect.anything(),
			);
		});
		await new Promise((resolve) => setTimeout(resolve, 700));
		expect(toast.success).toHaveBeenCalledTimes(1);
		expect(useAppStore.getState().config?.device).toBe("cuda");
	});

	it("drops the Cancel action once the job has completed", async () => {
		renderHook(() => useCudaInstallToast(mockT));
		mockCall.mockImplementation((type: string) => {
			if (type === "get_gpu_capability") {
				if (activationFailed) {
					return Promise.resolve(
						capability({
							activation: { state: "failed", reason: "gpu_not_ready" },
						}),
					);
				}
				return Promise.resolve(
					capability({
						state: "gpu_ready",
						cuda_ready: true,
						stack_complete: true,
						active_backend_gpu_ready: true,
					}),
				);
			}
			if (type === "get_config") {
				return Promise.resolve({ device: "cuda", active_device: "cuda" });
			}
			return Promise.resolve({});
		});

		fire("cuda_progress", progress({ status: "completed" }));

		await vi.waitFor(() => {
			const descriptions = (
				toast.info as unknown as ReturnType<typeof vi.fn>
			).mock.calls.map((call) =>
				String((call[1] as Record<string, unknown>).description),
			);
			expect(descriptions).toContain("gpuSwitch.toastActivating");
		});
		const afterCompletion = (
			toast.info as unknown as ReturnType<typeof vi.fn>
		).mock.calls.filter((call) => {
			const description = String(
				(call[1] as Record<string, unknown>).description,
			);
			return (
				description === "gpuSwitch.toastRestarting" ||
				description === "gpuSwitch.toastActivating"
			);
		});
		expect(afterCompletion.length).toBeGreaterThan(0);
		for (const call of afterCompletion) {
			// No Cancel button: the download is already finished.
			expect("action" in (call[1] as Record<string, unknown>)).toBe(false);
		}
	});

	it("does not respawn when the install failed", async () => {
		renderHook(() => useCudaInstallToast(mockT));
		fire(
			"cuda_progress",
			progress({ status: "failed", error: "checksum_mismatch" }),
		);
		await vi.waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith(
				"gpuSwitch.errorChecksum",
				expect.anything(),
			);
		});
		expect(restartBackend).not.toHaveBeenCalled();
		expect(toast.dismiss).toHaveBeenCalledWith(CUDA_INSTALL_TOAST_ID);
	});

	it("keeps CPU and clears the sticky toast on cancel", async () => {
		renderHook(() => useCudaInstallToast(mockT));
		fire("cuda_progress", progress({ status: "cancelled" }));
		await vi.waitFor(() => {
			expect(toast.info).toHaveBeenCalledWith(
				"gpuSwitch.toastCancelled",
				expect.anything(),
			);
		});
		expect(restartBackend).not.toHaveBeenCalled();
		expect(toast.dismiss).toHaveBeenCalledWith(CUDA_INSTALL_TOAST_ID);
	});

	it("stays on CPU when the respawn command refuses", async () => {
		restartBackend.mockResolvedValue({ ok: false, reason: "no_host" });
		renderHook(() => useCudaInstallToast(mockT));
		fire("cuda_progress", progress({ status: "completed" }));
		await vi.waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith(
				"gpuSwitch.toastFailed",
				expect.anything(),
			);
		});
		expect(toast.success).not.toHaveBeenCalled();
	});
});

describe("useCudaInstallToast, reattach after a renderer reload", () => {
	it("restores the sticky toast for a job that is still running", async () => {
		mockCall.mockImplementation((type: string) => {
			if (type === "get_gpu_capability") {
				// Job in flight: `download.progress` is a live download.
				return Promise.resolve(
					capability({ download: { progress: progress() } }),
				);
			}
			return Promise.resolve({});
		});
		renderHook(() => useCudaInstallToast(mockT));
		await vi.waitFor(() => {
			expect(toast.info).toHaveBeenCalledTimes(1);
		});
		const [, options] = (toast.info as unknown as ReturnType<typeof vi.fn>).mock
			.calls[0] as [string, Record<string, unknown>];
		expect(options.id).toBe(CUDA_INSTALL_TOAST_ID);
		expect(options.duration).toBe(Number.POSITIVE_INFINITY);
	});

	it("explains and acknowledges a failure recorded while the window was closed", async () => {
		mockCall.mockImplementation((type: string) => {
			if (type === "get_gpu_capability") {
				return Promise.resolve(
					capability({
						activation: { state: "failed", reason: "persist_failed" },
					}),
				);
			}
			return Promise.resolve({});
		});
		renderHook(() => useCudaInstallToast(mockT));
		await vi.waitFor(() => {
			expect(toast.error).toHaveBeenCalled();
		});
		expect(mockCall).toHaveBeenCalledWith("ack_cuda_activation");
		// No toast for a job that is not running.
		expect(toast.info).not.toHaveBeenCalled();
	});
});

describe("pure helpers", () => {
	it("maps install error codes to catalog keys", () => {
		expect(installErrorKey("checksum_mismatch")).toBe(
			"gpuSwitch.errorChecksum",
		);
		expect(installErrorKey("size_mismatch")).toBe("gpuSwitch.errorSize");
		expect(installErrorKey("network")).toBe("gpuSwitch.errorNetwork");
		expect(installErrorKey("insufficient_disk")).toBe("gpuSwitch.errorDisk");
		expect(installErrorKey("unsupported_python")).toBe(
			"gpuSwitch.errorUnsupported",
		);
		expect(installErrorKey("something_new")).toBe("gpuSwitch.errorInternal");
	});

	it("formats an ETA compactly and blanks an unknown one", () => {
		expect(formatEta(42)).toBe("42s");
		expect(formatEta(114)).toBe("1m 54s");
		expect(formatEta(3900)).toBe("1h 05m");
		expect(formatEta(null)).toBe("");
		expect(formatEta(Number.NaN)).toBe("");
	});

	it("omits unknown fields instead of rendering placeholders", () => {
		const text = describeProgress(mockT, progress({ artifact: null }));
		expect(text).not.toContain("gpuSwitch.toastArtifact");
		expect(text).toContain("gpuSwitch.toastProgress");
	});
});
