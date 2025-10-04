import argparse
import csv
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch, helpers
from readability import Document

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover - optional dependency
    pass


DEFAULT_MAX_CHARS = 3200
DEFAULT_OVERLAP = 400


@dataclass
class Article:
    title: str
    link: str


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")


def load_articles(csv_path: str) -> List[Article]:
    articles: List[Article] = []
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            title = (row.get("Title") or "").strip()
            link = (row.get("Link") or "").strip()
            if not link:
                logging.warning("Skipping row without link: %s", row)
                continue
            articles.append(Article(title=title, link=link))
    logging.info("Loaded %d links from %s", len(articles), csv_path)
    return articles


def fetch_html(url: str, timeout: int = 20, max_retries: int = 3) -> Optional[str]:
    headers = {
        "User-Agent": "SpacehacksRAG/1.0 (+https://github.com/tashapais/Spacehacks)"
    }
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=headers)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            logging.warning("Attempt %d failed for %s: %s", attempt, url, exc)
            time.sleep(1.5 * attempt)
    logging.error("Failed to fetch %s after %d attempts", url, max_retries)
    return None


def extract_main_text(html: str) -> str:
    doc = Document(html)
    cleaned_html = doc.summary(html_partial=True)
    soup = BeautifulSoup(cleaned_html, "html.parser")
    text = soup.get_text(separator=" ")
    text = " ".join(text.split())
    return text


def chunk_text(text: str, max_chars: int, overlap: int) -> Iterable[str]:
    if not text:
        return []

    if max_chars <= overlap:
        raise ValueError("max_chars must be greater than overlap")

    start = 0
    end = len(text)
    while start < end:
        stop = min(end, start + max_chars)
        chunk = text[start:stop].strip()
        if chunk:
            yield chunk
        start = stop - overlap
        if start < 0:
            start = 0
        if start == stop:
            break


