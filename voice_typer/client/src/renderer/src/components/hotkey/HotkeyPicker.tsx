import {
	Cancel01Icon,
	ChevronDownIcon,
	KeyboardIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { t } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import { HotkeyChips } from "./HotkeyChips";
import { formatHotkeyLabel, tryCommitHotkey } from "./hotkey-utils";
import { formatHotkeyForMessage } from "./hotkey-validation";
import { useHotkeyCapture } from "./useHotkeyCapture";

// The resting pill is sized by the 22px keycap chip, while the capture label
// is a shorter text line, so the control shrank the moment capture began.
// Pinning the chip-row height keeps both states the same box.
const CAPTURE_BUTTON_SIZE = "min-h-9";

interface HotkeyPickerProps {
	value: string;
	onChange: (hotkey: string) => void;
	mode: "single" | "combo";
	presets?: { value: string; label: string }[];
	className?: string;
	"aria-label"?: string;
	onCaptureStart?: () => void;
	onCaptureEnd?: () => void;
	occupiedHotkeys?: string[];
	allowClear?: boolean;
	/** Surface the push-to-talk key contract while capturing. */
	pushToTalk?: boolean;
}

export function HotkeyPicker({
	value,
	onChange,
	mode,
	presets,
	className,
	"aria-label": ariaLabel = t("hotkeyPicker.ariaLabel"),
	onCaptureStart,
	onCaptureEnd,
	occupiedHotkeys,
	allowClear = false,
	pushToTalk = false,
}: HotkeyPickerProps) {
	const {
		recording,
		secondsRemaining,
		heldModifiersLabel,
		startRecording,
		cancelRecording,
		setError,
		containerRef,
	} = useHotkeyCapture({
		value,
		mode,
		onChange,
		onCaptureStart,
		onCaptureEnd,
		occupiedHotkeys,
		pushToTalk,
	});

	// "Custom" sentinel. When the current
	// hotkey is not one of the preset values, the Select would render
	// an empty trigger (Radix Select quirk: a non-empty value that
	// matches no SelectItem suppresses the placeholder). We detect
	// custom values and map them to a "__custom__" sentinel that
	// displays the actual hotkey label, so the dropdown always shows
	// something meaningful.
	// The presets are now passed in from the parent via the `presets`
	// prop, no hard-coded preset logic in this component. If no
	// presets are provided, the dropdown is not rendered at all.
	const presetOptions = presets ?? [];
	const rawPresetValue = mode === "single" ? value.replace(/[<>]/g, "") : value;
	const isPresetValue = presetOptions.some(
		(opt) => opt.value === rawPresetValue,
	);
	const customLabel = value ? formatHotkeyLabel(value) : "";

	return (
		<div className="flex flex-col gap-2" ref={containerRef}>
			<div className="flex items-center gap-2">
				<Button
					variant={recording ? "default" : "outline"}
					size="sm"
					onClick={recording ? cancelRecording : startRecording}
					className={cn(CAPTURE_BUTTON_SIZE, "gap-2 font-mono", className)}
					aria-label={
						recording
							? t("hotkeyPicker.cancelRecordingAria", { label: ariaLabel })
							: t("hotkeyPicker.recordNewAria", { label: ariaLabel })
					}
					// expose the in-progress modifier combo
					// via aria-keyshortcuts so assistive tech can announce
					// what the user is currently holding. Cleared (omitted)
					// when no modifiers are held so screen readers don't
					// read a stale value.
					{...(recording && heldModifiersLabel
						? { "aria-keyshortcuts": heldModifiersLabel }
						: {})}
				>
					<HugeiconsIcon
						icon={recording ? Cancel01Icon : KeyboardIcon}
						strokeWidth={1.625}
						className="h-4 w-4"
					/>
					{recording ? (
						<span className="animate-pulse">{t("hotkeyPicker.pressAKey")}</span>
					) : value ? (
						// Render the assigned hotkey as design-system keycap
						// chips inside the button (each key its own <Kbd>,
						// joined with a small gap, no "+" separator).
						<HotkeyChips keys={formatHotkeyLabel(value)} />
					) : (
						<span>{t("hotkeyPicker.none")}</span>
					)}
				</Button>

				{presetOptions.length > 0 && (
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button
								variant="outline"
								size="sm"
								className="min-w-40 justify-between font-mono"
								aria-label={t("hotkeyPicker.presetHotkeysAria", {
									label: ariaLabel,
								})}
							>
								<span className="flex items-center">
									{(() => {
										if (!value) return t("hotkeyPicker.presets");
										if (isPresetValue) {
											const opt = presetOptions.find(
												(o) => o.value === rawPresetValue,
											);
											return (
												<HotkeyChips
													keys={opt?.label ?? formatHotkeyLabel(value)}
												/>
											);
										}
										return (
											<HotkeyChips
												keys={t("hotkeyPicker.customLabel", {
													label: customLabel,
												})}
											/>
										);
									})()}
								</span>
								{/* Dropdown affordance, the app-standard
                                                                        hugeicons chevron (same glyph as the shared
                                                                        SelectTrigger), replacing the former
                                                                        hand-rolled chevron SVG. Muted to match
                                                                        the trigger's secondary affordance. */}
								<HugeiconsIcon
									icon={ChevronDownIcon}
									strokeWidth={1.625}
									className="pointer-events-none h-4 w-4 opacity-50"
									aria-hidden="true"
								/>
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent className="min-w-40" align="start">
							{presetOptions.map((opt) => (
								<DropdownMenuItem
									key={opt.value}
									onSelect={() => {
										const newValue =
											mode === "single" ? `<${opt.value}>` : opt.value;
										//shared validate-then-conflict-check.
										// resetSession:false because the dropdown has no
										// capture session to reset.
										const r = tryCommitHotkey(newValue, {
											mode,
											value,
											occupiedHotkeys,
											pushToTalk,
											t,
											resetSession: false,
										});
										if (!r.ok) {
											setError(r.error, formatHotkeyForMessage(newValue));
											return;
										}
										setError(null);
										onChange(newValue);
									}}
								>
									<HotkeyChips keys={opt.label} />
								</DropdownMenuItem>
							))}
							{!isPresetValue && value && (
								<DropdownMenuItem
									disabled
									className="text-muted-foreground cursor-default"
								>
									<HotkeyChips
										keys={t("hotkeyPicker.customLabel", {
											label: customLabel,
										})}
									/>
								</DropdownMenuItem>
							)}
						</DropdownMenuContent>
					</DropdownMenu>
				)}
				{/* Clear button, lets the user unset a
                                    hotkey without having to capture a new one. Only
                                    shown when ``allowClear`` is true, a hotkey is
                                    currently assigned, and we're not in the middle of
                                    capture (the capture button itself toggles to a
                                    cancel button during recording, so a second X would
                                    be redundant).

                                    Accessibility: aria-label and title are
                                    localised via ``t("hotkeyPicker.clearAria",
                                    { label })`` and ``t("hotkeyPicker.clearTitle")``.
                                    Native translations exist in all 8 locale JSON
                                    files. */}
				{allowClear && value && !recording && (
					<Button
						variant="ghost"
						size="icon-sm"
						className="text-muted-foreground"
						onClick={() => onChange("")}
						aria-label={t("hotkeyPicker.clearAria", { label: ariaLabel })}
						title={t("hotkeyPicker.clearTitle")}
					>
						<HugeiconsIcon
							icon={Cancel01Icon}
							strokeWidth={1.625}
							className="h-3.5 w-3.5"
						/>
					</Button>
				)}
			</div>
			{recording && (
				// No max-width: the hint sizes to its own content so the
				// instruction stays on ONE line instead of wrapping.
				<output
					className="text-xs text-muted-foreground"
					// Polite live region: screen readers announce the
					// countdown ticks as they update.
					aria-live="polite"
				>
					{t("hotkeyPicker.assignHint")}
					{/* countdown timer. Shown the whole
                                        time so the user knows how long they have;
                                        turns red in the last 10 seconds for emphasis. */}
					<span
						className={cn(
							"ms-2 tabular-nums",
							secondsRemaining <= 10 && "text-destructive",
						)}
					>
						({secondsRemaining}s)
					</span>
				</output>
			)}
		</div>
	);
}
