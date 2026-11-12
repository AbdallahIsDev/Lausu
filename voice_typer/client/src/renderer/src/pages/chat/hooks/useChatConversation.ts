// Bridge + state for the Chat page (push-to-talk voice conversation).
//
// The page is a pure view over `chat_state` + the `chat_turn` push event:
// every phase it renders comes from the backend, never from a command reply
// (except the optimistic "listening" the reply confirms). The manager owns the
// message list; this hook mirrors it, so a remount rehydrates instead of
// rebuilding history.
//
// `call` is mirrored into a ref (the sanctioned idiom) because a `[call]`
// effect dep is the documented render-loop class.

import { useCallback, useEffect, useRef, useState } from "react";
import { useLatestRef } from "@/hooks/useLatestRef";
import { usePython, usePythonEvent } from "@/hooks/usePython";

export type ChatPhase =
	| "idle"
	| "listening"
	| "transcribing"
	| "thinking"
	| "speaking"
	| "error";

export type ChatRole = "user" | "assistant";

export interface ChatMessageView {
	/** Stable render key (the backend sends no message ids). */
	id: number;
	role: ChatRole;
	text: string;
}

interface ChatStatePayload {
	messages?: unknown;
	phase?: unknown;
}

interface ChatTurnPayload {
	phase?: unknown;
	role?: unknown;
	text?: unknown;
	error_code?: unknown;
}

interface ChatConfigSlice {
	llm_provider?: unknown;
	llm_model_id?: unknown;
	voice_biometric_consent?: unknown;
}

/** One message as the backend sends it (no render id yet). */
interface PendingMessage {
	role: ChatRole;
	text: string;
}

const PHASES: ReadonlySet<string> = new Set([
	"idle",
	"listening",
	"transcribing",
	"thinking",
	"speaking",
	"error",
]);

function toPhase(value: unknown): ChatPhase {
	return typeof value === "string" && PHASES.has(value)
		? (value as ChatPhase)
		: "idle";
}

/** The single role/text guard shared by the snapshot parser and `chat_turn`. */
function toMessage(role: unknown, text: unknown): PendingMessage | null {
	if (
		(role === "user" || role === "assistant") &&
		typeof text === "string" &&
		text.length > 0
	) {
		return { role, text };
	}
	return null;
}

function toMessages(value: unknown): PendingMessage[] {
	if (!Array.isArray(value)) return [];
	const messages: PendingMessage[] = [];
	for (const entry of value) {
		if (!entry || typeof entry !== "object") continue;
		const { role, text } = entry as { role?: unknown; text?: unknown };
		const message = toMessage(role, text);
		if (message !== null) messages.push(message);
	}
	return messages;
}

/**
 * How many LEADING queued messages the snapshot's tail already carries.
 *
 * A queued `chat_turn` may have been published after the snapshot request but
 * before its reply, so its message can already be inside the snapshot. The
 * overlap is always a suffix of the snapshot against a prefix of the queue, and
 * a partial overlap is real (the user transcript landed, the reply had not):
 * scan the longest window first and stop at the first exact match.
 */
function countAlreadyInSnapshot(
	snapshot: readonly PendingMessage[],
	pending: readonly PendingMessage[],
): number {
	for (
		let count = Math.min(pending.length, snapshot.length);
		count > 0;
		count -= 1
	) {
		const offset = snapshot.length - count;
		let identical = true;
		for (let index = 0; index < count; index += 1) {
			const seen = snapshot[offset + index];
			const queued = pending[index];
			if (
				!seen ||
				!queued ||
				seen.role !== queued.role ||
				seen.text !== queued.text
			) {
				identical = false;
				break;
			}
		}
		if (identical) return count;
	}
	return 0;
}

export interface UseChatConversationResult {
	messages: ChatMessageView[];
	phase: ChatPhase;
	/** Namespaced IPC code from the last failed turn, or null. */
	errorCode: string | null;
	/** null while the config probe is in flight. */
	configured: boolean | null;
	/** `voice_biometric_consent`; the backend refuses capture without it. */
	voiceConsent: boolean;
	loading: boolean;
	loadFailed: boolean;
	startListening: () => Promise<void>;
	stopListening: () => Promise<void>;
	reset: () => Promise<void>;
	/** Drop the last failure so the page is ready for another hold. */
	clearError: () => void;
	reload: () => void;
}

