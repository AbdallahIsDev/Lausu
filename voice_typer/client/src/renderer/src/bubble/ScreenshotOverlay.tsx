import { useCallback, useEffect, useRef, useState } from "react";
import { tf } from "./helpers";

export interface ScreenshotRect {
	left: number;
	top: number;
	width: number;
	height: number;
}

interface DragPoint {
	x: number;
	y: number;
}

// Drags shorter than this (CSS px) count as a click, which cancels
// without capturing, so an accidental click never writes a file.
const MIN_SELECTION_PX = 4;

function toDeviceRect(start: DragPoint, end: DragPoint): ScreenshotRect | null {
	const left = Math.min(start.x, end.x);
	const top = Math.min(start.y, end.y);
	const width = Math.abs(end.x - start.x);
	const height = Math.abs(end.y - start.y);
	if (width < MIN_SELECTION_PX || height < MIN_SELECTION_PX) return null;
	const scale =
		typeof window !== "undefined" && window.devicePixelRatio > 0
			? window.devicePixelRatio
			: 1;
	return {
		left: Math.round(left * scale),
		top: Math.round(top * scale),
		width: Math.round(width * scale),
		height: Math.round(height * scale),
	};
}

export function ScreenshotOverlay({
	onCapture,
	onCancel,
}: {
	onCapture: (rect: ScreenshotRect) => void;
	onCancel: () => void;
}) {
	const [start, setStart] = useState<DragPoint | null>(null);
	const [current, setCurrent] = useState<DragPoint | null>(null);
	const draggingRef = useRef(false);
	const startRef = useRef<DragPoint | null>(null);

	// Esc cancels without capturing, the recording keeps running.
	useEffect(() => {
		const onKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") {
				e.stopPropagation();
				onCancel();
			}
		};
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [onCancel]);

	const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
		if (e.button !== 0) return;
		draggingRef.current = true;
		const point = { x: e.clientX, y: e.clientY };
		startRef.current = point;
		setStart(point);
		setCurrent(point);
	}, []);

	const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
		if (!draggingRef.current) return;
		setCurrent({ x: e.clientX, y: e.clientY });
	}, []);

	const handleMouseUp = useCallback(
		(e: React.MouseEvent<HTMLDivElement>) => {
			if (!draggingRef.current) return;
			draggingRef.current = false;
			const end = { x: e.clientX, y: e.clientY };
			const begun = startRef.current;
			startRef.current = null;
			setStart(null);
			setCurrent(end);
			if (begun) {
				const rect = toDeviceRect(begun, end);
				if (rect) onCapture(rect);
				else onCancel();
			} else {
				onCancel();
			}
		},
		[onCapture, onCancel],
	);

	const selection =
		start && current
			? {
					left: Math.min(start.x, current.x),
					top: Math.min(start.y, current.y),
					width: Math.abs(current.x - start.x),
					height: Math.abs(current.y - start.y),
				}
			: null;

	return (
		<div
			role="dialog"
			aria-label={tf("screenshot.consentTitle", "Screenshot capture")}
			className="fixed inset-0 z-[100] cursor-crosshair bg-black/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
			tabIndex={-1}
			onMouseDown={handleMouseDown}
			onMouseMove={handleMouseMove}
			onMouseUp={handleMouseUp}
		>
			<p className="pointer-events-none absolute left-1/2 top-6 -translate-x-1/2 rounded-full bg-surface px-4 py-2.5 text-xs font-medium text-foreground">
				{tf(
					"bubble.screenshotHint",
					"Drag to select a region — release to capture, Esc to cancel",
				)}
			</p>
			{selection && (
				<div
					aria-hidden
					className="absolute border border-white bg-white/10"
					style={{
						left: selection.left,
						top: selection.top,
						width: selection.width,
						height: selection.height,
					}}
				>
					<span className="absolute -bottom-6 left-0 rounded bg-surface px-2 py-0.5 text-[11px] text-foreground">
						{Math.round(selection.width)} × {Math.round(selection.height)}
					</span>
				</div>
			)}
		</div>
	);
}
