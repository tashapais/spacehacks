import { json } from '@sveltejs/kit';
import type { RequestHandler } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { Buffer } from 'node:buffer';

interface Entity {
  id: string;
  name: string;
  type: string;
  frequency: number;
  properties: Record<string, any>;
}

interface Relationship {
  source: string;
  target: string;
  relation_type: string;
  strength: number;
  context: string;
  source_doc: string;
}

interface KnowledgeGraphData {
  summary: {
    total_entities: number;
    total_relationships: number;
    entity_types: Record<string, number>;
    relationship_types: Record<string, number>;
    top_entities: Array<{
      name: string;
      type: string;
      frequency: number;
    }>;
    metadata: Record<string, any>;
  };
  entities: Entity[];
  relationships: Relationship[];
}

export const POST: RequestHandler = async ({ request, fetch }) => {
  const {
    ELASTIC_URL,
    ELASTIC_API_KEY,
    ELASTIC_INDEX = 'spacehacks'
  } = env;

  if (!ELASTIC_URL || !ELASTIC_API_KEY) {
    return json({ error: 'Elasticsearch environment variables are missing' }, { status: 500 });
  }

  try {
    const { sessionContext }: { sessionContext?: string[] } = await request.json();
    
    const elasticAuthHeader = buildElasticAuthHeader(ELASTIC_API_KEY);
    
    // Get documents relevant to the session context
    const documents = await getRelevantDocuments(fetch, {
      elasticUrl: ELASTIC_URL,
      authHeader: elasticAuthHeader,
      index: ELASTIC_INDEX,
      sessionContext: sessionContext || []
    });

    // Extract knowledge graph from relevant documents only
    const knowledgeGraph = await extractKnowledgeGraph(documents, sessionContext || []);

    return json(knowledgeGraph);
  } catch (error) {
    console.error('Knowledge graph endpoint error', error);
    return json({ error: 'Failed to generate knowledge graph' }, { status: 500 });
  }
};

async function getRelevantDocuments(
  fetchFn: typeof fetch,
  {
    elasticUrl,
    authHeader,
    index,
    sessionContext
  }: {
    elasticUrl: string;
    authHeader: string;
    index: string;
    sessionContext: string[];
  }
) {
  // If no session context, get a small sample of documents
  if (sessionContext.length === 0) {
    const response = await fetchFn(`${elasticUrl.replace(/\/$/, '')}/${encodeURIComponent(index)}/_search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: authHeader
      },
      body: JSON.stringify({
        query: { match_all: {} },
        size: 20, // Small sample
        _source: ['title', 'content', 'url']
      })
    });

    if (!response.ok) {
      const details = await response.text();
      throw new Error(`Document retrieval failed: ${response.status} ${details}`);
    }

    const data = await response.json();
    return data?.hits?.hits ?? [];
  }

  // Create a query that searches for documents containing any of the session context terms
  const query = {
    query: {
      bool: {
        should: sessionContext.map(term => ({
          multi_match: {
            query: term,
            fields: ['title^2', 'content'],
            fuzziness: 'AUTO'
          }
        })),
        minimum_should_match: 1
      }
    },
    size: 50, // Limit to most relevant documents
    _source: ['title', 'content', 'url']
  };

  const response = await fetchFn(`${elasticUrl.replace(/\/$/, '')}/${encodeURIComponent(index)}/_search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: authHeader
    },
    body: JSON.stringify(query)
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(`Document retrieval failed: ${response.status} ${details}`);
  }

  const data = await response.json();
  return data?.hits?.hits ?? [];
}

