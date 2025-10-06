import os
import sys
import csv
import time
import hashlib
import argparse
import gc
import json
from datetime import datetime, timezone
from typing import Dict, List, Iterable

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

from chunking_utils import (
    normalize_whitespace,
    split_into_sentences,
    chunk_sentences,
    paragraph_first_chunking,
)

# ---------------------------
# Environment configuration
# ---------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

ELASTIC_URL = os.getenv('ELASTIC_URL')
ELASTIC_API_KEY = os.getenv('ELASTIC_API_KEY')
INDEX_NAME = os.getenv('ELASTIC_INDEX_V2', 'articles_v2')
MODEL_ID = os.getenv('ELASTIC_MODEL_ID', '.multilingual-e5-small-elasticsearch')
CSV_PATH = os.path.join(PROJECT_ROOT, 'SB_publication_PMC.csv')

DEFAULT_CHUNK_SIZE = int(os.getenv('BULK_BATCH_SIZE', '50'))
DEFAULT_THROTTLE_MS = int(os.getenv('THROTTLE_MS', '0'))
VERBOSE = os.getenv('VERBOSE', '0') == '1'
MAX_ARTICLES = int(os.getenv('MAX_ARTICLES', '0'))  # 0 = all
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '4'))

if not (ELASTIC_URL and ELASTIC_API_KEY):
    print('❌ Please set ELASTIC_URL and ELASTIC_API_KEY in .env')
    sys.exit(1)
# Hints for static checkers
assert ELASTIC_URL is not None
assert ELASTIC_API_KEY is not None

# ---------------------------
# CLI
# ---------------------------
parser = argparse.ArgumentParser(description='Chunk and stream-ingest articles into Elasticsearch.')
parser.add_argument('--reset', action='store_true', help='Delete and recreate the target index before ingesting')
parser.add_argument('--chunk-size', type=int, default=DEFAULT_CHUNK_SIZE, help='streaming_bulk chunk size (default 50)')
parser.add_argument('--throttle-ms', type=int, default=DEFAULT_THROTTLE_MS, help='sleep between chunks (ms)')
parser.add_argument('--max-articles', type=int, default=MAX_ARTICLES, help='limit number of articles (debug)')
parser.add_argument('--max-retries', type=int, default=MAX_RETRIES, help='max retries for ES bulk and embedding')
args = parser.parse_args()

CHUNK_SIZE = max(10, args.chunk_size)
THROTTLE_SEC = max(0, args.throttle_ms) / 1000.0
MAX_ARTICLES = args.max_articles
MAX_RETRIES = args.max_retries

# ---------------------------
# Connect to Elasticsearch
# ---------------------------
es = Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY, verify_certs=True)
print('🔌 Connected to Elasticsearch')

# ---------------------------
# Index setup
# ---------------------------
try:
    if args.reset and es.indices.exists(index=INDEX_NAME):
        print(f"🧹 Deleting existing index '{INDEX_NAME}' …")
        es.indices.delete(index=INDEX_NAME)
except Exception as e:
    print(f'❌ Failed to delete index: {e}')
    sys.exit(1)

try:
    exists = es.indices.exists(index=INDEX_NAME)
except Exception as e:
    print(f'❌ Failed to check index existence: {e}')
    sys.exit(1)

if not exists:
    mapping = {
        'settings': {
            'index': {
                'refresh_interval': '30s'
            }
        },
        'mappings': {
            'properties': {
                'url': {'type': 'keyword'},
                'title': {'type': 'text'},
                'article_id': {'type': 'keyword'},
                'chunk_id': {'type': 'keyword'},
                'chunk_index': {'type': 'integer'},
                'n_chars': {'type': 'integer'},
                'content': {'type': 'text'},
                'timestamp': {'type': 'date'},
                'content_vector': {
                    'type': 'dense_vector',
                    'dims': 384,
                    'index': True,
                    'similarity': 'cosine'
                }
            }
        }
    }
    es.indices.create(index=INDEX_NAME, body=mapping)
    print(f"✅ Created index '{INDEX_NAME}'")
