"""Knowledge graph construction utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

import networkx as nx

from atlas.graph.schema import Edge, GraphSchema, Node
from atlas.ingest.models import PublicationRecord
from atlas.processing.entities import Entity


DEFAULT_SCHEMA = GraphSchema(
    node_types={
        "Publication": {"plural": "Publications"},
        "Organism": {"plural": "Organisms"},
        "Mission": {"plural": "Missions"},
        "Environment": {"plural": "Environments"},
        "Outcome": {"plural": "Outcomes"},
    },
    edge_types={
        "STUDIED": {"description": "Publication studied organism"},
        "OCCURRED_DURING": {"description": "Publication occurred during mission"},
        "UNDER_CONDITION": {"description": "Experiment under environment"},
        "REPORTS": {"description": "Publication reports outcome"},
    },
)


@dataclass
class KnowledgeGraph:
    graph: nx.MultiDiGraph = field(default_factory=nx.MultiDiGraph)

    def add_node(self, node: Node) -> None:
        self.graph.add_node(node.uid, label=node.label, **node.properties)

    def add_edge(self, edge: Edge) -> None:
        self.graph.add_edge(edge.source, edge.target, key=edge.uid, label=edge.label, **edge.properties)


class KnowledgeGraphBuilder:
    """Constructs a knowledge graph from publication records and extracted entities."""

    def __init__(self, schema: GraphSchema | None = None) -> None:
        self.schema = schema or DEFAULT_SCHEMA
        self.graph = KnowledgeGraph()

    def ingest_publications(
        self,
        publications: Iterable[PublicationRecord],
        entities: Optional[Dict[str, Iterable[Entity]]] = None,
    ) -> KnowledgeGraph:
        entity_map = entities or {}
        for record in publications:
            self._add_publication(record)
            record_entities = list(entity_map.get(record.uid, []))
            self._attach_entities(record, record_entities)
        return self.graph

    def _add_publication(self, record: PublicationRecord) -> None:
        node = Node(
            uid=record.uid,
            label="Publication",
            properties={
                "title": record.title,
                "year": record.year,
                "doi": record.doi,
                "mission": record.mission,
                "organism": record.organism,
                "source": record.source,
            },
        )
        self.graph.add_node(node)

    def _attach_entities(self, record: PublicationRecord, entities: Iterable[Entity]) -> None:
        for entity in entities:
            node_uid = f"{entity.label}:{entity.text.lower()}"
            if not self.graph.graph.has_node(node_uid):
                self.graph.add_node(
                    Node(
                        uid=node_uid,
                        label=entity.label.title(),
                        properties={"name": entity.text, "source": record.source},
                    )
                )

            edge_label = self._edge_label_for_entity(entity)
            edge_uid = f"{record.uid}->{node_uid}:{edge_label}"
            self.graph.add_edge(
                Edge(
                    uid=edge_uid,
                    source=record.uid,
                    target=node_uid,
                    label=edge_label,
                    properties={"confidence": entity.score},
                )
            )

    def _edge_label_for_entity(self, entity: Entity) -> str:
        label_map = {
            "ORGANISM": "STUDIED",
            "MISSION": "OCCURRED_DURING",
            "ENVIRONMENT": "UNDER_CONDITION",
        }
        return label_map.get(entity.label, "MENTIONS")
