// Measured-skeleton sample for the Vocabulary page.
// Short realistic correction pairs so the skeleton matches the
// width of the two text columns the rows render.
import type { VocabRow } from "./transform";

export const SAMPLE_VOCAB_ENTRIES: VocabRow[] = [
	{
		_id: "sample-vocab-0",
		category: "misspellings",
		original: "alphabeticl",
		correction: "alphabetical",
		autoApplied: false,
	},
	{
		_id: "sample-vocab-1",
		category: "technical_terms",
		original: "kubernates",
		correction: "kubernetes",
		autoApplied: false,
	},
	{
		_id: "sample-vocab-2",
		category: "phrase_corrections",
		original: "thanks for your help",
		correction: "thank you for your help",
		autoApplied: false,
	},
	{
		_id: "sample-vocab-3",
		category: "names",
		original: "Jonathan Smith",
		correction: "Jonathan Smyth",
		autoApplied: false,
	},
	{
		_id: "sample-vocab-4",
		category: "products",
		original: "macbook pro",
		correction: "MacBook Pro",
		autoApplied: false,
	},
	{
		_id: "sample-vocab-5",
		category: "misspellings",
		original: "occured yesterday",
		correction: "occurred yesterday",
		autoApplied: false,
	},
	{
		_id: "sample-vocab-6",
		category: "technical_terms",
		original: "postgres ql",
		correction: "postgresql",
		autoApplied: false,
	},
	{
		_id: "sample-vocab-7",
		category: "phrase_corrections",
		original: "meet at three pm",
		correction: "meet at 3:00 PM",
		autoApplied: false,
	},
];
