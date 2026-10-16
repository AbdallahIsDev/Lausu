// "Save as preset" dialog for custom microphone presets.
// Name input with duplicate detection; Enter submits, Escape cancels.

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { t } from "@/i18n/i18n";
import { cn } from "@/lib/utils";

export interface SavePresetDialogProps {
	open: boolean;
	takenNames: readonly string[];
	onSave: (name: string) => void;
	onClose: () => void;
}

export function SavePresetDialog({
	open,
	takenNames,
	onSave,
	onClose,
}: SavePresetDialogProps) {
	const [name, setName] = useState("");
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		if (open) {
			setName("");
			setError(null);
		}
	}, [open]);

	const taken =
		name.trim() !== "" &&
		takenNames.some((n) => n.toLowerCase() === name.trim().toLowerCase());

	const submit = () => {
		const trimmed = name.trim();
		if (trimmed === "") return;
		if (taken) {
			setError(t("microphoneTest.savePresetNameTaken"));
			return;
		}
		onSave(trimmed);
	};

	return (
		<Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
			<DialogContent className="max-w-sm">
				<DialogHeader>
					<DialogTitle>{t("microphoneTest.savePresetTitle")}</DialogTitle>
					<DialogDescription>
						{t("microphoneTest.savePresetHint")}
					</DialogDescription>
				</DialogHeader>
				<form
					onSubmit={(e) => {
						e.preventDefault();
						submit();
					}}
					className="flex flex-col gap-2"
				>
					<label
						htmlFor="save-preset-name"
						className="text-sm font-medium text-foreground"
					>
						{t("microphoneTest.savePresetName")}
					</label>
					<Input
						id="save-preset-name"
						value={name}
						maxLength={80}
						placeholder={t("microphoneTest.savePresetPlaceholder")}
						onChange={(e) => {
							setName(e.target.value);
							setError(null);
						}}
						autoFocus
						aria-invalid={error !== null}
					/>
					{error && (
						<p className="text-xs text-destructive" role="alert">
							{error}
						</p>
					)}
					<DialogFooter className={cn("gap-2")}>
						<Button type="button" variant="ghost" onClick={onClose}>
							{t("common.cancel")}
						</Button>
						<Button type="submit" disabled={name.trim() === ""}>
							{t("microphoneTest.savePresetSave")}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
