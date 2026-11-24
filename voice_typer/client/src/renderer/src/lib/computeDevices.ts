// The compute-device vocabulary shared by the sidebar switch, config
// types and the IPC validator. The native ASR runner advertises
// `cpu`/`vulkan`/`cuda` (see worker/asr_runner/runner.py); `cuda` remains
// valid for configs written by older builds. `auto`/`metal`/`rocm` are
// runner request values, not persisted app settings.

export const COMPUTE_DEVICE_VALUES = ["cpu", "vulkan", "cuda"] as const;

export type ComputeDevice = (typeof COMPUTE_DEVICE_VALUES)[number];

export function asComputeDevice(value: unknown): ComputeDevice | null {
	return COMPUTE_DEVICE_VALUES.find((device) => device === value) ?? null;
}

export function isGpuDevice(value: ComputeDevice | null | undefined): boolean {
	return value === "vulkan" || value === "cuda";
}