async function getAllDocuments(
  fetchFn: typeof fetch,
  {
    elasticUrl,
    authHeader,
    index
  }: {
    elasticUrl: string;
    authHeader: string;
    index: string;
  }
) {
  const response = await fetchFn(`${elasticUrl.replace(/\/$/, '')}/${encodeURIComponent(index)}/_search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: authHeader
    },
    body: JSON.stringify({
      query: { match_all: {} },
      size: 200,
      _source: ['title', 'content', 'url']
    })
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(`Document retrieval failed: ${response.status} ${details}`);
  }

  const data = await response.json();
  return data?.hits?.hits ?? [];
}

async function extractKnowledgeGraph(documents: any[], sessionContext: string[] = []): Promise<KnowledgeGraphData> {
  // Entity patterns for space biology
  const entityPatterns = {
    organism: [
      /\b(mice?|rats?|humans?|monkeys?|zebrafish|drosophila|C\. elegans)\b/gi,
      /\b(Mus musculus|Rattus norvegicus|Homo sapiens)\b/gi
    ],
    protein: [
      /\b[A-Z][a-z]+\d*\b/g,
      /\b(actin|myosin|collagen|fibronectin|laminin)\b/gi,
      /\b[A-Z]{2,}\d*\b/g
    ],
    gene: [
      /\b[A-Z][a-z]+\d*\b/g,
      /\b(CDKN1a|p21|RUNX2|ALP|OCN)\b/gi
    ],
    condition: [
      /\b(microgravity|spaceflight|radiation|oxidative stress|bone loss|muscle atrophy)\b/gi,
      /\b(osteoporosis|osteopenia|sarcopenia)\b/gi
    ],
    method: [
      /\b(RT-PCR|qPCR|Western blot|immunohistochemistry|flow cytometry)\b/gi,
      /\b(RNA-seq|microarray|proteomics|metabolomics)\b/gi
    ],
    location: [
      /\b(ISS|International Space Station|space|Earth|ground control)\b/gi,
      /\b(bone|muscle|heart|liver|brain|kidney)\b/gi
    ]
  };

  // Relationship patterns
  const relationshipPatterns = {
    affects: [
      /(\w+)\s+(affects?|influences?|impacts?)\s+(\w+)/gi,
      /(\w+)\s+(leads? to|results? in|causes?)\s+(\w+)/gi
    ],
    inhibits: [
      /(\w+)\s+(inhibits?|suppresses?|blocks?)\s+(\w+)/gi,
      /(\w+)\s+(prevents?|reduces?)\s+(\w+)/gi
    ],
    promotes: [
      /(\w+)\s+(promotes?|enhances?|stimulates?)\s+(\w+)/gi,
      /(\w+)\s+(increases?|upregulates?)\s+(\w+)/gi
    ],
    regulates: [
      /(\w+)\s+(regulates?|controls?|modulates?)\s+(\w+)/gi,
      /(\w+)\s+(mediates?|orchestrates?)\s+(\w+)/gi
    ],
    expressed_in: [
      /(\w+)\s+(expressed in|found in|present in)\s+(\w+)/gi,
      /(\w+)\s+(localized to|distributed in)\s+(\w+)/gi
    ]
  };

  const entities = new Map<string, Entity>();
  const relationships: Relationship[] = [];

  // Process each document
  for (const doc of documents) {
    const source = doc._source;
    const title = source.title || '';
    const content = source.content || '';
    const url = source.url || '';
    
    const fullText = `${title} ${content}`;

    // Extract entities
    for (const [entityType, patterns] of Object.entries(entityPatterns)) {
      for (const pattern of patterns) {
        const matches = fullText.match(pattern);
        if (matches) {
          for (const match of matches) {
            const entityName = match.trim();
            const entityId = `${entityType}_${entityName.toLowerCase().replace(/\s+/g, '_')}`;
            
            if (entities.has(entityId)) {
              entities.get(entityId)!.frequency++;
            } else {
              entities.set(entityId, {
                id: entityId,
                name: entityName,
                type: entityType,
                frequency: 1,
                properties: {}
              });
            }
          }
        }
      }
    }

    // Extract relationships
    for (const [relationType, patterns] of Object.entries(relationshipPatterns)) {
      for (const pattern of patterns) {
        const matches = [...fullText.matchAll(pattern)];
        for (const match of matches) {
          const sourceName = match[1]?.trim();
          const targetName = match[3]?.trim();
          
          if (sourceName && targetName) {
            const sourceEntity = findEntityByName(sourceName, entities);
            const targetEntity = findEntityByName(targetName, entities);
            
            if (sourceEntity && targetEntity && sourceEntity.id !== targetEntity.id) {
              relationships.push({
                source: sourceEntity.id,
                target: targetEntity.id,
                relation_type: relationType,
                strength: 1.0,
                context: match[0],
                source_doc: url || title
              });
            }
          }
        }
      }
    }
  }

  // Boost entities that appear in session context
  const sessionContextLower = sessionContext.map(term => term.toLowerCase());
  for (const entity of entities.values()) {
    if (sessionContextLower.some(term => 
      entity.name.toLowerCase().includes(term) || 
      term.includes(entity.name.toLowerCase())
    )) {
      entity.frequency += 5; // Boost session-relevant entities
    }
  }

  // Filter entities by frequency (lower threshold for session-relevant entities)
  const filteredEntities = Array.from(entities.values()).filter(entity => 
    entity.frequency >= 1 || sessionContextLower.some(term => 
      entity.name.toLowerCase().includes(term) || 
      term.includes(entity.name.toLowerCase())
    )
  );
  
  // Calculate relationship strengths
  const relationshipStrengths = calculateRelationshipStrengths(relationships);
  
  // Update relationship strengths and filter
  const filteredRelationships = relationships
    .map(rel => ({
      ...rel,
      strength: relationshipStrengths.get(`${rel.source}-${rel.target}-${rel.relation_type}`) || 1.0
    }))
    .filter(rel => 
      rel.strength >= 0.5 && 
      filteredEntities.some(e => e.id === rel.source) &&
      filteredEntities.some(e => e.id === rel.target)
    );

  // Generate summary
  const entityTypes = filteredEntities.reduce((acc, entity) => {
    acc[entity.type] = (acc[entity.type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const relationshipTypes = filteredRelationships.reduce((acc, rel) => {
    acc[rel.relation_type] = (acc[rel.relation_type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const topEntities = filteredEntities
    .sort((a, b) => b.frequency - a.frequency)
    .slice(0, 10)
    .map(entity => ({
      name: entity.name,
      type: entity.type,
      frequency: entity.frequency
    }));

  return {
    summary: {
      total_entities: filteredEntities.length,
      total_relationships: filteredRelationships.length,
      entity_types: entityTypes,
      relationship_types: relationshipTypes,
      top_entities: topEntities,
      metadata: {
        total_documents: documents.length,
        extraction_timestamp: new Date().toISOString()
      }
    },
    entities: filteredEntities,
    relationships: filteredRelationships
  };
}

function findEntityByName(name: string, entities: Map<string, Entity>): Entity | null {
  const nameLower = name.toLowerCase();
  for (const entity of entities.values()) {
    if (entity.name.toLowerCase() === nameLower) {
      return entity;
    }
  }
  return null;
}

function calculateRelationshipStrengths(relationships: Relationship[]): Map<string, number> {
  const counts = new Map<string, number>();
  
  for (const rel of relationships) {
    const key = `${rel.source}-${rel.target}-${rel.relation_type}`;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  
  const maxCount = Math.max(...counts.values());
  const strengths = new Map<string, number>();
  
  for (const [key, count] of counts) {
    strengths.set(key, count / maxCount);
  }
  
  return strengths;
}

function buildElasticAuthHeader(rawApiKey: string): string {
  const trimmed = rawApiKey.trim();
  if (trimmed.includes(':')) {
    return `ApiKey ${Buffer.from(trimmed, 'utf8').toString('base64')}`;
  }
  return `ApiKey ${trimmed}`;
}
