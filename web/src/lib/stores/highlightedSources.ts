import { writable } from 'svelte/store';

export interface HighlightedSource {
	url: string;
	citationNumber: number;
}

export const highlightedSources = writable<HighlightedSource[]>([]);
