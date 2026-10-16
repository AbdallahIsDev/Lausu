// OfflinePackSection, Settings → Advanced card for the pack state machine.
// One status query (`get_status` → `offline_pack {state, installed_version,
// download_progress}`) seeds the card on mount; the shared
// `useOfflinePackDownload` hook drives live updates, so this card and the
// App-level pack toast (usePackUpdateToast) never disagree.
// Every recovery action reuses `check_offline_pack_update`; there is no
// remove IPC, so there is no Remove button.

import { useEffect, useRef, useState } from "react";
import { ReadonlyRow } from "@/components/common/ReadonlyRow";
import { SettingsSection } from "@/components/common/SettingsSection";
import { Button } from "@/components/ui/button";
import { useLatestRef } from "@/hooks/useLatestRef";
import {
	type OfflinePackStatus,
	useOfflinePackDownload,
} from "@/hooks/useOfflinePackDownload";
import { usePython } from "@/hooks/usePython";
import { t } from "@/i18n/i18n";
import type { IsVisibleFn } from "./types";

/** Backend `offline_pack` snapshot fields the mount catch-up reads. */
interface BackendPackSnapshot {
	state: string | null;
	installedVersion: string | null;
	downloadProgress: number | null;
}

function parseBackendSnapshot(value: unknown): BackendPackSnapshot {
	const blank: BackendPackSnapshot = {
		state: null,
		installedVersion: null,
		downloadProgress: null,
	};
	if (!value || typeof value !== "object") return blank;
	const op = value as Record<string, unknown>;
	const rawState = op["state"];
	const rawVersion = op["installed_version"];
	const rawProgress = op["download_progress"];
	return {
		state:
			typeof rawState === "string" && rawState.length > 0 ? rawState : null,
		installedVersion:
			typeof rawVersion === "string" && rawVersion.length > 0
				? rawVersion
				: null,
		downloadProgress:
			typeof rawProgress === "number" && Number.isFinite(rawProgress)
				? Math.max(0, Math.min(100, Math.round(rawProgress)))
				: null,
	};
}

/** Backend PK-2 `state` literals line up with the hook literals. */
const BACKEND_STATES: ReadonlySet<string> = new Set([
	"outdated",
	"downloading",
	"verifying",
	"ready",
	"missing",
]);

function mapBackendState(state: string | null): OfflinePackStatus {
	if (state !== null && BACKEND_STATES.has(state)) {
		return state as OfflinePackStatus;
	}
	return "idle";
}

type PackAction = "download" | "retry" | "repair" | null;

function actionFor(status: OfflinePackStatus): PackAction {
	if (status === "missing" || status === "idle" || status === "outdated") {
		return "download";
	}
	if (
		status === "failed" ||
		status === "worker-crashed" ||
		status === "worker-unloaded"
	) {
		return "retry";
	}
	if (status === "corrupt") return "repair";
	return null;
}

export interface OfflinePackSectionProps {
	/** Search-filter predicate. Optional, defaults to "always visible". */
	isVisible?: IsVisibleFn;
}

const ALWAYS_VISIBLE: IsVisibleFn = () => true;

/** Translated labels rendered by this component, folded into the
 *  Advanced page's search universe (see `useSettingsSearch`) so queries
 *  like "pack" / "offline engine" / "retry" route here. */
export function getOfflinePackSectionLabels(): string[] {
	return [
		t("pack.offlinePackTitle"),
		t("pack.offlinePackDescription"),
		t("pack.packStatus"),
		t("pack.packInstalledVersion"),
		t("pack.downloadOfflineEngine"),
		t("pack.packRetryDownload"),
		t("pack.packRepairPack"),
	];
}

