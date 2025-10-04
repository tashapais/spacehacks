"""Entity and relation extraction interfaces."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Literal, Optional


@dataclass
class Entity:
    """Detected entity within a text span."""

    text: str
    label: Literal["ORGANISM", "MISSION", "HARDWARE", "ENVIRONMENT", "PHENOTYPE", "PROCESS", "OTHER"]
    start: int
    end: int
    score: float


@dataclass
class Relation:
    """Relationship between two entities."""

    subject: Entity
    predicate: str
    obj: Entity
    score: float


class EntityExtractor:
    """Abstract entity extractor."""

    def extract(self, text: str) -> List[Entity]:
        raise NotImplementedError


class RuleBasedEntityExtractor(EntityExtractor):
    """Simplistic rule-based extractor leveraging keyword dictionaries."""

    def __init__(self, keyword_map: Optional[dict[str, str]] = None) -> None:
        self.keyword_map = keyword_map or {}

    def extract(self, text: str) -> List[Entity]:
        entities: List[Entity] = []
        lower_text = text.lower()
        for keyword, label in self.keyword_map.items():
            idx = lower_text.find(keyword.lower())
            if idx >= 0:
                entities.append(
                    Entity(
                        text=text[idx : idx + len(keyword)],
                        label=label,  # type: ignore[arg-type]
                        start=idx,
                        end=idx + len(keyword),
                        score=0.4,
                    )
                )
        return entities


class RelationExtractor:
    """Relation extraction interface."""

    def extract(self, text: str, entities: Iterable[Entity]) -> List[Relation]:
        raise NotImplementedError