def ensure_index(client: Elasticsearch, index_name: str, embedding_dim: int) -> None:
    if client.indices.exists(index=index_name):
        logging.info("Index %s already exists", index_name)
        return

    base_body = {
        "mappings": {
            "properties": {
                "title": {"type": "text"},
                "link": {"type": "keyword"},
                "content": {"type": "text"},
                "chunk_index": {"type": "integer"},
                "chunk_id": {"type": "keyword"},
                "content_vector": {
                    "type": "dense_vector",
                    "dims": embedding_dim,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }

    try:
        body_with_settings = {
            **base_body,
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 1
            },
        }
        client.indices.create(index=index_name, body=body_with_settings)
        logging.info("Created index %s", index_name)
    except Exception as exc:
        message = str(exc)
        if "serverless" in message.lower():
            logging.info("Retrying index creation without shard settings for serverless deployment")
            client.indices.create(index=index_name, body=base_body)
            logging.info("Created index %s (serverless mode)", index_name)
        else:
            raise


def create_pipeline_if_needed(client: Elasticsearch, pipeline_id: str, model_id: str) -> None:
    if client.ingest.get_pipeline(id=pipeline_id, ignore=404):
        logging.info("Pipeline %s already exists", pipeline_id)
        return

    body = {
        "description": "Spacehacks semantic ingest pipeline",
        "processors": [
            {
                "inference": {
                    "model_id": model_id,
                    "target_field": "ml",
                    "field_map": {
                        "content": "content"
                    },
                    "inference_config": {
                        "text_embedding": {
                            "results_field": "predicted_value"
                        }
                    }
                }
            },
            {
                "script": {
                    "lang": "painless",
                    "source": "if (ctx.containsKey('ml') && ctx.ml.containsKey('predicted_value')) { ctx.content_vector = ctx.ml.predicted_value; ctx.remove('ml'); }"
                }
            }
        ]
    }
    client.ingest.put_pipeline(id=pipeline_id, body=body)
    logging.info("Created pipeline %s using model %s", pipeline_id, model_id)


def prepare_documents(article: Article, max_chars: int, overlap: int) -> List[dict]:
    html = fetch_html(article.link)
    if html is None:
        return []
    text = extract_main_text(html)
    chunks = list(chunk_text(text, max_chars=max_chars, overlap=overlap))
    documents = []
    for idx, chunk in enumerate(chunks):
        doc_id = f"{article.link}#chunk-{idx}"
        documents.append(
            {
                "_id": doc_id,
                "title": article.title,
                "link": article.link,
                "content": chunk,
                "chunk_index": idx,
                "chunk_id": doc_id,
            }
        )
    logging.debug("Prepared %d chunks for %s", len(documents), article.link)
    return documents


def index_documents(
    client: Elasticsearch,
    index_name: str,
    pipeline_id: str,
    documents: Iterable[dict],
    request_timeout: int = 60
) -> None:
    actions = (
        {
            "_op_type": "index",
            "_index": index_name,
            "_id": doc["_id"],
            "_source": {
                k: v for k, v in doc.items() if k != "_id"
            }
        }
        for doc in documents
    )

    helpers.bulk(
        client,
        actions,
        pipeline=pipeline_id,
        chunk_size=100,
        request_timeout=request_timeout
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Spacehacks corpus into Elastic with embeddings")
    parser.add_argument("--csv", default="SB_publication_PMC.csv", help="Path to CSV with Title, Link columns")
    parser.add_argument("--elastic-url", default=os.getenv("ELASTIC_URL", "http://localhost:9200"))
    parser.add_argument("--elastic-username", default=os.getenv("ELASTIC_USERNAME"))
    parser.add_argument("--elastic-password", default=os.getenv("ELASTIC_PASSWORD"))
    parser.add_argument("--elastic-api-key", default=os.getenv("ELASTIC_API_KEY"))
    parser.add_argument("--index", default=os.getenv("ELASTIC_INDEX", "spacehacks"))
    parser.add_argument("--pipeline", default=os.getenv("ELASTIC_PIPELINE", "spacehacks-semantic"))
    parser.add_argument("--model-id", default=os.getenv("ELASTIC_MODEL_ID"), help="Inference model id for pipeline creation")
    parser.add_argument("--embedding-dim", type=int, default=int(os.getenv("ELASTIC_EMBED_DIM", "384")))
    parser.add_argument("--max-chars", type=int, default=int(os.getenv("CHUNK_MAX_CHARS", str(DEFAULT_MAX_CHARS))))
    parser.add_argument("--overlap", type=int, default=int(os.getenv("CHUNK_OVERLAP", str(DEFAULT_OVERLAP))))
    parser.add_argument("--max-workers", type=int, default=int(os.getenv("INGEST_WORKERS", "4")))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("REQUEST_TIMEOUT", "60")))
    parser.add_argument("--skip-tls-verify", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--create-pipeline", action="store_true", help="Create ingest pipeline if it does not exist")
    args = parser.parse_args()

    configure_logging(args.verbose)

    if args.elastic_api_key:
        client = Elasticsearch(
            args.elastic_url,
            api_key=args.elastic_api_key,
            verify_certs=not args.skip_tls_verify
        )
    else:
        client = Elasticsearch(
            args.elastic_url,
            basic_auth=(args.elastic_username, args.elastic_password),
            verify_certs=not args.skip_tls_verify
        )

    ensure_index(client, args.index, args.embedding_dim)

    if args.create_pipeline:
        if not args.model_id:
            raise ValueError("--model-id is required when --create-pipeline is used")
        create_pipeline_if_needed(client, args.pipeline, args.model_id)

    articles = load_articles(args.csv)

    total_chunks = 0
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_map = {
            executor.submit(prepare_documents, article, args.max_chars, args.overlap): article
            for article in articles
        }
        for future in as_completed(future_map):
            article = future_map[future]
            try:
                docs = future.result()
            except Exception as exc:
                logging.error("Failed to process %s: %s", article.link, exc)
                continue
            if not docs:
                logging.warning("No text extracted for %s", article.link)
                continue
            index_documents(client, args.index, args.pipeline, docs, request_timeout=args.timeout)
            total_chunks += len(docs)
            logging.info("Indexed %d chunks for %s", len(docs), article.link)

    logging.info("Completed ingestion. Total chunks indexed: %d", total_chunks)


if __name__ == "__main__":
    main()
