export interface Entity {
  id: string;
  name: string;
  type: string;
  frequency: number;
  properties: Record<string, any>;
}

export interface Relationship {
  source: string;
  target: string;
  relation_type: string;
  strength: number;
  context: string;
  source_doc: string;
}

export interface KnowledgeGraphData {
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
