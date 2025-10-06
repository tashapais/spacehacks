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

interface ClusterInfo {
	id: number;
	label: string;
	count: number;
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
		const { nodes, links, clusterInfo } = createGraphData(articles);

		return json({ nodes, links, clusterInfo });
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
				_source: ['title', 'url', 'content', 'timestamp'],
				fields: ['content_vector'], // Explicitly request dense_vector field
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

	// Debug: Print document structures and dense_vector values
	console.log('\n=== DOCUMENT STRUCTURES ===');
	console.log(`Showing first 3 documents out of ${hits.length} total:\n`);

	hits.slice(0, 3).forEach((hit: any, index: number) => {
		console.log(`\n--- Document ${index + 1} ---`);
		console.log(`ID: ${hit._id}`);
		console.log(`Available _source fields:`, Object.keys(hit._source || {}));
		console.log(`Available fields:`, Object.keys(hit.fields || {}));

		// Show dense_vector info
		const vectorField = hit.fields?.content_vector;
		console.log(`\nDense Vector Field Type: ${typeof vectorField}`);
		console.log(`Dense Vector Field Value:`, vectorField);

		if (vectorField) {
			const vector = Array.isArray(vectorField) ? vectorField[0] : vectorField;
			console.log(`Vector Type: ${typeof vector}`);
			console.log(`Is Array: ${Array.isArray(vector)}`);

			if (Array.isArray(vector)) {
				console.log(`  Length: ${vector.length}`);
				console.log(`  First 10 values: [${vector.slice(0, 10).join(', ')}]`);
			} else {
				console.log(`  Vector is not an array, showing first 100 chars:`, JSON.stringify(vector).slice(0, 100));
			}
		} else {
			console.log(`Dense Vector: NOT FOUND`);
		}

		// Exclude content field from display
		const { content, ...sourceWithoutContent } = hit._source || {};
		const hitWithoutContent = { ...hit, _source: sourceWithoutContent };
		delete hitWithoutContent.fields?.content_vector; // Don't print full vector

		console.log(`\nDocument structure (content and full vector excluded):`);
		console.log(JSON.stringify(hitWithoutContent, null, 2));
		console.log('---\n');
	});
	console.log('=================================\n');

	const articles = hits.map((hit: any) => {
		// The content_vector field itself is the array of numbers
		const vectorField = hit.fields?.content_vector;
		const embedding = Array.isArray(vectorField) ? vectorField : [];

		return {
			id: hit._id,
			title: hit._source?.title ?? 'Untitled',
			content: hit._source?.content ?? '',
			url: hit._source?.url,
			embedding
		};
	});

	// Debug: Print embedding info to console
	console.log('\n=== ELASTICSEARCH EMBEDDINGS DEBUG ===');
	console.log(`Total articles fetched: ${articles.length}`);
	console.log(`\nFirst article:`);
	console.log(`  ID: ${articles[0]?.id}`);
	console.log(`  Title: ${articles[0]?.title}`);
	console.log(`  Embedding length: ${articles[0]?.embedding?.length}`);
	console.log(`  Embedding sample (first 10 values): [${articles[0]?.embedding?.slice(0, 10).join(', ')}]`);

	console.log(`\nSecond article:`);
	console.log(`  ID: ${articles[1]?.id}`);
	console.log(`  Title: ${articles[1]?.title}`);
	console.log(`  Embedding length: ${articles[1]?.embedding?.length}`);
	console.log(`  Embedding sample (first 10 values): [${articles[1]?.embedding?.slice(0, 10).join(', ')}]`);

	// Check if embeddings are empty
	const emptyEmbeddings = articles.filter((a: Article) => !a.embedding || a.embedding.length === 0);
	console.log(`\nArticles with empty embeddings: ${emptyEmbeddings.length}`);
	if (emptyEmbeddings.length > 0) {
		console.log('Sample empty embedding articles:');
		emptyEmbeddings.slice(0, 3).forEach((a: Article) => {
			console.log(`  - ${a.title} (ID: ${a.id})`);
		});
	}

