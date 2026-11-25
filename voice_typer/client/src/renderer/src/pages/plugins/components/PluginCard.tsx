// One compact plugin card: icon tile, name, Active/Inactive status and the
// activation switch on the far right. The switch is a SIBLING of the card
// body — nesting a Radix Switch (<button>) inside a <button> would be
// invalid markup and would swallow the click. The whole card stays a
// non-interactive surface; activation is the only action it offers.

import { Switch } from "@/components/ui/switch";
import { useT } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import type { PluginInfo } from "@/types/plugins";
import { pluginIconNeedsInvert, pluginIconSrc } from "../lib/pluginIcon";

interface PluginCardProps {
	plugin: PluginInfo;
	onActivate: (pluginId: string, active: boolean) => void;
}

/** First letter of the plugin name, used as the icon tile glyph. */
function initialOf(plugin: PluginInfo): string {
	const source = plugin.name.trim() || plugin.id.trim();
	// Take the first code point so a non-latin name is not split mid-surrogate.
	const first = Array.from(source)[0];
	return (first ?? "?").toLocaleUpperCase();
}

export function PluginCard({ plugin, onActivate }: PluginCardProps) {
	const t = useT();
	const iconSrc = pluginIconSrc(plugin.icon);
	const statusLabel = plugin.active
		? t("plugins.statusActive")
		: t("plugins.statusInactive");
	return (
		<div
			data-testid={`plugin-card-${plugin.id}`}
			className="flex items-center gap-3 rounded-lg border border-border/8 bg-surface-subtle px-2 py-2"
		>
			{/* Icon tile. A plugin declares an icon IDENTIFIER, not a path: when
			    an asset ships for that id it renders bare — the chip fill and
			    border frame only the placeholder initial. */}
			<span
				aria-hidden="true"
				className={cn(
					"flex size-10 shrink-0 items-center justify-center rounded-lg text-sm font-medium text-foreground",
					!iconSrc && "border border-border/8 bg-surface",
				)}
			>
				{iconSrc ? (
					<img
						src={iconSrc}
						alt=""
						className={
							pluginIconNeedsInvert(plugin.icon)
								? "size-8 object-contain dark:invert"
								: "size-8 object-contain"
						}
					/>
				) : (
					initialOf(plugin)
				)}
			</span>

			{/* Name over status. The description lives on the Plugins page's
			    shared-settings section, not on the card. */}
			<span className="flex min-w-0 flex-1 flex-col gap-1">
				<span className="truncate text-sm font-medium text-foreground">
					{plugin.name}
				</span>
				<span className="flex items-center gap-2">
					<span
						aria-hidden="true"
						data-slot="plugin-status-dot"
						className={cn(
							"size-1.5 shrink-0 rounded-full",
							plugin.active ? "bg-success" : "bg-muted-foreground/40",
						)}
					/>
					<span className="text-xs text-muted-foreground">{statusLabel}</span>
				</span>
			</span>

			<Switch
				checked={plugin.active}
				onCheckedChange={(checked) => onActivate(plugin.id, checked)}
				aria-label={`${t("plugins.activateAria")}: ${plugin.name}`}
				data-testid={`plugin-activate-switch-${plugin.id}`}
			/>
		</div>
	);
}