else:
    print(f"ℹ️ Using existing index '{INDEX_NAME}'")

# ---------------------------
# Helpers
# ---------------------------

def make_article_id(url: str) -> str:
    return hashlib.sha1(url.encode('utf-8')).hexdigest()


def make_chunk_id(url: str, idx: int) -> str:
    return hashlib.sha1(f"{url}#{idx}".encode('utf-8')).hexdigest()


def extract_main_text(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html, 'html.parser')

    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    container = soup.find('article') or soup.find('main') or soup.body or soup

    # Remove noisy sections common on PMC pages
    noisy_selectors = [
        '#reference-list', '.ref-list', '#references', '.references',
        '#citedby', '.citedby', '#footnotes', '.footnotes',
        '#figures', '.figures', '#tables', '.tables',
        '#supplementary-material', '.supplementary-material'
    ]
    for sel in noisy_selectors:
        for node in container.select(sel):
            try:
                node.decompose()
            except Exception:
                pass

    blocks: List[str] = []
    for tag in container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li']):
        txt = tag.get_text(' ', strip=True)
        if txt:
            blocks.append(txt)
    if not blocks:
        txt = container.get_text('\n', strip=True)
        blocks = [t for t in txt.split('\n') if t.strip()]

    # Heuristic: cut off at References/Footnotes sections if present
    cut_markers = {m.lower() for m in ['References', 'REFERENCES', 'Footnotes', 'Acknowledgments', 'Supplementary Material']}
    cut_idx = None
    for idx, b in enumerate(blocks):
        if b.strip().lower() in cut_markers:
            cut_idx = idx
            break
    if cut_idx is not None and cut_idx > 5:
        blocks = blocks[:cut_idx]

    raw_text = "\n\n".join(blocks)
    text = normalize_whitespace(raw_text)
    return {'title': title or '', 'text': text}


def build_elastic_auth_header(raw_key: str) -> str:
    if ':' in raw_key and not raw_key.strip().endswith('='):
        import base64
        b64 = base64.b64encode(raw_key.encode('utf-8')).decode('utf-8')
        return f"ApiKey {b64}"
    return f"ApiKey {raw_key.strip()}"

ELASTIC_URL_BASE = (ELASTIC_URL or '').rstrip('/')

es_http = requests.Session()
es_http.headers.update({
    'Authorization': build_elastic_auth_header(ELASTIC_API_KEY),
    'Content-Type': 'application/json'
})

page_session = requests.Session()
page_session.headers.update({'User-Agent': 'ElasticDemo/1.0'})

# ---------------------------
# Read CSV
# ---------------------------
articles: List[Dict[str, str]] = []
try:
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError('CSV appears to have no header row')
        reader.fieldnames = [name.strip().lower() for name in reader.fieldnames if name]
        for row in reader:
            title = (row.get('title') or '').strip()
            url = (row.get('link') or '').strip()
            if title and url:
                articles.append({'title': title, 'url': url})
except Exception as e:
    print(f'❌ Failed to read CSV: {e}')
    sys.exit(1)

if MAX_ARTICLES:
    articles = articles[:MAX_ARTICLES]

print(f'📄 Found {len(articles)} articles; chunk_size={CHUNK_SIZE}, throttle={THROTTLE_SEC}s, retries={MAX_RETRIES}')

# ---------------------------
# Embedding with retries
# ---------------------------

