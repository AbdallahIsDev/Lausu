// One compact plugin card in the Plugins grid: the initial tile, then the
// plugin name with its active/inactive status beside it. The whole card is
// a single button so it is mouse- and keyboard-activatable; the focus ring
// is the shared full-opacity `focus-visible:ring-1 ring-ring` contract
// (C-FOCUS-1/2/5) and is never removed or dimmed. The card carries NO hover
// treatment by design — only the focus ring responds.

import { useT } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import type { PluginInfo } from "@/types/plugins";
import { pluginIconSrc } from "../lib/pluginIcon";

interface PluginCardProps {
	plugin: PluginInfo;
	onOpen: (pluginId: string) => void;
}

/** First letter of the plugin name, used as the icon tile glyph. */
function initialOf(plugin: PluginInfo): string {
	const source = plugin.name.trim() || plugin.id.trim();
	// Take the first code point so a non-latin name is not split mid-surrogate.
	const first = Array.from(source)[0];
	return (first ?? "?").toLocaleUpperCase();
}

export function PluginCard({ plugin, onOpen }: PluginCardProps) {
	const t = useT();
	const iconSrc = pluginIconSrc(plugin.icon);
	const statusLabel = plugin.active
		? t("plugins.statusActive")
		: t("plugins.statusInactive");
	return (
		<button
			type="button"
			data-testid={`plugin-card-${plugin.id}`}
			aria-label={`${plugin.name} — ${statusLabel}`}
			onClick={() => onOpen(plugin.id)}
			className={cn(
				"flex items-center gap-3 rounded-lg border border-border/8 bg-surface-subtle p-2 text-start",
				// Full-opacity ring at the app's standard 1px thickness.
				"focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none",
			)}
		>
			{/* Icon tile. A plugin declares an icon IDENTIFIER, not a path: when
			    an asset ships for that id (see `../lib/pluginIcon`) it renders
			    bare — a real logo carries its own visual weight, so the chip
			    fill + border frame only the placeholder initial. A plugin
			    cannot point the renderer at an arbitrary file. */}
			<span
				aria-hidden="true"
				className={cn(
					"flex size-10 shrink-0 items-center justify-center rounded-lg text-sm font-semibold text-foreground",
					!iconSrc && "border border-border/8 bg-surface",
				)}
			>
				{iconSrc ? (
					<img src={iconSrc} alt="" className="size-8 object-contain" />
				) : (
					initialOf(plugin)
				)}
			</span>

			{/* Name over status. The description deliberately lives on the
			    detail view only (PluginDetail's PageHeading) so the card
			    stays a compact two-line row. */}
			<span className="flex min-w-0 flex-1 flex-col gap-1">
				<span className="truncate text-sm font-medium text-foreground">
					{plugin.name}
				</span>
				{/* Status row, same shape as the app's other status dots
				    (DiagnosticsSettingsSection / PrewarmAndUpdates): the
				    decorative dot first, then the state label. */}
				<span className="flex items-center gap-2">
					<span
						aria-hidden="true"
						data-slot="plugin-status-dot"
						className={cn(
							"size-1.5 shrink-0 rounded-full",
							// Green means "routing dictation through this plugin";
							// the muted grey is the untouched default.
							plugin.active ? "bg-success" : "bg-muted-foreground/40",
						)}
					/>
					<span className="text-xs text-muted-foreground">{statusLabel}</span>
				</span>
			</span>
		</button>
	);
}
