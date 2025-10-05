#!/usr/bin/env python3
"""
Test script for knowledge graph extraction
Run this to test the knowledge graph functionality
"""

import os
import sys
import json
from pathlib import Path

# Add the rag directory to the path
sys.path.append(str(Path(__file__).parent))

from knowledge_graph import KnowledgeGraphExtractor
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

def main():
    load_dotenv()
    
    # Environment setup
    ELASTIC_URL = os.getenv("ELASTIC_URL")
    ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")
    ELASTIC_INDEX = os.getenv("ELASTIC_INDEX", "spacehacks")
    
    if not ELASTIC_URL or not ELASTIC_API_KEY:
        print("❌ Missing Elasticsearch environment variables")
        print("Please set ELASTIC_URL and ELASTIC_API_KEY in .env")
        return
    
    print("🔍 Testing Knowledge Graph Extraction")
    print(f"Elasticsearch URL: {ELASTIC_URL}")
    print(f"Index: {ELASTIC_INDEX}")
    
    try:
        # Connect to Elasticsearch
        client = Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY, verify_certs=True)
        
        # Test connection
        info = client.info()
        print(f"✅ Connected to Elasticsearch {info['version']['number']}")
        
        # Check if index exists
        if not client.indices.exists(index=ELASTIC_INDEX):
            print(f"❌ Index '{ELASTIC_INDEX}' does not exist")
            print("Please run the ingestion scripts first to populate the index")
            return
        
        # Get document count
        count_response = client.count(index=ELASTIC_INDEX)
        doc_count = count_response['count']
        print(f"📊 Found {doc_count} documents in index")
        
        if doc_count == 0:
            print("❌ No documents found in index")
            return
        
        # Build knowledge graph
        print("🧠 Building knowledge graph...")
        extractor = KnowledgeGraphExtractor(client, ELASTIC_INDEX)
        kg = extractor.build_knowledge_graph(max_docs=min(50, doc_count))
        
        # Get summary
        summary = extractor.get_graph_summary(kg)
        
        print("\n📈 Knowledge Graph Summary:")
        print(f"  Total Entities: {summary['total_entities']}")
        print(f"  Total Relationships: {summary['total_relationships']}")
        print(f"  Entity Types: {summary['entity_types']}")
        print(f"  Relationship Types: {summary['relationship_types']}")
        
        print("\n🔝 Top Entities:")
        for i, entity in enumerate(summary['top_entities'][:5], 1):
            print(f"  {i}. {entity['name']} ({entity['type']}) - {entity['frequency']} mentions")
        
        # Export sample data
        sample_data = {
            "summary": summary,
            "entities": [entity.__dict__ for entity in list(kg.entities.values())[:20]],
            "relationships": [rel.__dict__ for rel in kg.relationships[:20]]
        }
        
        with open("knowledge_graph_sample.json", "w") as f:
            json.dump(sample_data, f, indent=2)
        
        print(f"\n💾 Sample data exported to knowledge_graph_sample.json")
        print("✅ Knowledge graph extraction test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
