/**
 * TtsPanel — local text-to-speech engines on the Models page.
 *
 * Every engine is a row shaped exactly like a local ASR model row: a Download
 * button while its pack is missing, then Select (the same `Select` / `Active`
 * states the ASR card uses) with a test-render button beside it. The stored
 * `tts_engine` config value IS the selection, so there is no separate toggle
 * control, and nothing is rendered for an engine that cannot run yet.
 *
 * The buttons come from `ModelActionButtons`, the module both surfaces share,
 * so TTS actions can never drift from the ASR ones.
 */

import { memo, useCallback, useEffect, useState } from "react";
import {
	ActiveActionButton,
	DownloadActionButton,
	SelectActionButton,
	TestActionButton,
} from "@/components/models/ModelActionButtons";
import { ModelVariantRow } from "@/components/models/ModelGroupList";
import { usePython } from "@/hooks/usePython";
import { t } from "@/i18n/i18n";
import { formatBytes } from "@/lib/format";

type TtsEngine = "off" | "audio8" | "magpie";

/** Engines with a pack row, in display order (mirrors the backend tuple). */
const TTS_ENGINES = ["audio8", "magpie"] as const;
type TtsEngineId = (typeof TTS_ENGINES)[number];

interface TtsEngineInfo {
	available: boolean;
	label: string;
	download_bytes: number;
	models_dir: string;
}

interface TtsStatusData {
	engine: TtsEngine;
	voice: string;
	language: string;
	engines: Record<string, TtsEngineInfo>;
}

interface TtsSpeakResult {
	engine: string;
	duration_s: number;
	wall_s: number;
	realtime_factor: number;
}

/** IPC envelopes are `{ type, data }`; tolerate a bare payload too. */
function unwrap<T>(response: unknown): T {
	const envelope = response as { data?: T } | undefined;
	return (envelope?.data ?? (response as T)) as T;
}

export const TtsPanel = memo(function TtsPanel() {
	const { call } = usePython();
	const [status, setStatus] = useState<TtsStatusData | null>(null);
	/** Engine whose pack is arriving right now (that row shows the spinner). */
	const [preparing, setPreparing] = useState<TtsEngineId | null>(null);
	/** Engine being made active right now. */
	const [selecting, setSelecting] = useState<TtsEngineId | null>(null);
	/** Engine whose sample is being rendered right now. */
	const [speaking, setSpeaking] = useState<TtsEngineId | null>(null);
	const [message, setMessage] = useState<string | null>(null);

	const busy = preparing !== null || selecting !== null || speaking !== null;

	const refresh = useCallback(async () => {
		try {
			const response = await call("tts_status");
			setStatus(unwrap<TtsStatusData>(response));
		} catch (err) {
			setMessage(err instanceof Error ? err.message : String(err));
		}
	}, [call]);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const run = useCallback(async (action: () => Promise<void>) => {
		setMessage(null);
		try {
			await action();
		} catch (err) {
			setMessage(err instanceof Error ? err.message : String(err));
		}
	}, []);

	const selectEngine = useCallback(
		(engine: TtsEngineId) => {
			setSelecting(engine);
			return run(async () => {
				try {
					await call("set_config", { tts_engine: engine });
					await refresh();
				} finally {
					setSelecting(null);
				}
			});
		},
		[call, refresh, run],
	);

	const prepare = useCallback(
		(engine: TtsEngineId) => {
			setPreparing(engine);
			return run(async () => {
				try {
					await call("tts_prepare", { engine });
					await refresh();
				} finally {
					setPreparing(null);
				}
			});
		},
		[call, refresh, run],
	);

	const speak = useCallback(
		(engine: TtsEngineId) => {
			setSpeaking(engine);
			return run(async () => {
				try {
					const result = unwrap<TtsSpeakResult>(
						await call("tts_speak", {
							text: t("tts.sampleText"),
							engine,
						}),
					);
					setMessage(
						`${result.engine}: ${result.wall_s}s wall, ${result.duration_s}s audio, ${result.realtime_factor}x realtime`,
					);
				} finally {
					setSpeaking(null);
				}
			});
		},
		[call, run],
	);

	const active = status?.engine ?? "off";
	const engines = status?.engines ?? {};

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

			<div className="divide-y divide-border/8">
				{TTS_ENGINES.map((engine) => {
					const info = engines[engine];
					const label = info?.label ?? engine;
					const available = info?.available ?? false;
					const isActive = active === engine;
					const isPreparing = preparing === engine;
					const sizeLabel = formatBytes(info?.download_bytes ?? 0);
					const downloadLabel = `${t("tts.prepare")} (${sizeLabel})`;
					return (
						<ModelVariantRow
							key={engine}
							name={label}
							meta={
								<span className="text-muted-foreground">
									{available ? t("tts.ready") : t("tts.missing")}
								</span>
							}
							actions={
								<div className="flex items-center gap-2">
									{/* Test exists only on a runnable engine, never as a
									    disabled placeholder. */}
									{available ? (
										<TestActionButton
											busy={speaking === engine}
											disabled={busy && speaking !== engine}
											onClick={() => void speak(engine)}
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
					);
				})}
			</div>

			{message ? (
				<p className="border-t border-border/8 px-4 py-2.5 text-xs text-muted-foreground">
					{message}
				</p>
			) : null}
		</section>
	);
});
