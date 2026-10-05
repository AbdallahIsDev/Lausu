// One square plugin card in the Plugins grid. The whole card is a single
// button so it is mouse- and keyboard-activatable; the focus ring is the
// shared full-opacity `focus-visible:ring-1 ring-ring` contract
// (C-FOCUS-1/2/5) and is never removed or dimmed.

import { useT } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import type { PluginInfo } from "@/types/plugins";

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
				"flex aspect-square flex-col gap-3 rounded-lg border border-border/8 bg-surface-subtle p-4 text-start",
				"transition-[background-color,border-color] duration-200 ease-out",
				"hover:border-border/15 hover:bg-surface",
				// Full-opacity ring at the app's standard 1px thickness.
				"focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none",
			)}
		>
			{/* Initial tile. A plugin declares an icon IDENTIFIER, and no icon
			    asset ships with the app, so the name's first letter is the
			    glyph — an image reference could only ever render broken. */}
			<span
				aria-hidden="true"
				className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border/8 bg-surface text-sm font-semibold text-foreground"
			>
				{initialOf(plugin)}
			</span>

			<span className="flex min-w-0 flex-col gap-1">
				<span className="truncate text-sm font-medium text-foreground">
					{plugin.name}
				</span>
				{plugin.description && (
					<span className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
						{plugin.description}
					</span>
				)}
			</span>

			{/* Status indicator: a filled dot + label. `ms-auto` keeps it at
			    the row's inline-end edge (RTL-safe), the card's own `gap`
			    spaces it from the label above. */}
			<span className="mt-auto flex items-center gap-2">
				<span
					aria-hidden="true"
					className={cn(
						"size-1.5 shrink-0 rounded-full",
						plugin.active ? "bg-primary" : "bg-border",
					)}
				/>
				<span className="text-xs text-muted-foreground">{statusLabel}</span>
			</span>
		</button>
	);
}
