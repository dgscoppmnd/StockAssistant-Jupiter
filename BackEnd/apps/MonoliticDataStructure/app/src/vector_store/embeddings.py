"""Carga perezosa del modelo de embeddings."""

from functools import lru_cache
from typing import Iterable, List

from sentence_transformers import SentenceTransformer

from ..api.config import settings


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Carga el modelo una sola vez por proceso."""
    return SentenceTransformer(
        settings.EMBEDDING_MODEL,
        device="cpu",
        model_kwargs={"low_cpu_mem_usage": False},
    )


def encode_texts(texts: Iterable[str]) -> List[List[float]]:
    """Genera embeddings normalizados para una colección de textos."""
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
