// Active speech model caption for the sidebar.
// One line, directly above the CPU/GPU switch, so the running model is
// identifiable from any page without opening Models. Truncated (full name
// in `title`) to keep the rail width stable; hidden in the icon rail where
// there is no room for text, mirroring DeviceToggle.

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
