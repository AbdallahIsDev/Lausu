// types/ipc/vocabulary.ts
// Vocabulary-domain types, mirrors the Python `VocabularyManager`.

export interface VocabularyData {
	misspellings?: Record<string, string>;
	technical_terms?: Record<string, string>;
	names?: Record<string, string>;
	products?: Record<string, string>;
	phrase_corrections?: Array<[string, string]>;
	extra_word_patterns?: Array<[string, string]>;
	/** Auto-apply origin marks: {category: {original: corrected}}. */
	_auto_applied?: Record<string, Record<string, string>>;
}

export interface VocabularyEntry {
	category: string;
	original: string;
	correction: string;
	index?: number;
	/** True when the automation added this entry (badged "Auto"). */
	autoApplied?: boolean;
}
