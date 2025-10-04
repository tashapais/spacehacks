"""Bootstrap a demo knowledge graph snapshot from the NASA publication CSV."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import typer

from atlas.ai.llm import MockLLMClient
from atlas.ai.summarizer import Summarizer, SummaryRequest
from atlas.graph.builder import KnowledgeGraphBuilder
from atlas.ingest.csv_loader import load_publications_csv
from atlas.ingest.models import PublicationRecord
from atlas.processing.entities import Entity, RuleBasedEntityExtractor
from atlas.processing.text import TextChunk, chunk_text

app = typer.Typer(help="Bootstrap a demo knowledge-graph atlas snapshot")

DEFAULT_CSV = Path("data/raw/nasa_space_biology_publications.csv")
DEFAULT_OUTPUT = Path("data/processed/demo_summary.json")


def _load_records(csv_path: Path) -> List[PublicationRecord]:
    if csv_path.exists():
        batch = load_publications_csv(csv_path)
        if batch.issues:
            typer.secho("Ingestion issues detected:", fg=typer.colors.YELLOW)
            for issue in batch.issues:
                typer.secho(f"- {issue}", fg=typer.colors.YELLOW)
        return batch.records

    typer.secho("CSV not found; using stub record for demonstration.", fg=typer.colors.YELLOW)
    return [
        PublicationRecord(
            uid="demo_0001",
            title="Simulated Microgravity Effects on Arabidopsis Root Development",
            authors=["Doe, Jane", "Smith, Alex"],
            year=2022,
            doi="10.1234/demo",
            mission="ISS",
            organism="Arabidopsis thaliana",
            environment="microgravity",
            abstract=(
                "Arabidopsis seedlings grown aboard the ISS exhibited altered root gravitropism"
                " and differential gene expression in auxin signaling pathways. Ground controls"
                " under 1g maintained typical root orientation. Findings suggest adaptive"
                " mechanisms mitigating microgravity stress."
            ),
        )
    ]


def _extract_entities(records: List[PublicationRecord]) -> dict[str, List[Entity]]:
    extractor = RuleBasedEntityExtractor(
        keyword_map={
            "arabidopsis": "ORGANISM",
            "iss": "MISSION",
            "microgravity": "ENVIRONMENT",
        }
    )
    entity_map: dict[str, List[Entity]] = {}
    for record in records:
        text = record.abstract or record.title
        entity_map[record.uid] = extractor.extract(text)
    return entity_map


def _build_context_chunks(records: List[PublicationRecord]) -> List[TextChunk]:
    chunks: List[TextChunk] = []
    for record in records:
        if record.abstract:
            chunks.extend(chunk_text(record.uid, record.abstract, section="abstract"))
    return chunks


@app.command()
def run(
    csv_path: Path = typer.Option(DEFAULT_CSV, exists=False, help="Path to the 608 publication CSV"),
    persona: str = typer.Option("scientist", help="Target persona for the summary"),
    output_path: Path = typer.Option(DEFAULT_OUTPUT, help="Where to write the summary JSON"),
) -> None:
    """Run the bootstrap workflow."""
    records = _load_records(csv_path)
    if not records:
        raise typer.Exit(code=1)

    entity_map = _extract_entities(records)

    builder = KnowledgeGraphBuilder()
    graph = builder.ingest_publications(records, entities=entity_map)
    typer.secho(
        f"Graph constructed with {graph.graph.number_of_nodes()} nodes and {graph.graph.number_of_edges()} edges.",
        fg=typer.colors.GREEN,
    )

    context_chunks = _build_context_chunks(records)
    mock_payload = {
        "summary_text": (
            "Arabidopsis studies aboard the ISS reveal altered root orientation and gene"
            " regulation compared to 1g controls, highlighting adaptive auxin signaling [1]."
            " Microgravity-exposed seedlings show mitigated stress responses applicable to"
            " future long-duration missions [1].\n\nKey Takeaways:\n- Microgravity reshapes root gravitropism dynamics [1]\n- Auxin signaling shifts suggest adaptive plasticity [1]\n- ISS results inform crop support strategies for Mars transits [1]"
        ),
        "citations": [
            {
                "publication_id": records[0].uid,
                "sentence": "ISS-grown Arabidopsis modified root orientation relative to ground controls.",
                "evidence_spans": ["chunk_0"],
            }
        ],
        "image_suggestions": ["ISS plant growth chamber", "Arabidopsis microgravity experiment"],
    }

    summarizer = Summarizer(MockLLMClient(response=json.dumps(mock_payload)))
    summary = summarizer.summarize(
        SummaryRequest(
            target_id=records[0].uid,
            title=records[0].title,
            persona=persona,
            context_chunks=context_chunks,
        )
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "persona": summary.persona,
                "summary_text": summary.summary_text,
                "citations": [
                    {
                        "publication_id": c.publication_id,
                        "sentence": c.sentence,
                        "evidence_spans": c.evidence_spans,
                    }
                    for c in summary.citations
                ],
                "image_suggestions": summary.image_suggestions,
            },
            f,
            indent=2,
        )

    typer.secho(f"Summary written to {output_path}", fg=typer.colors.GREEN)


if __name__ == "__main__":  # pragma: no cover
    app()
