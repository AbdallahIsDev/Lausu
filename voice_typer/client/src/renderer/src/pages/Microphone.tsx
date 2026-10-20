// Microphone page, thin composition root.
// ``pages/microphone/`` package: this file wires the three hooks
// (``useMicrophoneData`` / ``useMicrophonePermission`` /
// ``useMicrophoneTest``) and renders the three sub-components
// (``MicrophonePermissionBanner`` / ``ActiveMicrophoneCard`` /
// ``AvailableMicrophonesList``). All business logic lives in the
// hooks; all layout lives in the components.
// The default export signature is preserved so ``App.tsx`` routing is
// unaffected.

import { AlertCircleIcon } from "@hugeicons/core-free-icons";
import { useCallback, useRef, useState } from "react";
import { filterFactoryDefaults } from "@/components/audio/audioFilterRowDescriptors";
import PageHeading from "@/components/common/PageHeading";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useSnackbar } from "@/hooks/useSnackbar";
import { t } from "@/i18n/i18n";
import { VOICE_BIOMETRIC_CONSENT_FIELD } from "@/lib/consent";
import { consentBodyKey, openConsentGate } from "@/lib/consentGate";
import { useDeviceLostStore } from "@/stores/deviceLostStore";
import type { LausuConfig } from "@/types/config";
import { ActiveMicrophoneCard } from "./microphone/components/ActiveMicrophoneCard";
import { AvailableMicrophonesList } from "./microphone/components/AvailableMicrophonesList";
import { MicrophonePermissionBanner } from "./microphone/components/MicrophonePermissionBanner";
import { MicrophoneSkeleton } from "./microphone/components/MicrophoneSkeleton";
import { useLiveListen } from "./microphone/hooks/useLiveListen";
import { useLiveSpeakerOffer } from "./microphone/hooks/useLiveSpeakerOffer";
import { useMicrophoneData } from "./microphone/hooks/useMicrophoneData";
import { useMicrophonePermission } from "./microphone/hooks/useMicrophonePermission";
import { useMicrophoneTest } from "./microphone/hooks/useMicrophoneTest";
import { snapshotFilterValues } from "./microphone/lib/filterSnapshot";

