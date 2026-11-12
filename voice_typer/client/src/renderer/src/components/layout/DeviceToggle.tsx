import { useCallback, useState } from "react";
import { GpuRequestDialog } from "@/components/gpu/GpuRequestDialog";
import { ToggleGroup } from "@/components/ui/toggle-group";
import { isRunningStatus } from "@/hooks/useCudaInstallToast";
import { usePython, usePythonEvent } from "@/hooks/usePython";
import { t } from "@/i18n/i18n";
import { useAppStore } from "@/stores/appStore";

type ComputeDevice = "cpu" | "cuda";

function asComputeDevice(value: unknown): ComputeDevice | null {
	return value === "cpu" || value === "cuda" ? value : null;
}

/**
 * Sidebar CPU/GPU switch. Renders only when expanded AND the machine has
 * NVIDIA hardware (`gpu_hardware_present`, or `gpu_available` on older
 * sidecars); on a machine with no NVIDIA adapter the toggle stays hidden
 * and CPU is the fixed default.
 *
 * Visibility and readiness are separate questions:
 *
 * * visible — an NVIDIA adapter is enumerated, even if its driver or the
 *   CUDA runtime is missing. Without that split a driver-only machine
 *   would have no way to learn why GPU is unavailable.
 * * ready — the capability state is `gpu_ready`. When it is not, clicking
 *   the GPU pill opens `GpuRequestDialog` (explain + Download / Stay on
 *   CPU) instead of writing `set_config`. Nothing is persisted until the
 *   respawned sidecar proves the stack and writes `cuda` itself.
 *
 * The checked pill is `active_device` (read-only: what the LOADED engine
 * reports), never the persisted `device` REQUEST. An engine can end up on
 * CPU while the request still says GPU (CPU-only onnxruntime build,
 * forced-CPU load, worker fallback), and showing the request would claim
 * a GPU that is not serving (C-UI-15). Clicking still writes the request
 * through `set_config`; the pill moves when the backend reports the new
 * engine's effective device.
 */
export function DeviceToggle({ collapsed = false }: { collapsed?: boolean }) {
	const requested = useAppStore((s) => s.config?.device);
	const active = useAppStore((s) => s.config?.active_device);
	const gpuAvailable = useAppStore((s) => s.config?.gpu_available);
	const hardwarePresent = useAppStore((s) => s.config?.gpu_hardware_present);
	const capability = useAppStore((s) => s.config?.gpu_capability);
	// A selected plugin owns dictation end to end (its own browser, its own
	// audio path), so the CPU/GPU switch is meaningless: the local model is
	// not running. The caption above carries the plugin name + state instead.
	const pluginActive = useAppStore(
		(s) => (s.config?.active_plugin ?? "") !== "",
	);
	const { call } = usePython();
	const [dialogOpen, setDialogOpen] = useState(false);

	// `config_changed` from set_config carries only the applied request; the
	// effective device arrives on load/fallback pushes. Merge it so the pill
	// tracks the engine without a get_config round-trip.
	usePythonEvent("config_changed", (data) => {
		const next = asComputeDevice(data?.active_device);
		if (next !== null) {
			useAppStore.getState().mergeConfig({ active_device: next });
		}
	});

	const capabilityState = capability?.state;
	// No NVIDIA adapter → no GPU affordance at all (owner decision).
	// Older sidecars have no capability report; fall back to the two flat
	// flags so the toggle keeps its pre-CUDA behaviour.
	const visible = capability
		? capabilityState !== "no_nvidia_gpu" &&
			capability.hardware_present === true
		: gpuAvailable === true || hardwarePresent === true;

	// Readiness is per BACKEND, never the global `state`: `state` is
	// `gpu_ready` when ANY backend works, so on a machine where CTranslate2
	// sees the GPU and the installed onnxruntime is the CPU-only wheel, a
	// Parakeet user would get a silent CPU fallback with no modal. The
	// matching `backends` entry is the authority; `active_backend_gpu_ready`
	// is the same value pre-computed by the sidecar.
	const activeEntry = capability?.backends?.find(
		(entry) => entry.name === capability?.active_backend,
	);
	const activeCapable = activeEntry ? activeEntry.gpu_capable !== false : true;
	const activeReady = activeEntry
		? activeEntry.gpu_ready === true
		: capability?.active_backend_gpu_ready === true;
	// A backend that cannot do GPU at all (Qwen is pinned to CPU by design)
	// makes `device` a global preference, not a claim about this engine.
	const needsCuda = activeCapable && !activeReady;

	const handleChange = useCallback(
		(next: ComputeDevice) => {
			if (next === "cuda") {
				// A job in flight owns the device: the sticky toast reports
				// progress, and the switch happens on activation, not now.
				if (isRunningStatus(capability?.download?.progress?.status)) return;
				// Not proven ready for THIS backend → explain instead of
				// persisting a request it cannot serve. Legacy sidecars (no
				// capability) keep the old write-through behaviour.
				const ready = capability ? !needsCuda : gpuAvailable === true;
				if (!ready) {
					setDialogOpen(true);
					return;
				}
			}
			// Clicking the pill that is both requested and running is a no-op;
			// any other click is a request, including re-requesting the GPU
			// while a CPU fallback serves the current engine.
			if (next === requested && next === (active ?? requested)) return;
			useAppStore.getState().mergeConfig({ device: next });
			call("set_config", { device: next }).catch((err) => {
				console.warn("[renderer:DeviceToggle] set_config device failed:", err);
				useAppStore.getState().mergeConfig({ device: requested });
			});
		},
		[active, call, capability, gpuAvailable, needsCuda, requested],
	);

	if (collapsed || pluginActive || !visible) return null;
	const requestedDevice = asComputeDevice(requested);
	if (requestedDevice === null) return null;
	const value = asComputeDevice(active) ?? requestedDevice;

	return (
		<>
			<ToggleGroup<ComputeDevice>
				options={[
					{ value: "cpu", label: t("computeDevice.cpu") },
					{ value: "cuda", label: t("computeDevice.gpu") },
				]}
				value={value}
				onChange={handleChange}
				ariaLabel={t("computeDevice.ariaLabel")}
				className="w-full mb-4"
			/>
			<GpuRequestDialog open={dialogOpen} onOpenChange={setDialogOpen} />
		</>
	);
}
