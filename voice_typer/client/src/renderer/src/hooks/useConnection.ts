import { useCallback, useEffect, useRef } from "react";
import { useShallow } from "zustand/react/shallow";
import { useLatestRef } from "@/hooks/useLatestRef";
import { usePythonEvent } from "@/hooks/usePython";
import { useT } from "@/i18n/i18n";
import { useAppStore } from "@/stores/appStore";
import type { LausuConfig } from "@/types/config";
import type { Page } from "@/types/ipc";
import {
	applyStatusWithReason,
	asRecordingState,
	BACKGROUND_RECONNECT_INTERVAL_MS,
	CONNECTION_PROBE_GRACE_EXTRA_RETRIES,
	CONNECTION_PROBE_MAX_RETRIES,
	CONNECTION_PROBE_RETRY_DELAY_MS,
	CONNECTION_PROBE_STARTUP_GRACE_MS,
	HEALTH_CHECK_EVENT_GRACE_MS,
	HEALTH_CHECK_INTERVAL_MS,
	HEALTH_CHECK_MAX_RETRIES,
	HEALTH_CHECK_RETRY_DELAY_MS,
	isTransientTimeoutError,
	MANUAL_RETRY_PROBE_MAX_ATTEMPTS,
	MAX_BACKGROUND_RECONNECTS,
	RESPAWN_EXHAUSTED_CODE,
} from "./connectionStatus";

interface UseConnectionArgs {
	/**
	 * Python bridge `call` function (from usePython).
	 */
	call: <T = unknown>(
		type: string,
		data?: Record<string, unknown>,
	) => Promise<T>;
	/**
	 * @deprecated accepted + discarded; first-run check is unconditional.
	 */
	currentPage?: Page;
	/**
	 * Navigate callback (used to route to onboarding on first run).
	 */
	navigate: (page: Page) => void;
}

/**
 * Python-backend connection lifecycle + pushed recording state + TCP recovery.
 * Zustand appStore-backed. C-HOME-1: recordingState and lastError always
 */
