// Active speech-engine caption: a state DOT plus the engine name (plugin when a
// plugin owns dictation). Reads only engine-identity fields + recording state —
// never `device`/`gpu_available`, so a missing or broken DeviceToggle cannot
// blank or hide it (C-UI-10).

import { useT } from "@/i18n/i18n";
import { statusColorFor } from "@/lib/dictationStatus";
import { activeEngine } from "@/lib/utils/activeEngine";
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
	const engineKind = useAppStore((s) => activeEngine(s.config).kind);
	const state = useAppStore((s) => s.recordingState);
	const lastError = useAppStore((s) => s.lastError);

	const engine =
		engineKind === "plugin"
			? pluginName
			: engineKind === "local"
				? modelLabel
				: t("models.noModelSelected");
	if (collapsed) return null;
	// LOADING only describes a LOCAL model load. A plugin (or no engine at all)
	// cannot be loading a local model — a stale startup push must not paint a
	// yellow dot over the plugin caption (server state is the authority).
	const dotState =
		engineKind === "local" ? state : state === "loading" ? "idle" : state;
	const color = statusColorFor(dotState, !!lastError);
	// The dot is decorative; the state word stays reachable for assistive
	// tech (and on hover) instead of living in the visible row.
	const stateLabel = t(`trayState.${dotState}`);

	return (
		<div
			className="flex items-center gap-2 px-2 py-1"
			title={`${engine} · ${stateLabel}`}
			data-testid="sidebar-active-model"
		>
			<span
				aria-hidden
				data-testid="sidebar-active-model-dot"
				className="h-2 w-2 shrink-0 rounded-full transition-colors duration-300"
				style={{ backgroundColor: color }}
			/>
			<span className="min-w-0 truncate text-xs text-muted-foreground">
				{engine}
			</span>
			<span className="sr-only">{stateLabel}</span>
		</div>
	);
}
