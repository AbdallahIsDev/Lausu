// Key dialog for one provider. The card carries only the trigger; the
// credential editor lives here so a modal owns that surface.

import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { useT } from "@/i18n/i18n";
import type { ProviderEntry } from "../lib/types";
import { KeyEditor } from "./KeyEditor";

export interface ProviderKeyDialogProps {
	provider: ProviderEntry;
	draft: string;
	busy: boolean;
	onDraftChange: (value: string) => void;
	onSave: () => void;
	onTest: () => void;
	onClear: () => void;
	onClose: () => void;
}

export function ProviderKeyDialog({
	provider,
	draft,
	busy,
	onDraftChange,
	onSave,
	onTest,
	onClear,
	onClose,
}: ProviderKeyDialogProps) {
	const t = useT();
	return (
		<Dialog open onOpenChange={(open) => !open && onClose()}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>{provider.label}</DialogTitle>
					<DialogDescription>{t("providers.keyDialogHint")}</DialogDescription>
				</DialogHeader>
				<KeyEditor
					provider={provider}
					draft={draft}
					busy={busy}
					onDraftChange={onDraftChange}
					onSave={onSave}
					onTest={onTest}
					onClear={onClear}
				/>
			</DialogContent>
		</Dialog>
	);
}
