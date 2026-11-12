/**
 * Providers — one key per provider, three independent model domains.
 *
 * Layout follows the Plugins page: a two-per-row card grid for connections,
 * then one divided surface for model routing. Selections persist through
 * `provider_set_domain`, which reuses the validated `set_config` path. A card
 * button opens the key dialog (the Models → cloud models pattern); failures
 * surface as in-app notifications, never as text under a field.
 */

import { AlertCircleIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useId, useState } from "react";
import PageHeading from "@/components/common/PageHeading";
import { SettingsSection } from "@/components/common/SettingsSection";
import { MeasuredSkeleton } from "@/components/feedback/MeasuredSkeleton";
import { skeletonLoadingLabel } from "@/components/feedback/skeletons";
import { Button } from "@/components/ui/button";
import { useT } from "@/i18n/i18n";
import { DomainCard } from "./components/DomainCard";
import { ProviderCard } from "./components/ProviderCard";
import { ProviderKeyDialog } from "./components/ProviderKeyDialog";
import { SAMPLE_PROVIDER_LIST } from "./lib/sample";
import { useProviderData } from "./lib/useProviderData";

export default function Providers() {
	const t = useT();
	const connectionsHeadingId = useId();
	const [keyTarget, setKeyTarget] = useState<string | null>(null);
	const { data, model, loadError, actions, reload } = useProviderData();
	const keyConnection =
		model?.connections.find(
			(connection) => connection.provider.id === keyTarget,
		) ?? null;

	return (
		<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-4 px-16 pt-20 pb-6">
			<PageHeading
				title={t("providers.title")}
				description={t("providers.subtitle")}
			/>

			{loadError ? (
				<div
					role="alert"
					className="flex items-center justify-between gap-3 rounded-lg border border-border/8 bg-surface-subtle px-4 py-3"
				>
					<div className="flex items-center gap-2 text-sm text-foreground">
						<HugeiconsIcon
							icon={AlertCircleIcon}
							strokeWidth={1.8}
							aria-hidden="true"
							className="size-4 shrink-0 text-destructive"
						/>
						{t("providers.loadFailed")}
					</div>
					<Button size="sm" variant="outline" onClick={() => void reload()}>
						{t("common.retry")}
					</Button>
				</div>
			) : null}

			<MeasuredSkeleton
				stackClassName="gap-4"
				data={data}
				sample={SAMPLE_PROVIDER_LIST}
				id="providers"
				label={skeletonLoadingLabel()}
			>
				{() =>
					model ? (
						<>
							<section
								aria-labelledby={connectionsHeadingId}
								className="flex flex-col gap-4"
							>
								<h2 id={connectionsHeadingId} className="sr-only">
									{t("providers.connectionsTitle")}
								</h2>
								<div className="grid grid-cols-2 gap-4">
									{model.connections.map((connection) => (
										<ProviderCard
											key={connection.provider.id}
											provider={connection.provider}
											onEditKey={() => setKeyTarget(connection.provider.id)}
										/>
									))}
								</div>
							</section>

							<SettingsSection title={t("providers.routingTitle")}>
								{model.domains.map((view) => (
									<DomainCard
										key={view.domain}
										domain={view.domain}
										label={view.label}
										selection={view.selection}
										providers={view.providers}
										models={view.models}
										activeProvider={view.activeProvider}
										busy={view.busy}
										usesCredits={view.usesCredits}
										showConsent={view.showConsent}
										onnxNote={view.onnxNote}
										onEnabledChange={(enabled) =>
											actions.onEnabledChange(view.domain, enabled)
										}
										onProviderChange={(provider) =>
											actions.onProviderChange(view.domain, provider)
										}
										onModelChange={(modelId) =>
											actions.onModelChange(view.domain, modelId)
										}
										onConsentChange={(consent) =>
											actions.onConsentChange(view.domain, consent)
										}
									/>
								))}
							</SettingsSection>
						</>
					) : null
				}
			</MeasuredSkeleton>

			{keyConnection ? (
				<ProviderKeyDialog
					provider={keyConnection.provider}
					draft={keyConnection.draft}
					busy={keyConnection.busy}
					onDraftChange={(value) =>
						actions.onDraftChange(keyConnection.provider.id, value)
					}
					onSave={() => actions.onSave(keyConnection.provider.id)}
					onTest={() => actions.onTest(keyConnection.provider.id)}
					onClear={() => actions.onClear(keyConnection.provider.id)}
					onClose={() => setKeyTarget(null)}
				/>
			) : null}
		</div>
	);
}
