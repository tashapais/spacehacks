import type { RequestHandler } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { Buffer } from 'node:buffer';
import { EXPERTISE_CONFIGS, DEFAULT_EXPERTISE, type ExpertiseLevel } from '$lib/expertise';

const DEFAULT_TOP_K = 4;
const DEFAULT_NUM_CANDIDATES = 50;
const MAX_CONTEXT_CHARS = 3600;

interface ChatMessage {
	role: 'user' | 'assistant';
	text: string;
}

interface Citation {
	id: string;
	title: string;
	url?: string;
	snippet?: string;
}

export const POST: RequestHandler = async ({ request, fetch }) => {
	const {
		ELASTIC_URL,
		ELASTIC_API_KEY,
		ELASTIC_INDEX = 'articles_v2',
		ELASTIC_MODEL_ID,
		OPENAI_API_KEY
	} = env;

	if (!ELASTIC_URL || !ELASTIC_API_KEY || !ELASTIC_MODEL_ID) {
		return new Response(
			JSON.stringify({ error: 'Elasticsearch environment variables are missing' }),
			{
				status: 500,
				headers: { 'Content-Type': 'application/json' }
			}
		);
	}

	if (!OPENAI_API_KEY) {
		return new Response(JSON.stringify({ error: 'OpenAI API key is missing' }), {
			status: 500,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	const { messages, expertise }: { messages: ChatMessage[]; expertise?: ExpertiseLevel } =
		await request.json();
	const expertiseLevel = expertise || DEFAULT_EXPERTISE;
	const expertiseConfig = EXPERTISE_CONFIGS[expertiseLevel];
	if (!messages?.length) {
		return new Response(JSON.stringify({ error: 'No messages provided' }), {
			status: 400,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	const question = [...messages]
		.reverse()
		.find((m) => m.role === 'user')
		?.text?.trim();
	if (!question) {
		return new Response(JSON.stringify({ error: 'No user question found' }), {
			status: 400,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	try {
		const elasticAuthHeader = buildElasticAuthHeader(ELASTIC_API_KEY);

		const embedding = await embedQuery(fetch, {
			elasticUrl: ELASTIC_URL,
			authHeader: elasticAuthHeader,
			modelId: ELASTIC_MODEL_ID,
			query: question
		});

		const rawHits = await knnRetrieve(fetch, {
			elasticUrl: ELASTIC_URL,
			authHeader: elasticAuthHeader,
			index: ELASTIC_INDEX,
			vector: embedding,
			k: DEFAULT_TOP_K,
			numCandidates: DEFAULT_NUM_CANDIDATES
		});

		const hits = dedupeByArticle(rawHits, DEFAULT_TOP_K);
		const citations = formatCitations(hits);

		// Create SSE stream
		const stream = new ReadableStream({
			async start(controller) {
				const encoder = new TextEncoder();

				try {
					// Send citations first
					controller.enqueue(
						encoder.encode(
							`data: ${JSON.stringify({
								type: 'citations',
								citations
							})}\n\n`
						)
					);

					// Stream OpenAI response with expertise-specific parameters
					const response = await fetch('https://api.openai.com/v1/chat/completions', {
						method: 'POST',
						headers: {
							'Content-Type': 'application/json',
							Authorization: `Bearer ${OPENAI_API_KEY}`
						},
						body: JSON.stringify({
							model: 'gpt-4o-mini',
							messages: [
								{
									role: 'system',
									content: expertiseConfig.systemPrompt
								},
								{
									role: 'user',
									content: `Question: ${question}\n\nContext:\n${buildContext(hits)}`
								}
							],
							stream: true,
							temperature: expertiseConfig.temperature,
							max_tokens: expertiseConfig.maxTokens
						})
					});

					if (!response.ok) {
						const details = await response.text();
						throw new Error(`OpenAI request failed: ${response.status} ${details}`);
					}

					const reader = response.body?.getReader();
					const decoder = new TextDecoder();

					while (true) {
						const { done, value } = await reader!.read();
						if (done) break;

						const chunk = decoder.decode(value);
						const lines = chunk.split('\n');

						for (const line of lines) {
							if (line.startsWith('data: ')) {
								const data = line.slice(6);
								if (data === '[DONE]') continue;

								try {
									const parsed = JSON.parse(data);
									const content = parsed.choices?.[0]?.delta?.content;

									if (content) {
										// Clamp bracket citations to valid range [1..hits.length]
										const clampedContent = content.replace(
											/\[(\d+)\]/g,
											(_match: string, num: string) => {
												const n = parseInt(num, 10);
												if (n >= 1 && n <= hits.length) return `[${n}]`;
												return ''; // Remove invalid citations
											}
										);

										controller.enqueue(
											encoder.encode(
												`data: ${JSON.stringify({
													type: 'chunk',
													content: clampedContent
												})}\n\n`
											)
										);
									}
								} catch (e) {
									// Skip malformed JSON lines
									continue;
								}
							}
						}
					}

					controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'done' })}\n\n`));
					controller.close();
				} catch (error) {
					console.error('Streaming error', error);
					controller.enqueue(
						encoder.encode(
							`data: ${JSON.stringify({
								type: 'error',
								error: 'Failed to generate answer'
							})}\n\n`
						)
					);
					controller.close();
				}
			}
		});

		return new Response(stream, {
			headers: {
				'Content-Type': 'text/event-stream',
				'Cache-Control': 'no-cache',
				Connection: 'keep-alive'
			}
		});
	} catch (error) {
		console.error('Chat endpoint error', error);
		return new Response(JSON.stringify({ error: 'Failed to generate answer' }), {
			status: 500,
			headers: { 'Content-Type': 'application/json' }
		});
	}
};

async function embedQuery(
	fetchFn: typeof fetch,
	{
		elasticUrl,
		authHeader,
		modelId,
		query
	}: { elasticUrl: string; authHeader: string; modelId: string; query: string }
): Promise<number[]> {
	const response = await fetchFn(
		`${elasticUrl.replace(/\/$/, '')}/_inference/text_embedding/${modelId}`,
		{
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: authHeader
			},
			body: JSON.stringify({ input: query })
		}
	);

	if (!response.ok) {
		const details = await response.text();
		throw new Error(`Embedding request failed: ${response.status} ${details}`);
	}

	const data = await response.json();
	const predicted = data?.predicted_value;

	if (Array.isArray(predicted)) {
		return Array.isArray(predicted[0]) ? predicted[0] : predicted;
	}

	const textEmbedding = data?.text_embedding?.[0]?.embedding;
	if (Array.isArray(textEmbedding)) {
		return textEmbedding;
	}

	throw new Error('Embedding response missing vector');
}

function dedupeByArticle(hits: any[], limit: number) {
	const byArticle: Record<string, any[]> = {};
	for (const h of hits) {
		const a = h?._source?.article_id as string | undefined;
		const key = a || Math.random().toString();
		if (!byArticle[key]) byArticle[key] = [];
		byArticle[key].push(h);
	}
	const out: any[] = [];
	for (const chunks of Object.values(byArticle)) {
		// Select the chunk with highest _score (or first if no score)
		chunks.sort((a, b) => (b._score || 0) - (a._score || 0));
		out.push(chunks[0]);
		if (out.length >= limit) break;
	}
	return out;
}

async function knnRetrieve(
	fetchFn: typeof fetch,
	{
		elasticUrl,
		authHeader,
		index,
		vector,
		k,
		numCandidates
	}: {
		elasticUrl: string;
		authHeader: string;
		index: string;
		vector: number[];
		k: number;
		numCandidates: number;
	}
) {
	const response = await fetchFn(
		`${elasticUrl.replace(/\/$/, '')}/${encodeURIComponent(index)}/_search`,
		{
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: authHeader
			},
			body: JSON.stringify({
				knn: {
					field: 'content_vector',
					query_vector: vector,
					k,
					num_candidates: numCandidates
				},
				_source: ['title', 'url', 'content', 'article_id', 'chunk_index', 'n_chars'],
				highlight: {
					fields: {
						content: {}
					}
				},
				size: Math.max(k * 2, k)
			})
		}
	);

	if (!response.ok) {
		const details = await response.text();
		throw new Error(`KNN search failed: ${response.status} ${details}`);
	}

	const data = await response.json();
	return data?.hits?.hits ?? [];
}

function buildContext(hits: any[]): string {
	if (hits.length === 0) {
		return '';
	}

	// Build focused context from chunked docs, respecting total budget
	const snippets: string[] = [];
	let used = 0;
	const perSnippet = 1200;
	for (let i = 0; i < hits.length; i++) {
		const source = hits[i]?._source ?? {};
		const title = source.title ?? 'Untitled';
		const content: string = source.content ?? '';
		const snippet = content.slice(0, perSnippet);
		const block = `[${i + 1}] ${title}\n${snippet}`;
		if (used + block.length > MAX_CONTEXT_CHARS) break;
		snippets.push(block);
		used += block.length + 8; // separators allowance
	}
	return snippets.join('\n\n---\n\n');
}

function formatCitations(hits: any[]): Citation[] {
	return hits.map((hit, idx) => {
		const source = hit?._source ?? {};
		const highlight = hit?.highlight?.content?.[0] || source.content || '';
		// Extract full sentence containing the highlight
		const fullContent = source.content || '';
		const snippet = extractFullSentence(highlight, fullContent, 400);
		return {
			id: String(idx + 1),
			title: source.title ?? 'Untitled',
			url: source.url ?? undefined,
			snippet
		} as any;
	});
}

function extractFullSentence(
	highlight: string,
	fullContent: string,
	maxLen: number
): string | undefined {
	if (!highlight || !fullContent) return undefined;
	// Find the highlight in fullContent and expand to full sentence
	const idx = fullContent.indexOf(highlight);
	if (idx === -1) return highlight.slice(0, maxLen);
	// Find sentence start (look back for . ! ?)
	let start = idx;
	for (let i = idx - 1; i >= 0 && start - i < 100; i--) {
		if (['.', '!', '?'].includes(fullContent[i])) {
			start = i + 1;
			break;
		}
	}
	// Find sentence end
	let end = idx + highlight.length;
	for (let i = end; i < fullContent.length && i - idx < 200; i++) {
		if (['.', '!', '?'].includes(fullContent[i])) {
			end = i + 1;
			break;
		}
	}
	const sentence = fullContent.slice(start, end).trim();
	return sentence.length > maxLen ? sentence.slice(0, maxLen) + '…' : sentence;
}

function buildElasticAuthHeader(rawApiKey: string): string {
	const trimmed = rawApiKey.trim();
	if (trimmed.includes(':')) {
		return `ApiKey ${Buffer.from(trimmed, 'utf8').toString('base64')}`;
	}
	return `ApiKey ${trimmed}`;
}
