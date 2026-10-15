"""Búsqueda semántica de productos (Qdrant o S3 Vectors)."""

from typing import Any, Dict, List, Optional

from api.config import settings
from .embeddings import encode_query
from .s3vectors_store import use_s3_vectors


def _search_s3(query: str, limit: Optional[int], category: Optional[str]) -> List[Dict[str, Any]]:
    from .product_indexer import _products_store

    metadata_filter = {"product_category": {"$eq": category}} if category else None
    hits = _products_store().query(
        encode_query(query), limit or settings.VECTOR_SEARCH_LIMIT, metadata_filter
    )
    return [{"score": hit["score"], **hit["metadata"]} for hit in hits]


def search_products(
    query: str,
    limit: Optional[int] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Busca productos similares y devuelve su payload junto a la puntuación."""
    if use_s3_vectors():
        return _search_s3(query, limit, category)

    from qdrant_client import QdrantClient
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    from .product_indexer import get_client

    client: QdrantClient = get_client()
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        client.close()
        return []
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
