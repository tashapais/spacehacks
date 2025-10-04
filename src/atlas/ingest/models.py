"""Data models for ingestion layer."""
from __future__ import annotations

from typing import Iterable, List, Optional

from pydantic import BaseModel, Field


class PublicationRecord(BaseModel):
    """Normalized metadata for a single publication."""

    uid: str = Field(..., description="Unique identifier derived from source data")
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    mission: Optional[str] = None
    organism: Optional[str] = None
    environment: Optional[str] = None
    document_path: Optional[str] = None
    abstract: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    source: str = Field(default="nasa_catalog")


class IngestionBatch(BaseModel):
    """Container for ingestion results along with provenance metadata."""

    source_name: str
    records: List[PublicationRecord]
    raw_path: str
    issues: List[str] = Field(default_factory=list)

    def iter_records(self) -> Iterable[PublicationRecord]:
        return iter(self.records)
