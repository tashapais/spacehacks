"""CSV ingestion utilities for NASA bioscience publications."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .models import IngestionBatch, PublicationRecord


COLUMN_ALIASES: Dict[str, List[str]] = {
    "uid": ["uid", "id", "record_id", "document_id"],
    "title": ["title", "publication_title", "document_title"],
    "authors": ["authors", "author_list"],
    "year": ["year", "publication_year"],
    "doi": ["doi"],
    "url": ["url", "link"],
    "mission": ["mission", "experiment_mission"],
    "organism": ["organism", "species", "subject"],
    "environment": ["environment", "condition"],
    "abstract": ["abstract", "summary"],
    "keywords": ["keywords", "tags"],
}


def _match_column(columns: List[str], candidates: List[str]) -> Optional[str]:
    lower = {c.lower(): c for c in columns}
    for alias in candidates:
        if alias.lower() in lower:
            return lower[alias.lower()]
    return None


def load_publications_csv(path: Path, source_name: str = "nasa_catalog") -> IngestionBatch:
    """Load publications from CSV into normalized records."""
    df = pd.read_csv(path)
    column_cache: Dict[str, Optional[str]] = {
        field: _match_column(df.columns.tolist(), aliases)
        for field, aliases in COLUMN_ALIASES.items()
    }

    records: List[PublicationRecord] = []
    issues: List[str] = []

    for idx, row in df.iterrows():
        data: Dict[str, Optional[str]] = {}
        for field_name, column_name in column_cache.items():
            if column_name is None:
                continue
            data[field_name] = row.get(column_name)

        uid = str(data.get("uid") or f"{source_name}_{idx:04d}")
        title = (data.get("title") or "").strip()
        if not title:
            issues.append(f"Row {idx} missing title; skipped")
            continue

        authors = []
        raw_authors = data.get("authors")
        if isinstance(raw_authors, str):
            authors = [a.strip() for a in raw_authors.replace(";", ",").split(",") if a.strip()]

        keywords = []
        raw_keywords = data.get("keywords")
        if isinstance(raw_keywords, str):
            keywords = [k.strip() for k in raw_keywords.split(";") if k.strip()]

        record = PublicationRecord(
            uid=uid,
            title=title,
            authors=authors,
            year=int(data["year"]) if data.get("year") else None,
            doi=(data.get("doi") or None),
            url=(data.get("url") or None),
            mission=(data.get("mission") or None),
            organism=(data.get("organism") or None),
            environment=(data.get("environment") or None),
            abstract=(data.get("abstract") or None),
            keywords=keywords,
            source=source_name,
        )
        records.append(record)

    return IngestionBatch(
        source_name=source_name,
        records=records,
        raw_path=str(path),
        issues=issues,
    )
