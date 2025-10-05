import json
import os
import sys
import csv
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
# Read CSV and process articles
# ---------------------------
# csv_path = os.path.join(os.path.dirname(__file__), '..', 'SB_publication_PMC.csv')
#
csv_path = os.path.join('..', 'SB_publication_PMC.csv')
articles = []
try:
    with open(csv_path, "r", encoding="utf-8-sig") as f:  # utf-8-sig removes Excel BOM
        reader = csv.DictReader(f)

        # Normalize header names (strip spaces & lowercase them)
        reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]

        for row in reader:
            # Safely get columns using .get() (avoids KeyErrors)
            title = row.get("title", "").strip()
            url = row.get("link", "").strip()

            # Skip incomplete rows
            if title and url:
                articles.append({"title": title, "url": url})

except Exception as e:
    print(f"❌ Failed to read CSV: {e}")
    sys.exit(1)

total_articles = len(articles)
print(f"📄 Found {total_articles} articles to process")

for i, article in enumerate(articles, 1):
    url = article['url']
    expected_title = article['title']
    print(f"🔄 Processing article {i}/{total_articles}: {expected_title[:50]}...")

    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": "ElasticDemo/1.0"})
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to fetch URL {url}: {e}")
        continue

    soup = BeautifulSoup(response.text, "html.parser")

    # Find <article> tag
    article_tag = soup.find("article")
    if not article_tag:
        print(f"❌ No <article> tag found for {url}")
        continue

    # Extract title and text
    title = soup.title.string.strip() if soup.title and soup.title.string else expected_title
    text = " ".join(article_tag.get_text(separator=" ", strip=True).split())

    if not text:
        print(f"❌ No text extracted from <article> tag for {url}")
        continue

    # ---------------------------
    # Create embedding via inference model
    # ---------------------------
    try:
        response = es.inference.text_embedding(
            inference_id=MODEL_ID,
            input=text[:8000]          # you can also pass a list of strings
        )
        embedding = response['text_embedding'][0]['embedding']
    except Exception as e:
        print(f"❌ Failed to create embedding for {url}: {e}")
        continue

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

    try:
        res = es.index(index=INDEX_NAME, document=doc)
        print(f"✅ Indexed article {i}: {title[:30]}... ID: {res['_id']}")
    except Exception as e:
        print(f"❌ Failed to index article {i}: {e}")
        continue

print(f"🔗 Check your Elastic dashboard for index: {INDEX_NAME} ({total_articles} articles processed)")
