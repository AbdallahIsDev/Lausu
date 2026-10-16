// Active-microphone card.
// Renders the currently-selected microphone (or "System Default")
// header (with the level readout on its trailing edge), the live
// LevelBar, the start/stop test buttons (with the recording dot +
// countdown on their trailing edge while a test runs), the
// TestReviewPanel (post-test transcription, quality + playback),
// and the PresetAccordionSelector.
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
import { cn } from "@/lib/utils";
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
	hasFiltersEnabled: boolean;
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
	onRetest: () => void;
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
	hasFiltersEnabled,
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
	onRetest,
	onToggleAdvanced,
	onPresetChange,
	onConfigChange,
}: ActiveMicrophoneCardProps) {
	return (
		<div
			className={cn(
				// Inter-child spacing is owned by this flex stack (one
				// consistent `gap-3` rhythm): the children carry no `mt-*`
				// of their own. The direct children are the header, the
				// LevelBar, the test controls row, `TestReviewPanel` and
				// the preset-selector wrapper.
				"flex flex-col gap-3 rounded-lg border border-border/8 p-4 transition-colors",
				"bg-surface-subtle",
			)}
		>
			{/* Mic header. The level readout rides this row's trailing edge
			    (above the bar) rather than the controls row's, so the space
			    under the bar is reserved for the test readout alone and the
			    controls never shift when a test starts.
			    Two groups: the outer row is `items-end` so the level readout
			    sits on the bottom edge, while the icon + title/subtitle group
			    keeps its own `items-center` (an `items-end` on the row alone
			    would drag the icon down with it). */}
			<div className="flex items-end gap-3 min-w-0">
				<div className="flex items-center gap-3 min-w-0">
					<HugeiconsIcon
						icon={Mic02Icon}
						strokeWidth={1.625}
						className="h-4 w-4 shrink-0"
					/>
					<div className="min-w-0">
						<p className="text-sm font-medium text-foreground truncate">
							{activeMicName}
						</p>
						{/* Description only for System Default, its text carries
                                        information (which device the OS routes to). For a selected
                                        device a "Selected microphone" line is redundant with the
                                        radio list + card context (C-MIC-13), so no desc renders. */}
						{isSystemDefault && (
							<p className="text-xs text-muted-foreground">
								{t("microphone.systemDefaultDesc")}
							</p>
						)}
					</div>
				</div>

				{/*(a11y): the live level is NOT announced — it fluctuates at up
                                    to 30 Hz (the ``mic_level`` push rate) and would spam a
                                    screen reader. ``aria-hidden`` is therefore unconditional:
                                    the sibling ``LevelBar`` already exposes the same value to
                                    assistive tech via its ``role="progressbar"`` +
                                    ``aria-valuenow``, so this text is the visual duplicate. */}
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

				{/* Live monitor ("hear yourself"): pure frontend
				passthrough, no recording. Disabled while a test,
				playback, or start is in flight (one mic stream at a
				time). */}
				{!testRunning && (
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
				)}

				{/* Test readout (recording dot + countdown), trailing edge of
                                    this row. Renders nothing while no test runs, so the row
                                    keeps its button-driven height and nothing jumps. */}
				<LiveQualityFeedback
					isRecording={testRunning}
					elapsedSeconds={testElapsed}
					totalSeconds={MICROPHONE_TEST_DURATION_SEC}
				/>
			</div>

			{/* Live-monitor hint + error. The hint shows while
			listening (headphones warning against feedback); errors
			map the hook's code to copy. */}
			{liveListening && !testRunning && (
				<p className="text-xs text-muted-foreground">
					{t("microphoneTest.liveListenHint")}
				</p>
			)}
			{liveListenError && !testRunning && (
				<p className="text-xs text-destructive" role="alert">
					{t(
						liveListenError === "denied"
							? "microphoneTest.liveListenDenied"
							: liveListenError === "unavailable"
								? "microphoneTest.liveListenUnavailable"
								: "microphoneTest.liveListenFailed",
					)}
				</p>
			)}

			{/* : Test Review Panel, memoised. Re-renders only when
                            the post-test data (duration, quality, audio, playback
                            state) actually changes, NOT on every mic_level push.
                            The comparator ignores callback identity (the parent
                            Microphone.tsx creates fresh inline closures for
                            onPlayEnhanced / onPlayOriginal / onStop / onRetest on
                            every render, those don't affect TestReviewPanel's
                            rendered output, so skipping the re-render is safe). */}
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
				onRetest={onRetest}
				hasFiltersEnabled={hasFiltersEnabled}
				// Wire the preset-applier so detected-noise
				// issues render a one-click "Apply Noisy Room preset"
				// CTA. ``onPresetChange`` is useCallback-stable in
				// useMicrophoneTest, so identity churn never re-renders
				// the panel (verified by the custom memo comparator below,
				// which now includes ``onApplyPreset`` + ``currentPreset``).
				onApplyPreset={onPresetChange}
				currentPreset={
					config ? ((config.audio_preset as AudioPreset) ?? "auto") : undefined
				}
			/>

			{/* : Preset selector (accordion + radio), memoised.
                            Re-renders only when the preset / config / showAdvanced
                            flag changes, NOT on every mic_level push. The
                            comparator includes `onConfigChange` and `onPresetChange`
                            (both useCallback-stable in `useMicrophoneTest`) but
                            excludes `onToggleAdvanced` (inline closure in
                            Microphone.tsx, identity changes per render but the
                            behavior is identical, so skipping is safe). */}
			<div>
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
		</div>
	);
}

// ── : Memoised children ─────────────────────────────────────────
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
		prev.playingOriginal === next.playingOriginal &&
		prev.hasFiltersEnabled === next.hasFiltersEnabled &&
		// Include the new preset-applier + current preset in
		// the comparator. ``onApplyPreset`` is useCallback-stable
		// (delegated to ``onPresetChange`` in useMicrophoneTest) so
		// identity churn is rare; ``currentPreset`` flips when the
		// user picks a new preset, which SHOULD re-render so the
		// recommendation CTA's disabled-state updates.
		prev.onApplyPreset === next.onApplyPreset &&
		prev.currentPreset === next.currentPreset,
);
