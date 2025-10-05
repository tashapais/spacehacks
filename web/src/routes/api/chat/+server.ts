import { json } from '@sveltejs/kit';
import type { RequestHandler } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { Buffer } from 'node:buffer';

const DEFAULT_TOP_K = 4;
const DEFAULT_NUM_CANDIDATES = 50;
const MAX_CONTEXT_CHARS = 1200;

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
}

interface Citation {
  id: string;
  title: string;
  url?: string;
}

export const POST: RequestHandler = async ({ request, fetch }) => {
  const {
    ELASTIC_URL,
    ELASTIC_API_KEY,
    ELASTIC_INDEX = 'articles',
    ELASTIC_MODEL_ID
  } = env;

  if (!ELASTIC_URL || !ELASTIC_API_KEY || !ELASTIC_MODEL_ID) {
    return json({ error: 'Elasticsearch environment variables are missing' }, { status: 500 });
  }

  const { messages }: { messages: ChatMessage[] } = await request.json();
  if (!messages?.length) {
    return json({ error: 'No messages provided' }, { status: 400 });
  }

  const question = [...messages].reverse().find((m) => m.role === 'user')?.text?.trim();
  if (!question) {
    return json({ error: 'No user question found' }, { status: 400 });
  }

  try {
    const elasticAuthHeader = buildElasticAuthHeader(ELASTIC_API_KEY);

    const embedding = await embedQuery(fetch, {
      elasticUrl: ELASTIC_URL,
      authHeader: elasticAuthHeader,
      modelId: ELASTIC_MODEL_ID,
      query: question
    });

    const hits = await knnRetrieve(fetch, {
      elasticUrl: ELASTIC_URL,
      authHeader: elasticAuthHeader,
      index: ELASTIC_INDEX,
      vector: embedding,
      k: DEFAULT_TOP_K,
      numCandidates: DEFAULT_NUM_CANDIDATES
    });

    const citations = formatCitations(hits);

    // Format Elasticsearch results as the answer
    const answer = formatElasticsearchResults(hits, question);

    return json({ answer, citations });
  } catch (error) {
    console.error('Chat endpoint error', error);
    return json({ error: 'Failed to generate answer' }, { status: 500 });
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
  const response = await fetchFn(`${elasticUrl.replace(/\/$/, '')}/_inference/text_embedding/${modelId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: authHeader
    },
    body: JSON.stringify({ input: query })
  });

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
  const response = await fetchFn(`${elasticUrl.replace(/\/$/, '')}/${encodeURIComponent(index)}/_search`, {
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
      _source: ['title', 'url', 'content'],
      size: k
    })
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(`KNN search failed: ${response.status} ${details}`);
  }

  const data = await response.json();
  return data?.hits?.hits ?? [];
}

function formatElasticsearchResults(hits: any[], question: string): string {
  if (hits.length === 0) {
    return `No results found in the Elasticsearch index for your question: "${question}"`;
  }

  let result = `Found ${hits.length} relevant documents in Elasticsearch:\n\n`;

  hits.forEach((hit, idx) => {
    const source = hit?._source ?? {};
    const title = source.title ?? 'Untitled';
    const url = source.url ?? '';
    const score = hit._score ?? 'N/A';
    const excerpt = (source.content ?? '')
      .replace(/\s+/g, ' ')
      .slice(0, 400);

    result += `**[${idx + 1}] ${title}**\n`;
    result += `*Relevance score: ${score}*\n`;
    if (url) {
      result += `URL: ${url}\n`;
    }
    result += `\nExcerpt: ${excerpt}${excerpt.length === 400 ? '...' : ''}\n\n`;
  });

  return result;
}

function formatCitations(hits: any[]): Citation[] {
  return hits.map((hit, idx) => {
    const source = hit?._source ?? {};
    return {
      id: String(idx + 1),
      title: source.title ?? 'Untitled',
      url: source.url ?? undefined
    };
  });
}

function buildElasticAuthHeader(rawApiKey: string): string {
  const trimmed = rawApiKey.trim();
  if (trimmed.includes(':')) {
    return `ApiKey ${Buffer.from(trimmed, 'utf8').toString('base64')}`;
  }
  return `ApiKey ${trimmed}`;
}
