/**
 * TtsPanel — local text-to-speech engines on the Models page.
 *
 * Every engine is a row shaped exactly like a local ASR model row: a Download
 * button while its pack is missing, then Select (the same `Select` / `Active`
 * states the ASR card uses) with the icon-only voice test beside it. The stored
 * `tts_engine` config value IS the selection, so there is no separate engine
 * toggle, and nothing is rendered for an engine that cannot run yet.
 *
 * The test control is ONE icon with three states (play → spinner → stop) and is
 * driven by the `tts_playback_state` push event, so a natural end returns it to
 * play without a poll. Failures become a plain-language toast; the card never
 * renders engine text, timings or "cached sample" diagnostics.
 */

import { Delete01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { memo, useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { LevelBar } from "@/components/feedback/LevelBar";
import {
	ActiveActionButton,
	DownloadActionButton,
	SelectActionButton,
	TestActionButton,
	type TestActionState,
} from "@/components/models/ModelActionButtons";
import { ModelVariantRow } from "@/components/models/ModelGroupList";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useLatestRef } from "@/hooks/useLatestRef";
import { usePython, usePythonEvent } from "@/hooks/usePython";
import { t } from "@/i18n/i18n";
import { formatBytes } from "@/lib/format";

type TtsEngine = string;

/**
 * Engine ids come from the `tts_status.engines` payload, which is produced by
 * the backend's own `ENGINES`/pack registry. No second id literal lives here.
 */
type TtsEngineId = string;

interface TtsVoiceInfo {
	id: string;
	label: string;
	gender: "female" | "male" | "";
}

interface TtsEngineInfo {
	available: boolean;
	label: string;
	download_bytes: number;
	models_dir: string;
	capabilities?: string[];
	voices?: TtsVoiceInfo[];
	languages?: string[];
	default_voice?: string;
}

/** engine → voice → language → cached (no render needed to answer). */
type SampleCachedMap = Record<string, Record<string, Record<string, boolean>>>;

interface TtsStatusData {
	engine: TtsEngine;
	enabled: boolean;
	voice: string;
	language: string;
	/** Voices of the ACTIVE engine (what will speak). */
	voices?: TtsVoiceInfo[];
	languages?: string[];
	engines: Record<string, TtsEngineInfo>;
	sample_cached?: SampleCachedMap;
}

interface TtsSpeakResult {
	ok: boolean;
	error?: string;
	engine?: string;
	voice?: string;
}

interface TtsPrepareProgress {
	engine: string;
	artifact: string;
	artifact_index: number;
	artifact_count: number;
	bytes_done: number;
	bytes_total: number;
	percent: number;
}

/** IPC envelopes are `{ type, data }`; tolerate a bare payload too. */
function unwrap<T>(response: unknown): T {
	const envelope = response as { data?: T } | undefined;
	return (envelope?.data ?? (response as T)) as T;
}

export const TtsPanel = memo(function TtsPanel() {
	const { call } = usePython();
	// Mirror the bridge call: `call` identity can change per render, and a
	// `[call]` effect dep is the documented OOM render-loop class.
	const callRef = useLatestRef(call);
	const [status, setStatus] = useState<TtsStatusData | null>(null);
	/** Engine whose pack is arriving right now (that row shows the spinner). */
	const [preparing, setPreparing] = useState<TtsEngineId | null>(null);
	/** Last pushed byte counter for the in-flight download. */
	const [prepareProgress, setPrepareProgress] =
		useState<TtsPrepareProgress | null>(null);
	/** Engine being removed right now. */
	const [deleting, setDeleting] = useState<TtsEngineId | null>(null);
	/** Engine being made active right now. */
	const [selecting, setSelecting] = useState<TtsEngineId | null>(null);
	/** Engine whose clip is rendering right now (spinner state). */
	const [generating, setGenerating] = useState<TtsEngineId | null>(null);
	/** Engine that is actually playing (driven by `tts_playback_state`). */
	const [playingEngine, setPlayingEngine] = useState<TtsEngineId | null>(null);
	/** Consecutive failures: the second one offers Restart instead of Retry. */
	const failures = useRef(0);
	const playRef = useRef<(engine: TtsEngineId) => void>(() => {});

	const busy = preparing !== null || selecting !== null || deleting !== null;

	const refresh = useCallback(async () => {
		const response = await callRef.current("tts_status");
		setStatus(unwrap<TtsStatusData>(response));
	}, [callRef]);

	useEffect(() => {
		void refresh().catch(() => {
			// The connection banner owns "backend unreachable"; the card stays
			// on its skeleton rather than duplicating that error here.
		});
	}, [refresh]);

	usePythonEvent("tts_playback_state", (data) => {
		const payload = (data ?? {}) as { engine?: unknown; state?: unknown };
		if (typeof payload.engine !== "string") return;
		const engine = payload.engine as TtsEngineId;
		if (payload.state === "playing") {
			setPlayingEngine(engine);
			return;
		}
		setPlayingEngine((current) => (current === engine ? null : current));
	});

	usePythonEvent("tts_prepare_progress", (data) => {
		const payload = (data ?? {}) as Partial<TtsPrepareProgress>;
		if (typeof payload.engine !== "string") return;
		const percent =
			typeof payload.percent === "number" && Number.isFinite(payload.percent)
				? Math.max(0, Math.min(100, payload.percent))
				: 0;
		setPrepareProgress({
			engine: payload.engine,
			artifact: typeof payload.artifact === "string" ? payload.artifact : "",
			artifact_index:
				typeof payload.artifact_index === "number" ? payload.artifact_index : 0,
			artifact_count:
				typeof payload.artifact_count === "number" ? payload.artifact_count : 0,
			bytes_done:
				typeof payload.bytes_done === "number" ? payload.bytes_done : 0,
			bytes_total:
				typeof payload.bytes_total === "number" ? payload.bytes_total : 0,
			percent,
		});
	});

	const run = useCallback(async (action: () => Promise<void>) => {
		try {
			await action();
		} catch {
			// Callers map failures themselves; a rejected transport call is the
			// same plain-language story as a refused render.
			toast.error(t("tts.errorTitle"), {
				description: t("tts.errorBodyGeneric"),
			});
		}
	}, []);

	const selectEngine = useCallback(
		(engine: TtsEngineId) => {
			setSelecting(engine);
			return run(async () => {
				try {
					await callRef.current("set_config", { tts_engine: engine });
					await refresh();
				} finally {
					setSelecting(null);
				}
			});
		},
		[callRef, refresh, run],
	);

	const prepare = useCallback(
		(engine: TtsEngineId) => {
			setPrepareProgress(null);
			setPreparing(engine);
			return run(async () => {
				try {
					await callRef.current("tts_prepare", { engine });
					await refresh();
				} finally {
					setPreparing(null);
				}
			});
		},
		[callRef, refresh, run],
	);

	const remove = useCallback(
		(engine: TtsEngineId) => {
			setDeleting(engine);
			return run(async () => {
				try {
					await callRef.current("tts_delete", { engine });
					await refresh();
				} finally {
					setDeleting(null);
					setPrepareProgress(null);
				}
			});
		},
		[callRef, refresh, run],
	);

	const reportError = useCallback(
		(engine: TtsEngineId, code?: string) => {
			failures.current += 1;
			const body =
				code === "not_installed"
					? t("tts.errorBodyNotInstalled")
					: code === "no_output"
						? t("tts.errorBodyNoOutput")
						: t("tts.errorBodyGeneric");
			const retry = failures.current < 2;
			toast.error(t("tts.errorTitle"), {
				id: `tts-error-${engine}`,
				description: body,
				action: retry
					? {
							label: t("tts.errorActionRetry"),
							onClick: () => void playRef.current(engine),
						}
					: {
							label: t("tts.errorActionRestart"),
							onClick: () => void callRef.current("restart_app"),
						},
			});
		},
		[callRef],
	);

	const play = useCallback(
		async (engine: TtsEngineId) => {
			const activeEngine = status?.engine ?? "off";
			const voice =
				engine === activeEngine
					? (status?.voice ?? "")
					: (status?.engines[engine]?.default_voice ?? "");
			const language =
				engine === activeEngine
					? (status?.language ?? "")
					: (status?.engines[engine]?.languages?.[0] ?? "");
			const cached = Boolean(
				status?.sample_cached?.[engine]?.[voice]?.[language],
			);
			// A cached clip starts instantly: no generating state at all.
			if (!cached) setGenerating(engine);
			try {
				const result = unwrap<TtsSpeakResult>(
					await callRef.current("tts_speak", { engine, sample: true }),
				);
				if (!result.ok) {
					reportError(engine, result.error);
					return;
				}
				failures.current = 0;
				setPlayingEngine(engine);
			} catch {
				reportError(engine, "generic");
			} finally {
				setGenerating(null);
			}
		},
		[callRef, reportError, status],
	);
	playRef.current = (engine) => void play(engine);

	const stop = useCallback(async () => {
		try {
			await callRef.current("tts_stop");
		} finally {
			setPlayingEngine(null);
		}
	}, [callRef]);

	const onTestClick = useCallback(
		(engine: TtsEngineId) => {
			if (playingEngine === engine) {
				void stop();
				return;
			}
			if (playingEngine !== null) {
				void (async () => {
					await stop();
					await play(engine);
				})();
				return;
			}
			void play(engine);
		},
		[play, playingEngine, stop],
	);

	const changeVoice = useCallback(
		(voice: string) =>
			run(async () => {
				await callRef.current("set_config", { tts_voice: voice });
				await refresh();
			}),
		[callRef, refresh, run],
	);

	const changeLanguage = useCallback(
		(language: string) =>
			run(async () => {
				await callRef.current("set_config", { tts_language: language });
				await refresh();
			}),
		[callRef, refresh, run],
	);

	const toggleEnabled = useCallback(
		(enabled: boolean) =>
			run(async () => {
				await callRef.current("set_config", { tts_enabled: enabled });
				await refresh();
			}),
		[callRef, refresh, run],
	);

	const active = status?.engine ?? "off";
	const engines = status?.engines ?? {};
	// Display order is whatever the backend registry ships (Audio8, Magpie).
	const engineIds = Object.keys(engines);
	const enabled = status?.enabled ?? false;
	const selectedVoice = status?.voice ?? "";
	const activeLanguages =
		active === "off"
			? []
			: (engines[active]?.languages ?? status?.languages ?? []);
	const selectedLanguage = status?.language ?? "";

	return (
		<section
			aria-label={t("tts.title")}
			className="rounded-lg border border-border/8 bg-surface-subtle"
		>
			<div className="border-b border-border/8 px-4 py-2.5">
				<h2 className="text-sm font-medium text-foreground">
					{t("tts.title")}
				</h2>
				<p className="mt-0.5 text-xs text-muted-foreground">
					{t("tts.description")}
				</p>
			</div>

			<div className="flex items-center justify-between gap-3 border-b border-border/8 px-4 py-2.5">
				<div className="min-w-0">
					<p className="text-sm font-medium text-foreground">
						{t("tts.enabled")}
					</p>
					<p className="text-xs text-muted-foreground">
						{t("tts.enabledDescription")}
					</p>
				</div>
				<Switch
					checked={enabled}
					onCheckedChange={(next) => void toggleEnabled(next)}
					aria-label={t("tts.enabled")}
				/>
			</div>

			<div className="divide-y divide-border/8">
				{engineIds.map((engine) => {
					const info = engines[engine];
					const label = info?.label ?? engine;
					const available = info?.available ?? false;
					const isActive = active === engine;
					const isPreparing = preparing === engine;
					const sizeLabel = formatBytes(info?.download_bytes ?? 0);
					const downloadLabel = `${t("tts.prepare")} (${sizeLabel})`;
					const voices = info?.voices ?? [];
					const languages = info?.languages ?? [];
					const gendered = voices.filter((voice) => voice.gender !== "");
					const ungendered = voices.filter((voice) => voice.gender === "");
					const testState: TestActionState =
						generating === engine
							? "generating"
							: playingEngine === engine
								? "playing"
								: "idle";
					return (
						<div key={engine}>
							<ModelVariantRow
								name={label}
								headingLevel={3}
								actions={
									<div className="flex items-center gap-2">
										{/* Test exists only on a runnable engine, never as a
										    disabled placeholder. */}
										{available ? (
											<TestActionButton
												state={testState}
												disabled={busy && generating !== engine}
												onClick={() => onTestClick(engine)}
											/>
										) : null}
										{!available ? (
											<DownloadActionButton
												sizeLabel={sizeLabel}
												busy={isPreparing}
												disabled={busy && !isPreparing}
												ariaLabel={
													isPreparing ? t("models.downloading") : downloadLabel
												}
												title={downloadLabel}
												onClick={() => void prepare(engine)}
											/>
										) : isActive ? (
											<ActiveActionButton
												ariaLabel={t("models.card.activeAria", { name: label })}
											/>
										) : (
											<SelectActionButton
												busy={selecting === engine}
												ariaLabel={t("models.card.selectAria", { name: label })}
												onClick={() => void selectEngine(engine)}
											/>
										)}
										{available && !isActive ? (
											<Button
												variant="outline"
												size="icon-sm"
												disabled={busy && deleting !== engine}
												aria-busy={deleting === engine}
												aria-label={`${t("models.deleteModel")} ${label}`}
												title={`${t("models.deleteModel")} ${label}`}
												onClick={() => void remove(engine)}
											>
												<HugeiconsIcon
													icon={Delete01Icon}
													strokeWidth={2}
													className="h-3.5 w-3.5"
												/>
											</Button>
										) : null}
									</div>
								}
							/>

							{isPreparing && prepareProgress?.engine === engine ? (
								<div className="flex flex-col gap-1 border-t border-border/8 px-4 py-2.5">
									<LevelBar
										level={prepareProgress.percent / 100}
										playing={false}
										ariaLabel={downloadLabel}
										ariaValueText={`${prepareProgress.percent}%`}
									/>
									<p className="text-xs text-muted-foreground">
										{prepareProgress.artifact} ·{" "}
										{prepareProgress.artifact_index}/
										{prepareProgress.artifact_count}
									</p>
								</div>
							) : null}

							{isActive ? (
								<div className="flex flex-col gap-3 border-t border-border/8 px-4 py-3">
									{engine === "audio8" ? (
										<p className="text-xs text-muted-foreground">
											{t("tts.audio8Capability")}
										</p>
									) : null}

									{voices.length > 1 ? (
										<div className="flex items-center justify-between gap-3">
											<p className="text-sm font-medium text-foreground">
												{t("tts.voice")}
											</p>
											<Select value={selectedVoice} onValueChange={changeVoice}>
												<SelectTrigger
													className="w-52"
													aria-label={t("tts.voice")}
												>
													<SelectValue />
												</SelectTrigger>
												<SelectContent>
													{ungendered.length > 0 ? (
														<SelectGroup>
															{ungendered.map((voice) => (
																<SelectItem key={voice.id} value={voice.id}>
																	{voice.label}
																</SelectItem>
															))}
														</SelectGroup>
													) : null}
													{(["female", "male"] as const).map((gender) => {
														const group = gendered.filter(
															(voice) => voice.gender === gender,
														);
														if (group.length === 0) return null;
														return (
															<SelectGroup key={gender}>
																<SelectLabel>
																	{gender === "female"
																		? t("tts.genderFemale")
																		: t("tts.genderMale")}
																</SelectLabel>
																{group.map((voice) => (
																	<SelectItem key={voice.id} value={voice.id}>
																		{voice.label}
																	</SelectItem>
																))}
															</SelectGroup>
														);
													})}
												</SelectContent>
											</Select>
										</div>
									) : null}

									{languages.length > 1 ? (
										<div className="flex items-center justify-between gap-3">
											<p className="text-sm font-medium text-foreground">
												{t("tts.language")}
											</p>
											<Select
												value={selectedLanguage}
												onValueChange={changeLanguage}
											>
												<SelectTrigger
													className="w-52"
													aria-label={t("tts.language")}
												>
													<SelectValue />
												</SelectTrigger>
												<SelectContent>
													{activeLanguages.map((code) => (
														<SelectItem key={code} value={code}>
															{code}
														</SelectItem>
													))}
												</SelectContent>
											</Select>
										</div>
									) : null}
								</div>
							) : null}
						</div>
					);
				})}
			</div>

			{active === "off" ? (
				<p className="border-t border-border/8 px-4 py-2.5 text-xs text-muted-foreground">
					{t("tts.selectEngineHint")}
				</p>
			) : null}
		</section>
	);
});