export default function MicrophonePage() {
	// ref-to-latest-selectMicrophone so the
	// ``microphones_changed`` event handler (subscribed inside
	// ``useMicrophoneData``) can invoke the latest closure (assigned
	// inside ``useMicrophoneTest``) without re-subscribing on every
	// render.
	const selectMicrophoneRef = useRef<(micId: string | null) => Promise<void>>(
		async () => {},
	);
	// meter wrapper ref. The level monitor's rAF loop imperatively
	// writes the latest level to the ``LevelBar``'s fill div inside this
	// wrapper, bypassing React's re-render cycle (mirrors the bubble's
	// ``useAudioLevels`` ref+rAF pattern). Attached to a ``<div>`` wrapping
	// ``<ActiveMicrophoneCard>`` so ``querySelector('[role="progressbar"]
	// > div')`` can reach the ``LevelBar``'s fill element without modifying
	// ``ActiveMicrophoneCard``.
	const meterRef = useRef<HTMLDivElement | null>(null);

	const {
		microphones,
		config,
		setConfig,
		loading,
		loadError,
		loadData,
		updateConfig,
	} = useMicrophoneData({ selectMicrophoneRef });

	const { micPermission } = useMicrophonePermission();

	// Device-lost state, written ONCE by the App-level
	// ``useDeviceLostToast`` subscriber (single event → single mechanism:
	// the toast notification IS the user-facing device-lost signal; there
	// is deliberately NO persistent in-page banner for it). While a loss
	// is flagged the level monitor is paused (futile to monitor a
	// vanished stream); selecting a microphone clears the flag, which
	// un-pauses the meter, and the ``microphones_changed`` hot-swap
	// handler auto-falls-back to System Default when the device is
	// genuinely gone.
	const lostSource = useDeviceLostStore((s) => s.lostSource);
	const clearLost = useDeviceLostStore((s) => s.clearLost);

	// Pack progress is NOT rendered here: the mic test uses RMS only
	// and works without the pack (§4.9: "RMS meter works; VAD
	// 'smartness' degrades silently"), and pack states surface via
	// the App-level usePackUpdateToast, so this page needs no
	// pack-driven element at all.
	// Live-monitor stop signal. Bumped whenever the mic stream is
	// claimed elsewhere (test start, device switch): the monitor must
	// release it so only one consumer holds the device.
	const [liveListenStopSignal, setLiveListenStopSignal] = useState(0);
	const bumpLiveListenStop = useCallback(
		() => setLiveListenStopSignal((n) => n + 1),
		[],
	);

	const {
		testRunning,
		testStarting,
		testElapsed,
		testAudioBase64,
		rawAudioBase64,
		testDurationMs,
		testQuality,
		testTranscription,
		testTranscriptionUnavailable,
		level,
		micMonitoring,
		playingEnhanced,
		playingOriginal,
		startTest: rawStartTest,
		stopTest,
		selectMicrophone: rawSelectMicrophone,
		playAudio,
		stopPlayback,
		handlePresetChange,
		handleConfigChange,
	} = useMicrophoneTest({
		config,
		microphones,
		setConfig,
		updateConfig,
		selectMicrophoneRef,
		meterRef,
		levelMonitorPaused: lostSource !== null,
	});

	// GDPR Art. 9 gate, mirrors Home.tsx handleToggle: the backend
	// refuses mic-test starts while ``voice_biometric_consent`` is off,
	// but its refusal only surfaces as a post-hoc error path. Gate
	// client-side at ACTION time so pressing Start Test opens the unified
	// point-of-use consent dialog INSTEAD of firing a doomed IPC; once the
	// consent flag is true the test starts directly and never re-prompts.
	// The session hook's reactive refusal paths remain as the backstop for
	// hotkey-triggered tests and config races.
	const startTest = useCallback(
		(...args: Parameters<typeof rawStartTest>) => {
			bumpLiveListenStop();
			if (config && !config.voice_biometric_consent) {
				openConsentGate({
					consentField: VOICE_BIOMETRIC_CONSENT_FIELD,
					bodyKey: consentBodyKey(VOICE_BIOMETRIC_CONSENT_FIELD),
					// Retry after granting: run the test start that was blocked.
					onAllow: () => void rawStartTest(...args),
				});
				return;
			}
			return rawStartTest(...args);
		},
		[rawStartTest, config, bumpLiveListenStop],
	);

	// Wrap selectMicrophone so selecting a microphone WHILE a
	// device-lost flag is active clears that flag first, otherwise the
	// stale banner + frozen meter linger over a now-working device. If
	// the picked mic is still gone the backend re-emits ``device_lost``
	// and the banner returns. A data refresh follows so the device list
	// reflects the switch immediately.
	const selectMicrophone = useCallback(
		async (...args: Parameters<typeof rawSelectMicrophone>) => {
			bumpLiveListenStop();
			if (lostSource !== null) {
				clearLost();
			}
			try {
				return await rawSelectMicrophone(...args);
			} finally {
				if (lostSource !== null) {
					await loadData();
				}
			}
		},
		[rawSelectMicrophone, lostSource, clearLost, loadData, bumpLiveListenStop],
	);

	// ── Custom presets + Advanced restore ─────────────────────────
	// Saved customs live in config (backend-canonical); selecting one
	// sends its values explicitly AND names it active, so the backend
	// snapshot applier and the UI agree even if a push lags. Returning
	// to Advanced later shows whatever the selected preset holds —
	// no separate "last saved" state exists anywhere.
	const { showSnack } = useSnackbar();
	const customs = config?.custom_presets ?? [];
	const activeCustomPresetId =
		config?.audio_preset === "custom"
			? (config?.active_custom_preset ?? null)
			: null;

	const selectCustomPreset = useCallback(
		(id: string) => {
			const custom = (config?.custom_presets ?? []).find((c) => c.id === id);
			if (!custom) return;
			updateConfig({
				audio_preset: "custom",
				active_custom_preset: id,
				...custom.values,
			} as Partial<LausuConfig>);
		},
		[config, updateConfig],
	);

	const saveCustomPreset = useCallback(
		(name: string) => {
			const values: Record<string, boolean | number | string> = {};
			for (const [key, value] of Object.entries(snapshotFilterValues(config))) {
				if (
					typeof value === "boolean" ||
					typeof value === "number" ||
					typeof value === "string"
				) {
					values[key] = value;
				}
			}
			const id = `custom-${Date.now().toString(36)}`;
			const entry = { id, name, values };
			updateConfig({
				custom_presets: [...(config?.custom_presets ?? []), entry],
				audio_preset: "custom",
				active_custom_preset: id,
				...values,
			} as Partial<LausuConfig>);
			showSnack(t("microphoneTest.presetSaved", { name }), "success");
		},
		[config, updateConfig, showSnack],
	);

	const restoreMicDefaults = useCallback(() => {
		updateConfig({ ...filterFactoryDefaults() } as Partial<LausuConfig>);
	}, [updateConfig]);

	// ── Derived state ─────────────────────────────────────────────

	const activeMicId = config?.microphone ?? null;
	const isSystemDefault = activeMicId === null;
	const activeMicName =
		activeMicId === null
			? t("microphone.systemDefault")
			: (microphones.find((m) => (m.id ?? String(m.index)) === activeMicId)
					?.name ?? t("microphone.unknown"));

	// Live monitor ("hear yourself"). Backend-streamed: the level
	// monitor's own AudioProcessor chain filters it and the renderer only
	// schedules playback, so the preview sounds exactly like the 10 s
	// test. Nothing is recorded. Stops on test start / device switch
	// (stopSignal), tab-hide, and unmount (all inside the hook), each of
	// which also disables the sidecar stream.
	const {
		listening: liveListening,
		starting: liveStarting,
		error: liveListenError,
		toggle: toggleLiveListen,
	} = useLiveListen({
		activeMicName: isSystemDefault ? null : activeMicName,
		isSystemDefault,
		stopSignal: liveListenStopSignal,
	});
	// One-time offer to lower loud speakers when the preview starts (S1).
	useLiveSpeakerOffer(liveListening);
	const liveListenDisabled =
		testRunning ||
		testStarting ||
		playingEnhanced ||
		playingOriginal ||
		microphones.length === 0;

	// ── Render ────────────────────────────────────────────────────

	// On first visit (no cached data + still loading), show the full
	// spinner. On re-visit, the module-level caches in
	// ``useMicrophoneData`` populate the initial state so we render the
	// page immediately (the spinner would flash stale-then-real).
	if (!microphones.length && !config && loading) {
		return <MicrophoneSkeleton />;
	}

	//distinguish "backend failed to load" from "no microphones
	// found" so the user knows to retry instead of being told to connect
	// a microphone when the real issue is the backend is unreachable.
	if (loadError && microphones.length === 0) {
		return (
			<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-4 px-16 pt-20 pb-6">
				<PageHeading
					title={t("microphone.microphone")}
					description={t("microphone.description")}
				/>
				{/*variant="error" so the destructive
					tint + Alert02Icon swap make the failure visually distinct
					from a genuine empty list (matches the Vocabulary/Templates
					load-failure pattern from ). */}
				<EmptyState
					variant="error"
					icon={AlertCircleIcon}
					title={t("microphone.loadFailedTitle")}
					description={loadError}
					actionLabel={t("microphone.retry")}
					onAction={() => loadData()}
				/>
			</div>
		);
	}

	return (
		<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-4 px-16 pt-20 pb-6">
			<PageHeading
				title={t("microphone.microphone")}
				description={t("microphone.description")}
			/>

			<div className="flex flex-col gap-4">
				<MicrophonePermissionBanner micPermission={micPermission} />

				{/* ``meterRef`` wrapper. The level monitor's rAF
					loop queries inside this div for the ``LevelBar``'s fill
					node (``[role="progressbar"] > div``) and imperatively
					writes the latest level (scaleX transform) at ≤60 Hz —
					bypassing
					React's re-render cycle so a 30 Hz ``mic_level`` push
					no longer re-renders the entire Microphone page subtree.
					The wrapper itself is a no-op layout element (no extra
					className) so the visual structure is unchanged. */}
				<div ref={meterRef}>
					<ActiveMicrophoneCard
						activeMicName={activeMicName}
						isSystemDefault={isSystemDefault}
						canTest={microphones.length > 0}
						testRunning={testRunning}
						testStarting={testStarting}
						testElapsed={testElapsed}
						testDurationMs={testDurationMs}
						level={level}
						micMonitoring={micMonitoring}
						testAudioBase64={testAudioBase64}
						rawAudioBase64={rawAudioBase64}
						testQuality={testQuality}
						testTranscription={testTranscription}
						testTranscriptionUnavailable={testTranscriptionUnavailable}
						enhancementActive={config?.audio_preset !== "off"}
						playing={playingEnhanced || playingOriginal}
						playingOriginal={playingOriginal}
						config={config}
						customPresets={customs}
						activeCustomPresetId={activeCustomPresetId}
						onSelectCustomPreset={selectCustomPreset}
						onSaveCustomPreset={saveCustomPreset}
						onRestoreMicDefaults={restoreMicDefaults}
						liveListening={liveListening}
						liveStarting={liveStarting}
						liveListenError={liveListenError}
						liveListenDisabled={liveListenDisabled}
						onToggleLiveListen={toggleLiveListen}
						onStartTest={startTest}
						onStopTest={stopTest}
						onPlayEnhanced={() =>
							testAudioBase64 && playAudio(testAudioBase64, true)
						}
						onPlayOriginal={() =>
							rawAudioBase64 ? playAudio(rawAudioBase64, false) : undefined
						}
						onStopPlayback={stopPlayback}
						onPresetChange={handlePresetChange}
						onConfigChange={handleConfigChange}
					/>
				</div>

				<AvailableMicrophonesList
					microphones={microphones}
					activeMicId={activeMicId}
					testRunning={testRunning}
					onSelectMicrophone={selectMicrophone}
				/>
			</div>
		</div>
	);
}
