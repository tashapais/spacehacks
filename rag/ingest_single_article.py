import json
import os
import sys
import requests
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

# ---------------------------
# Environment configuration
# ---------------------------
ELASTIC_URL = os.getenv("ELASTIC_URL")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")
INDEX_NAME = os.getenv("ELASTIC_INDEX", "articles")
MODEL_ID = os.getenv("ELASTIC_MODEL_ID", ".multilingual-e5-small-elasticsearch")

if not (ELASTIC_URL and ELASTIC_API_KEY):
    print("❌ Please set ELASTIC_URL and ELASTIC_API_KEY in .env")
    sys.exit(1)

# ---------------------------
# Connect to Elasticsearch
# ---------------------------
es = Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY, verify_certs=True)
print("Successfully connected to Elasticsearch")
print(es.inference.get())

# ---------------------------
# Ensure index exists
# ---------------------------
if not es.indices.exists(index=INDEX_NAME):
    mapping = {
        "mappings": {
            "properties": {
                "url": {"type": "keyword"},
                "title": {"type": "text"},
                "content": {"type": "text"},
                "timestamp": {"type": "date"},
                 "content_vector": {
                     "type": "dense_vector",
                     "dims": 384,  # for multilingual-e5-small
                     "index": True,
                     "similarity": "cosine"
                 }
            }
        }
    }
    es.indices.create(index=INDEX_NAME, body=mapping)
    print(f"✅ Created index '{INDEX_NAME}'")
else:
    print(f"ℹ️ Using existing index '{INDEX_NAME}'")
# ---------------------------
# Fetch & parse article
# ---------------------------
# url = input("Enter article URL: ").strip()
url = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4136787/"
try:
    response = requests.get(url, timeout=30, headers={"User-Agent": "ElasticDemo/1.0"})
    response.raise_for_status()
except Exception as e:
    print(f"❌ Failed to fetch URL: {e}")
    sys.exit(1)

soup = BeautifulSoup(response.text, "html.parser")

# Find <article> tag
article_tag = soup.find("article")
if not article_tag:
    print("❌ No <article> tag found on page.")
    sys.exit(1)

# Extract title and text
title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled"
print(title)
text = " ".join(article_tag.get_text(separator=" ", strip=True).split())

if not text:
    print("❌ No text extracted from <article> tag.")
    sys.exit(1)

# print(text)

# ---------------------------
# Create embedding via inference model
# ---------------------------
response = es.inference.text_embedding(
    inference_id=MODEL_ID,
    input=text[:8000]          # you can also pass a list of strings
)
embedding = response['text_embedding'][0]['embedding']

# ---------------------------
# Index document
# ---------------------------
doc = {
    "url": url,
    "title": title,
    "content": text,
    "timestamp": datetime.now(timezone.utc),
    "content_vector": embedding,
}
# print(doc)

res = es.index(index=INDEX_NAME, document=doc)
print(f"✅ Indexed document ID: {res['_id']}")
print(f"🔗 Check your Elastic dashboard for index: {INDEX_NAME}")
