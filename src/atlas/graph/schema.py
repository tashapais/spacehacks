"""Knowledge graph schema definitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Node:
    uid: str
    label: str
    properties: Dict[str, object] = field(default_factory=dict)


@dataclass
class Edge:
    uid: str
    source: str
    target: str
    label: str
    properties: Dict[str, object] = field(default_factory=dict)


@dataclass
class GraphSchema:
    """Declarative schema for node and edge types."""

    node_types: Dict[str, Dict[str, str]]
    edge_types: Dict[str, Dict[str, str]]

    def describe_node(self, node_type: str) -> Optional[Dict[str, str]]:
        return self.node_types.get(node_type)

    def describe_edge(self, edge_type: str) -> Optional[Dict[str, str]]:
        return self.edge_types.get(edge_type)
