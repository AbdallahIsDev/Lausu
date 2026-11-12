import { Mic02Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useRef } from "react";
import { cn } from "@/lib/utils";

interface PushToTalkButtonProps {
	/** True while the backend reports `phase: "listening"`. */
	listening: boolean;
	/** A turn is in flight or the conversation is not configured yet. */
	disabled: boolean;
	label: string;
	onPressStart: () => void;
	onPressEnd: () => void;
}

/**
 * Hold-to-talk control. Mirrors the Home mic button's visual contract (same
 * accent fill, same destructive "capturing now" red) because the interaction
 * language is the app's, only the trigger differs: hold instead of toggle.
 * The idle glow and the animated capture ring are deliberately absent: the
 * button is the page's only accent, so it does not need to pulse for attention.
 *
 * Pointer capture keeps `pointerup`/`pointercancel` coming even when the
 * pointer leaves the button, and `onLostPointerCapture` covers a capture the
 * browser drops, so the release always reaches `chat_listen_stop`. Space/Enter
 * are handled explicitly (a native `<button>` would only fire `click`), with
 * `preventDefault` to suppress that synthetic activation and the page scroll.
 */
export function PushToTalkButton({
	listening,
	disabled,
	label,
	onPressStart,
	onPressEnd,
}: PushToTalkButtonProps) {
	const heldRef = useRef(false);

	const begin = () => {
		if (disabled || heldRef.current) return;
		heldRef.current = true;
		onPressStart();
	};
	const end = () => {
		if (!heldRef.current) return;
		heldRef.current = false;
		onPressEnd();
	};

	return (
		<div className="relative">
			{listening ? (
				<span
					aria-hidden="true"
					className="absolute -inset-2 rounded-full bg-destructive/15"
				/>
			) : null}
			<button
				type="button"
				aria-pressed={listening}
				aria-disabled={disabled || undefined}
				aria-label={label}
				title={label}
				data-testid="chat-push-to-talk"
				onPointerDown={(event) => {
					if (event.pointerType === "mouse" && event.button !== 0) return;
					// Capture keeps pointerup/pointercancel coming when the
					// pointer leaves the button. jsdom has no implementation,
					// so the call is optional and its failure is ignored: the
					// release path still listens on the element itself.
					try {
						event.currentTarget.setPointerCapture(event.pointerId);
					} catch {
						// Not supported by this engine (jsdom).
					}
					begin();
				}}
				onPointerUp={end}
				onPointerCancel={end}
				onLostPointerCapture={end}
				onKeyDown={(event) => {
					if (event.key !== " " && event.key !== "Enter") return;
					event.preventDefault();
					if (event.repeat) return;
					begin();
				}}
				onKeyUp={(event) => {
					if (event.key !== " " && event.key !== "Enter") return;
					event.preventDefault();
					end();
				}}
				onBlur={end}
				className={cn(
					"press-scale relative z-10 flex h-21 w-21 touch-none select-none items-center justify-center rounded-full",
					"transition-colors duration-200 ease-out outline-hidden",
					"focus-visible:ring-1 focus-visible:ring-ring",
					disabled
						? "cursor-not-allowed bg-primary/40"
						: listening
							? "bg-destructive"
							: "bg-primary hover:bg-primary/90",
				)}
			>
				<HugeiconsIcon
					icon={Mic02Icon}
					strokeWidth={1.625}
					className={cn(
						"h-8 w-8",
						listening
							? "text-(--destructive-foreground)"
							: "text-(--primary-foreground)",
					)}
				/>
			</button>
		</div>
	);
}
