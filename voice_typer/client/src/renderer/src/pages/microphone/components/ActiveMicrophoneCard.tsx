// Active-microphone card.
// Renders the currently-selected microphone (or "System Default")
// header (with the level readout on its trailing edge), the live
// LevelBar, the start/stop test buttons (with the recording dot +
// countdown on their trailing edge while a test runs) in one standard
// card, then the TestReviewPanel (post-test transcription, quality +
// playback) and the PresetAccordionSelector as sibling cards.
// This is the primary interactive surface of the Microphone page.
// Pure presentational component, all state and handlers are passed in
// from the page (which wires them from ``useMicrophoneData`` /
// ``useMicrophoneTest``). The card owns no business logic.
// Memoised children: the heaviest subtrees —
// `PresetAccordionSelector` (renders the full `AudioFilterChain` when
// `preset === "custom"`) and `TestReviewPanel` (post-test quality
// metrics + playback controls), are wrapped in `React.memo` with a
// custom comparator so a 10 Hz `mic_level` push (which updates
// `level`/`peak` and re-renders this card) doesn't re-render them.

import {
	Mic02Icon,
	PlayIcon,
	StopIcon,
	VolumeHighIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { memo } from "react";
import { LevelBar } from "@/components/feedback/LevelBar";
import { LiveQualityFeedback } from "@/components/feedback/LiveQualityFeedback";
import { TestReviewPanel } from "@/components/microphone/TestReviewPanel";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n/i18n";
import type { AudioPreset } from "@/lib/utils/audioPresets";
import type { CustomMicPreset, LausuConfig } from "@/types/config";
import type { LiveListenError } from "../hooks/useLiveListen";
import { MICROPHONE_TEST_DURATION_SEC } from "../hooks/useMicrophoneTestSession";
import type { TestResultQuality } from "../lib/types";
import { PresetAccordionSelector } from "./PresetAccordionSelector";

export interface ActiveMicrophoneCardProps {
	activeMicName: string;
	isSystemDefault: boolean;
	/** Whether the Start Test button should be enabled. False when the
	 *  backend reports zero available microphones, issuing
	 *  ``microphone_test_start`` with no mic (even the system default)
	 *  fails and spams error snacks. */
	canTest: boolean;
	testRunning: boolean;
	/** True while the start-test IPC is in flight (Start disabled, no recording UI yet). */
	testStarting?: boolean;
	testElapsed: number;
	testDurationMs: number;
	level: number;
	micMonitoring: boolean;
	testAudioBase64: string | null;
	rawAudioBase64: string | null;
	testQuality: TestResultQuality | null;
	/** Transcription of the last test recording (null = none/failed). */
	testTranscription?: string | null;
	/** True when no speech model is loaded, so no transcription can exist. */
	testTranscriptionUnavailable?: boolean;
	/** Whether enhanced OR original playback is in flight. */
	playing: boolean;
	playingOriginal: boolean;
	showAdvanced: boolean;
	config: LausuConfig | null;
	customPresets: CustomMicPreset[];
	activeCustomPresetId: string | null;
	onSelectCustomPreset: (id: string) => void;
	onSaveCustomPreset: (name: string) => void;
	onRestoreMicDefaults: () => void;
	/** Live monitor ("hear yourself") state, owned by useLiveListen in the page. */
	liveListening: boolean;
	liveStarting: boolean;
	liveListenError: LiveListenError;
	liveListenDisabled: boolean;
	onToggleLiveListen: () => void;
	onStartTest: () => void;
	onStopTest: () => void;
	onPlayEnhanced: () => void;
	onPlayOriginal: () => void;
	onStopPlayback: () => void;
	onToggleAdvanced: () => void;
	onPresetChange: (preset: AudioPreset) => void;
	onConfigChange: (updates: Partial<LausuConfig>) => void;
}

export function ActiveMicrophoneCard({
	activeMicName,
	isSystemDefault,
	canTest,
	testRunning,
	testStarting = false,
	testElapsed,
	testDurationMs,
	level,
	micMonitoring,
	testAudioBase64,
	rawAudioBase64,
	testQuality,
	testTranscription,
	testTranscriptionUnavailable,
	playing,
	playingOriginal,
	showAdvanced,
	config,
	customPresets,
	activeCustomPresetId,
	onSelectCustomPreset,
	onSaveCustomPreset,
	onRestoreMicDefaults,
	liveListening,
	liveStarting,
	liveListenError,
	liveListenDisabled,
	onToggleLiveListen,
	onStartTest,
	onStopTest,
	onPlayEnhanced,
	onPlayOriginal,
	onStopPlayback,
	onToggleAdvanced,
	onPresetChange,
	onConfigChange,
}: ActiveMicrophoneCardProps) {
	return (
		<div className="flex flex-col overflow-hidden rounded-lg border border-border/8 bg-surface-subtle">
			<div className="flex items-start justify-center flex-col gap-3 min-w-0 px-4 py-2.5">
				<div className="w-full flex items-end justify-between gap-3 min-w-0">
					<div className="flex items-center justify-between gap-3 min-w-0">
						<HugeiconsIcon
							icon={Mic02Icon}
							strokeWidth={1.625}
							className="h-4 w-4 shrink-0"
						/>
						<div className="min-w-0">
							<p className="text-sm font-medium text-foreground truncate">
								{activeMicName}
							</p>

							{isSystemDefault && (
								<p className="text-xs text-muted-foreground">
									{t("microphone.systemDefaultDesc")}
								</p>
							)}
						</div>
					</div>
					<span
						className="text-xs text-muted-foreground ms-auto shrink-0"
						aria-hidden={true}
					>
						{testRunning || micMonitoring
							? t("microphone.level", {
									percent: String(Math.round(level * 100)),
								})
							: t("microphone.monitoringOff")}
					</span>
				</div>

				{/* Level bar */}
				<LevelBar level={level} playing={playing} />

				{/* Test controls */}
				<div className="w-full flex items-center justify-between gap-2">
					<div className="flex items-center gap-2">
						{!testRunning ? (
							<Button
								variant="default"
								size="sm"
								className="gap-2"
								disabled={playing || !canTest || testStarting}
								onClick={onStartTest}
							>
								<HugeiconsIcon
									icon={PlayIcon}
									strokeWidth={1.625}
									className="h-4 w-4"
								/>
								{t("microphone.startTest")}
							</Button>
						) : (
							<Button
								variant="default"
								size="sm"
								className="gap-2 animate-pulse"
								onClick={onStopTest}
							>
								<HugeiconsIcon
									icon={StopIcon}
									strokeWidth={1.625}
									className="h-4 w-4"
								/>
								{t("microphone.stopTest")}
							</Button>
						)}
						<Button
							variant="outline"
							size="sm"
							className="gap-2"
							disabled={liveListenDisabled || liveStarting}
							onClick={onToggleLiveListen}
							aria-pressed={liveListening}
						>
							<HugeiconsIcon
								icon={liveListening ? StopIcon : VolumeHighIcon}
								strokeWidth={1.625}
								className="h-4 w-4"
							/>
							{liveListening
								? t("microphoneTest.stopListening")
								: t("microphoneTest.liveListen")}
						</Button>
					</div>

					<LiveQualityFeedback
						isRecording={testRunning}
						elapsedSeconds={testElapsed}
						totalSeconds={MICROPHONE_TEST_DURATION_SEC}
					/>
				</div>

				{/* Live-monitor hint + error. The hint shows while
					listening (headphones warning against feedback); errors
					map the hook's code to copy. */}
				{liveListenError && !testRunning && (
					<p className="px-4 pb-2.5 text-xs text-destructive" role="alert">
						{t(
							liveListenError === "denied"
								? "microphoneTest.liveListenDenied"
								: liveListenError === "unavailable"
									? "microphoneTest.liveListenUnavailable"
									: "microphoneTest.liveListenFailed",
						)}
					</p>
				)}
				<p className="text-xs text-muted-foreground">
					{t("microphoneTest.liveListenGuideNote")}
				</p>
			</div>
			<MemoizedTestReviewPanel
				durationMs={testDurationMs}
				quality={testQuality}
				transcription={testTranscription}
				transcriptionUnavailable={testTranscriptionUnavailable}
				testAudioBase64={testAudioBase64}
				rawAudioBase64={rawAudioBase64}
				playing={playing}
				playingOriginal={playingOriginal}
				onPlayEnhanced={onPlayEnhanced}
				onPlayOriginal={onPlayOriginal}
				onStop={onStopPlayback}
			/>

			{config && (
				<MemoizedPresetAccordionSelector
					preset={(config.audio_preset as AudioPreset) ?? "auto"}
					config={config}
					showAdvanced={showAdvanced}
					onPresetChange={onPresetChange}
					onToggleAdvanced={onToggleAdvanced}
					onConfigChange={onConfigChange}
					customPresets={customPresets}
					activeCustomPresetId={activeCustomPresetId}
					onSelectCustomPreset={onSelectCustomPreset}
					onSaveCustomPreset={onSaveCustomPreset}
					onRestoreMicDefaults={onRestoreMicDefaults}
				/>
			)}
		</div>
	);
}

// ── Memoised children ─────────────────────────────────────────
// `React.memo` with a custom comparator. The comparator focuses on the
// props that actually affect the rendered output, callback identity
// changes (which happen on every Microphone.tsx render due to inline
// closures) are ignored so a 10–30 Hz `mic_level` push doesn't
// re-render these heavy subtrees.
// `onConfigChange` IS included in the PresetAccordionSelector comparator
// because it's `useCallback`-stable in `useMicrophoneTest` (its
// identity changes only when `updateConfig` changes, which happens
// rarely). Including it lets us skip re-renders even when an upstream
// component forgets to memoise a wrapper. Same for `onPresetChange`.

const MemoizedPresetAccordionSelector = memo(
	PresetAccordionSelector,
	(prev, next) =>
		prev.preset === next.preset &&
		prev.config === next.config &&
		prev.showAdvanced === next.showAdvanced &&
		prev.onConfigChange === next.onConfigChange &&
		prev.onPresetChange === next.onPresetChange &&
		prev.customPresets === next.customPresets &&
		prev.activeCustomPresetId === next.activeCustomPresetId &&
		prev.onSelectCustomPreset === next.onSelectCustomPreset &&
		prev.onSaveCustomPreset === next.onSaveCustomPreset &&
		prev.onRestoreMicDefaults === next.onRestoreMicDefaults,
);

const MemoizedTestReviewPanel = memo(
	TestReviewPanel,
	(prev, next) =>
		prev.durationMs === next.durationMs &&
		prev.quality === next.quality &&
		prev.transcription === next.transcription &&
		prev.transcriptionUnavailable === next.transcriptionUnavailable &&
		prev.testAudioBase64 === next.testAudioBase64 &&
		prev.rawAudioBase64 === next.rawAudioBase64 &&
		prev.playing === next.playing &&
		prev.playingOriginal === next.playingOriginal,
);
