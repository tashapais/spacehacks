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
PIPELINE_ID = os.getenv('ELASTIC_PIPELINE_ID', 'articles_v2_embed')

VERBOSE = os.getenv('VERBOSE', '0') == '1'
CHUNK_THROTTLE_SEC = float(os.getenv('CHUNK_THROTTLE_SEC', '0.2'))

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

    # Heuristic: cut off at References/Footnotes headings
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


def ensure_pipeline(es: Elasticsearch):
    body = {
        'processors': [
            {
                'inference': {
                    'model_id': MODEL_ID,
                    'target_field': 'content_vector',
                    'field_map': {'content': 'text'},
                    'inference_config': {'text_embedding': {}},
                    'on_failure': [
                        {'set': {'field': 'pipeline_failure', 'value': '{{ _ingest.on_failure_message }}'}}
                    ]
                }
            }
        ]
    }
    # Some clusters use input_output format; try both
    try:
        es.ingest.put_pipeline(id=PIPELINE_ID, processors=body['processors'])
    except Exception:
        alt = {
            'processors': [
                {
                    'inference': {
                        'model_id': MODEL_ID,
                        'input_output': {
                            'input_text_field': 'content',
                            'predicted_value_field': 'content_vector'
                        },
                        'on_failure': [
                            {'set': {'field': 'pipeline_failure', 'value': '{{ _ingest.on_failure_message }}'}}
                        ]
                    }
                }
            ]
        }
        es.ingest.put_pipeline(id=PIPELINE_ID, processors=alt['processors'])


def ingest_with_pipeline(url: str, expected_title: Optional[str] = None) -> int:
    es = Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY, verify_certs=True)
    ensure_pipeline(es)

    page_session = requests.Session()
    page_session.headers.update({'User-Agent': 'ElasticDemo/1.0'})

    print(f"🔄 Ingesting via pipeline: {url}")
    try:
        r = page_session.get(url, timeout=60)
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

    target_chars = 1800 if len(text) > 60000 else 3000
    sents = split_into_sentences(text)
    chunks = chunk_sentences(sents, target_chars=target_chars, overlap_sentences=2)
    if not chunks:
        chunks = paragraph_first_chunking(text, target_chars=target_chars)
    print(f"   • Chunks: {len(chunks)} (target_chars={target_chars})")

    art_id = make_article_id(url)
    now = datetime.now(timezone.utc)

    success = 0
    for idx, chunk_text in enumerate(chunks):
        doc_id = make_chunk_id(url, idx)
        doc = {
            'url': url,
            'title': title,
            'article_id': art_id,
            'chunk_id': doc_id,
            'chunk_index': idx,
            'n_chars': len(chunk_text),
            'content': chunk_text,
            'timestamp': now,
        }
        try:
            es.index(index=INDEX_NAME, id=doc_id, document=doc, pipeline=PIPELINE_ID, op_type='create')
            success += 1
        except Exception as e:
            msg = str(e)
            if 'version_conflict_engine_exception' in msg or 'document_already_exists_exception' in msg or '409' in msg:
                success += 1
            else:
                print(f"     × Index failed chunk {idx}: {e}")
        time.sleep(CHUNK_THROTTLE_SEC)

    print(f"✅ Done article via pipeline. Indexed chunks: {success}/{len(chunks)}")
    try:
        es.close()
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Ingest a single article using ES ingest pipeline for embeddings.')
    ap.add_argument('--url', required=True, help='Article URL')
    ap.add_argument('--title', default='', help='Optional expected title')
    args = ap.parse_args()
    sys.exit(ingest_with_pipeline(args.url, args.title or None))