export default function OfflinePackSection({
	isVisible = ALWAYS_VISIBLE,
}: OfflinePackSectionProps = {}) {
	const { call } = usePython();
	const callRef = useLatestRef(call);
	const live = useOfflinePackDownload();
	const [snapshot, setSnapshot] = useState<BackendPackSnapshot | null>(null);
	const [actionBusy, setActionBusy] = useState(false);
	const aliveRef = useRef(true);
	useEffect(() => {
		aliveRef.current = true;
		return () => {
			aliveRef.current = false;
		};
	}, []);

	// Mount catch-up: the single status query. The hook owns live
	// updates after this; a failed fetch leaves the card on the hook's
	// idle state (missing + Download action), never a stuck loader.
	useEffect(() => {
		let cancelled = false;
		const load = async () => {
			try {
				const res = await callRef.current<{
					offline_pack?: Record<string, unknown>;
				}>("get_status");
				if (!cancelled) setSnapshot(parseBackendSnapshot(res?.offline_pack));
			} catch {
				if (!cancelled) {
					setSnapshot({
						state: null,
						installedVersion: null,
						downloadProgress: null,
					});
				}
			}
		};
		load();
		return () => {
			cancelled = true;
		};
	}, [callRef]);

	// The hook wins once it has seen an event; before that the mount
	// snapshot covers cold starts (e.g. backend already downloading).
	const effective: OfflinePackStatus =
		live.status !== "idle"
			? live.status
			: mapBackendState(snapshot?.state ?? null);
	const effectiveProgress: number | null =
		live.progress ??
		(effective === "downloading" ? (snapshot?.downloadProgress ?? null) : null);

	const onAction = async () => {
		if (actionBusy) return;
		setActionBusy(true);
		try {
			await call("check_offline_pack_update", {});
		} catch {
			// Bridge missing / IPC failure: user can click again.
		} finally {
			if (aliveRef.current) setActionBusy(false);
		}
	};

	const title = t("pack.offlinePackTitle");
	const statusLabel = t("pack.packStatus");
	const versionLabel = t("pack.packInstalledVersion");

	let statusValue: string;
	if (snapshot === null && live.status === "idle") {
		statusValue = t("pack.packStateChecking");
	} else if (
		effective === "downloading" &&
		typeof effectiveProgress === "number"
	) {
		statusValue = t("pack.downloadingOfflineEngine", {
			percent: String(effectiveProgress),
		});
	} else if (
		effective === "downloading" ||
		effective === "verifying" ||
		effective === "worker-starting"
	) {
		statusValue = t("pack.preparingOfflineEngine");
	} else if (effective === "ready") {
		statusValue = t("pack.packStateReady");
	} else if (effective === "outdated") {
		statusValue = t("pack.packStateOutdated");
	} else if (effective === "failed") {
		statusValue = t("pack.packStateFailed");
	} else if (effective === "corrupt") {
		statusValue = t("pack.packStateCorrupt");
	} else if (effective === "worker-crashed") {
		statusValue = t("pack.packStateWorkerCrashed");
	} else if (effective === "worker-unloaded") {
		statusValue = t("pack.packStateWorkerUnloaded");
	} else {
		statusValue = t("pack.packStateMissing");
	}

	const versionValue =
		snapshot === null
			? t("pack.packStateChecking")
			: (snapshot.installedVersion ?? t("pack.packNotInstalled"));

	const action = actionFor(effective);
	const actionLabel =
		action === "retry"
			? t("pack.packRetryDownload")
			: action === "repair"
				? t("pack.packRepairPack")
				: t("pack.downloadOfflineEngine");

	if (
		![title, statusLabel, versionLabel].some((l) =>
			isVisible(l, undefined, title),
		)
	) {
		return null;
	}

	return (
		<div data-testid="offline-pack-section">
			<SettingsSection
				title={title}
				description={t("pack.offlinePackDescription")}
			>
				{isVisible(statusLabel, undefined, title) && (
					<ReadonlyRow
						label={statusLabel}
						value={<span aria-live="polite">{statusValue}</span>}
					/>
				)}
				{isVisible(versionLabel, undefined, title) && (
					<ReadonlyRow label={versionLabel} value={versionValue} />
				)}
				{action !== null && (
					<div className="flex flex-wrap items-center justify-end gap-2 p-4">
						<Button
							variant="outline"
							size="sm"
							onClick={() => void onAction()}
							disabled={actionBusy}
							aria-label={t("pack.downloadOfflineEngineAria")}
						>
							{actionBusy ? t("pack.downloadOfflineEngineBusy") : actionLabel}
						</Button>
					</div>
				)}
			</SettingsSection>
		</div>
	);
}
