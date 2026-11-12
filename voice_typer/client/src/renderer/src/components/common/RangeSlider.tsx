import { useEffect, useRef, useState } from "react";
import { InlineSlider } from "@/components/ui/inline-slider";
import { cn } from "@/lib/utils";

interface RangeSliderProps {
	value: number;
	min: number;
	max: number;
	step: number;
	onChange: (value: number) => void;
	ariaLabel: string;
	/** Unit suffix displayed after the value (e.g. "ms", "%", "Hz") */
	suffix: string;
	/** Optional wrapper className */
	className?: string;
	/** Disable the slider (greyed out, no interaction) */
	disabled?: boolean;
	deferApply?: boolean;
}

export function RangeSlider({
	value,
	min,
	max,
	step,
	onChange,
	ariaLabel,
	suffix,
	className,
	disabled = false,
	deferApply = false,
}: RangeSliderProps) {
	// The visible label belongs to the surrounding SettingRow, so the slider
	// renders only its value readout instead of repeating the row title.
	const [displayValue, setDisplayValue] = useState(value);
	const dirtyRef = useRef(false);
	const pendingRef = useRef({ value, displayValue, onChange, deferApply });
	pendingRef.current = { value, displayValue, onChange, deferApply };

	// Sync the shadow value when the committed config changes (reload,
	// keyboard shortcut, parent reset).
	useEffect(() => {
		if (!dirtyRef.current) setDisplayValue(value);
	}, [value]);

	// Navigating away mid-drag must not drop the last value.
	useEffect(() => {
		return () => {
			const pending = pendingRef.current;
			if (pending.deferApply && dirtyRef.current) {
				pending.onChange(pending.displayValue);
			}
		};
	}, []);

	const handleValueChange = (next: number) => {
		setDisplayValue(next);
		if (deferApply) {
			dirtyRef.current = true;
			return;
		}
		onChange(next);
	};

	const handleValueCommit = (next: number) => {
		if (!deferApply) return;
		dirtyRef.current = false;
		if (next !== value) onChange(next);
	};

	return (
		<InlineSlider
			value={deferApply ? displayValue : value}
			min={min}
			max={max}
			step={step}
			disabled={disabled}
			aria-label={ariaLabel}
			label=""
			format={(next) => `${next}${suffix}`}
			formatValueText={(next) => `${next}${suffix}`}
			onValueChange={handleValueChange}
			onValueCommit={handleValueCommit}
			className={cn("w-52", className)}
		/>
	);
}
