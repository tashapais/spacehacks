import os
import sys
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

load_dotenv()

ELASTIC_URL = os.getenv("ELASTIC_URL")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")
INDEX_NAME = os.getenv("ELASTIC_INDEX", "articles")
MODEL_ID = os.getenv("ELASTIC_MODEL_ID", ".multilingual-e5-small-elasticsearch")

if not (ELASTIC_URL and ELASTIC_API_KEY):
    print("Please set ELASTIC_URL and ELASTIC_API_KEY in .env")
    sys.exit(1)

es = Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY, verify_certs=True)

question = input("Enter your question: ")

try:
    response = es.inference.text_embedding(
        inference_id=MODEL_ID,
        input=question
    )
    embedding = response['text_embedding'][0]['embedding']
except Exception as e:
    print(f"Failed to create embedding: {e}")
    sys.exit(1)

search_body = {
    "knn": {
        "field": "content_vector",
        "query_vector": embedding,
        "k": 5,
        "num_candidates": 600
    },
    "_source": ["title"]
}

try:
    result = es.search(index=INDEX_NAME, body=search_body)
    hits = result['hits']['hits']
    for hit in hits:
        print(hit['_source']['title'])
except Exception as e:
    print(f"Failed to search: {e}")
    sys.exit(1)
