/**
 * ModelActionButtons — the row action buttons shared by the local ASR model
 * rows and the local TTS engine rows.
 *
 * One visual language for "download this pack", "make this the active model"
 * and "this IS the active model": identical variants, identical fixed 96px
 * width, identical left alignment and 12px icons. A TTS row therefore reads
 * exactly like an ASR row instead of inventing its own button shapes.
 *
 * `TestActionButton` is the row-level "render a sample" action; it only exists
 * on rows that can actually run (a downloaded engine), never disabled-as-a-
 * placeholder for one that cannot.
 */

import {
	CircleIcon,
	Download01Icon,
	Loading03Icon,
	PlayIcon,
	Tick02Icon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n/i18n";
import { cn } from "@/lib/utils";

/** Fixed width shared by every action button so rows line up. */
export const ACTION_BUTTON_WIDTH = "w-24";
/** Content starts at the same left position in every row. */
export const ACTION_BUTTON_ALIGN = "justify-start";
/** Compact icon that reads proportional to the 11px label text. */
export const ACTION_ICON_CLASS = "h-3 w-3";

export interface DownloadActionButtonProps {
	/** Human size label ("1.8 GB") shown next to the download glyph. */
	sizeLabel: string;
	/** Transfer in flight: spinner + localized "Downloading…". */
	busy?: boolean;
	/** Request accepted but waiting behind another transfer. */
	queued?: boolean;
	/** Position tooltip for the queued state. */
	queuedLabel?: string;
	disabled?: boolean;
	ariaLabel: string;
	title?: string;
	onClick: () => void;
}

export function DownloadActionButton({
	sizeLabel,
	busy = false,
	queued = false,
	queuedLabel,
	disabled,
	ariaLabel,
	title,
	onClick,
}: DownloadActionButtonProps) {
	return (
		<Button
			variant="outline"
			size="sm"
			// The fixed width belongs to the at-rest label: the in-flight and
			// queued states are label swaps, so they size to their content
			// rather than truncating inside a disabled button.
			className={cn(
				"gap-2 text-xs whitespace-nowrap",
				!busy && !queued && ACTION_BUTTON_WIDTH,
				ACTION_BUTTON_ALIGN,
			)}
			onClick={onClick}
			disabled={disabled}
			aria-busy={busy}
			aria-label={ariaLabel}
			title={title}
		>
			<HugeiconsIcon
				icon={busy ? Loading03Icon : Download01Icon}
				strokeWidth={2}
				className={cn(
					busy ? "h-3.5 w-3.5" : ACTION_ICON_CLASS,
					busy && "animate-spin",
				)}
			/>
			{busy ? (
				t("models.downloading")
			) : queued ? (
				(queuedLabel ?? t("models.download.queued"))
			) : (
				<span className="font-medium">{sizeLabel}</span>
			)}
		</Button>
	);
}

export interface SelectActionButtonProps {
	/** Selection in flight: spinner + localized "Selecting…". */
	busy?: boolean;
	ariaLabel: string;
	onClick: () => void;
}

export function SelectActionButton({
	busy = false,
	ariaLabel,
	onClick,
}: SelectActionButtonProps) {
	return (
		<Button
			variant={busy ? "secondary" : "outline"}
			size="sm"
			// The fixed width keeps the row stable when the spinner swaps in.
			className={cn("gap-2 text-xs whitespace-nowrap", ACTION_BUTTON_WIDTH)}
			onClick={onClick}
			disabled={busy}
			aria-busy={busy}
			aria-label={ariaLabel}
		>
			{/* A neutral circle, never a tick: a tick here would read as
			    "already selected" rather than "select this". */}
			<HugeiconsIcon
				icon={busy ? Loading03Icon : CircleIcon}
				strokeWidth={2}
				className={cn(ACTION_ICON_CLASS, busy && "animate-spin")}
			/>
			{busy ? t("models.selecting") : t("models.select")}
		</Button>
	);
}

export interface ActiveActionButtonProps {
	ariaLabel: string;
}

export function ActiveActionButton({ ariaLabel }: ActiveActionButtonProps) {
	return (
		<Button
			variant="secondary"
			size="sm"
			className="gap-2 cursor-default opacity-60 h-fit px-3 py-1.5 text-xs whitespace-nowrap w-24 justify-start"
			disabled
			aria-label={ariaLabel}
		>
			<HugeiconsIcon
				icon={Tick02Icon}
				strokeWidth={2}
				className={ACTION_ICON_CLASS}
			/>
			{t("models.active")}
		</Button>
	);
}

export interface TestActionButtonProps {
	/** Sample render in flight: spinner + localized "Generating speech…". */
	busy?: boolean;
	disabled?: boolean;
	onClick: () => void;
}

export function TestActionButton({
	busy = false,
	disabled,
	onClick,
}: TestActionButtonProps) {
	return (
		<Button
			variant="outline"
			size="sm"
			className="gap-2 text-xs whitespace-nowrap"
			onClick={onClick}
			disabled={disabled || busy}
			aria-busy={busy}
			aria-label={t("tts.testVoice")}
		>
			<HugeiconsIcon
				icon={busy ? Loading03Icon : PlayIcon}
				strokeWidth={2}
				className={cn(ACTION_ICON_CLASS, busy && "animate-spin")}
			/>
			{busy ? t("tts.working") : t("tts.testVoice")}
		</Button>
	);
}
