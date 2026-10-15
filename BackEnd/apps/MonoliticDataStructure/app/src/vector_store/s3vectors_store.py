"""Acceso a S3 Vectors (sustituye a Qdrant en AWS Lambda)."""

from __future__ import annotations

import os
from typing import Any, Iterable, Iterator, Sequence

PUT_BATCH_SIZE = 500
DELETE_BATCH_SIZE = 500
MAX_TOP_K = 100


def _batches(values: Sequence[Any], size: int) -> Iterator[Sequence[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def vector_backend() -> str:
    return os.getenv("VECTOR_BACKEND", "qdrant").strip().lower() or "qdrant"


def use_s3_vectors() -> bool:
    return vector_backend() == "s3vectors"


def vector_bucket_name() -> str:
    return os.getenv("S3_VECTORS_BUCKET", "stockassistant-vectors").strip()


def _default_client() -> Any:
    import boto3

    return boto3.client("s3vectors", region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"))


class S3VectorsStore:
    """Envoltorio fino sobre un índice de S3 Vectors."""

    def __init__(self, index_name: str, *, bucket: str | None = None, client: Any | None = None):
        self.index_name = index_name
        self.bucket = bucket or vector_bucket_name()
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = _default_client()
        return self._client

    def put(self, items: Iterable[dict[str, Any]]) -> int:
        """Inserta o sustituye vectores. Cada item: key, vector, metadata opcional."""
        vectors = [
            {
                "key": item["key"],
                "data": {"float32": [float(value) for value in item["vector"]]},
                **({"metadata": item["metadata"]} if item.get("metadata") else {}),
            }
            for item in items
        ]
        for batch in _batches(vectors, PUT_BATCH_SIZE):
            self.client.put_vectors(
                vectorBucketName=self.bucket,
                indexName=self.index_name,
                vectors=list(batch),
            )
        return len(vectors)

    def delete(self, keys: Sequence[str]) -> None:
        for batch in _batches(list(keys), DELETE_BATCH_SIZE):
            self.client.delete_vectors(
                vectorBucketName=self.bucket,
                indexName=self.index_name,
                keys=list(batch),
            )

    def query(
        self,
        vector: Sequence[float],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Devuelve key, score (similitud coseno = 1 - distancia) y metadata."""
        params: dict[str, Any] = {
            "vectorBucketName": self.bucket,
            "indexName": self.index_name,
            "topK": max(1, min(int(top_k), MAX_TOP_K)),
            "queryVector": {"float32": [float(value) for value in vector]},
            "returnMetadata": True,
            "returnDistance": True,
        }
        if metadata_filter:
            params["filter"] = metadata_filter
        response = self.client.query_vectors(**params)
        return [
            {
                "key": hit["key"],
                "score": 1.0 - float(hit["distance"]),
                "metadata": hit.get("metadata") or {},
            }
            for hit in response.get("vectors", [])
        ]


def truncate_metadata(metadata: dict[str, Any], limits: dict[str, int] | None = None) -> dict[str, Any]:
    """Acota textos largos: S3 Vectors limita a 2 KB la metadata filtrable por vector."""
    limits = limits or {}
    return {
        key: (value[: limits.get(key, 300)] if isinstance(value, str) else value)
        for key, value in metadata.items()
        if value is not None
    }
