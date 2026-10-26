// Active speech model caption for the sidebar.
// One line, directly above the CPU/GPU switch, so the running model is
// identifiable from any page without opening Models. Truncated (full name
// in `title`) to keep the rail width stable; hidden in the icon rail where
// there is no room for text.
//
// INDEPENDENCE CONTRACT: this caption reads ONLY speech-model fields
// (`asr_backend`, `model_size`, `cloud_provider`, `cloud_model`). It must
// never consult `device` / `gpu_available`, and it must never be gated on
// DeviceToggle rendering. The device switch is an optional control that can
// be absent (no GPU), lagging (set_config round-trip), or broken; none of
// those states say anything about which model is running, so none of them
// may hide this line. The caption is the sidebar half of what the tray
// tooltip already reports.

import { formatActiveModel } from "@/lib/utils/configDisplay";
import { useAppStore } from "@/stores/appStore";

export function SidebarActiveModel({
	collapsed = false,
}: {
	collapsed?: boolean;
}) {
	// Selector returns a primitive, so unrelated config writes never
	// re-render this caption.
	const label = useAppStore((s) => formatActiveModel(s.config));

	if (collapsed || label === "") return null;

	return (
		<p
			className="truncate px-2 py-1 text-xs text-muted-foreground"
			title={label}
			data-testid="sidebar-active-model"
		>
			{label}
		</p>
	);
}
