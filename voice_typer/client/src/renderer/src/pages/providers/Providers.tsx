/**
 * Providers — one key per provider, three independent model domains.
 *
 * Each provider row owns its credential (masked read-only, never echoed) and a
 * connection test. The three domain blocks below are independent: Dictation
 * (ASR), Speech (TTS) and Polish (LLM) each pick their own provider + model,
 * toggle on/off, and gate paid/remote use behind consent. Selections persist
 * through `provider_set_domain`, which reuses the validated `set_config` path.
 */

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useLatestRef } from "@/hooks/useLatestRef";
import { usePython, usePythonEvent } from "@/hooks/usePython";
import { useT } from "@/i18n/i18n";

type Domain = "asr" | "tts" | "llm";

const DOMAINS: Domain[] = ["asr", "tts", "llm"];

interface ProviderModel {
	id: string;
	label: string;
	domains?: string[];
	context_length?: number | null;
	free?: boolean;
	note?: string | null;
}

interface ProviderEntry {
	id: string;
	label: string;
	domains: string[];
	local: boolean;
	auth: string;
	models: ProviderModel[];
	unsupported_reason: Record<string, string>;
	key: { configured: boolean; masked: string };
	consent_required: boolean;
}

interface DomainSelection {
	provider: string;
	model_id: string;
	consent: boolean;
	fallback: string;
	enabled: boolean;
}

interface ProviderListData {
	providers: ProviderEntry[];
	domains: Record<Domain, DomainSelection>;
}

interface OnnxState {
	model: string;
	state: string;
	error: string | null;
}

/** IPC envelopes are `{ type, data }`; tolerate a bare payload too. */
function unwrap<T>(response: unknown): T {
	const envelope = response as { data?: T } | undefined;
	return (envelope?.data ?? (response as T)) as T;
}

function errorText(err: unknown): string {
	return err instanceof Error ? err.message : String(err);
}