export function useConnection({
	call,
	currentPage: _currentPage,
	navigate,
}: UseConnectionArgs) {
	const t = useT();
	const { setConnectionStatus, setRecordingState, setLastError, setConfig } =
		useAppStore(
			useShallow((s) => ({
				setConnectionStatus: s.setConnectionStatus,
				setRecordingState: s.setRecordingState,
				setLastError: s.setLastError,
				setConfig: s.setConfig,
			})),
		);
	const connectionStatus = useAppStore((s) => s.connectionStatus);
	const recordingState = useAppStore((s) => s.recordingState);
	const lastError = useAppStore((s) => s.lastError);

	const lastEventReceivedAtRef = useRef<number>(0);
	const markEventReceived = useCallback(() => {
		lastEventReceivedAtRef.current = Date.now();
	}, []);

	const callRef = useLatestRef(call);

	// CONFIG-HYDRATE: a push event can promote the app to "connected"
	// without the startup probe ever landing its get_config payload (the
	// probe gives up after its retry budget on a cold boot, then a
	// `state_changed` push flips the status). Without a config the
	// config-derived surfaces render nothing — the sidebar's active-model
	// caption and CPU/GPU switch both bail — so hydrate on demand.
	//
	// The completeness test is `model_size !== undefined`: it is a persisted
	// speech-model field, always present in a full get_config and never
	// carried by a `config_changed` push, so its absence means the store
	// never saw a full snapshot — including the case where an early push
	// seeded a PARTIAL object through mergeConfig's null-base branch, which
	// is truthy but leaves the model fields missing. Deliberately NOT
	// `gpu_available`: the model caption must not have a GPU term in its
	// data path, or a machine whose GPU probe is slow/absent would look
	// like "config incomplete" forever and refetch on every status push.
	// In the steady state the field is present and this costs no IPC.
	const hydrateConfigIfMissing = useCallback(() => {
		const cfg = useAppStore.getState().config;
		if (cfg && cfg.model_size !== undefined) return;
		callRef
			.current<LausuConfig>("get_config")
			.then((fresh) => {
				if (fresh) setConfig(fresh);
			})
			.catch((err) =>
				console.warn("[renderer:useConnection] config hydration failed:", err),
			);
	}, [callRef, setConfig]);

	useEffect(() => {
		let retries = 0;
		const maxRetries = CONNECTION_PROBE_MAX_RETRIES;
		const probeStartTs = Date.now();
		let timer: ReturnType<typeof setTimeout>;
		let cancelled = false;

		const checkConnection = async () => {
			if (cancelled) return;
			try {
				const cfg = await callRef.current<LausuConfig>("get_config");
				if (!cancelled) {
					setConnectionStatus("connected");
					setConfig(cfg);
					callRef
						.current<{ status?: string; message?: string }>("get_status")
						.then((s) => {
							if (!cancelled && s?.status) {
								const validated = asRecordingState(s.status);
								if (validated) {
									applyStatusWithReason(
										validated,
										typeof s.message === "string" ? s.message : null,
										setRecordingState,
										setLastError,
									);
								}
							}
						})
						.catch((err) =>
							console.warn("[renderer:useConnection] get_status failed:", err),
						);
					const pos = cfg?.bubble_position;
					if (pos === "bottom" || pos === "top") {
						// Awaited BEFORE show: the edge placement must land
						// before the window becomes visible, otherwise the
						// pill sits at the OS default position all session.
						// One retry covers a display stack still coming up
						// at logon; failure still shows (unpositioned beats
						// hidden), loudly.
						try {
							await window.bubble?.setPosition?.(pos);
						} catch (err) {
							console.warn(
								"[renderer:useConnection] bubble_set_position failed, retrying once:",
								err,
							);
							await new Promise((r) => setTimeout(r, 2000));
							if (cancelled) return;
							try {
								await window.bubble?.setPosition?.(pos);
							} catch (err2) {
								console.error(
									"[renderer:useConnection] bubble_set_position retry failed, showing unpositioned:",
									err2,
								);
							}
						}
					}
					const draggable = cfg?.bubble_draggable;
					if (typeof draggable === "boolean") {
						window.bubble?.setDraggable?.(draggable);
					}
					const behavior = cfg?.bubble_behavior;
					const showOnStartup = cfg?.bubble_show_on_startup;
					if (behavior === "always_visible" && showOnStartup !== false) {
						window.bubble?.show?.();
					}

					if (!cancelled) {
						try {
							const fr = await callRef.current<{ is_first_run: boolean }>(
								"onboarding_is_first_run",
							);
							if (!cancelled && fr?.is_first_run) {
								navigate("onboarding");
							}
						} catch (e) {
							console.warn(
								"[renderer:useConnection] onboarding_is_first_run probe failed:",
								e,
							);
						}
					}
				}
			} catch (err) {
				console.warn(
					`[renderer:useConnection] get_config connection probe failed (attempt ${retries + 1}/${maxRetries}):`,
					err,
				);
				retries++;
				// Startup grace: a dispatch timeout while the backend is
				// still in its launch storm is transient. Grant extra
				// attempts without flipping to "disconnected"; fast
				// failures (pre-handshake refusal) keep the plain budget
				// so a truly dead backend still surfaces in seconds.
				const transient = isTransientTimeoutError(err);
				const inGrace =
					Date.now() - probeStartTs < CONNECTION_PROBE_STARTUP_GRACE_MS;
				const budget =
					inGrace && transient
						? maxRetries + CONNECTION_PROBE_GRACE_EXTRA_RETRIES
						: maxRetries;
				if (!cancelled && retries < budget) {
					timer = setTimeout(checkConnection, CONNECTION_PROBE_RETRY_DELAY_MS);
				} else if (!cancelled) {
					setConnectionStatus("disconnected");
				}
			}
		};

		checkConnection();

		return () => {
			cancelled = true;
			clearTimeout(timer);
		};
	}, [
		navigate,
		setConnectionStatus,
		setRecordingState,
		setLastError,
		setConfig,
		callRef,
	]);

	useEffect(() => {
		if (connectionStatus !== "connected") return;

		let cancelled = false;
		let retryTimer: ReturnType<typeof setTimeout> | undefined;
		let failureCount = 0;

		const probe = async (isRetry: boolean): Promise<void> => {
			const lastEventMs = lastEventReceivedAtRef.current;
			if (
				lastEventMs > 0 &&
				Date.now() - lastEventMs < HEALTH_CHECK_EVENT_GRACE_MS
			) {
				failureCount = 0;
				return;
			}
			try {
				await callRef.current("get_status");
				failureCount = 0;
			} catch {
				if (cancelled) return;
				if (isRetry) failureCount++;
				else failureCount = 1;
				if (failureCount > HEALTH_CHECK_MAX_RETRIES) {
					setConnectionStatus("disconnected");
				} else {
					retryTimer = setTimeout(() => {
						probe(true);
					}, HEALTH_CHECK_RETRY_DELAY_MS);
				}
			}
		};

		const interval = setInterval(() => probe(false), HEALTH_CHECK_INTERVAL_MS);

		return () => {
			cancelled = true;
			clearInterval(interval);
			if (retryTimer) clearTimeout(retryTimer);
		};
	}, [connectionStatus, setConnectionStatus, callRef]);

	useEffect(() => {
		if (connectionStatus !== "disconnected") return;

		let cancelled = false;
		let attempts = 0;
		let timer: ReturnType<typeof setTimeout> | undefined;

		const tryReconnect = async () => {
			if (cancelled) return;
			if (attempts >= MAX_BACKGROUND_RECONNECTS) return;
			attempts++;
			try {
				const cfg = await callRef.current<LausuConfig>("get_config");
				if (!cancelled) {
					setConnectionStatus("connected");
					setConfig(cfg);
					setLastError(null);
					// reconnect snapshot must hydrate pill + reason line
					callRef
						.current<{ status?: string; message?: string }>("get_status")
						.then((s) => {
							if (!cancelled && s?.status) {
								const validated = asRecordingState(s.status);
								if (validated) {
									applyStatusWithReason(
										validated,
										typeof s.message === "string" ? s.message : null,
										setRecordingState,
										setLastError,
									);
								}
							}
						})
						.catch((err) =>
							console.warn(
								"[renderer:useConnection] background-reconnect get_status failed:",
								err,
							),
						);
				}
			} catch {
				if (!cancelled && attempts < MAX_BACKGROUND_RECONNECTS) {
					timer = setTimeout(tryReconnect, BACKGROUND_RECONNECT_INTERVAL_MS);
				}
			}
		};

		timer = setTimeout(tryReconnect, BACKGROUND_RECONNECT_INTERVAL_MS);

		return () => {
			cancelled = true;
			if (timer) clearTimeout(timer);
		};
	}, [
		connectionStatus,
		setConnectionStatus,
		setConfig,
		setLastError,
		setRecordingState,
		callRef,
	]);

	usePythonEvent(
		"status_change",
		useCallback(
			(data): (() => void) | undefined => {
				markEventReceived();
				if (data?.status) {
					const validated = asRecordingState(data.status);
					if (validated) {
						// why recordingState + lastError must move together
						applyStatusWithReason(
							validated,
							data.message,
							setRecordingState,
							setLastError,
						);
					}
				}
				return undefined;
			},
			[markEventReceived, setRecordingState, setLastError],
		),
	);

	usePythonEvent(
		"error",
		useCallback(
			(data): (() => void) | undefined => {
				markEventReceived();
				if (
					typeof data?.message === "string" ||
					typeof data?.code === "string"
				) {
					// event with `code: "respawn_exhausted"`. The UI must
					if (data?.code === RESPAWN_EXHAUSTED_CODE) {
						setLastError(t("connection.respawnFailed"));
						setConnectionStatus("disconnected");
					} else if (typeof data?.message === "string") {
						setLastError(data.message);
						// error line must render. The respawn_exhausted branch
						setRecordingState("error");
					}
				}
				return undefined;
			},
			[
				markEventReceived,
				setLastError,
				setRecordingState,
				setConnectionStatus,
				t,
			],
		),
	);

	usePythonEvent(
		"reconnecting",
		useCallback((): (() => void) | undefined => {
			markEventReceived();
			setConnectionStatus("reconnecting");
			return undefined;
		}, [markEventReceived, setConnectionStatus]),
	);
	usePythonEvent(
		"reconnected",
		useCallback((): (() => void) | undefined => {
			markEventReceived();
			call<LausuConfig>("get_config")
				.then((cfg) => {
					setConfig(cfg);
					setConnectionStatus("connected");
					// Same status catch-up as the other connect paths: without it the
					// pill/description keep the pre-respawn state (C-HOME-1).
					call<{ status?: string; message?: string }>("get_status")
						.then((s) => {
							if (s?.status) {
								const validated = asRecordingState(s.status);
								if (validated) {
									applyStatusWithReason(
										validated,
										typeof s.message === "string" ? s.message : null,
										setRecordingState,
										setLastError,
									);
								}
							}
						})
						.catch((err) =>
							console.warn(
								"[renderer:useConnection] reconnected get_status failed:",
								err,
							),
						);
				})
				.catch(() => setConnectionStatus("disconnected"));
			return undefined;
		}, [
			markEventReceived,
			call,
			setConfig,
			setConnectionStatus,
			setRecordingState,
			setLastError,
		]),
	);

	usePythonEvent(
		"state_changed",
		useCallback(
			(data): (() => void) | undefined => {
				markEventReceived();
				setConnectionStatus("connected");
				// CONFIG-HYDRATE: connected without a config snapshot
				// means every config-derived surface renders empty.
				hydrateConfigIfMissing();

				const rawStatus = data?.status;
				const validated =
					typeof rawStatus === "string" ? asRecordingState(rawStatus) : null;
				if (validated) {
					applyStatusWithReason(
						validated,
						typeof data?.message === "string" ? data.message : null,
						setRecordingState,
						setLastError,
					);
				} else {
					setLastError(null);
				}
				return undefined;
			},
			[
				markEventReceived,
				setConnectionStatus,
				setLastError,
				setRecordingState,
				hydrateConfigIfMissing,
			],
		),
	);

	const retryInFlightRef = useRef(false);

	const handleRetryConnection = useCallback(async () => {
		// Single-flight: a click while a retry is already probing, or
		// while the status is mid-transition, must not stack a second
		// kill escalation. Each kill resets a booting backend's clock,
		// so stacked retries turn a slow boot into a restart loop.
		if (retryInFlightRef.current) return;
		const cur = useAppStore.getState().connectionStatus;
		if (cur === "connecting" || cur === "restarting") return;
		retryInFlightRef.current = true;
		try {
			setConnectionStatus("connecting");
			for (
				let attempt = 1;
				attempt <= MANUAL_RETRY_PROBE_MAX_ATTEMPTS;
				attempt++
			) {
				try {
					// CONFIG-HYDRATE: install the payload. A bare
					// ``await call("get_config")`` proves the transport is
					// alive but leaves the store's config null, and every
					// config-derived surface then renders nothing: the
					// sidebar loses the active-model caption
					// (formatActiveModel(null) === "") and the CPU/GPU
					// switch (needs config.device + gpu_available). The
					// app looks connected but half-built, which is exactly
					// what a cold autostart produces once the startup probe
					// budget is spent and the user clicks retry.
					const cfg = await call<LausuConfig>("get_config");
					if (cfg) setConfig(cfg);
					setConnectionStatus("connected");
					return;
				} catch (err) {
					// Fast refusals mean no transport: escalate now, as
					// before. Only timeout-shaped errors earn another
					// probe — a booting backend answers slowly, not never.
					const last = attempt >= MANUAL_RETRY_PROBE_MAX_ATTEMPTS;
					if (!isTransientTimeoutError(err) || last) break;
					await new Promise((resolve) =>
						setTimeout(resolve, CONNECTION_PROBE_RETRY_DELAY_MS),
					);
				}
			}
		} finally {
			retryInFlightRef.current = false;
		}
		// A background path may have healed meanwhile; never kill a
		// backend the store already considers connected.
		if (useAppStore.getState().connectionStatus === "connected") {
			return;
		}
		try {
			const res = await window.window_?.restartBackend?.();
			if (res?.ok) {
				setConnectionStatus("restarting");
				return;
			}
			setLastError(t("connection.restartBackendHint"));
			setConnectionStatus("disconnected");
		} catch (e) {
			console.warn(
				"[renderer:useConnection] restartBackend escalation failed:",
				e,
			);
			setLastError(t("connection.restartBackendHint"));
			setConnectionStatus("disconnected");
		}
	}, [call, setConfig, setConnectionStatus, setLastError, t]);

	return {
		recordingState,
		connectionStatus,
		lastError,
		handleRetryConnection,
	};
}
