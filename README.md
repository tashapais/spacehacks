# NASA Bioscience Knowledge-Graph Atlas

Interactively explore NASA's space biology experiments through a knowledge graph enhanced by AI-generated summaries, citations, and imagery tailored to scientists, managers, and mission architects.

## Repository Layout
- `docs/` architecture, design notes, and research references.
- `data/` raw and processed datasets (placeholders for now).
- `src/atlas/` Python package implementing ingestion, processing, graph construction, and AI services.
- `scripts/` operational entrypoints (ETL orchestration, demo pipelines).

## Quick Start (planned)
1. Create a virtual environment and install dependencies via `pip install -e .[dev]`.
2. Copy `.env.example` to `.env` and set `NASA_API_KEY` to your key (or leave as `DEMO_KEY` for limited access).
3. Place the 608-publication CSV inside `data/raw/nasa_space_biology_publications.csv`.
4. Run `scripts/bootstrap_demo.py` to build a sample knowledge graph snapshot and cache AI summaries locally.

### NASA API Utilities
- `scripts/fetch_nasa_data.py apod --date 2024-01-01 --output data/processed/apod.json`
- `scripts/fetch_nasa_data.py search-images "ISS plant biology" --output data/processed/iss_plants.json`

## Current Status
- Architecture blueprint defined in `docs/architecture.md`.
- Python package scaffolding for ingestion, processing, graph, and AI layers.
- Demo bootstrap script illustrating the orchestration flow (stubs until real data provided).

## Next Steps
1. Implement connectors to NASA resources (OSDR, Task Book, NSLSL).
2. Build production-grade entity and relation extraction pipelines.
3. Integrate LLM provider of choice for summarization with citation tracebacks.
4. Develop the web dashboard to visualize graph insights per persona.
