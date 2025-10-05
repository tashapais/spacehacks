import { json } from '@sveltejs/kit';
import type { RequestHandler } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { Buffer } from 'node:buffer';

interface Article {
	id: string;
	title: string;
	content: string;
	url?: string;
	embedding: number[];
}

interface GraphNode {
	id: string;
	title: string;
	url?: string;
	cluster?: number;
}

interface GraphLink {
	source: string;
	target: string;
	similarity: number;
}

export const GET: RequestHandler = async ({ fetch }) => {
	const { ELASTIC_URL, ELASTIC_API_KEY, ELASTIC_INDEX = 'articles' } = env;

	if (!ELASTIC_URL || !ELASTIC_API_KEY) {
		return json({ error: 'Elasticsearch environment variables are missing' }, { status: 500 });
	}

	try {
		const elasticAuthHeader = buildElasticAuthHeader(ELASTIC_API_KEY);

		// Fetch all articles with embeddings
		const articles = await fetchAllArticles(fetch, {
			elasticUrl: ELASTIC_URL,
			authHeader: elasticAuthHeader,
			index: ELASTIC_INDEX
		});

		// Calculate similarity and create graph data
		const { nodes, links } = createGraphData(articles);

		return json({ nodes, links });
	} catch (error) {
		console.error('Graph endpoint error', error);
		return json({ error: 'Failed to generate graph data' }, { status: 500 });
	}
};

async function fetchAllArticles(
	fetchFn: typeof fetch,
	{
		elasticUrl,
		authHeader,
		index
	}: { elasticUrl: string; authHeader: string; index: string }
): Promise<Article[]> {
	// First, get the index mapping to see available fields
	const mappingResponse = await fetchFn(
		`${elasticUrl.replace(/\/$/, '')}/${encodeURIComponent(index)}/_mapping`,
		{
			method: 'GET',
			headers: {
				'Content-Type': 'application/json',
				Authorization: authHeader
			}
		}
	);

	if (mappingResponse.ok) {
		const mappingData = await mappingResponse.json();
		console.log('\n=== ELASTICSEARCH INDEX MAPPING ===');
		console.log(JSON.stringify(mappingData, null, 2));
		console.log('====================================\n');
	}

	const response = await fetchFn(
		`${elasticUrl.replace(/\/$/, '')}/${encodeURIComponent(index)}/_search`,
		{
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: authHeader
			},
			body: JSON.stringify({
				size: 603,
				_source: true, // Get all fields to see what's available
				query: {
					match_all: {}
				}
			})
		}
	);

	if (!response.ok) {
		const details = await response.text();
		throw new Error(`Elasticsearch query failed: ${response.status} ${details}`);
	}

	const data = await response.json();
	const hits = data?.hits?.hits ?? [];

	// Debug: Print first document structure to see all available fields
	if (hits.length > 0) {
		console.log('\n=== FIRST DOCUMENT STRUCTURE ===');
		// console.log('Available fields:', Object.keys(hits[0]._source || {}));
		// console.log('\nFull first document:');
		console.log(JSON.stringify(hits[0]));
		console.log('=================================\n');
	}

	const articles = hits.map((hit: any) => ({
		id: hit._id,
		title: hit._source?.title ?? 'Untitled',
		content: hit._source?.content ?? '',
		url: hit._source?.url,
		embedding: hit._source?.content_vector ?? []
	}));

	// Debug: Print embedding info to console
	console.log('\n=== ELASTICSEARCH EMBEDDINGS DEBUG ===');
	console.log(`Total articles fetched: ${articles.length}`);
	console.log(`\nFirst article:`);
	console.log(`  ID: ${articles[0]?.id}`);
	console.log(`  Title: ${articles[0]?.title}`);
	console.log(`  Embedding length: ${articles[0]?.embedding?.length}`);
	console.log(`  Embedding sample (first 10 values): ${articles[0]?.embedding?.slice(0, 10)}`);

	// Check if embeddings are empty
	const emptyEmbeddings = articles.filter((a: Article) => !a.embedding || a.embedding.length === 0);
	console.log(`\nArticles with empty embeddings: ${emptyEmbeddings.length}`);
	if (emptyEmbeddings.length > 0) {
		console.log('Sample empty embedding articles:');
		emptyEmbeddings.slice(0, 3).forEach((a: Article) => {
			console.log(`  - ${a.title} (ID: ${a.id})`);
		});
	}
	console.log('=====================================\n');

	return articles;
}

