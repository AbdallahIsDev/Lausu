import { cn } from "@/lib/utils";
import type { ChatMessageView } from "../hooks/useChatConversation";

interface ChatMessageListProps {
	messages: ChatMessageView[];
	/** Accessible name for the transcript region. */
	label: string;
	roleLabels: Record<ChatMessageView["role"], string>;
	/** Rendered when the thread is empty. */
	empty: React.ReactNode;
}

/**
 * The transcript: user turns right, assistant turns left, oldest first.
 *
 * `aria-live="polite"` on the list means a new turn is announced once, when it
 * is appended, without stealing focus from the push-to-talk button.
 */
export function ChatMessageList({
	messages,
	label,
	roleLabels,
	empty,
}: ChatMessageListProps) {
	if (messages.length === 0) {
		return (
			<div className="flex min-h-0 flex-1 items-center justify-center">
				{empty}
			</div>
		);
	}

	return (
		<div
			className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto pe-1"
			aria-label={label}
			aria-live="polite"
			role="log"
		>
			{messages.map((message) => (
				<div
					key={message.id}
					className={cn(
						"flex w-full",
						message.role === "user" ? "justify-end" : "justify-start",
					)}
				>
					<div className="flex max-w-[80%] flex-col gap-1">
						<span
							className={cn(
								"text-xs text-muted-foreground",
								message.role === "user" ? "text-end" : "text-start",
							)}
						>
							{roleLabels[message.role]}
						</span>
						<p
							className={cn(
								"whitespace-pre-wrap break-words rounded-lg border border-border/8 px-3.5 py-2.5 text-sm leading-relaxed text-foreground",
								message.role === "user" ? "bg-primary/10" : "bg-surface",
							)}
						>
							{message.text}
						</p>
					</div>
				</div>
			))}
		</div>
	);
}