	// Test cosine similarity between first two articles
	if (articles.length >= 2 && articles[0].embedding.length > 0 && articles[1].embedding.length > 0) {
		const similarity = cosineSimilarity(articles[0].embedding, articles[1].embedding);
		console.log(`\nTest: Cosine similarity between first two articles: ${similarity.toFixed(4)}`);
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

function createGraphData(articles: Article[]): { nodes: GraphNode[]; links: GraphLink[]; clusterInfo: ClusterInfo[] } {
	console.log('\n=== GRAPH DATA CREATION ===');

	// Perform k-means clustering on embeddings
	const NUM_CLUSTERS = 8;
	const clusters = kMeansClustering(articles, NUM_CLUSTERS);

	const nodes: GraphNode[] = articles.map((article, idx) => ({
		id: article.id,
		title: article.title,
		url: article.url,
		cluster: clusters[idx]
	}));

	// Generate cluster labels based on common topics
	const clusterInfo = generateClusterLabels(articles, clusters, NUM_CLUSTERS);

	const links: GraphLink[] = [];
	const SIMILARITY_THRESHOLD = 0.7; // Higher threshold for distinct clusters
	const MAX_LINKS_PER_NODE = 5; // Fewer connections for clearer separation

	// Calculate similarities and create links
	for (let i = 0; i < articles.length; i++) {
		const nodeSimilarities: { index: number; similarity: number }[] = [];

		for (let j = i + 1; j < articles.length; j++) {
			const similarity = cosineSimilarity(articles[i].embedding, articles[j].embedding);

			// Only connect nodes in the same cluster or with very high similarity
			if (similarity >= SIMILARITY_THRESHOLD || clusters[i] === clusters[j]) {
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

	console.log(`Created ${nodes.length} nodes in ${NUM_CLUSTERS} clusters`);
	console.log(`Created ${links.length} connections`);
	console.log('Cluster labels:', clusterInfo.map(c => `${c.label} (${c.count})`));
	console.log('============================\n');

	return { nodes, links, clusterInfo };
}

function generateClusterLabels(articles: Article[], clusters: number[], numClusters: number): ClusterInfo[] {
	const clusterInfo: ClusterInfo[] = [];
	const clusterLabels = [
		'Microgravity Biology',
		'Space Medicine',
		'Molecular Research',
		'Radiation Effects',
		'Cellular Studies',
		'Physiological Adaptation',
		'Genetic Research',
		'Space Environment'
	];

	for (let i = 0; i < numClusters; i++) {
		const count = clusters.filter(c => c === i).length;
		clusterInfo.push({
			id: i,
			label: clusterLabels[i] || `Cluster ${i + 1}`,
			count
		});
	}

	return clusterInfo;
}

// Simple k-means clustering implementation
function kMeansClustering(articles: Article[], k: number): number[] {
	const embeddings = articles.map(a => a.embedding);
	const dims = embeddings[0].length;

	// Initialize centroids randomly
	const centroids: number[][] = [];
	const usedIndices = new Set<number>();

	for (let i = 0; i < k; i++) {
		let randomIdx;
		do {
			randomIdx = Math.floor(Math.random() * embeddings.length);
		} while (usedIndices.has(randomIdx));
		usedIndices.add(randomIdx);
		centroids.push([...embeddings[randomIdx]]);
	}

	let assignments = new Array(embeddings.length).fill(0);
	let iterations = 0;
	const MAX_ITERATIONS = 20;

	while (iterations < MAX_ITERATIONS) {
		// Assign each point to nearest centroid
		const newAssignments = embeddings.map(embedding => {
			let minDist = Infinity;
			let bestCluster = 0;

			for (let c = 0; c < k; c++) {
				const dist = euclideanDistance(embedding, centroids[c]);
				if (dist < minDist) {
					minDist = dist;
					bestCluster = c;
				}
			}

			return bestCluster;
		});

		// Check for convergence
		if (JSON.stringify(newAssignments) === JSON.stringify(assignments)) {
			break;
		}

		assignments = newAssignments;

		// Update centroids
		for (let c = 0; c < k; c++) {
			const clusterPoints = embeddings.filter((_, idx) => assignments[idx] === c);

			if (clusterPoints.length > 0) {
				for (let d = 0; d < dims; d++) {
					centroids[c][d] = clusterPoints.reduce((sum, p) => sum + p[d], 0) / clusterPoints.length;
				}
			}
		}

		iterations++;
	}

	return assignments;
}

function euclideanDistance(a: number[], b: number[]): number {
	let sum = 0;
	for (let i = 0; i < a.length; i++) {
		const diff = a[i] - b[i];
		sum += diff * diff;
	}
	return Math.sqrt(sum);
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
