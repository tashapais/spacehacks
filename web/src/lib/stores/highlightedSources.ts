import { writable } from 'svelte/store';

export const highlightedSourceUrls = writable<string[]>([]);