function cosineSimilarity(a: number[], b: number[]): number {
	if (a.length !== b.length || a.length === 0) return 0;

	let dotProduct = 0;
	let normA = 0;
	let normB = 0;

	for (let i = 0; i < a.length; i++) {
		dotProduct += a[i] * b[i];
		normA += a[i] * a[i];
		normB += b[i] * b[i];
	}

	const denominator = Math.sqrt(normA) * Math.sqrt(normB);
	return denominator === 0 ? 0 : dotProduct / denominator;
}

function createGraphData(articles: Article[]): { nodes: GraphNode[]; links: GraphLink[] } {
	const nodes: GraphNode[] = articles.map((article) => ({
		id: article.id,
		title: article.title,
		url: article.url
	}));

	const links: GraphLink[] = [];
	const SIMILARITY_THRESHOLD = 0.3; // Lower threshold to create more connections
	const MAX_LINKS_PER_NODE = 15; // Increase connections for better clustering

	// Calculate similarities and create links
	for (let i = 0; i < articles.length; i++) {
		const nodeSimilarities: { index: number; similarity: number }[] = [];

		for (let j = i + 1; j < articles.length; j++) {
			const similarity = cosineSimilarity(articles[i].embedding, articles[j].embedding);

			if (similarity >= SIMILARITY_THRESHOLD) {
				nodeSimilarities.push({ index: j, similarity });
			}
		}

		// Sort by similarity and take top N connections
		nodeSimilarities.sort((a, b) => b.similarity - a.similarity);
		const topConnections = nodeSimilarities.slice(0, MAX_LINKS_PER_NODE);

		for (const { index, similarity } of topConnections) {
			links.push({
				source: articles[i].id,
				target: articles[index].id,
				similarity
			});
		}
	}

	// Perform simple clustering based on connectivity
	const clusters = assignClusters(nodes, links);
	nodes.forEach((node) => {
		node.cluster = clusters.get(node.id) ?? 0;
	});

	return { nodes, links };
}

function assignClusters(nodes: GraphNode[], links: GraphLink[]): Map<string, number> {
	const clusters = new Map<string, number>();
	const adjacency = new Map<string, Set<string>>();

	// Build adjacency list
	for (const link of links) {
		if (!adjacency.has(link.source)) adjacency.set(link.source, new Set());
		if (!adjacency.has(link.target)) adjacency.set(link.target, new Set());
		adjacency.get(link.source)!.add(link.target);
		adjacency.get(link.target)!.add(link.source);
	}

	let currentCluster = 0;

	// Simple BFS clustering
	for (const node of nodes) {
		if (clusters.has(node.id)) continue;

		const queue = [node.id];
		clusters.set(node.id, currentCluster);

		while (queue.length > 0) {
			const current = queue.shift()!;
			const neighbors = adjacency.get(current);

			if (neighbors) {
				for (const neighbor of neighbors) {
					if (!clusters.has(neighbor)) {
						clusters.set(neighbor, currentCluster);
						queue.push(neighbor);
					}
				}
			}
		}

		currentCluster++;
	}

	return clusters;
}

function buildElasticAuthHeader(rawApiKey: string): string {
	const trimmed = rawApiKey.trim();
	if (trimmed.includes(':')) {
		return `ApiKey ${Buffer.from(trimmed, 'utf8').toString('base64')}`;
	}
	return `ApiKey ${trimmed}`;
}
