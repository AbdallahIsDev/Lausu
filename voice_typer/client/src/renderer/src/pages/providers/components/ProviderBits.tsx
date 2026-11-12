// Identity mark shared by the provider cards: a cloud for remote providers, a
// chip for on-device ones. Deliberately icon-only — no status or capability
// labels live on the card.

import { CloudIcon, CpuIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { cn } from "@/lib/utils";

export function ProviderGlyph({
	local,
	size = "md",
}: {
	local: boolean;
	size?: "sm" | "md";
}) {
	return (
		<span
			className={cn(
				"flex shrink-0 items-center justify-center rounded-full bg-border/5 text-muted-foreground",
				size === "sm" ? "size-7" : "size-9",
			)}
		>
			<HugeiconsIcon
				icon={local ? CpuIcon : CloudIcon}
				strokeWidth={1.6}
				aria-hidden="true"
				className={size === "sm" ? "size-3.5" : "size-4"}
			/>
		</span>
	);
}
