// Speaker-offer button row: a real DOM group (honest container, not
// grid-row/sibling hacks). Both buttons ALWAYS render while the toast is
// up (C-CACHE-6); parent flex + gap only, never margins (C-UI-4).
// Lower = outline (visible, neutral), Keep = ghost (de-emphasized).
import { Button } from "@/components/ui/button";

export function SpeakerOfferActions({
	lowerLabel,
	keepLabel,
	onLower,
	onKeep,
}: {
	lowerLabel: string;
	keepLabel: string;
	onLower: () => void;
	onKeep: () => void;
}) {
	return (
		<div className="flex items-center gap-2">
			<Button variant="outline" size="xs" onClick={onLower}>
				{lowerLabel}
			</Button>
			<Button variant="ghost" size="xs" onClick={onKeep}>
				{keepLabel}
			</Button>
		</div>
	);
}
