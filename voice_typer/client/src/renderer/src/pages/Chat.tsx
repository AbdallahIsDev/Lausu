// Chat page: hold the button, speak, release, hear the reply.
//
// Thin composition root: `useChatConversation` owns the bridge + state, the
// three `pages/chat/components/` files own the layout. Every string is an i18n
// key; every phase comes from the backend's `chat_turn` event.

import {
	Add01Icon,
	AlertCircleIcon,
	MessageMultiple01Icon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { Skeleton } from "skullet/react";
import PageHeading from "@/components/common/PageHeading";
import { EmptyState } from "@/components/feedback/EmptyState";
import { skeletonLoadingLabel } from "@/components/feedback/skeletons";
import { Button } from "@/components/ui/button";
import { useNavigation } from "@/hooks/useNavigation";
import { useT } from "@/i18n/i18n";
import { VOICE_BIOMETRIC_CONSENT_FIELD } from "@/lib/consent";
import { consentBodyKey, openConsentGate } from "@/lib/consentGate";
import { ChatMessageList } from "./chat/components/ChatMessageList";
import { ChatPhaseIndicator } from "./chat/components/ChatPhaseIndicator";
import { PushToTalkButton } from "./chat/components/PushToTalkButton";
import { useChatConversation } from "./chat/hooks/useChatConversation";
import { chatErrorAction, chatErrorKey } from "./chat/lib/errorCopy";
import { SAMPLE_CHAT_MESSAGES } from "./chat/lib/sample";

export default function ChatPage() {
	const t = useT();
	const { navigate } = useNavigation();
	const {
		messages,
		phase,
		errorCode,
		configured,
		voiceConsent,
		loading,
		loadFailed,
		startListening,
		stopListening,
		reset,
		clearError,
		reload,
	} = useChatConversation();

	const listening = phase === "listening";
	const busy =
		phase === "transcribing" || phase === "thinking" || phase === "speaking";
	const configuredState = configured === true && !loadFailed;

	// GDPR Art. 9 gate at ACTION time, like the Microphone page: the backend
	// refuses capture without `voice_biometric_consent`, and its refusal only
	// arrives after a doomed IPC. Granting does NOT start capture — the dialog
	// takes the pointer away, so a capture started from `onAllow` would latch
	// with nobody holding the button.
	const onPressStart = () => {
		if (!voiceConsent) {
			openConsentGate({
				consentField: VOICE_BIOMETRIC_CONSENT_FIELD,
				bodyKey: consentBodyKey(VOICE_BIOMETRIC_CONSENT_FIELD),
			});
			return;
		}
		void startListening();
	};

	const phaseLabel = (() => {
		switch (phase) {
			case "listening":
				return t("chat.phaseListening");
			case "transcribing":
				return t("chat.phaseTranscribing");
			case "thinking":
				return t("chat.phaseThinking");
			case "speaking":
				return t("chat.phaseSpeaking");
			default:
				return t("chat.phaseIdle");
		}
	})();

	const errorAction = chatErrorAction(errorCode);
	const errorActionLabel =
		errorAction === "models"
			? t("chat.openModels")
			: errorAction === "providers"
				? t("chat.openProviders")
				: t("chat.retry");
	const onErrorAction = () => {
		if (errorAction === "models") navigate("models");
		else if (errorAction === "providers") navigate("providers");
		else clearError();
	};

	const stateBody = () => {
		if (loadFailed) {
			return (
				<EmptyState
					variant="error"
					icon={AlertCircleIcon}
					title={t("chat.loadFailedTitle")}
					description={t("chat.loadFailedDescription")}
					actionLabel={t("chat.retry")}
					onAction={reload}
				/>
			);
		}
		// Loading has no state body: the transcript's measured <Skeleton>
		// below covers it, so the control bar stays mounted per C-UI-16.
		if (configured === false) {
			return (
				<EmptyState
					icon={MessageMultiple01Icon}
					title={t("chat.notConfiguredTitle")}
					description={t("chat.notConfiguredDescription")}
					actionLabel={t("chat.openProviders")}
					onAction={() => navigate("providers")}
				/>
			);
		}
		return null;
	};

	// Two sibling surfaces, never a bordered card inside another card: the
	// transcript (or its state screen) and a control bar that stays mounted in
	// every state, so a disabled mic never looks like a missing feature.
	const state = stateBody();

	return (
		<div className="mx-auto flex h-full w-full max-w-3xl flex-col gap-6 px-16 pt-20 pb-6">
			<PageHeading title={t("chat.title")} description={t("chat.description")}>
				<Button
					variant="outline"
					size="sm"
					onClick={() => void reset()}
					disabled={messages.length === 0 && !busy && !listening}
				>
					<HugeiconsIcon icon={Add01Icon} strokeWidth={1.75} />
					{t("chat.newConversation")}
				</Button>
			</PageHeading>

			{errorCode !== null ? (
				<div
					role="alert"
					className="flex items-center justify-between gap-3 rounded-lg border border-border/8 bg-surface-subtle px-4 py-3"
				>
					<div className="flex items-center gap-2 text-sm text-foreground">
						<HugeiconsIcon
							icon={AlertCircleIcon}
							strokeWidth={1.8}
							aria-hidden="true"
							className="size-4 shrink-0 text-destructive"
						/>
						{t(chatErrorKey(errorCode))}
					</div>
					<Button variant="outline" size="sm" onClick={onErrorAction}>
						{errorActionLabel}
					</Button>
				</div>
			) : null}

			<div className="flex min-h-0 flex-1 flex-col gap-4">
				{state ? (
					<div className="flex min-h-0 flex-1 items-center justify-center">
						{state}
					</div>
				) : (
					<div className="flex min-h-0 flex-1 flex-col rounded-lg border border-border/8 bg-surface-subtle p-4">
						{/* Measured wrap: the list renders from the sample while
							the conversation loads; heading + control bar stay
							mounted outside per C-UI-16. */}
						<Skeleton
							data={loading ? null : messages}
							sample={SAMPLE_CHAT_MESSAGES}
							id="chat-transcript"
							label={skeletonLoadingLabel()}
						>
							{(d) => (
								<ChatMessageList
									messages={d}
									label={t("chat.transcriptLabel")}
									roleLabels={{
										user: t("chat.you"),
										assistant: t("chat.assistant"),
									}}
									empty={
										<div className="flex flex-col items-center gap-2 py-10 text-center">
											<HugeiconsIcon
												icon={MessageMultiple01Icon}
												strokeWidth={1.5}
												aria-hidden="true"
												className="size-8 text-muted-foreground"
											/>
											<p className="text-sm font-medium text-foreground">
												{t("chat.emptyTitle")}
											</p>
											<p className="max-w-sm text-xs text-muted-foreground">
												{t("chat.emptyDescription")}
											</p>
										</div>
									}
								/>
							)}
						</Skeleton>
					</div>
				)}

				<div className="flex flex-col items-center gap-3 rounded-lg border border-border/8 bg-surface-subtle px-4 py-5">
					<ChatPhaseIndicator phase={phase} label={phaseLabel} />
					<PushToTalkButton
						listening={listening}
						disabled={!configuredState || busy}
						label={t("chat.holdToTalk")}
						onPressStart={onPressStart}
						onPressEnd={() => void stopListening()}
					/>
				</div>
			</div>
		</div>
	);
}
