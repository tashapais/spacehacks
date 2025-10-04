"""CLI utilities for fetching data from NASA APIs."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from atlas.ingest.nasa_api import NASAAPIClient

app = typer.Typer(help="Interact with NASA APIs using the configured API key")


def _write_output(data: dict, output: Path | None) -> None:
    payload = json.dumps(data, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        typer.secho(f"Response written to {output}", fg=typer.colors.GREEN)
    else:
        typer.echo(payload)


@app.command()
def apod(date: str = typer.Option(None, help="Target date YYYY-MM-DD"), output: Path | None = None) -> None:
    """Fetch Astronomy Picture of the Day metadata."""
    client = NASAAPIClient()
    data = client.apod(date=date)
    _write_output(data, output)


@app.command()
def search_images(
    query: str = typer.Argument(..., help="Search phrase"),
    page: int = typer.Option(1, min=1, help="Results page to fetch"),
    output: Path | None = typer.Option(None, help="Optional path to dump JSON response"),
) -> None:
    """Search NASA Image and Video Library."""
    client = NASAAPIClient()
    data = client.search_images(query=query, page=page)
    _write_output(data, output)


if __name__ == "__main__":  # pragma: no cover
    app()
