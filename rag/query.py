import argparse
import json
import logging
import os
from typing import Dict, List

from elasticsearch import Elasticsearch

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover - optional dependency
    pass

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")


def build_client(args: argparse.Namespace) -> Elasticsearch:
    if args.elastic_api_key:
        return Elasticsearch(
            args.elastic_url,
            api_key=args.elastic_api_key,
            verify_certs=not args.skip_tls_verify
        )
    return Elasticsearch(
        args.elastic_url,
        basic_auth=(args.elastic_username, args.elastic_password),
        verify_certs=not args.skip_tls_verify
    )


def embed_query(client: Elasticsearch, model_id: str, query: str) -> List[float]:
    path = f"/_inference/text_embedding/{model_id}"
    body = {"input": query}
    response = client.transport.perform_request("POST", path, body=body)
    predicted = response.get("predicted_value")
    if not predicted:
        raise RuntimeError(f"Inference response missing predicted_value: {json.dumps(response, indent=2)}")
    if isinstance(predicted[0], list):
        return predicted[0]
    return predicted


def knn_retrieve(
    client: Elasticsearch,
    index_name: str,
    vector: List[float],
    k: int,
    num_candidates: int
) -> List[Dict]:
    response = client.knn_search(
        index=index_name,
        knn={
            "field": "content_vector",
            "query_vector": vector,
            "k": k,
            "num_candidates": num_candidates,
        },
        source=["title", "link", "content", "chunk_index"],
        size=k
    )
    hits = response.get("hits", {}).get("hits", [])
    logging.info("Retrieved %d documents", len(hits))
    return hits


def format_context(hits: List[Dict]) -> str:
    blocks = []
    for idx, hit in enumerate(hits, start=1):
        source = hit.get("_source", {})
        title = source.get("title") or "Untitled"
        link = source.get("link") or ""
        excerpt = source.get("content") or ""
        blocks.append(
            f"[{idx}] Title: {title}\nLink: {link}\nExcerpt: {excerpt}"
        )
    return "\n\n".join(blocks)


def format_citation_map(hits: List[Dict]) -> Dict[str, Dict[str, str]]:
    citation_map: Dict[str, Dict[str, str]] = {}
    for idx, hit in enumerate(hits, start=1):
        source = hit.get("_source", {})
        citation_map[str(idx)] = {
            "title": source.get("title") or "Untitled",
            "link": source.get("link") or ""
        }
    return citation_map


def call_llm(question: str, context: str, model: str, temperature: float) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package not installed. Run `pip install openai`. ")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required")

    client = OpenAI(api_key=api_key)
    system_prompt = (
        "You are a research assistant answering questions about space biology. "
        "Only answer using the provided context. Include in-text citations using [n] "
        "where n corresponds to the numbered sources. If the context does not "
        "contain the answer, respond that the information is not available in the corpus."
    )

    user_prompt = (
        f"Question: {question}\n\n"
        "Context:\n"
        f"{context}\n\n"
        "Instructions:\n- Only use the provided context.\n"
        "- Include bracket citations like [1] referencing the relevant source numbers.\n"
        "- If unsure or unsupported, say you could not find the answer in the provided sources."
    )

    response = client.responses.create(
        model=model,
        temperature=temperature,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.output_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Query Elastic vector index and answer with citations")
    parser.add_argument("question", help="Natural language question to answer")
    parser.add_argument("--elastic-url", default=os.getenv("ELASTIC_URL", "http://localhost:9200"))
    parser.add_argument("--elastic-username", default=os.getenv("ELASTIC_USERNAME"))
    parser.add_argument("--elastic-password", default=os.getenv("ELASTIC_PASSWORD"))
    parser.add_argument("--elastic-api-key", default=os.getenv("ELASTIC_API_KEY"))
    parser.add_argument("--index", default=os.getenv("ELASTIC_INDEX", "spacehacks"))
    parser.add_argument("--model-id", default=os.getenv("ELASTIC_MODEL_ID"), help="Text embedding model id")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--num-candidates", type=int, default=50)
    parser.add_argument("--llm-model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--temperature", type=float, default=float(os.getenv("OPENAI_TEMPERATURE", "0.0")))
    parser.add_argument("--skip-tls-verify", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--print-context", action="store_true")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM call and only show retrieved context")
    args = parser.parse_args()

    configure_logging(args.verbose)

    if not args.model_id:
        raise ValueError("--model-id or ELASTIC_MODEL_ID environment variable is required")

    client = build_client(args)

    vector = embed_query(client, args.model_id, args.question)
    hits = knn_retrieve(client, args.index, vector, args.top_k, args.num_candidates)

    if args.print_context or args.no_llm:
        citation_map = format_citation_map(hits)
        context = format_context(hits)
        print("\nRetrieved context:\n")
        print(context)
        print("\nCitation legend:")
        for label, meta in citation_map.items():
            print(f"[{label}] {meta['title']} - {meta['link']}")

    if args.no_llm:
        return

    context = format_context(hits)
    answer = call_llm(args.question, context, args.llm_model, args.temperature)
    print("\nAnswer:\n")
    print(answer)


if __name__ == "__main__":
    main()