def embed_with_retries(text: str) -> List[float] | None:
    delay = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            inf_url = f"{ELASTIC_URL_BASE}/_inference/text_embedding/{MODEL_ID}"
            resp = es_http.post(inf_url, data=json.dumps({'input': text[:8000]}), timeout=30)
            if resp.status_code == 429:
                raise RuntimeError('429 Too Many Requests')
            if not resp.ok:
                raise RuntimeError(f"{resp.status_code} {resp.text[:200]}")
            data = resp.json()
            predicted = data.get('predicted_value')
            if isinstance(predicted, list):
                vec = predicted[0] if (predicted and isinstance(predicted[0], list)) else predicted
            else:
                te = data.get('text_embedding') or []
                vec = te[0]['embedding'] if te and isinstance(te, list) and 'embedding' in te[0] else None
            if isinstance(vec, list):
                return vec
            raise RuntimeError('Embedding vector missing')
        except Exception as e:
            if VERBOSE:
                print(f"       × Embed attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay = min(delay * 2, 30)
            else:
                return None

# ---------------------------
# Generator of actions (low memory)
# ---------------------------

def generate_actions() -> Iterable[dict]:
    total_chunks = 0
    for i, art in enumerate(articles, 1):
        url = art['url']
        expected_title = art['title']
        print(f"\n🔄 [{i}/{len(articles)}] {expected_title[:80]} …")
        try:
            r = page_session.get(url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"   • Fetch failed: {e}")
            continue

        parsed = extract_main_text(r.text)
        title = (parsed['title'] or expected_title).strip()
        text = parsed['text']
        print(f"   • Extracted {len(text):,} chars")
        if not text or len(text) < 200:
            print("   • Skipping: insufficient text")
            continue

        target_chars = 2000 if len(text) > 60000 else 3200
        sents = split_into_sentences(text)
        chunks = chunk_sentences(sents, target_chars=target_chars, overlap_sentences=2)
        if not chunks:
            chunks = paragraph_first_chunking(text, target_chars=target_chars)
        print(f"   • Chunks: {len(chunks)} (target_chars={target_chars})")

        art_id = make_article_id(url)
        now = datetime.now(timezone.utc)

        for idx, chunk_text in enumerate(chunks):
            if VERBOSE:
                print(f"     · Chunk {idx} ({len(chunk_text)} chars)")
            vec = embed_with_retries(chunk_text)
            if not vec:
                print(f"       × Skipping chunk {idx}: embedding failed")
                continue

            chunk_id = make_chunk_id(url, idx)
            action = {
                '_index': INDEX_NAME,
                '_id': chunk_id,
                '_op_type': 'create',  # idempotent; 409 -> already exists
                'url': url,
                'title': title,
                'article_id': art_id,
                'chunk_id': chunk_id,
                'chunk_index': idx,
                'n_chars': len(chunk_text),
                'content': chunk_text,
                'timestamp': now,
                'content_vector': vec,
            }
            total_chunks += 1
            if THROTTLE_SEC:
                time.sleep(THROTTLE_SEC)
            yield action

        # free memory between articles
        del r, parsed, text, sents, chunks
        gc.collect()

    print(f"\n➡️ Generated ~{total_chunks} chunk actions")

# ---------------------------
# Stream to Elasticsearch with retries/backoff
# ---------------------------

success = 0
errors = 0
start = time.time()

for ok, item in streaming_bulk(
    es,
    generate_actions(),
    chunk_size=CHUNK_SIZE,
    max_retries=MAX_RETRIES,
    initial_backoff=2,
    max_backoff=60,
    request_timeout=180,
    yield_ok=True,
    raise_on_error=False,
    raise_on_exception=False,
):
    if ok:
        success += 1
        if success % (CHUNK_SIZE * 2) == 0:
            print(f"     📦 Progress: {success} indexed, {errors} errors")
    else:
        errors += 1
        # item contains the action result; report concise reason
        try:
            info = list(item.values())[0]
            err = info.get('error')
            if isinstance(err, dict):
                reason = err.get('reason') or err.get('type')
            else:
                reason = str(err)
            status = info.get('status')
            print(f"     ❌ Index error (status {status}): {reason}")
        except Exception:
            print(f"     ❌ Index error: {item}")

elapsed = time.time() - start
print(f"\n✅ Done. Indexed={success}, errors={errors}, elapsed={elapsed:.1f}s")
print(f"🔗 Check index: {INDEX_NAME}")
