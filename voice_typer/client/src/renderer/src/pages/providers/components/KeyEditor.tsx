// The credential editor shared by every layout: paste field, save, test and
// clear. Outcomes surface as in-app notifications, so no verdict text lives
// under this field. Callers own open/closed state; this component only owns
// the controls.

import { Delete02Icon, RefreshIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useT } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import type { ProviderEntry } from "../lib/types";

export interface KeyEditorProps {
	provider: ProviderEntry;
	draft: string;
	busy: boolean;
	id?: string;
	className?: string;
	onDraftChange: (value: string) => void;
	onSave: () => void;
	onTest: () => void;
	onClear: () => void;
}

export function KeyEditor({
	provider,
	draft,
	busy,
	id,
	className,
	onDraftChange,
	onSave,
	onTest,
	onClear,
}: KeyEditorProps) {
	const t = useT();
	return (
		<div id={id} className={cn("flex flex-col gap-3", className)}>
			<div className="flex flex-wrap items-center gap-2">
				<Input
					type="password"
					className="min-w-40 max-w-xs flex-1"
					value={draft}
					placeholder={t("providers.keysPlaceholder")}
					aria-label={t("providers.keyInputAria", {
						provider: provider.label,
					})}
					onChange={(event) => onDraftChange(event.target.value)}
				/>
				<Button size="sm" disabled={busy || !draft.trim()} onClick={onSave}>
					{t("providers.keySave")}
				</Button>
			</div>
			<div className="flex flex-wrap items-center gap-2">
				{/* The backend refuses a keyed test without a key, so the
				    control stays disabled instead of offering a doomed action. */}
				<Button
					size="sm"
					variant="outline"
					disabled={busy || !provider.key.configured}
					onClick={onTest}
				>
					<HugeiconsIcon
						icon={RefreshIcon}
						strokeWidth={1.8}
						aria-hidden="true"
						className="size-3.5"
					/>
					{t("providers.keyTest")}
				</Button>
				<Button
					size="sm"
					variant="ghost"
					disabled={busy || !provider.key.configured}
					onClick={onClear}
				>
					<HugeiconsIcon
						icon={Delete02Icon}
						strokeWidth={1.8}
						aria-hidden="true"
						className="size-3.5"
					/>
					{t("providers.keyClear")}
				</Button>
			</div>
		</div>
	);
}
