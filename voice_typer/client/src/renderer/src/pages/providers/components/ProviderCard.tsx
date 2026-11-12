// One provider card in the connections grid, matching the Plugins page card
// rhythm: icon, name, and (when the provider takes a key) one small action.
// The action opens the key dialog; no editor lives inside the card.

import { Button } from "@/components/ui/button";
import { useT } from "@/i18n/i18n";
import type { ProviderEntry } from "../lib/types";
import { ProviderGlyph } from "./ProviderBits";

interface ProviderCardProps {
	provider: ProviderEntry;
	onEditKey: () => void;
}

export function ProviderCard({ provider, onEditKey }: ProviderCardProps) {
	const t = useT();
	const keyed = provider.auth === "api_key";

	return (
		<div className="flex items-center gap-3 rounded-lg border border-border/8 bg-surface-subtle p-2">
			<ProviderGlyph local={provider.local} />
			<span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
				{provider.label}
			</span>
			{keyed ? (
				<Button
					size="sm"
					variant="ghost"
					className="shrink-0 px-2.5"
					onClick={onEditKey}
				>
					{provider.key.configured
						? t("providers.keyEdit")
						: t("providers.keyAdd")}
				</Button>
			) : null}
		</div>
	);
}
