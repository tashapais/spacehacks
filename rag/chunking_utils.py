import re
from typing import List, Tuple

# Simple, dependency-free sentence splitter. Not perfect, but good enough.
_SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+")


def normalize_whitespace(text: str) -> str:
    # Preserve paragraph breaks while normalizing spaces within lines
    # First collapse Windows newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse more than 2 newlines to exactly 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Trim each line
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]
    # Remove empty lines at extremes
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def split_into_sentences(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    # Keep paragraph boundaries by splitting sentences per paragraph, then flatten
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    sentences: List[str] = []
    for p in paragraphs:
        # Basic sentence split within paragraph
        parts = _SENTENCE_SPLIT_REGEX.split(p.strip())
        # Merge tiny trailing fragments with previous sentence if too short
        tmp: List[str] = []
        for s in parts:
            s = s.strip()
            if not s:
                continue
            if tmp and len(s) < 20:
                tmp[-1] = (tmp[-1] + " " + s).strip()
            else:
                tmp.append(s)
        # Re-join with paragraph newline marker by adding a special token
        if sentences:
            sentences.append("\n\n")  # paragraph separator sentinel
        sentences.extend(tmp)
    return sentences


def chunk_sentences(
    sentences: List[str],
    target_chars: int = 3500,  # ~800-900 tokens
    overlap_sentences: int = 2,
) -> List[str]:
    if not sentences:
        return []

    chunks: List[str] = []
    buf: List[str] = []
    buf_len = 0

    def emit():
        nonlocal buf, buf_len
        if buf:
            # When emitting, strip paragraph sentinels at edges
            chunk = " ".join([s for s in buf if s != "\n\n"]).strip()
            if chunk:
                chunks.append(chunk)
        buf = []
        buf_len = 0

    i = 0
    n = len(sentences)
    while i < n:
        s = sentences[i]
        s_len = len(s)
        if buf_len == 0 and s == "\n\n":
            i += 1
            continue

        if buf_len + s_len + 1 > target_chars and buf:
            emit()
            # add overlap from previous emitted chunk
            if overlap_sentences > 0:
                # take last k non-sentinel sentences
                back: List[str] = []
                j = i - 1
                while j >= 0 and len(back) < overlap_sentences:
                    if sentences[j] != "\n\n":
                        back.append(sentences[j])
                    j -= 1
                for s_back in reversed(back):
                    buf.append(s_back)
                    buf_len += len(s_back) + 1
            continue

        buf.append(s)
        buf_len += s_len + 1
        i += 1

    emit()
    # Filter out tiny chunks
    chunks = [c for c in chunks if len(c) >= max(200, int(target_chars * 0.15))]
    return chunks


def paragraph_first_chunking(text: str, target_chars: int = 3500) -> List[str]:
    """Alternative: chunk by paragraphs with minimal splitting; fallback to sentences.
    """
    text = text.strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0
    for p in paragraphs:
        p_len = len(p)
        if cur_len + p_len + 2 <= target_chars or not cur:
            cur.append(p)
            cur_len += p_len + 2
        else:
            chunks.append("\n\n".join(cur))
            cur = [p]
            cur_len = p_len + 2
    if cur:
        chunks.append("\n\n".join(cur))
    # If any chunk is still too large, split that chunk by sentences
    final: List[str] = []
    for c in chunks:
        if len(c) > target_chars * 1.5:
            sents = split_into_sentences(c)
            final.extend(chunk_sentences(sents, target_chars=target_chars))
        else:
            final.append(c)
    return final
