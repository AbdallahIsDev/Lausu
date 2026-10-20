import { PlayIcon, StopIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n/i18n";

const RESULT_UNMOUNT_DELAY_MS = 250;

interface QualityData {
	volume_level: "good" | "low" | "very_low";
	volume_rms: number;
	peak_level: number;
	noise_level: "low" | "moderate" | "high";
	has_voice: boolean;
	has_clipping: boolean;
	detected_issues: string[];
	estimated_transcription_quality: number;
	silence_ratio: number;
	speech_quality?: number;
	speech_ratio?: number;
	speech_rms?: number;
	speech_peak?: number;
	noise_floor_rms?: number;
	vad_used?: boolean;
}

interface TestReviewPanelProps {
	durationMs: number;
	quality: QualityData | null;
	/** Transcription of the test recording (null/undefined = none). */
	transcription?: string | null;
	/** True when no speech model is loaded, so no transcription can exist. */
	transcriptionUnavailable?: boolean;
	/** True while the microphone-quality chain is active (audio_preset !== "off"). */
	enhancementActive: boolean;
	testAudioBase64: string | null;
	rawAudioBase64: string | null;
	playing: boolean;
	playingOriginal: boolean;
	onPlayEnhanced: () => void;
	onPlayOriginal: () => void;
	onStop: () => void;
}

interface TestResultSnapshot {
	durationMs: number;
	quality: QualityData | null;
	transcription: string | null;
	transcriptionUnavailable: boolean;
	enhancementActive: boolean;
	testAudioBase64: string | null;
	rawAudioBase64: string | null;
}

const DETECTED_ISSUE_LITERALS: Record<string, string> = {
	"High background noise": "microphoneTest.detectedIssueCodes.high_noise",
	"Moderate background noise":
		"microphoneTest.detectedIssueCodes.moderate_noise",
	"Audio clipping detected": "microphoneTest.detectedIssueCodes.clipping",
	"Volume too low, speak closer to the microphone":
		"microphoneTest.detectedIssueCodes.volume_too_low",
	"Volume is low, consider raising input gain":
		"microphoneTest.detectedIssueCodes.volume_low",
	"No voice detected, try speaking during the test":
		"microphoneTest.detectedIssueCodes.no_voice",
};

function translateDetectedIssue(raw: string): string {
	const key = DETECTED_ISSUE_LITERALS[raw];
	if (key) return t(key);
	return raw;
}

const VOLUME_PENALTY = { good: 0, low: 18, very_low: 38 } as const;
const NOISE_PENALTY = { low: 0, moderate: 12, high: 30 } as const;

function getAudioQuality(quality: QualityData): number {
	if (typeof quality.speech_quality === "number") {
		return Math.max(0, Math.min(100, Math.round(quality.speech_quality)));
	}
	const score =
		100 -
		VOLUME_PENALTY[quality.volume_level] -
		NOISE_PENALTY[quality.noise_level] -
		(quality.has_clipping ? 22 : 0);
	return Math.max(0, Math.min(100, Math.round(score)));
}

function getAudioQualityColor(score: number): string {
	if (score >= 50) {
		const successWeight = ((score - 50) / 50) * 100;
		return `color-mix(in oklch, var(--success) ${successWeight}%, var(--warning))`;
	}
	return `color-mix(in oklch, var(--warning) ${score * 2}%, var(--destructive))`;
}

export function TestReviewPanel({
	durationMs,
	quality,
	transcription,
	transcriptionUnavailable,
	enhancementActive,
	testAudioBase64,
	rawAudioBase64,
	playing,
	playingOriginal,
	onPlayEnhanced,
	onPlayOriginal,
	onStop,
}: TestReviewPanelProps) {
	const [retainedResult, setRetainedResult] =
		useState<TestResultSnapshot | null>(null);

	const transcriptionText = transcription?.trim() ?? "";
	const hasVerdict =
		durationMs > 0 || quality !== null || transcriptionText !== "";
	const hasTestResult = Boolean(
		testAudioBase64 || rawAudioBase64 || hasVerdict,
	);

	const currentResult: TestResultSnapshot = {
		durationMs,
		quality,
		transcription: transcription ?? null,
		transcriptionUnavailable: transcriptionUnavailable === true,
		enhancementActive,
		testAudioBase64,
		rawAudioBase64,
	};
	const displayedResult = hasTestResult ? currentResult : retainedResult;
	const displayedTranscriptionText =
		displayedResult?.transcription?.trim() ?? "";
	const showTranscriptionQuality =
		displayedTranscriptionText !== "" &&
		!(displayedResult?.transcriptionUnavailable ?? false);
	const audioQuality = displayedResult?.quality
		? getAudioQuality(displayedResult.quality)
		: null;

	useEffect(() => {
		if (!hasTestResult) return;
		setRetainedResult({
			durationMs,
			quality,
			transcription: transcription ?? null,
			transcriptionUnavailable: transcriptionUnavailable === true,
			enhancementActive,
			testAudioBase64,
			rawAudioBase64,
		});
	}, [
		hasTestResult,
		durationMs,
		quality,
		transcription,
		transcriptionUnavailable,
		enhancementActive,
		testAudioBase64,
		rawAudioBase64,
	]);

	useEffect(() => {
		if (hasTestResult || retainedResult === null) return;
		const timer = window.setTimeout(
			() => setRetainedResult(null),
			RESULT_UNMOUNT_DELAY_MS,
		);
		return () => window.clearTimeout(timer);
	}, [hasTestResult, retainedResult]);

	return (
		<div className="collapse-root" data-open={hasTestResult}>
			<div inert={!hasTestResult} aria-hidden={!hasTestResult}>
				{displayedResult && (
					// Divider section of the parent microphone card. The card's
					// `divide-y`/`gap` owns inter-section rhythm, so no own margin.
					<div className="flex flex-col gap-4 border-t border-border/8 bg-surface-subtle p-4">
						<header className="flex items-baseline justify-between gap-3">
							<h2 className="text-sm font-medium text-foreground">
								{t("microphoneTest.title")}
							</h2>
							<span className="text-xs tabular-nums text-foreground">
								{t("microphoneTest.duration", {
									duration: (displayedResult.durationMs / 1000).toFixed(1),
								})}
							</span>
						</header>

						{/* Transcript: only rendered when the backend produced text. An
			    empty result is normal (short test, no speech) and must not
			    leave an explanatory block behind. */}
						{displayedTranscriptionText && (
							<div className="flex flex-col gap-1.5">
								<p className="text-xs font-medium text-muted-foreground">
									{t("microphone.youSaid")}
								</p>
								<p
									className="line-clamp-3 wrap-break-word rounded-lg border border-border/8 bg-background px-3 py-2 text-sm text-foreground"
									title={displayedTranscriptionText}
									data-testid="test-transcription"
								>
									{displayedTranscriptionText}
								</p>
							</div>
						)}

						{displayedResult.quality && (
							<div
								className="flex flex-col gap-3"
								// BG-71: the verdict updates after a test, announce the
								// complete quality + issues block atomically.
								aria-live="polite"
								aria-atomic="true"
							>
								<div className="flex items-center justify-between gap-3">
									<span className="text-sm text-foreground">
										{t("microphoneTest.audioQuality")}
									</span>
									<span
										className="text-sm font-medium tabular-nums"
										style={{
											color: getAudioQualityColor(audioQuality ?? 0),
										}}
										data-testid="audio-quality-value"
									>
										{audioQuality ?? 0}%
									</span>
								</div>

								{showTranscriptionQuality && (
									<div className="flex items-center justify-between gap-3">
										<span className="text-sm text-foreground">
											{t("microphoneTest.estimatedQuality")}
										</span>
										<span
											className="text-sm font-medium tabular-nums text-foreground"
											data-testid="estimated-quality-value"
										>
											{displayedResult.quality.estimated_transcription_quality}%
										</span>
									</div>
								)}

								{displayedResult.quality.detected_issues.length > 0 && (
									<div className="flex flex-col gap-2">
										<output className="text-xs font-medium text-muted-foreground">
											{t("microphoneTest.detectedIssues")}
										</output>
										<ul className="flex flex-col gap-2">
											{displayedResult.quality.detected_issues.map((issue) => (
												<li
													key={issue}
													className="flex items-center gap-2 text-sm text-foreground"
													data-testid="detected-issue-row"
												>
													<span
														className="size-1.5 shrink-0 rounded-full bg-warning"
														aria-hidden="true"
													/>
													<span>{translateDetectedIssue(issue)}</span>
												</li>
											))}
										</ul>
									</div>
								)}
							</div>
						)}

						{/* Enhanced-left / Original-right: Enhanced is the A/B compare
					    partner, so it exists only while the quality chain is active
					    (chain off makes it byte-identical to Original). */}
						<div className="flex flex-wrap items-center gap-2">
							{displayedResult.enhancementActive &&
								displayedResult.testAudioBase64 && (
									<Button
										variant="outline"
										size="sm"
										className="gap-2"
										onClick={
											playing && !playingOriginal ? onStop : onPlayEnhanced
										}
									>
										<HugeiconsIcon
											icon={playing && !playingOriginal ? StopIcon : PlayIcon}
											strokeWidth={1.625}
											className="h-4 w-4"
										/>
										{playing && !playingOriginal
											? t("microphoneTest.stop")
											: t("microphoneTest.playEnhanced")}
									</Button>
								)}

							{displayedResult.rawAudioBase64 && (
								<Button
									variant="outline"
									size="sm"
									className="gap-2"
									onClick={playing && playingOriginal ? onStop : onPlayOriginal}
								>
									<HugeiconsIcon
										icon={playing && playingOriginal ? StopIcon : PlayIcon}
										strokeWidth={1.625}
										className="h-4 w-4"
									/>
									{playing && playingOriginal
										? t("microphoneTest.stop")
										: t("microphoneTest.playOriginal")}
								</Button>
							)}
						</div>
					</div>
				)}
			</div>
		</div>
	);
}
