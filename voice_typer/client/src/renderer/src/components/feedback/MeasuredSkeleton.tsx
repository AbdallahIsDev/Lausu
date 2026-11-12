// Measured skeleton whose revealed content keeps its own flex stack.
// Skullet wraps the render-prop body in panes, so a parent column's `gap-*`
// can never reach the content's direct children. `stackClassName` carries
// that gap (and any flex sizing) to one wrapper inside the wrap.
import type { ReactNode } from "react";
import { Skeleton } from "skullet/react";
import { cn } from "@/lib/utils";

export interface MeasuredSkeletonProps<T> {
	data: T | null | undefined;
	sample: T;
	id?: string;
	label?: string;
	/** Layout classes for skullet's wrapper (width/height claims). */
	className?: string;
	/** Stack classes for the revealed content (e.g. `gap-4`, `flex-1`). */
	stackClassName?: string;
	children: (data: T) => ReactNode;
}

export function MeasuredSkeleton<T>({
	data,
	sample,
	id,
	label,
	className,
	stackClassName,
	children,
}: MeasuredSkeletonProps<T>) {
	return (
		<Skeleton
			data={data}
			sample={sample}
			id={id}
			label={label}
			className={className}
		>
			{(d) => (
				<div className={cn("flex w-full flex-col", stackClassName)}>
					{children(d)}
				</div>
			)}
		</Skeleton>
	);
}
