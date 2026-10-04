import { ToggleGroup } from "@/components/ui/toggle-group";
import { usePython } from "@/hooks/usePython";
import { t } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/appStore";

type ComputeDevice = "cpu" | "cuda";

/**
 * Sidebar CPU/GPU switch. Renders only when expanded AND the backend
 * reports a CUDA-capable GPU (`gpu_available` from `get_config`); on
 * CPU-only machines the toggle stays hidden and CPU is the fixed
 * default. The value rides the shared config snapshot, so a backend
 * GPU→CPU fallback (published as `config_changed`) shifts the active
 * pill without a round-trip.
 */
export function DeviceToggle({ collapsed = false }: { collapsed?: boolean }) {
	const device = useAppStore((s) => s.config?.device);
	const gpuAvailable = useAppStore((s) => s.config?.gpu_available);
	const { call } = usePython();

	if (collapsed || gpuAvailable !== true) return null;
	if (device !== "cpu" && device !== "cuda") return null;
	const value: ComputeDevice = device;

	const handleChange = (next: ComputeDevice) => {
		if (next === value) return;
		useAppStore.getState().mergeConfig({ device: next });
		call("set_config", { device: next }).catch((err) => {
			console.warn("[renderer:DeviceToggle] set_config device failed:", err);
			useAppStore.getState().mergeConfig({ device: value });
		});
	};

	return (
		<div className={cn("flex flex-col items-center gap-1 px-1")}>
			<ToggleGroup<ComputeDevice>
				options={[
					{ value: "cpu", label: t("computeDevice.cpu") },
					{ value: "cuda", label: t("computeDevice.gpu") },
				]}
				value={value}
				onChange={handleChange}
				ariaLabel={t("computeDevice.ariaLabel")}
				context="sidebar"
				className="w-full"
			/>
		</div>
	);
}
