"""Búsqueda semántica de productos en Qdrant."""

from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from ..api.config import settings
from .embeddings import encode_query
from .product_indexer import get_client


def search_products(
    query: str,
    limit: Optional[int] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Busca productos similares y devuelve su payload junto a la puntuación."""
    client: QdrantClient = get_client()
    query_filter = None
    if category:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="product_category",
                    match=MatchValue(value=category),
                )
            ]
        )

    response = client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=encode_query(query),
        query_filter=query_filter,
        limit=limit or settings.VECTOR_SEARCH_LIMIT,
        with_payload=True,
    )
    return [
        {
            "score": point.score,
            **(point.payload or {}),
        }
        for point in response.points
    ]
