// The ADR-0030 translator's install surface. One row: Download / Cancel /
// Delete, a determinate progress bar and a persistent status slot. The
// download is the ONLY trigger for the GGUF; consent is granted in the
// shared dialog before any IPC call can reach the network.

import { Cancel01Icon, Delete01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useCallback, useEffect, useState } from "react";
import { LevelBar } from "@/components/feedback/LevelBar";
import { DownloadActionButton } from "@/components/models/ModelActionButtons";
import { Button } from "@/components/ui/button";
import {
	expireModelStatusSnapshot,
	fetchSharedModelStatus,
	patchCachedModelDownloaded,
} from "@/hooks/models/modelStatusCache";
import { usePython, usePythonEvent } from "@/hooks/usePython";
import { useT } from "@/i18n/i18n";
import { consentBodyKey, openConsentGate } from "@/lib/consentGate";
import type { LausuConfig } from "@/types/config";
import { TRANSLATION_MODEL_ID } from "./translationModel";

interface DownloadResult {
	success: boolean;
	error?: string;
	cancelled?: boolean;
	consent_required?: boolean;
	code?: string;
}

interface TranslationModelDownloadRowProps {
	config: LausuConfig | null;
	/** Translated label of the row's Download control. */
	downloadLabel: string;
	/** Translated product label ("1.31 GB" included). */
	sizeLabel: string;
}

export function TranslationModelDownloadRow({
	config,
	downloadLabel,
	sizeLabel,
}: TranslationModelDownloadRowProps) {
	const t = useT();
	const { call } = usePython();
	const [downloaded, setDownloaded] = useState<boolean | null>(null);
	const [busy, setBusy] = useState(false);
	const [progress, setProgress] = useState(0);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let live = true;
		void fetchSharedModelStatus(call).then((status) => {
			if (!live) return;
			const entry = status?.[TRANSLATION_MODEL_ID];
			setDownloaded(
				typeof entry?.downloaded === "boolean" ? entry.downloaded : false,
			);
		});
		return () => {
			live = false;
		};
	}, [call]);

	usePythonEvent("download_progress", (data) => {
		if (!data || data.model !== TRANSLATION_MODEL_ID) return undefined;
		if (typeof data.progress === "number") setProgress(data.progress);
		if (
			data.status === "Download cancelled" ||
			data.status === "Download complete"
		) {
			setBusy(false);
		}
		return undefined;
	});

	const start = useCallback(async () => {
		setBusy(true);
		setProgress(0);
		setError(null);
		try {
			const result = await call<DownloadResult>("download_model", {
				model: TRANSLATION_MODEL_ID,
			});
			if (result.cancelled) {
				setBusy(false);
				setProgress(0);
				return;
			}
			if (result.consent_required) {
				setBusy(false);
				openConsentGate({
					consentField: "huggingface_consent",
					bodyKey: consentBodyKey("huggingface_consent"),
					onAllow: () => void start(),
				});
				return;
			}
			if (result.success) {
				setDownloaded(true);
				setBusy(false);
				setProgress(100);
				expireModelStatusSnapshot();
				void fetchSharedModelStatus(call);
				return;
			}
			setError(
				result.code === "translation_disk_space_insufficient"
					? t("settings.translationDownloadInsufficientSpace")
					: t("settings.translationDownloadFailed"),
			);
		} catch {
			setError(t("settings.translationDownloadFailed"));
		}
		setBusy(false);
	}, [call, t]);

	const requestDownload = useCallback(() => {
		if (config?.huggingface_consent) {
			void start();
			return;
		}
		openConsentGate({
			consentField: "huggingface_consent",
			bodyKey: consentBodyKey("huggingface_consent"),
			onAllow: () => void start(),
		});
	}, [config?.huggingface_consent, start]);

	const cancel = useCallback(async () => {
		try {
			await call("cancel_model_download", { model: TRANSLATION_MODEL_ID });
		} catch {
			// The bridge reports the failure; the in-flight call still resolves.
		}
	}, [call]);

	const remove = useCallback(async () => {
		setError(null);
		try {
			const result = await call<{ success: boolean }>("delete_model", {
				model: TRANSLATION_MODEL_ID,
			});
			if (result.success) {
				setDownloaded(false);
				setProgress(0);
				patchCachedModelDownloaded(TRANSLATION_MODEL_ID, false);
				expireModelStatusSnapshot();
			}
		} catch {
			setError(t("settings.translationDownloadFailed"));
		}
	}, [call, t]);

	const caption = error
		? error
		: busy
			? t("settings.translationDownloadProgressAria", {
					percent: String(progress),
				})
			: downloaded === false && config?.translation_enabled
				? t("settings.translationDownloadRequired")
				: downloaded === true
					? t("settings.translationDownloaded")
					: "";

	return (
		<div className="flex w-72 flex-col items-end gap-1">
			<div className="flex items-center gap-2">
				{busy && (
					<Button
						variant="ghost"
						size="icon-xs"
						className="text-muted-foreground hover:text-destructive"
						aria-label={t("settings.translationCancelDownload")}
						title={t("settings.translationCancelDownload")}
						onClick={() => void cancel()}
					>
						<HugeiconsIcon
							icon={Cancel01Icon}
							strokeWidth={2.5}
							className="h-3 w-3"
						/>
					</Button>
				)}
				{downloaded && !busy && (
					<Button
						variant="ghost"
						size="icon-xs"
						className="text-muted-foreground hover:text-destructive"
						aria-label={t("settings.translationDelete")}
						title={t("settings.translationDelete")}
						onClick={() => void remove()}
					>
						<HugeiconsIcon
							icon={Delete01Icon}
							strokeWidth={2.5}
							className="h-3 w-3"
						/>
					</Button>
				)}
				<DownloadActionButton
					sizeLabel={sizeLabel}
					busy={busy}
					disabled={busy || downloaded === true}
					ariaLabel={downloadLabel}
					onClick={requestDownload}
				/>
			</div>
			{/* Reserved slot: starting or stopping the transfer never moves
			    the buttons (C-UI-5), and the bar is the shared LevelBar. */}
			<div className="flex h-6 w-full flex-col justify-end gap-1">
				{busy && (
					<LevelBar
						level={Math.min(1, Math.max(0, progress / 100))}
						playing={false}
						ariaLabel={t("settings.translationDownloadProgressAria", {
							percent: String(progress),
						})}
						ariaValueText={`${progress}%`}
					/>
				)}
				<span
					role="status"
					className={`truncate text-right text-xs ${error ? "text-destructive" : "text-muted-foreground"}`}
				>
					{caption}
				</span>
			</div>
		</div>
	);
}
