import type { Ref } from "react";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	getLocale,
	getLocaleLabel,
	type Locale,
	SUPPORTED_LOCALES,
	setLocale,
	t,
	useT,
} from "@/i18n/i18n";
import { HEADING_CLASS } from "../lib/constants";

const LOCALE_OPTIONS = SUPPORTED_LOCALES.map((locale) => ({
	value: locale,
	label: getLocaleLabel(locale),
}));

export interface WelcomeStepProps {
	headingRef: Ref<HTMLHeadingElement>;
	/** Number of input devices from the existing onboarding IPC. */
	microphoneCount?: number;
	/** Re-run the read-only microphone probe. */
	onCheckMicrophones?: () => void;
}

export function WelcomeStep({
	headingRef,
	microphoneCount = 0,
	onCheckMicrophones,
}: WelcomeStepProps) {
	useT();
	const currentLocale = getLocale();

	return (
		<>
			<h2 ref={headingRef} tabIndex={-1} className={HEADING_CLASS}>
				{t("onboarding.welcomeTitle")}
			</h2>
			<p className="text-sm text-muted-foreground">
				{t("onboarding.welcomeDescription")}
			</p>
			<p className="text-xs text-muted-foreground">
				{t("onboarding.orientation")}
			</p>
			<div
				className="flex flex-col gap-2"
				data-testid="onboarding-language-picker"
			>
				<label
					className="text-xs font-medium text-muted-foreground"
					htmlFor="onboarding-language-select"
				>
					{t("settings.appLanguage")}
				</label>
				<Select
					value={currentLocale}
					onValueChange={(v) => setLocale(v as Locale)}
				>
					<SelectTrigger
						id="onboarding-language-select"
						className="w-full"
						aria-label={t("settings.appLanguage")}
					>
						<SelectValue placeholder={t("settings.appLanguage")} />
					</SelectTrigger>
					<SelectContent>
						{LOCALE_OPTIONS.map((opt) => (
							<SelectItem key={opt.value} value={opt.value}>
								{opt.label}
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</div>
			{/* Read-only mic check on the Welcome step. No OS permission
			    prompt here: the check reports what the OS already exposes
			    and points at Settings → Microphone when nothing is found. */}
			<div
				className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/8 bg-surface-subtle px-3.5 py-3"
				data-testid="onboarding-microphone-check"
			>
				<p
					className={`text-xs ${microphoneCount > 0 ? "text-muted-foreground" : "text-foreground"}`}
				>
					{microphoneCount > 0
						? t("onboarding.microphoneReady", {
								count: String(microphoneCount),
							})
						: t("onboarding.microphoneMissing")}
				</p>
				{onCheckMicrophones ? (
					<Button
						type="button"
						variant="outline"
						size="sm"
						onClick={onCheckMicrophones}
					>
						{t("onboarding.microphoneCheck")}
					</Button>
				) : null}
			</div>
		</>
	);
}

export default WelcomeStep;
