// Measured-skeleton sample for the Chat transcript. While the conversation
// is loading the <Skeleton> measures this sample, so it carries typical
// alternating turns (layout only, no real conversation).
import type { ChatMessageView } from "../hooks/useChatConversation";

export const SAMPLE_CHAT_MESSAGES: ChatMessageView[] = [
	{ id: 1, role: "user", text: "What time is the team standup tomorrow?" },
	{
		id: 2,
		role: "assistant",
		text: "It starts at nine thirty in the main room.",
	},
	{ id: 3, role: "user", text: "Thanks, see you there." },
];
