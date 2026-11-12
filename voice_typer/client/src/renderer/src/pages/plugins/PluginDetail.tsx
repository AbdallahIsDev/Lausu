// Plugin detail page entry point (lazy route chunk target).
//
// Activation toggle FIRST: whether this plugin owns dictation is the
// decision this page exists to make, so its row sits above every
// plugin-declared setting. Data lives in `./hooks/usePlugins`, the
// generic setting controls in `./components/PluginSettingRow`.

import { ArrowLeft01Icon, Plug01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useCallback, useEffect, useState } from "react";
import PageHeading from "@/components/common/PageHeading";
import { SettingRow } from "@/components/common/SettingRow";
import { EmptyState } from "@/components/feedback/EmptyState";
import { MeasuredSkeleton } from "@/components/feedback/MeasuredSkeleton";
import { skeletonLoadingLabel } from "@/components/feedback/skeletons";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useT } from "@/i18n/i18n";
import {
	type PluginInfo,
	type PluginSettingSpec,
	settingValue,
} from "@/types/plugins";
import { PluginSettingRow } from "./components/PluginSettingRow";
import { usePlugins } from "./hooks/usePlugins";
import { SAMPLE_PLUGIN_DETAIL } from "./lib/sample";
import { usePluginSelection } from "./lib/usePluginSelection";

export default function PluginDetail() {
	const t = useT();
	const {
		plugins,
		activePluginId,
		setActivePlugin,
		setPluginSetting,
		loading,
	} = usePlugins();
	const selectedPluginId = usePluginSelection((s) => s.selectedPluginId);
	const clearSelection = usePluginSelection((s) => s.clearSelection);
	const plugin =
		selectedPluginId === null
			? undefined
			: plugins.find((p) => p.id === selectedPluginId);

	// Local, unsaved setting values, seeded from the payload (stored value
	// or declared default) whenever the selected plugin changes.
	const [values, setValues] = useState<Record<string, unknown>>({});
	useEffect(() => {
		if (!plugin) return;
		const seeded: Record<string, unknown> = {};
		for (const spec of plugin.settings) {
			seeded[spec.key] = settingValue(plugin, spec);
		}
		setValues(seeded);
	}, [plugin]);

	const goBack = useCallback(() => clearSelection(), [clearSelection]);

	// Optimistic, but not fire-and-forget: the backend validates the value
	// against the manifest and persists it beside the manifest, so a refusal
	// reverts the control instead of showing a value nothing stored.
	const handleSettingChange = useCallback(
		(plugin: PluginInfo, spec: PluginSettingSpec, next: unknown) => {
			const previous = plugin.values[spec.key] ?? spec.default;
			setValues((prev) => ({ ...prev, [spec.key]: next }));
			void setPluginSetting(plugin.id, spec.key, next).then((ok) => {
				if (ok) return;
				setValues((prev) => ({ ...prev, [spec.key]: previous }));
			});
		},
		[setPluginSetting],
	);

	const backButton = (
		<Button
			variant="outline"
			size="sm"
			className="self-start gap-2"
			onClick={goBack}
		>
			<HugeiconsIcon
				icon={ArrowLeft01Icon}
				strokeWidth={2}
				className="h-4 w-4"
			/>
			{t("plugins.back")}
		</Button>
	);

	// Nothing selected (or unknown id once loaded): the page still
	// offers the way back to the list. While still loading, the
	// measured wrap below shows the skeleton instead of this.
	if (!plugin && !loading) {
		return (
			<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-4 px-16 pt-20 pb-6">
				{backButton}
				<EmptyState
					icon={Plug01Icon}
					title={t("plugins.notFoundTitle")}
					description={t("plugins.notFoundDescription")}
				/>
			</div>
		);
	}

	return (
		<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-4 px-16 pt-20 pb-6">
			{backButton}
			<MeasuredSkeleton
				stackClassName="gap-4"
				data={plugin ?? null}
				sample={SAMPLE_PLUGIN_DETAIL}
				id="plugin-detail"
				label={skeletonLoadingLabel()}
			>
				{(p) => (
					<>
						<PageHeading title={p.name} description={p.description} />
						<div className="flex flex-col gap-4">
							<div className="overflow-hidden rounded-lg border border-border/8 bg-surface-subtle">
								<SettingRow
									label={t("plugins.activateLabel")}
									info={t("plugins.activateDescription")}
								>
									<Switch
										checked={activePluginId === p.id}
										// ON points at this plugin; OFF writes "" which
										// restores the built-in local model.
										onCheckedChange={(checked) =>
											setActivePlugin(checked ? p.id : "")
										}
										aria-label={t("plugins.activateAria")}
										data-testid="plugin-activate-switch"
									/>
								</SettingRow>
							</div>

							{p.settings.length > 0 && (
								<div className="flex flex-col gap-2">
									<p className="px-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
										{t("plugins.settingsSection")}
									</p>
									<div className="overflow-hidden rounded-lg border border-border/8 bg-surface-subtle">
										<div className="divide-y divide-border/8">
											{p.settings.map((spec) => (
												<PluginSettingRow
													key={spec.key}
													spec={spec}
													value={values[spec.key] ?? settingValue(p, spec)}
													onChange={(next) =>
														handleSettingChange(p, spec, next)
													}
												/>
											))}
										</div>
									</div>
								</div>
							)}
						</div>
					</>
				)}
			</MeasuredSkeleton>
		</div>
	);
}
