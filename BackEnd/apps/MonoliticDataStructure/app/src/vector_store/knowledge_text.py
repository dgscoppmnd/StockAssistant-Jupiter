"""Utilidades puras para normalizar y fragmentar conocimiento documental."""


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    """Divide texto conservando una pequena ventana entre fragmentos."""
    clean = normalize_text(text)
    if not clean:
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size debe ser mayor que overlap")

    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = find_chunk_end(clean, start, chunk_size)
        chunks.append(clean[start:end].strip())
        if end == len(clean):
            break
        start = end - overlap
    return chunks


def find_chunk_end(text: str, start: int, chunk_size: int) -> int:
    end = min(start + chunk_size, len(text))
    if end == len(text):
        return end
    split_at = text.rfind(". ", start, end)
    return split_at + 1 if split_at > start + chunk_size // 2 else end
