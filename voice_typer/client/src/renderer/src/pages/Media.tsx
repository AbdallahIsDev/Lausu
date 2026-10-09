// Media page (ADR-0023): link or local file → phased transcription
// progress (same card for URL and file sources). Job lifecycle lives in
// `media/hooks/useMediaJob`; this file is the view.

import {
	AlertCircleIcon,
	CheckmarkCircle01Icon,
	Folder02Icon,
	HistoryIcon,
	PlayCircleIcon,
	Upload01Icon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useCallback, useEffect, useRef, useState } from "react";
import PageHeading from "@/components/common/PageHeading";
import { SettingRow } from "@/components/common/SettingRow";
import { Spinner } from "@/components/feedback/Spinner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useNavigation } from "@/hooks/useNavigation";
import { useT } from "@/i18n/i18n";
import { formatClockDuration } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useMediaJob } from "./media/hooks/useMediaJob";
import { isNoModelError } from "./media/lib/mediaErrorCopy";

/** ADR-0023 E11: past this length the page warns about the total time. */
const LONG_MEDIA_SECONDS = 4 * 3600;

export default function MediaPage() {
	const t = useT();
	const { navigate } = useNavigation();
	const { job, starting, running, start, cancel } = useMediaJob();
	const [source, setSource] = useState("");
	const [useSubtitles, setUseSubtitles] = useState(true);
	const [dragOver, setDragOver] = useState(false);
	const fileInputRef = useRef<HTMLInputElement>(null);

	// Native drop: absolute paths (web File objects hide them).
	useEffect(() => {
		const api = window.window_;
		if (!api?.onDragDropFiles) return;
		return api.onDragDropFiles((paths) => {
			if (Array.isArray(paths) && paths.length > 0 && paths[0]) {
				setSource(paths[0]);
			}
		});
	}, []);

	const trimmed = source.trim();
	const canStart = trimmed.length > 0 && !running && !starting;
	const percent = Math.max(0, Math.min(100, Math.round(job.progress * 100)));
	const phaseLabel =
		job.phase === "downloading"
			? t("media.phaseDownloading")
			: job.phase === "transcribing"
				? t("media.phaseTranscribing")
				: t("media.phaseLoadingModel");
	const isLongMedia =
		job.durationSeconds !== null && job.durationSeconds > LONG_MEDIA_SECONDS;

	const handleStart = useCallback(() => {
		if (!canStart) return;
		void start(trimmed, useSubtitles);
	}, [canStart, start, trimmed, useSubtitles]);

	const onPickFile = () => {
		fileInputRef.current?.click();
	};

	return (
		<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-6 px-16 pt-20 pb-6">
			<PageHeading
				title={t("media.title")}
				description={t("media.description")}
			/>

			{/* Hidden file picker: drag-drop stays the primary path on Tauri. */}
			<input
				ref={fileInputRef}
				type="file"
				accept="audio/*,video/*"
				className="sr-only"
				aria-hidden
				tabIndex={-1}
				disabled={running}
				onChange={(e) => {
					const file = e.target.files?.[0];
					if (file) setSource(file.name);
					e.target.value = "";
				}}
			/>

			<div className="flex flex-col gap-3 rounded-lg border border-border/10 bg-surface-subtle">
				{/* Drop zone + link field share one clean row stack. */}
				<div className="flex flex-col gap-3 p-4">
					<button
						type="button"
						aria-label={t("media.dropZoneAria")}
						onClick={onPickFile}
						onDragOver={(e) => {
							e.preventDefault();
							setDragOver(true);
						}}
						onDragLeave={() => setDragOver(false)}
						onDrop={(e) => {
							e.preventDefault();
							setDragOver(false);
							const path =
								e.dataTransfer.getData("text/uri-list") ||
								e.dataTransfer.getData("text/plain");
							if (path) setSource(path.replace(/^file:\/\//, ""));
						}}
						className={cn(
							"flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-12 transition-colors",
							"border-border/10 bg-background focus-visible:ring-1 focus-visible:ring-ring",
							dragOver && "border-primary/40 bg-primary/5",
						)}
					>
						<HugeiconsIcon
							icon={Upload01Icon}
							strokeWidth={1.5}
							className="h-8 w-8 text-muted-foreground"
						/>
						<span className="text-sm text-foreground">
							{t("media.dropZoneTitle")}
						</span>
						<span className="text-xs text-muted-foreground">
							{t("media.browseFile")}
						</span>
					</button>

					<div className="flex items-center gap-3">
						<div className="h-px flex-1 bg-border/5" />
						<span className="text-[11px] uppercase tracking-wide text-muted-foreground">
							{t("media.orLink")}
						</span>
						<div className="h-px flex-1 bg-border/5" />
					</div>

					<div className="flex flex-wrap items-center gap-2">
						<Input
							id="media-source"
							value={source}
							onChange={(e) => setSource(e.target.value)}
							placeholder={t("media.sourcePlaceholder")}
							disabled={running}
							className="min-w-0 flex-1"
							onKeyDown={(e) => {
								if (e.key === "Enter") handleStart();
							}}
						/>
						<Button onClick={handleStart} disabled={!canStart}>
							{starting ? (
								<Spinner className="border-current" decorative />
							) : (
								<HugeiconsIcon
									icon={PlayCircleIcon}
									strokeWidth={2}
									className="h-4 w-4"
								/>
							)}
							{t("media.start")}
						</Button>
						{running && (
							<Button variant="outline" onClick={() => void cancel()}>
								{t("media.cancel")}
							</Button>
						)}
					</div>
				</div>

				<SettingRow
					label={t("media.useSubtitlesLabel")}
					info={t("media.useSubtitlesInfo")}
				>
					<Switch
						checked={useSubtitles}
						onCheckedChange={setUseSubtitles}
						disabled={running}
						aria-label={t("media.useSubtitlesLabel")}
					/>
				</SettingRow>
			</div>

			{/* Same progress card for link and local file sources. */}
			{running && (
				<div
					className="flex flex-col gap-3 rounded-lg border border-border/10 bg-surface-subtle p-4"
					role="status"
					aria-live="polite"
				>
					<div className="flex flex-wrap items-baseline justify-between gap-2">
						<span className="text-sm font-medium text-foreground">
							{phaseLabel}
						</span>
						<span className="text-xs text-muted-foreground tabular-nums">
							{t("media.percent", { percent: String(percent) })}
							{job.etaSeconds !== null &&
								` · ${t("media.eta", {
									time: formatClockDuration(job.etaSeconds),
								})}`}
							{job.durationSeconds !== null &&
								` · ${t("media.duration", {
									time: formatClockDuration(job.durationSeconds),
								})}`}
						</span>
					</div>
					<div
						className="h-1.5 w-full overflow-hidden rounded-full bg-border"
						role="progressbar"
						aria-valuemin={0}
						aria-valuemax={100}
						aria-valuenow={percent}
						aria-label={t("media.percent", { percent: String(percent) })}
					>
						<div
							className="h-full rounded-full bg-primary transition-transform duration-300"
							style={{ width: `${percent}%` }}
						/>
					</div>
					{isLongMedia && (
						<p className="text-xs text-muted-foreground">
							{t("media.longMediaNotice")}
						</p>
					)}
				</div>
			)}

			{job.phase === "done" && (
				<div
					className="flex flex-col gap-3 rounded-lg border border-border/10 bg-surface-subtle p-4"
					role="status"
				>
					<div className="flex items-center gap-2">
						<HugeiconsIcon
							icon={CheckmarkCircle01Icon}
							strokeWidth={2}
							className="h-4 w-4 text-primary"
						/>
						<span className="text-sm font-medium text-foreground">
							{t("media.completeTitle")}
						</span>
					</div>
					<p className="text-sm text-muted-foreground">
						{job.partial
							? t("media.partialDescription", {
									chars: String(job.chars ?? 0),
								})
							: t("media.completeDescription", {
									chars: String(job.chars ?? 0),
								})}
					</p>
					{job.rowId !== null && (
						<div>
							<Button
								variant="outline"
								size="sm"
								onClick={() => navigate("history")}
							>
								<HugeiconsIcon
									icon={HistoryIcon}
									strokeWidth={2}
									className="h-4 w-4"
								/>
								{t("media.openHistory")}
							</Button>
						</div>
					)}
				</div>
			)}

			{job.phase === "error" && (
				<div
					className="flex flex-col gap-3 rounded-lg border border-border/10 bg-surface-subtle p-4"
					role="alert"
				>
					<div className="flex items-center gap-2">
						<HugeiconsIcon
							icon={AlertCircleIcon}
							strokeWidth={2}
							className="h-4 w-4 text-destructive"
						/>
						<span className="text-sm font-medium text-foreground">
							{t("media.errorTitle")}
						</span>
					</div>
					<p className="text-sm text-muted-foreground">
						{job.errorKey ? t(job.errorKey) : t("media.errorGeneric")}
					</p>
					{isNoModelError(job.errorCode) && (
						<div>
							<Button
								variant="outline"
								size="sm"
								onClick={() => navigate("models")}
							>
								<HugeiconsIcon
									icon={Folder02Icon}
									strokeWidth={2}
									className="h-4 w-4"
								/>
								{t("media.noModelAction")}
							</Button>
						</div>
					)}
				</div>
			)}
		</div>
	);
}
