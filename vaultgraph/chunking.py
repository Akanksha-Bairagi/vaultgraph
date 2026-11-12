import re


def chunk_text(text: str, max_chars: int = 500) -> list[str]:
    """Sentence-aware packing: never cuts mid-sentence, merges small paragraphs."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        for s in re.split(r"(?<=[.!?])\s+", p):
            if cur and len(cur) + len(s) + 1 > max_chars:
                chunks.append(cur)
                cur = s
            else:
                cur = (cur + " " + s).strip()
    if cur:
        chunks.append(cur)
    return chunks
