#!/usr/bin/env python3
"""
Knowledge Graph Extraction Service for Space Biology Research
Extracts entities, relationships, and concepts from research articles
"""

import os
import json
import logging
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass, asdict
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
import re
from collections import defaultdict, Counter

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Entity:
    """Represents an entity in the knowledge graph"""
    id: str
    name: str
    type: str  # 'concept', 'organism', 'protein', 'gene', 'condition', 'method', 'location'
    frequency: int = 1
    properties: Dict[str, Any] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}

@dataclass
class Relationship:
    """Represents a relationship between entities"""
    source: str
    target: str
    relation_type: str  # 'affects', 'inhibits', 'promotes', 'regulates', 'expressed_in', 'causes'
    strength: float = 1.0
    context: str = ""
    source_doc: str = ""

@dataclass
class KnowledgeGraph:
    """Complete knowledge graph structure"""
    entities: Dict[str, Entity]
    relationships: List[Relationship]
    metadata: Dict[str, Any]

class KnowledgeGraphExtractor:
    """Extracts knowledge graph from research articles"""
    
    def __init__(self, elastic_client: Elasticsearch, index_name: str):
        self.client = elastic_client
        self.index_name = index_name
        
        # Define entity patterns for space biology
        self.entity_patterns = {
            'organism': [
                r'\b(mice?|rats?|humans?|monkeys?|zebrafish|drosophila|C\. elegans)\b',
                r'\b(Mus musculus|Rattus norvegicus|Homo sapiens)\b'
            ],
            'protein': [
                r'\b[A-Z][a-z]+\d*\b',  # Common protein naming
                r'\b(actin|myosin|collagen|fibronectin|laminin)\b',
                r'\b[A-Z]{2,}\d*\b'  # Acronyms like CDKN1a, p21
            ],
            'gene': [
                r'\b[A-Z][a-z]+\d*\b',  # Gene names
                r'\b(CDKN1a|p21|RUNX2|ALP|OCN)\b'
            ],
            'condition': [
                r'\b(microgravity|spaceflight|radiation|oxidative stress|bone loss|muscle atrophy)\b',
                r'\b(osteoporosis|osteopenia|sarcopenia)\b'
            ],
            'method': [
                r'\b(RT-PCR|qPCR|Western blot|immunohistochemistry|flow cytometry)\b',
                r'\b(RNA-seq|microarray|proteomics|metabolomics)\b'
            ],
            'location': [
                r'\b(ISS|International Space Station|space|Earth|ground control)\b',
                r'\b(bone|muscle|heart|liver|brain|kidney)\b'
            ]
        }
        
        # Relationship patterns
        self.relationship_patterns = {
            'affects': [
                r'(\w+)\s+(affects?|influences?|impacts?)\s+(\w+)',
                r'(\w+)\s+(leads? to|results? in|causes?)\s+(\w+)'
            ],
            'inhibits': [
                r'(\w+)\s+(inhibits?|suppresses?|blocks?)\s+(\w+)',
                r'(\w+)\s+(prevents?|reduces?)\s+(\w+)'
            ],
            'promotes': [
                r'(\w+)\s+(promotes?|enhances?|stimulates?)\s+(\w+)',
                r'(\w+)\s+(increases?|upregulates?)\s+(\w+)'
            ],
            'regulates': [
                r'(\w+)\s+(regulates?|controls?|modulates?)\s+(\w+)',
                r'(\w+)\s+(mediates?|orchestrates?)\s+(\w+)'
            ],
            'expressed_in': [
                r'(\w+)\s+(expressed in|found in|present in)\s+(\w+)',
                r'(\w+)\s+(localized to|distributed in)\s+(\w+)'
            ]
        }

    def extract_entities(self, text: str) -> Dict[str, Entity]:
        """Extract entities from text using pattern matching"""
        entities = {}
        
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entity_name = match.group().strip()
                    entity_id = f"{entity_type}_{entity_name.lower().replace(' ', '_')}"
                    
                    if entity_id not in entities:
                        entities[entity_id] = Entity(
                            id=entity_id,
                            name=entity_name,
                            type=entity_type,
                            frequency=1
                        )
                    else:
                        entities[entity_id].frequency += 1
        
        return entities

    def extract_relationships(self, text: str, entities: Dict[str, Entity]) -> List[Relationship]:
        """Extract relationships between entities"""
        relationships = []
        
        for relation_type, patterns in self.relationship_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    source_name = match.group(1).strip()
                    target_name = match.group(3).strip()
                    
                    # Find corresponding entities
                    source_entity = self._find_entity_by_name(source_name, entities)
                    target_entity = self._find_entity_by_name(target_name, entities)
                    
                    if source_entity and target_entity and source_entity.id != target_entity.id:
                        rel = Relationship(
                            source=source_entity.id,
                            target=target_entity.id,
                            relation_type=relation_type,
                            strength=1.0,
                            context=match.group(0),
                            source_doc=""
                        )
                        relationships.append(rel)
        
        return relationships

    def _find_entity_by_name(self, name: str, entities: Dict[str, Entity]) -> Entity:
        """Find entity by name (case-insensitive)"""
        name_lower = name.lower()
        for entity in entities.values():
            if entity.name.lower() == name_lower:
                return entity
        return None

    def build_knowledge_graph(self, max_docs: int = 100) -> KnowledgeGraph:
        """Build knowledge graph from all documents in the index"""
        logger.info(f"Building knowledge graph from {self.index_name} index")
        
        # Get all documents
        query = {
            "query": {"match_all": {}},
            "size": max_docs,
            "_source": ["title", "content", "url"]
        }
        
        response = self.client.search(index=self.index_name, body=query)
        documents = response['hits']['hits']
        
        logger.info(f"Processing {len(documents)} documents")
        
        all_entities = {}
        all_relationships = []
        
        for doc in documents:
            source = doc['_source']
            title = source.get('title', '')
            content = source.get('content', '')
            url = source.get('url', '')
            
            # Combine title and content for analysis
            full_text = f"{title} {content}"
            
            # Extract entities
            doc_entities = self.extract_entities(full_text)
            
            # Merge entities
            for entity_id, entity in doc_entities.items():
                if entity_id in all_entities:
                    all_entities[entity_id].frequency += entity.frequency
                else:
                    all_entities[entity_id] = entity
            
            # Extract relationships
            doc_relationships = self.extract_relationships(full_text, doc_entities)
            
            # Add source document info to relationships
            for rel in doc_relationships:
                rel.source_doc = url or title
                all_relationships.append(rel)
        
        # Filter out low-frequency entities
        filtered_entities = {
            entity_id: entity for entity_id, entity in all_entities.items()
            if entity.frequency >= 2  # Only keep entities mentioned at least twice
        }
        
        # Calculate relationship strengths based on co-occurrence
        relationship_strengths = self._calculate_relationship_strengths(all_relationships)
        
        # Update relationship strengths
        for rel in all_relationships:
            rel.strength = relationship_strengths.get((rel.source, rel.target, rel.relation_type), 1.0)
        
        # Filter weak relationships
        filtered_relationships = [
            rel for rel in all_relationships
            if rel.strength >= 0.5 and rel.source in filtered_entities and rel.target in filtered_entities
        ]
        
        metadata = {
            "total_documents": len(documents),
            "total_entities": len(filtered_entities),
            "total_relationships": len(filtered_relationships),
            "extraction_timestamp": str(pd.Timestamp.now())
        }
        
        return KnowledgeGraph(
            entities=filtered_entities,
            relationships=filtered_relationships,
            metadata=metadata
        )

    def _calculate_relationship_strengths(self, relationships: List[Relationship]) -> Dict[Tuple[str, str, str], float]:
        """Calculate relationship strengths based on frequency and context"""
        relationship_counts = Counter()
        
        for rel in relationships:
            key = (rel.source, rel.target, rel.relation_type)
            relationship_counts[key] += 1
        
        # Normalize strengths
        max_count = max(relationship_counts.values()) if relationship_counts else 1
        
        return {
            key: count / max_count
            for key, count in relationship_counts.items()
        }

    def get_graph_summary(self, kg: KnowledgeGraph) -> Dict[str, Any]:
        """Get summary statistics of the knowledge graph"""
        entity_types = Counter(entity.type for entity in kg.entities.values())
        relationship_types = Counter(rel.relation_type for rel in kg.relationships)
        
        return {
            "total_entities": len(kg.entities),
            "total_relationships": len(kg.relationships),
            "entity_types": dict(entity_types),
            "relationship_types": dict(relationship_types),
            "top_entities": [
                {"name": entity.name, "type": entity.type, "frequency": entity.frequency}
                for entity in sorted(kg.entities.values(), key=lambda x: x.frequency, reverse=True)[:10]
            ],
            "metadata": kg.metadata
        }

def main():
    """Main function to build and export knowledge graph"""
    # Environment setup
    ELASTIC_URL = os.getenv("ELASTIC_URL")
    ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")
    ELASTIC_INDEX = os.getenv("ELASTIC_INDEX", "spacehacks")
    
    if not ELASTIC_URL or not ELASTIC_API_KEY:
        logger.error("Missing Elasticsearch environment variables")
        return
    
    # Connect to Elasticsearch
    client = Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY, verify_certs=True)
    
    # Build knowledge graph
    extractor = KnowledgeGraphExtractor(client, ELASTIC_INDEX)
    kg = extractor.build_knowledge_graph(max_docs=200)
    
    # Get summary
    summary = extractor.get_graph_summary(kg)
    
    # Export to JSON
    output_data = {
        "summary": summary,
        "entities": [asdict(entity) for entity in kg.entities.values()],
        "relationships": [asdict(rel) for rel in kg.relationships]
    }
    
    with open("knowledge_graph.json", "w") as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Knowledge graph exported to knowledge_graph.json")
    logger.info(f"Summary: {summary}")

if __name__ == "__main__":
    import pandas as pd
    main()