export function useChatConversation(): UseChatConversationResult {
	const { call } = usePython();
	const callRef = useLatestRef(call);

	const [messages, setMessages] = useState<ChatMessageView[]>([]);
	const [phase, setPhase] = useState<ChatPhase>("idle");
	const [errorCode, setErrorCode] = useState<string | null>(null);
	const [configured, setConfigured] = useState<boolean | null>(null);
	const [voiceConsent, setVoiceConsent] = useState(true);
	const [loading, setLoading] = useState(true);
	const [loadFailed, setLoadFailed] = useState(false);
	const requestIdRef = useRef(0);

	// Last known LLM selection: `config_changed` may carry only one of the two
	// fields, so the gate is recomputed from the merged pair (C-CACHE-5).
	const llmRef = useRef({ provider: "", model: "" });

	// Events that arrive before the snapshot lands are replayed after it, so a
	// turn that finishes during mount is never dropped. A queued message the
	// snapshot ALREADY carries is not appended a second time: the replay skips
	// the leading queued messages whose (role, text) match the snapshot's tail
	// (see `countAlreadyInSnapshot`). Phase transitions always replay.
	const hydratedRef = useRef(false);
	const queuedRef = useRef<ChatTurnPayload[]>([]);
	const nextIdRef = useRef(0);

	const appendMessage = useCallback((role: ChatRole, text: string) => {
		nextIdRef.current += 1;
		const id = nextIdRef.current;
		setMessages((previous) => [...previous, { id, role, text }]);
	}, []);

	const applyTurn = useCallback(
		(payload: ChatTurnPayload, options?: { skipMessage?: boolean }) => {
			const nextPhase = toPhase(payload.phase);
			if (nextPhase === "error") {
				setErrorCode(
					typeof payload.error_code === "string" &&
						payload.error_code.length > 0
						? payload.error_code
						: "server.internal_error",
				);
				setPhase("error");
				return;
			}
			if (nextPhase === "listening") {
				setErrorCode(null);
			}
			const message = toMessage(payload.role, payload.text);
			if (message !== null && !options?.skipMessage) {
				appendMessage(message.role, message.text);
			}
			setPhase(nextPhase);
		},
		[appendMessage],
	);

	usePythonEvent("chat_turn", (payload) => {
		if (!payload) return;
		if (!hydratedRef.current) {
			queuedRef.current.push(payload);
			return;
		}
		applyTurn(payload);
	});

	// Settings → Providers (or the consent dialog) can change the gate while
	// this page is open; the page must not keep asserting stale state.
	usePythonEvent("config_changed", (data) => {
		if (!data) return;
		if (typeof data.voice_biometric_consent === "boolean") {
			setVoiceConsent(data.voice_biometric_consent);
		}
		if (typeof data.llm_provider === "string") {
			llmRef.current.provider = data.llm_provider;
		}
		if (typeof data.llm_model_id === "string") {
			llmRef.current.model = data.llm_model_id;
		}
		if ("llm_provider" in data || "llm_model_id" in data) {
			setConfigured(
				Boolean(llmRef.current.provider) && Boolean(llmRef.current.model),
			);
		}
	});

	// Mount / reload: one snapshot + the config gate, then flush the queue.
	// `requestId` invalidates an in-flight load on unmount or a newer reload,
	// so a late reply never writes state into a dead page.
	const load = useCallback(async () => {
		requestIdRef.current += 1;
		const requestId = requestIdRef.current;
		hydratedRef.current = false;
		queuedRef.current = [];
		setLoading(true);
		setLoadFailed(false);
		try {
			const [state, config] = await Promise.all([
				callRef.current<ChatStatePayload>("chat_state"),
				callRef.current<ChatConfigSlice>("get_config"),
			]);
			if (requestId !== requestIdRef.current) return;
			const snapshot = toMessages(state?.messages);
			nextIdRef.current = snapshot.length;
			setMessages(
				snapshot.map((message, index) => ({ ...message, id: index + 1 })),
			);
			setPhase(toPhase(state?.phase));
			llmRef.current = {
				provider:
					typeof config?.llm_provider === "string" ? config.llm_provider : "",
				model:
					typeof config?.llm_model_id === "string" ? config.llm_model_id : "",
			};
			setConfigured(
				Boolean(llmRef.current.provider) && Boolean(llmRef.current.model),
			);
			setVoiceConsent(config?.voice_biometric_consent !== false);
			setLoading(false);
			hydratedRef.current = true;
			const queued = queuedRef.current;
			queuedRef.current = [];
			const pending: PendingMessage[] = [];
			for (const turn of queued) {
				const message = toMessage(turn.role, turn.text);
				if (message !== null) pending.push(message);
			}
			let alreadyRendered = countAlreadyInSnapshot(snapshot, pending);
			for (const turn of queued) {
				const message = toMessage(turn.role, turn.text);
				const skipMessage = message !== null && alreadyRendered > 0;
				if (skipMessage) alreadyRendered -= 1;
				applyTurn(turn, { skipMessage });
			}
		} catch {
			if (requestId !== requestIdRef.current) return;
			setLoading(false);
			setLoadFailed(true);
		}
	}, [callRef, applyTurn]);

	useEffect(() => {
		void load();
		return () => {
			requestIdRef.current += 1;
		};
	}, [load]);

	// A page that unmounts while the button is held would otherwise leave the
	// manager latched busy; the backend has its own 30 s cap, this releases it
	// immediately. `heldRef` is set on press (not on the reply) so a press whose
	// `chat_listen_start` reply never lands is still released.
	const heldRef = useRef(false);
	useEffect(() => {
		return () => {
			if (heldRef.current) {
				heldRef.current = false;
				void callRef.current("chat_listen_stop").catch(() => undefined);
			}
		};
	}, [callRef]);

	const startListening = useCallback(async () => {
		heldRef.current = true;
		try {
			const result = await callRef.current<{ started?: boolean }>(
				"chat_listen_start",
			);
			if (result?.started) setPhase("listening");
		} catch {
			heldRef.current = false;
			setErrorCode("server.internal_error");
			setPhase("error");
		}
	}, [callRef]);

	const stopListening = useCallback(async () => {
		heldRef.current = false;
		try {
			await callRef.current("chat_listen_stop");
		} catch {
			setErrorCode("server.internal_error");
			setPhase("error");
		}
	}, [callRef]);

	const reset = useCallback(async () => {
		heldRef.current = false;
		setMessages([]);
		setPhase("idle");
		setErrorCode(null);
		try {
			await callRef.current("chat_reset");
		} catch {
			setErrorCode("server.internal_error");
		}
	}, [callRef]);

	const reload = useCallback(() => {
		void load();
	}, [load]);

	const clearError = useCallback(() => {
		setErrorCode(null);
		setPhase("idle");
	}, []);

	return {
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
	};
}
