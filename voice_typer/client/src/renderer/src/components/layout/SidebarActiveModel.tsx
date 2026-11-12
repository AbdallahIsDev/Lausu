// Active speech-engine caption for the sidebar.
// One line, directly above the CPU/GPU switch, so the running engine is
// identifiable from any page without opening Models. Truncated (full name
// in `title`) to keep the rail width stable; hidden in the icon rail where
// there is no room for text.
//
// A selected PLUGIN owns dictation, so the caption names the plugin instead
// of the local model (the model is not transcribing) and appends the live
// recording state — that is the sidebar half of "this is the engine in use".
//
// INDEPENDENCE CONTRACT: this caption reads ONLY speech-engine identity
// fields (`asr_backend`, `model_size`, `cloud_provider`, `cloud_model`,
// `active_plugin_name`) plus the recording state. It must never consult
// `device` / `gpu_available`, and it must never be gated on DeviceToggle
// rendering. The device switch is an optional control that can be absent
// (no GPU), lagging (set_config round-trip), or broken; none of those states
// say anything about which engine is running, so none of them may hide this
// line. The caption is the sidebar half of what the tray tooltip reports.

import { useT } from "@/i18n/i18n";
import { formatActiveModel } from "@/lib/utils/configDisplay";
import { useAppStore } from "@/stores/appStore";

export function SidebarActiveModel({
	collapsed = false,
}: {
	collapsed?: boolean;
}) {
	const t = useT();
	// Selectors return primitives, so unrelated config writes never
	// re-render this caption.
	const pluginName = useAppStore((s) => s.config?.active_plugin_name ?? "");
	const modelLabel = useAppStore((s) => formatActiveModel(s.config));
	const recording = useAppStore((s) => s.recordingState === "recording");

	const engine = pluginName || modelLabel;
	if (collapsed || engine === "") return null;
	const label = recording ? `${engine} · ${t("trayState.recording")}` : engine;

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
