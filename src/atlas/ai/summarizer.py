"""Summarization utilities producing persona-aware outputs with citations."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from textwrap import dedent
from typing import Dict, Iterable, List, Optional

from atlas.ai.llm import LLMClient
from atlas.processing.text import TextChunk


@dataclass
class Citation:
    publication_id: str
    sentence: str
    evidence_spans: List[str] = field(default_factory=list)


@dataclass
class SummaryResponse:
    summary_text: str
    citations: List[Citation] = field(default_factory=list)
    persona: str = "scientist"
    image_suggestions: List[str] = field(default_factory=list)


@dataclass
class SummaryRequest:
    target_id: str
    title: str
    persona: str
    context_chunks: List[TextChunk]
    focus_questions: Optional[List[str]] = None


PERSONA_PROMPTS: Dict[str, str] = {
    "scientist": "Emphasize experimental design, sample sizes, key findings, and methodological caveats.",
    "manager": "Highlight strategic value, investment signals, maturity level, and cross-program alignment.",
    "mission_architect": "Summarize operational implications, risks to crew/mission, hardware readiness, and mitigation strategies.",
}


class Summarizer:
    """Generates persona-specific summaries with citation tracebacks."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def summarize(self, request: SummaryRequest) -> SummaryResponse:
        prompt = self._build_prompt(request)
        raw_response = self.llm_client.complete(prompt)
        return self._parse_response(raw_response, request)

    def _build_prompt(self, request: SummaryRequest) -> str:
        persona_guidance = PERSONA_PROMPTS.get(request.persona, PERSONA_PROMPTS["scientist"])
        joined_context = "\n\n".join(
            dedent(
                f"Publication: {chunk.publication_id}\nSection: {chunk.section or 'body'}\nExcerpt: {chunk.text}"
            )
            for chunk in request.context_chunks
        )
        focus_text = "\n".join(request.focus_questions or [])
        instructions = dedent(
            f"""
            You are preparing a summary for persona: {request.persona}.
            Persona guidance: {persona_guidance}

            Requirements:
            - Produce 2-3 paragraphs and a bullet list of key takeaways.
            - Provide in-text numeric citations like [1], [2] that map to the references list.
            - Each citation must reference a specific publication ID from the context.
            - Recommend up to 3 relevant NASA imagery search terms.
            - Respond with JSON containing fields summary_text, citations, image_suggestions.

            Optional focus questions:
            {focus_text or 'None provided.'}

            Context passages:
            {joined_context}
            """
        ).strip()
        return instructions

    def _parse_response(self, raw: str, request: SummaryRequest) -> SummaryResponse:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback when the model returns plain text.
            fallback_citation = Citation(
                publication_id=request.context_chunks[0].publication_id if request.context_chunks else "unknown",
                sentence="Refer to original context chunks for evidence.",
            )
            return SummaryResponse(
                summary_text=raw.strip(),
                citations=[fallback_citation],
                persona=request.persona,
                image_suggestions=[],
            )

        citations = [
            Citation(
                publication_id=item.get("publication_id", "unknown"),
                sentence=item.get("sentence", ""),
                evidence_spans=item.get("evidence_spans", []) or [],
            )
            for item in payload.get("citations", [])
        ]

        return SummaryResponse(
            summary_text=payload.get("summary_text", ""),
            citations=citations,
            persona=request.persona,
            image_suggestions=payload.get("image_suggestions", []) or [],
        )