export default function Providers() {
	const t = useT();
	const { call } = usePython();
	// Mirror the bridge call: `call` identity can change per render, and a
	// `[call]` effect dep is the documented OOM render-loop class.
	const callRef = useLatestRef(call);
	const [data, setData] = useState<ProviderListData | null>(null);
	const [catalogues, setCatalogues] = useState<Record<string, ProviderModel[]>>(
		{},
	);
	const [drafts, setDrafts] = useState<Record<string, string>>({});
	const [busy, setBusy] = useState<string | null>(null);
	const [message, setMessage] = useState<string | null>(null);
	const [onnx, setOnnx] = useState<OnnxState | null>(null);

	const refresh = useCallback(async () => {
		const response = await callRef.current("provider_list");
		setData(unwrap<ProviderListData>(response));
	}, [callRef]);

	useEffect(() => {
		let cancelled = false;
		(async () => {
			try {
				const response = await callRef.current("provider_list");
				if (!cancelled) setData(unwrap<ProviderListData>(response));
			} catch (err) {
				if (!cancelled) setMessage(errorText(err));
			}
		})();
		return () => {
			cancelled = true;
		};
	}, [callRef]);

	usePythonEvent("provider_local_onnx_state", (payload) => {
		const state = payload as OnnxState | undefined;
		if (state) setOnnx(state);
	});

	const loadModels = useCallback(
		async (provider: string) => {
			const response = await callRef.current("provider_models", { provider });
			const payload = unwrap<{ models?: ProviderModel[] }>(response);
			setCatalogues((prev) => ({ ...prev, [provider]: payload.models ?? [] }));
		},
		[callRef],
	);

	const run = useCallback(async (key: string, action: () => Promise<void>) => {
		setBusy(key);
		setMessage(null);
		try {
			await action();
		} catch (err) {
			setMessage(errorText(err));
		} finally {
			setBusy(null);
		}
	}, []);

	const saveKey = (provider: string) =>
		run(`key:${provider}`, async () => {
			await callRef.current("provider_set_key", {
				provider,
				key: drafts[provider] ?? "",
			});
			setDrafts((prev) => ({ ...prev, [provider]: "" }));
			await refresh();
			await loadModels(provider);
		});

	const clearKey = (provider: string) =>
		run(`key:${provider}`, async () => {
			await callRef.current("provider_clear_key", { provider });
			await refresh();
			setCatalogues((prev) => ({ ...prev, [provider]: [] }));
		});

	const testProvider = (provider: string) =>
		run(`test:${provider}`, async () => {
			await callRef.current("provider_test", { provider });
			await loadModels(provider);
		});

	const setDomain = (domain: Domain, patch: Record<string, unknown>) =>
		run(`domain:${domain}`, async () => {
			await callRef.current("provider_set_domain", { domain, ...patch });
			await refresh();
		});

	const onProviderChange = (domain: Domain, provider: string) =>
		run(`domain:${domain}`, async () => {
			await callRef.current("provider_set_domain", {
				domain,
				provider,
				model_id: "",
			});
			await refresh();
			await loadModels(provider);
		});

	const domainLabel: Record<Domain, string> = {
		asr: t("providers.domainAsr"),
		tts: t("providers.domainTts"),
		llm: t("providers.domainLlm"),
	};

	return (
		<div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
			<header className="flex flex-col gap-1">
				<h1 className="text-lg font-semibold text-foreground">
					{t("providers.title")}
				</h1>
				<p className="text-xs text-muted-foreground">
					{t("providers.subtitle")}
				</p>
			</header>

			{message ? (
				<p role="status" className="text-xs text-destructive">
					{message}
				</p>
			) : null}

			<section
				aria-label={t("providers.keysTitle")}
				className="flex flex-col gap-2 rounded-lg border border-border/8 bg-surface p-4"
			>
				<h2 className="text-xs font-medium text-foreground">
					{t("providers.keysTitle")}
				</h2>
				{(data?.providers ?? []).map((provider) => (
					<div
						key={provider.id}
						className="flex flex-col gap-2 rounded-lg border border-border/8 p-3"
					>
						<div className="flex flex-wrap items-center gap-2">
							<span className="text-sm font-medium text-foreground">
								{provider.label}
							</span>
							{provider.domains.map((domain) => (
								<span
									key={domain}
									className="rounded-lg border border-border/8 px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground"
								>
									{domain}
								</span>
							))}
							<span className="text-[10px] text-muted-foreground">
								{provider.local ? t("providers.local") : t("providers.remote")}
							</span>
						</div>
						<p className="text-xs text-muted-foreground">
							{provider.key.configured
								? t("providers.keyMasked", { key: provider.key.masked })
								: t("providers.keyMissing")}
						</p>
						{provider.auth === "api_key" ? (
							<div className="flex flex-wrap items-center gap-2">
								<Input
									type="password"
									className="max-w-xs"
									value={drafts[provider.id] ?? ""}
									placeholder={t("providers.keysPlaceholder")}
									onChange={(event) =>
										setDrafts((prev) => ({
											...prev,
											[provider.id]: event.target.value,
										}))
									}
								/>
								<Button
									size="sm"
									disabled={
										busy !== null || !(drafts[provider.id] ?? "").trim()
									}
									onClick={() => void saveKey(provider.id)}
								>
									{t("providers.keySave")}
								</Button>
								<Button
									size="sm"
									variant="outline"
									disabled={busy !== null}
									onClick={() => void testProvider(provider.id)}
								>
									{t("providers.keyTest")}
								</Button>
								<Button
									size="sm"
									variant="outline"
									disabled={busy !== null || !provider.key.configured}
									onClick={() => void clearKey(provider.id)}
								>
									{t("providers.keyClear")}
								</Button>
							</div>
						) : null}
						{Object.entries(provider.unsupported_reason).map(
							([domain, reason]) => (
								<p key={domain} className="text-[11px] text-muted-foreground">
									{domain}: {reason}
								</p>
							),
						)}
					</div>
				))}
			</section>

			{DOMAINS.map((domain) => {
				const selection = data?.domains?.[domain];
				const options = (data?.providers ?? []).filter((provider) =>
					provider.domains.includes(domain),
				);
				const activeProvider = selection?.provider || options[0]?.id || "";
				const activeEntry = options.find(
					(provider) => provider.id === activeProvider,
				);
				// Only a remote provider spends the user's credits.
				const usesCredits = Boolean(selection?.enabled) && !activeEntry?.local;
				const models =
					catalogues[activeProvider] ??
					options.find((provider) => provider.id === activeProvider)?.models ??
					[];
				return (
					<section
						key={domain}
						aria-label={domainLabel[domain]}
						className="flex flex-col gap-3 rounded-lg border border-border/8 bg-surface p-4"
					>
						<div className="flex items-center justify-between gap-2">
							<h2 className="text-xs font-medium text-foreground">
								{domainLabel[domain]}
							</h2>
							<Switch
								checked={Boolean(selection?.enabled)}
								aria-label={domainLabel[domain]}
								onCheckedChange={(checked) =>
									void setDomain(domain, {
										provider: selection?.provider || activeProvider,
										enabled: checked,
									})
								}
							/>
						</div>
						<div className="grid gap-2 sm:grid-cols-2">
							<Select
								value={activeProvider}
								onValueChange={(value) => void onProviderChange(domain, value)}
							>
								<SelectTrigger size="sm" aria-label={t("providers.provider")}>
									<SelectValue placeholder={t("providers.provider")} />
								</SelectTrigger>
								<SelectContent>
									{options.map((provider) => (
										<SelectItem key={provider.id} value={provider.id}>
											{provider.label}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
							<Select
								value={selection?.model_id ?? ""}
								onValueChange={(value) =>
									void setDomain(domain, {
										provider: activeProvider,
										model_id: value,
									})
								}
							>
								<SelectTrigger size="sm" aria-label={t("providers.model")}>
									<SelectValue placeholder={t("providers.model")} />
								</SelectTrigger>
								<SelectContent>
									{models.length === 0 ? (
										<SelectItem value="__none" disabled>
											{t("providers.noModels")}
										</SelectItem>
									) : (
										models.map((model) => (
											<SelectItem key={model.id} value={model.id}>
												{model.label}
												{model.context_length
													? ` · ${t("providers.contextTokens", { count: String(model.context_length) })}`
													: ""}
												{" · "}
												{model.free ? t("providers.free") : t("providers.paid")}
											</SelectItem>
										))
									)}
								</SelectContent>
							</Select>
						</div>
						<div className="flex items-center gap-2 text-xs text-muted-foreground">
							<Checkbox
								aria-label={t("providers.consent")}
								checked={Boolean(selection?.consent)}
								onCheckedChange={(checked) =>
									void setDomain(domain, { consent: checked === true })
								}
							/>
							{t("providers.consent")}
						</div>
						{usesCredits ? (
							<p className="text-[11px] text-muted-foreground">
								{t("providers.credits")}
							</p>
						) : null}
						{domain === "llm" && onnx ? (
							<p role="status" className="text-[11px] text-muted-foreground">
								{onnx.state === "loading"
									? t("providers.onnxLoading", { model: onnx.model })
									: onnx.state === "failed"
										? t("providers.onnxFailed", { model: onnx.model })
										: t("providers.onnxReady", { model: onnx.model })}
							</p>
						) : null}
					</section>
				);
			})}
		</div>
	);
}
