# Knowledge-Graph Atlas Architecture

## Vision
Deliver an interactive NASA biosciences atlas that fuses structured knowledge graphs with AI-generated insights. Users (scientists, managers, mission architects) quickly surface experiments, trace relationships, and read evidence-grounded summaries with citations and imagery.

## Core Capabilities
- **Ingest & Normalize**: Import the 608-publication CSV, NASA OSDR metadata, Task Book entries, and NSLSL references into a unified schema.
- **Knowledge Graph Construction**: Extract entities (organisms, missions, habitats, assays, outcomes) and relationships ("studied_on", "performed_during", "supports") to build a graph representing the experimental landscape.
- **Semantic Enrichment**: Run NLP pipelines (entity recognition, relation extraction, topic modeling) to enrich nodes with attributes, embeddings, and temporal metadata.
- **AI Summaries with Citations**: Generate node- and cluster-level summaries referencing specific publications (e.g., `[Smith 2019]`). Maintain provenance by storing citation spans and sentence-level tracebacks.
- **Audience Layering**: Tailor summarization prompts and UI narratives for scientists (methodological detail), managers (investment signals), and mission architects (operational implications).
- **Insightful Visuals**: Surface mission imagery and experimental diagrams sourced from NASA media libraries; embed relevant thumbnails alongside summaries.

## Data Flow
1. **Acquisition**
   - Load base CSV of 608 publications.
   - Fetch supplemental metadata via API or offline dumps from OSDR, NSLSL, Task Book.
   - Archive raw assets in `data/raw/`.
2. **Preprocessing**
   - Clean title/abstract text, standardize identifiers, deduplicate experiments.
   - Parse PDF/HTML full text when available; segment into sections (Intro, Methods, Results, etc.).
3. **Entity & Relation Extraction**
   - Use spaCy/transformer-based NER fine-tuned on bioscience/space lexicons.
   - Derive mission phases, organisms, tissues, hardware, environmental factors via rule-based enrichments and ontology lookups (e.g., MeSH, Gene Ontology).
   - Construct candidate relations through dependency parsing and co-occurrence heuristics, then validate with an LLM-assisted labeler.
4. **Knowledge Graph Assembly**
   - Represent data using RDF triples or property graph (Neo4j / Memgraph / NetworkX for prototyping).
   - Version nodes/edges per ingestion batch; store provenance metadata (source_doc_id, confidence).
5. **Vector & Summary Generation**
   - Embed document chunks and graph node descriptions using sentence transformers.
   - Store embeddings in a local vector DB (FAISS/Chroma) for semantic search.
   - Summarize nodes, edges, and clusters via LLM prompts that include top supporting chunks; return structured JSON (summary text, citations list, image suggestions).
6. **Media Integration**
   - For each mission/study, lookup related imagery (e.g., NASA Image and Video Library API). Cache thumbnails in `data/media/`.
7. **API Layer**
   - Serve graph queries (filtered neighbors, path discovery) via FastAPI/GraphQL endpoints.
   - Expose summarization-on-demand endpoints with caching and rate limiting.
8. **Frontend Dashboard**
   - React + D3 (or Observable Plot) interface displaying graph exploration, detail panes, timeline sliders, and persona toggles.
   - Provide configurable filters (organism, mission, environment). Show AI summary with citations section and media carousel.

## Modular Components
- `ingest/` – connectors for CSV, APIs, document scraping.
- `processing/` – text cleaning, sectioning, NER, relation extraction.
- `graph/` – schema definitions, builders, storage adapters.
- `ai/` – embedding generation, summarization prompts, citation tracking.
- `api/` – FastAPI service exposing REST/GraphQL endpoints.
- `web/` – frontend application.
- `ops/` – orchestration scripts, ETL scheduling, monitoring notebooks.

## Persona-Specific Summaries
- **Scientist Mode**: Highlight experimental design, sample sizes, statistical outcomes, methodological caveats.
- **Manager Mode**: Emphasize program alignment, funding lineage, risk-reward scoring.
- **Mission Architect Mode**: Prioritize operational constraints, hardware readiness, physiological countermeasures.

## Data Provenance & Evaluation
- Maintain citation graph linking every generated statement to supporting sentences.
- Track extraction confidence and allow manual curation overrides.
- Implement unit/integration tests for ETL steps, schema validation, and summarization accuracy (spot checks with human labels).

## Deployment Considerations
- Containerize services; orchestrate via docker-compose / Kubernetes for scaling.
- Cache LLM outputs to minimize cost; support offline inference with local models where feasible.
- Provide observability (logging, metrics) for ingestion jobs and API latency.

## Next Steps
1. Formalize data schema and ontologies.
2. Prototype ingestion of the 608-publication CSV into a normalized database.
3. Build minimal knowledge graph with sample summaries to validate UX.
4. Iterate on persona-specific prompt templates and visualization components.
