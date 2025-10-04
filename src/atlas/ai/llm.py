"""LLM client abstractions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMClient(Protocol):
    """Minimal interface for LLM providers."""

    def complete(self, prompt: str) -> str:
        ...


@dataclass
class MockLLMClient:
    """Deterministic mock returning canned responses for testing."""

    response: str = ""

    def complete(self, prompt: str) -> str:  # pragma: no cover - trivial
        return self.response or "Summary unavailable; provide LLM integration."
