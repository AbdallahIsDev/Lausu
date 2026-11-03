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

import { memo, useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
	ActiveActionButton,
	DownloadActionButton,
	SelectActionButton,
	TestActionButton,
	type TestActionState,
} from "@/components/models/ModelActionButtons";
import { ModelVariantRow } from "@/components/models/ModelGroupList";
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

type TtsEngine = "off" | "audio8" | "magpie";

/** Engines with a pack row, in display order (mirrors the backend tuple). */
const TTS_ENGINES = ["audio8", "magpie"] as const;
type TtsEngineId = (typeof TTS_ENGINES)[number];

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
	/** Engine being made active right now. */
	const [selecting, setSelecting] = useState<TtsEngineId | null>(null);
	/** Engine whose clip is rendering right now (spinner state). */
	const [generating, setGenerating] = useState<TtsEngineId | null>(null);
	/** Engine that is actually playing (driven by `tts_playback_state`). */
	const [playingEngine, setPlayingEngine] = useState<TtsEngineId | null>(null);
	/** Consecutive failures: the second one offers Restart instead of Retry. */
	const failures = useRef(0);
	const playRef = useRef<(engine: TtsEngineId) => void>(() => {});

	const busy = preparing !== null || selecting !== null;

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
				{TTS_ENGINES.map((engine) => {
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
									</div>
								}
							/>

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
