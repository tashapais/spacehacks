# Spacehacks RAG Pipeline
Video on how to use: https://www.loom.com/share/436b11b432d24da1a8da409a6e799732?sid=c8fdd507-0d17-40b1-ab45-b8efccc94660


Project overview: https://www.canva.com/design/DAG03RClQs0/IisGjn7Af_J681ci4SG7aA/edit?utm_content=DAG03RClQs0&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton

This repository ingests 608 publicly available NASA/space biology links from `SB_publication_PMC.csv`, stores chunked content in Amazon OpenSearch Service / Elastic Cloud, and enables retrieval augmented generation (RAG) answers with inline citations.

## Prerequisites

- Python 3.10+
- Access to an Elastic deployment (Amazon OpenSearch Service or Elastic Cloud) with text-embedding support. The examples below assume Elastic 8.11+.
- An embedding model deployed in Elastic (for example `sentence-transformers__all-minilm-l6-v2`) and an ingest pipeline that writes the embedding vector into `content_vector`.
- (Optional) An OpenAI API key for the answer-generation step.

## Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Create inference model and ingest pipeline

Replace `YOUR_MODEL_ID` with the model you've deployed. The pipeline writes the embedding into `content_vector` so the index mapping must match the embedding dimension.

```bash
# 1. Create an inference pipeline that embeds during ingest
curl -u "$ELASTIC_USERNAME:$ELASTIC_PASSWORD" \
  -X PUT "$ELASTIC_URL/_ingest/pipeline/spacehacks-semantic" \
  -H 'Content-Type: application/json' \
  -d '{
    "description": "Spacehacks semantic ingest pipeline",
    "processors": [
      {
        "inference": {
          "model_id": "YOUR_MODEL_ID",
          "target_field": "ml",
          "field_map": { "content": "content" },
          "inference_config": { "text_embedding": { "results_field": "predicted_value" } }
        }
      },
      {
        "script": {
          "lang": "painless",
          "source": "if (ctx.containsKey(\"ml\") && ctx.ml.containsKey(\"predicted_value\")) { ctx.content_vector = ctx.ml.predicted_value; ctx.remove(\"ml\"); }"
        }
      }
    ]
  }'
```

## Configure environment variables

Create a `.env` file or export variables directly:

```
ELASTIC_URL=https://your-domain.es.amazonaws.com
ELASTIC_USERNAME=your-username
ELASTIC_PASSWORD=your-password
ELASTIC_INDEX=spacehacks
ELASTIC_PIPELINE=spacehacks-semantic
ELASTIC_MODEL_ID=YOUR_MODEL_ID
ELASTIC_EMBED_DIM=384  # match your model
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

The scripts automatically load `.env` if `python-dotenv` is installed (included in `requirements.txt`).

## Ingest the corpus

The ingestion script fetches each URL, extracts the main article text, chunks it with overlap, and indexes through the ingest pipeline so embeddings are generated at ingest time.

```bash
python rag/ingest.py \
  --csv SB_publication_PMC.csv \
  --create-pipeline \
  --verbose
```

Key flags:

- `--create-pipeline` creates the ingest pipeline if it does not exist (requires `ELASTIC_MODEL_ID`).
- `--max-chars`/`--overlap` control chunk sizing.
- `--max-workers` sets parallel fetch workers (default 4).

## Ask a question with citations

`rag/query.py` embeds the question using the same model, performs a kNN search, and (optionally) calls OpenAI for answer generation. Citations in the LLM response follow `[n]` format mapped to the retrieved source links.

```bash
python rag/query.py "How does microgravity affect bone density in mice?" --print-context
```

Add `--no-llm` to inspect the retrieved passages only, or supply `OPENAI_API_KEY` to let the script call OpenAI directly.

## Response format

When `rag/query.py` calls an LLM, it instructs the model to:

- Use only the retrieved excerpts.
- Provide inline citations such as `[1]` or `[2]` referencing the numbered legend returned alongside the answer.
- Respond that the answer is not available if the context lacks sufficient evidence.

## Next steps

- Tune chunk sizes and worker counts for your dataset.
- Add automated validation that ensures every chunk receives an embedding (e.g., by checking `_source.content_vector`).
- Expand the query script to log usage metrics or support additional LLM providers (Bedrock, Azure OpenAI, etc.).
