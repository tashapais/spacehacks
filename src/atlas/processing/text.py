"""Text processing utilities for publication content."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

SECTION_PATTERN = re.compile(r"^\s*(introduction|methods|results|discussion|conclusion)s?:", re.IGNORECASE)


@dataclass
class TextChunk:
    """Represents a chunk of text with provenance metadata."""

    publication_id: str
    section: Optional[str]
    text: str
    chunk_index: int
    char_start: int
    char_end: int


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_into_sections(text: str) -> Dict[str, str]:
    """Naively split text into sections based on common headings."""
    sections: Dict[str, List[str]] = {}
    current_section = "body"
    sections[current_section] = []

    for line in text.splitlines():
        match = SECTION_PATTERN.match(line)
        if match:
            current_section = match.group(1).lower()
            sections.setdefault(current_section, [])
            continue
        sections[current_section].append(line)

    return {name: normalize_whitespace(" ".join(lines)) for name, lines in sections.items() if lines}


def chunk_text(publication_id: str, text: str, section: Optional[str] = None, max_tokens: int = 300) -> Iterable[TextChunk]:
    """Split text into overlapping chunks suitable for embedding."""
    if not text:
        return []

    words = text.split()
    if not words:
        return []

    chunk_words = max_tokens
    stride = int(max_tokens * 0.4)
    chunks: List[TextChunk] = []

    idx = 0
    chunk_index = 0
    while idx < len(words):
        end = min(idx + chunk_words, len(words))
        chunk = " ".join(words[idx:end])
        char_start = len(" ".join(words[:idx]))
        char_end = char_start + len(chunk)
        chunks.append(
            TextChunk(
                publication_id=publication_id,
                section=section,
                text=chunk,
                chunk_index=chunk_index,
                char_start=char_start,
                char_end=char_end,
            )
        )
        chunk_index += 1
        if end == len(words):
            break
        idx = max(end - stride, idx + 1)

    return chunks
