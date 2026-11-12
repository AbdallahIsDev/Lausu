import { toast } from "sonner";
import { HotkeyChips } from "./HotkeyChips";

/** One id so repeated capture errors replace each other instead of stacking. */
export const HOTKEY_ERROR_TOAST_ID = "hotkey-capture-error";

const QUOTE_PAIRS: ReadonlyArray<readonly [string, string]> = [
	['"', '"'],
	["'", "'"],
	["\u201c", "\u201d"],
	["\u00ab", "\u00bb"],
];

function splitAroundHotkey(
	message: string,
	hotkeyLabel: string,
): { before: string; after: string } | null {
	const index = message.indexOf(hotkeyLabel);
	if (index === -1) return null;
	let start = index;
	let end = index + hotkeyLabel.length;
	const open = message[start - 1];
	const close = message[end];
	if (
		open !== undefined &&
		close !== undefined &&
		QUOTE_PAIRS.some(
			([opening, closing]) => open === opening && close === closing,
		)
	) {
		start -= 1;
		end += 1;
	}
	return { before: message.slice(0, start), after: message.slice(end) };
}

interface HotkeyErrorToastMessageProps {
	message: string;
	hotkeyLabel?: string;
}

/**
 * Toast body for a rejected hotkey: the message stays verbatim except the
 * attempted shortcut, which renders as design-system keycaps.
 */
export function HotkeyErrorToastMessage({
	message,
	hotkeyLabel,
}: HotkeyErrorToastMessageProps) {
	const label = hotkeyLabel?.trim() ?? "";
	const split = label ? splitAroundHotkey(message, label) : null;
	return (
		<span className="text-destructive">
			{split ? (
				<>
					{split.before}
					<HotkeyChips keys={label} />
					{split.after}
				</>
			) : (
				message
			)}
		</span>
	);
}

export function showHotkeyErrorToast(
	message: string,
	hotkeyLabel?: string,
): void {
	toast.error(
		<HotkeyErrorToastMessage message={message} hotkeyLabel={hotkeyLabel} />,
		{ id: HOTKEY_ERROR_TOAST_ID },
	);
}

export function dismissHotkeyErrorToast(): void {
	toast.dismiss(HOTKEY_ERROR_TOAST_ID);
}
