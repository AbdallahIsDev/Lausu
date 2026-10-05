// Renders ONE plugin-declared setting, choosing the control from its
// declared `type` (bool → Switch, enum → Select, int/float → number
// Input, string → text Input). Values live in the parent page's state,
// seeded from the payload and reset when the plugin changes.

import { SettingRow } from "@/components/common/SettingRow";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { PluginSettingSpec } from "@/types/plugins";

interface PluginSettingRowProps {
	spec: PluginSettingSpec;
	value: unknown;
	onChange: (value: unknown) => void;
}

/** Clamp a numeric value to the manifest's declared range. */
function clampNumber(raw: number, spec: PluginSettingSpec): number {
	let next = raw;
	if (spec.min !== undefined && Number.isFinite(next)) {
		next = Math.max(next, spec.min);
	}
	if (spec.max !== undefined && Number.isFinite(next)) {
		next = Math.min(next, spec.max);
	}
	return next;
}

export function PluginSettingRow({
	spec,
	value,
	onChange,
}: PluginSettingRowProps) {
	const controlId = `plugin-setting-${spec.key}`;

	if (spec.type === "bool") {
		return (
			// No `htmlFor`: Radix Switch/Select roots are <button>s, not
			// labelable form inputs, so the visible label stays a <span>
			// and the control carries its own accessible name.
			<SettingRow label={spec.label} info={spec.description || undefined}>
				<Switch
					checked={value === true}
					onCheckedChange={(checked) => onChange(checked)}
					aria-label={spec.label}
					data-testid={`plugin-setting-${spec.key}`}
				/>
			</SettingRow>
		);
	}

	if (spec.type === "enum") {
		const selected = typeof value === "string" ? value : "";
		return (
			<SettingRow label={spec.label} info={spec.description || undefined}>
				<Select value={selected} onValueChange={(next) => onChange(next)}>
					<SelectTrigger
						className="w-48"
						aria-label={spec.label}
						data-testid={`plugin-setting-${spec.key}`}
					>
						<SelectValue />
					</SelectTrigger>
					<SelectContent>
						{(spec.choices ?? []).map((choice) => (
							<SelectItem key={choice} value={choice}>
								{choice}
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</SettingRow>
		);
	}

	if (spec.type === "int" || spec.type === "float") {
		const step = spec.type === "int" ? 1 : "any";
		return (
			<SettingRow
				label={spec.label}
				info={spec.description || undefined}
				htmlFor={controlId}
			>
				<Input
					id={controlId}
					type="number"
					step={step}
					min={spec.min}
					max={spec.max}
					className="w-32"
					value={typeof value === "number" ? String(value) : ""}
					onChange={(e) => {
						const parsed = Number(e.target.value);
						// An empty / non-numeric input keeps the field blank
						// rather than writing NaN into plugin state.
						if (e.target.value === "" || Number.isNaN(parsed)) {
							onChange(e.target.value === "" ? "" : parsed);
							return;
						}
						onChange(
							spec.type === "int"
								? Math.round(clampNumber(parsed, spec))
								: clampNumber(parsed, spec),
						);
					}}
					aria-label={spec.label}
					data-testid={`plugin-setting-${spec.key}`}
				/>
			</SettingRow>
		);
	}

	return (
		<SettingRow
			label={spec.label}
			info={spec.description || undefined}
			htmlFor={controlId}
		>
			<Input
				id={controlId}
				type="text"
				className="w-48"
				value={typeof value === "string" ? value : ""}
				onChange={(e) => onChange(e.target.value)}
				aria-label={spec.label}
				data-testid={`plugin-setting-${spec.key}`}
			/>
		</SettingRow>
	);
}
