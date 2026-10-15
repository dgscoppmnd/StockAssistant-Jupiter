"""Embeddings de productos: modelo local (sentence-transformers) u OpenAI."""

import os
from functools import lru_cache
from typing import Iterable, List

from api.config import settings


def _use_openai() -> bool:
    return os.getenv("RAG_EMBEDDING_PROVIDER", "").strip().lower() == "openai"


@lru_cache(maxsize=1)
def get_embedding_model():
    """Carga el modelo una sola vez por proceso."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        settings.EMBEDDING_MODEL,
        device="cpu",
        model_kwargs={"low_cpu_mem_usage": False},
    )


def encode_texts(texts: Iterable[str]) -> List[List[float]]:
    """Genera embeddings normalizados para una colección de textos."""
    if _use_openai():
        from knowledge_vectors import embed

        vectors, _ = embed(list(texts))
        return vectors
    embeddings = get_embedding_model().encode(
        list(texts),
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()


def encode_query(text: str) -> List[float]:
    """Genera el embedding normalizado de una consulta."""
    return encode_texts([text])[0]
