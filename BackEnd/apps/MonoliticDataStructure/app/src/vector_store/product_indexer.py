"""Indexación idempotente de productos en Qdrant."""

import argparse
import hashlib
import logging
from pathlib import Path
from typing import Dict, List

import pandas as pd
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from ..api.config import settings
from .embeddings import encode_texts

logger = logging.getLogger(__name__)

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "generated" / "products.csv"


def product_text(product: Dict[str, object]) -> str:
    """Construye el texto semántico; los datos operativos quedan fuera."""
    return f"{product['product_name']}. {product['description']}"


def stable_point_id(product_id: str) -> str:
    """Genera un UUID estable para que las reindexaciones hagan upsert."""
    return hashlib.md5(product_id.encode("utf-8"), usedforsecurity=False).hexdigest()


def get_client() -> QdrantClient:
    return QdrantClient(url=settings.QDRANT_URL)


def ensure_collection(client: QdrantClient) -> None:
    """Crea la colección si no existe y evita borrar índices previos."""
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )


def index_products(csv_path: Path, batch_size: int = 128) -> int:
    """Indexa productos por lotes y devuelve el número de puntos escritos."""
    client = get_client()
    ensure_collection(client)
    total = 0

    for dataframe_batch in pd.read_csv(csv_path, chunksize=batch_size):
        batch: List[Dict[str, object]] = dataframe_batch.to_dict("records")
        texts = [product_text(product) for product in batch]
        vectors = encode_texts(texts)
        points = [
            PointStruct(
                id=stable_point_id(str(product["product_id"])),
                vector=vector,
                payload={
                    "product_id": product["product_id"],
                    "product_name": product["product_name"],
                    "product_category": product["product_category"],
                    "brand": product["brand"],
                    "sku": product["sku"],
                },
            )
            for product, vector in zip(batch, vectors)
        ]
        client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points, wait=True)
        total += len(points)
        logger.info("Indexados %s productos", total)

    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa productos en Qdrant")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    indexed = index_products(args.csv, args.batch_size)
    logger.info("Indexación completada: %s productos", indexed)


if __name__ == "__main__":
    main()
