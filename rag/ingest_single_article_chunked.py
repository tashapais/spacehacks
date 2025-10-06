import os
import sys
import time
import json
import argparse
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

from chunking_utils import (
    normalize_whitespace,
    split_into_sentences,
    chunk_sentences,
    paragraph_first_chunking,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

ELASTIC_URL = os.getenv('ELASTIC_URL')
ELASTIC_API_KEY = os.getenv('ELASTIC_API_KEY')
INDEX_NAME = os.getenv('ELASTIC_INDEX_V2', 'articles_v2')
MODEL_ID = os.getenv('ELASTIC_MODEL_ID', '.multilingual-e5-small-elasticsearch')

VERBOSE = os.getenv('VERBOSE', '0') == '1'
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '5'))
CHUNK_THROTTLE_SEC = float(os.getenv('CHUNK_THROTTLE_SEC', '0.1'))

if not (ELASTIC_URL and ELASTIC_API_KEY):
    print('❌ Missing ELASTIC_URL/ELASTIC_API_KEY')
    sys.exit(2)


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

    # Remove noisy sections often present in PMC pages
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


def embed_with_retries(es_http: requests.Session, elastic_url_base: str, text: str) -> Optional[List[float]]:
    delay = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            inf_url = f"{elastic_url_base}/_inference/text_embedding/{MODEL_ID}"
            resp = es_http.post(inf_url, json={'input': text[:8000]}, timeout=30)
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


def ingest_single(url: str, expected_title: Optional[str] = None) -> int:
    elastic_url_base = (ELASTIC_URL or '').rstrip('/')

    es = Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY, verify_certs=True)

    page_session = requests.Session()
    page_session.headers.update({'User-Agent': 'ElasticDemo/1.0'})

    es_http = requests.Session()
    es_http.headers.update({'Authorization': build_elastic_auth_header(ELASTIC_API_KEY or '')})

    print(f"🔄 Ingesting: {url}")
    try:
        r = page_session.get(url, timeout=45)
        r.raise_for_status()
    except Exception as e:
        print(f"❌ Fetch failed: {e}")
        return 1

    parsed = extract_main_text(r.text)
    title = (parsed['title'] or expected_title or '').strip()
    text = parsed['text']
    print(f"   • Extracted {len(text)} chars")

    if not text or len(text) < 200:
        print("   • Skipping: insufficient text")
        return 0

    # For very large articles, use smaller chunk size to reduce load
    target_chars = 2000 if len(text) > 60000 else 3200
    sents = split_into_sentences(text)
    chunks = chunk_sentences(sents, target_chars=target_chars, overlap_sentences=2)
    if not chunks:
        chunks = paragraph_first_chunking(text, target_chars=target_chars)
    print(f"   • Chunks: {len(chunks)} (target_chars={target_chars})")

    art_id = make_article_id(url)
    now = datetime.now(timezone.utc)

    success = 0
    for idx, chunk_text in enumerate(chunks):
        if VERBOSE:
            preview = (chunk_text[:120] + '…') if len(chunk_text) > 140 else chunk_text
            print(f"     · Chunk {idx} ({len(chunk_text)} chars): {preview}")
        vec = embed_with_retries(es_http, elastic_url_base, chunk_text)
        if not vec:
            print(f"       × Embedding failed. Skipping chunk {idx}")
            continue

        chunk_id = make_chunk_id(url, idx)
        doc = {
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
        # Idempotent create
        try:
            es.create(index=INDEX_NAME, id=chunk_id, document=doc, timeout='60s')
            success += 1
        except Exception as e:
            # If already exists, treat as success; else log
            msg = str(e)
            if 'version_conflict_engine_exception' in msg or 'document_already_exists_exception' in msg or '409' in msg:
                success += 1
            else:
                print(f"       × Index failed chunk {idx}: {e}")
        time.sleep(CHUNK_THROTTLE_SEC)

    print(f"✅ Done article. Indexed chunks: {success}/{len(chunks)}")
    try:
        es.close()
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Ingest a single article (chunked) into Elasticsearch.')
    ap.add_argument('--url', required=True, help='Article URL')
    ap.add_argument('--title', default='', help='Optional expected title (for logging)')
    args = ap.parse_args()
    sys.exit(ingest_single(args.url, args.title or None))
