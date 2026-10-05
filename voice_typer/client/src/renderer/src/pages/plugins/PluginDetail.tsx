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
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useT } from "@/i18n/i18n";
import { settingValue } from "@/types/plugins";
import { PluginSettingRow } from "./components/PluginSettingRow";
import { usePlugins } from "./hooks/usePlugins";
import { usePluginSelection } from "./lib/usePluginSelection";

export default function PluginDetail() {
	const t = useT();
	const { plugins, activePluginId, setActivePlugin } = usePlugins();
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

	const handleSettingChange = useCallback((specKey: string, next: unknown) => {
		setValues((prev) => ({ ...prev, [specKey]: next }));
		// TODO: persistence needs a new `set_plugin_setting` IPC command,
		// which does not exist yet. Until it does these edits are
		// session-local and are deliberately NOT written to app config:
		// plugin settings are not app-config fields.
	}, []);

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

	// Nothing selected: the page still offers the way back to the list.
	if (!plugin) {
		return (
			<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-6 px-16 pt-20 pb-6">
				{backButton}
				<EmptyState
					icon={Plug01Icon}
					title={t("plugins.notFoundTitle")}
					description={t("plugins.notFoundDescription")}
				/>
			</div>
		);
	}

	const isActive = activePluginId === plugin.id;

	return (
		<div className="mx-auto flex min-h-full w-full max-w-4xl flex-col gap-6 px-16 pt-20 pb-6">
			{backButton}

			<PageHeading title={plugin.name} description={plugin.description} />

			<div className="flex flex-col gap-6">
				<div className="overflow-hidden rounded-lg border border-border/8 bg-surface-subtle">
					<SettingRow
						label={t("plugins.activateLabel")}
						info={t("plugins.activateDescription")}
					>
						<Switch
							checked={isActive}
							// ON points at this plugin; OFF writes "" which
							// restores the built-in local model.
							onCheckedChange={(checked) =>
								setActivePlugin(checked ? plugin.id : "")
							}
							aria-label={t("plugins.activateAria")}
							data-testid="plugin-activate-switch"
						/>
					</SettingRow>
				</div>

				{plugin.settings.length > 0 && (
					<div className="flex flex-col gap-2">
						<p className="px-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
							{t("plugins.settingsSection")}
						</p>
						<div className="overflow-hidden rounded-lg border border-border/8 bg-surface-subtle">
							<div className="divide-y divide-border/8">
								{plugin.settings.map((spec) => (
									<PluginSettingRow
										key={spec.key}
										spec={spec}
										value={values[spec.key]}
										onChange={(next) => handleSettingChange(spec.key, next)}
									/>
								))}
							</div>
						</div>
					</div>
				)}
			</div>
		</div>
	);
}
