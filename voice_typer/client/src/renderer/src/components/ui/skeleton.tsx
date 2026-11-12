import { SkeletonBox, type SkeletonBoxProps } from "skullet/react";

// One placeholder box, drawn by Skullet. Every bar joins the page's
// single shimmer (one document-clock phase, however late it mounts)
// and follows the provider theme + reduced-motion, instead of the old
// per-div `animate-pulse` which never synced. Width/height/radius are
// explicit (Skullet draws them as inline geometry measured from the
// real component) - size Tailwind classes do NOT apply, a SkeletonBox
// size class is ignored by the inline style, so callers pass the
// dimension props.
export function Skeleton({
	width,
	height,
	radius,
	className,
	style,
}: SkeletonBoxProps) {
	return (
		<SkeletonBox
			width={width}
			height={height}
			radius={radius}
			className={className}
			style={style}
		/>
	);
}
