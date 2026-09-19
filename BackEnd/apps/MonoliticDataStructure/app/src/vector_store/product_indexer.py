"""Indexación idempotente de productos en Qdrant.

Admite tanto el catálogo analítico (``product_name``/``description``) como
los productos gestionados desde el frontend
(``name_product``/``description_product``).
"""

import argparse
import hashlib
import logging
from pathlib import Path
from itertools import islice
from typing import Dict, Iterable, Iterator, List

import pandas as pd
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointIdsList, PointStruct, VectorParams

from api.config import settings
from .embeddings import encode_texts

logger = logging.getLogger(__name__)

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "generated" / "products.csv"


def _first_value(product: Dict[str, object], *keys: str, default: object = "") -> object:
    for key in keys:
        value = product.get(key)
        if value is not None and value != "":
            return value
    return default


def product_text(product: Dict[str, object]) -> str:
    """Construye texto semántico compatible con ambos modelos de producto."""
    name = _first_value(product, "product_name", "name_product")
    description = _first_value(product, "description", "description_product")
    supplier = _first_value(product, "supplier")
    external_code = _first_value(product, "product_id", "cdgo_producto_externo")
    return ". ".join(
        str(value).strip()
        for value in (name, description, supplier, external_code)
        if str(value).strip()
    )


def stable_point_id(product_id: str) -> str:
    """Genera un UUID estable para que las reindexaciones hagan upsert."""
    return hashlib.md5(product_id.encode("utf-8"), usedforsecurity=False).hexdigest()


def product_point_key(product: Dict[str, object]) -> str:
    """Identidad estable del vector, incluso si cambia el código externo."""
    if product.get("pk_product") is not None:
        return f"operational:{product['pk_product']}"
    product_id = _first_value(product, "product_id", "cdgo_producto_externo")
    if not str(product_id).strip():
        raise ValueError("El producto necesita product_id, cdgo_producto_externo o pk_product")
    # Conserva la identidad histórica del indexador CSV para no duplicar
    # puntos en colecciones creadas antes de la sincronización operativa.
    return str(product_id)


def product_payload(product: Dict[str, object]) -> Dict[str, object]:
    """Metadata común devuelta por las búsquedas semánticas."""
    external_id = _first_value(
        product,
        "product_id",
        "cdgo_producto_externo",
        "pk_product",
    )
    payload: Dict[str, object] = {
        "product_id": str(external_id),
        "product_name": str(_first_value(product, "product_name", "name_product")),
        "description": str(_first_value(product, "description", "description_product")),
        "product_category": str(_first_value(product, "product_category")),
        "brand": str(_first_value(product, "brand")),
        "sku": str(_first_value(product, "sku")),
        "supplier": str(_first_value(product, "supplier")),
    }
    if product.get("pk_product") is not None:
        payload["pk_product"] = int(product["pk_product"])
    return payload


def _batches(values: Iterable[Dict[str, object]], size: int) -> Iterator[List[Dict[str, object]]]:
    iterator = iter(values)
    while batch := list(islice(iterator, size)):
        yield batch


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


def iter_upsert_product_records(
    products: Iterable[Dict[str, object]],
    batch_size: int = 128,
    client: QdrantClient | None = None,
) -> Iterator[int]:
    """Actualiza productos por lotes y comunica el total tras cada upsert."""
    if batch_size < 1:
        raise ValueError("batch_size debe ser mayor que cero")
    own_client = client is None
    qdrant = client or get_client()
    total = 0
    try:
        ensure_collection(qdrant)
        for batch in _batches(products, batch_size):
            vectors = encode_texts([product_text(product) for product in batch])
            points = [
                PointStruct(
                    id=stable_point_id(product_point_key(product)),
                    vector=vector,
                    payload=product_payload(product),
                )
                for product, vector in zip(batch, vectors)
            ]
            qdrant.upsert(
                collection_name=settings.QDRANT_COLLECTION,
                points=points,
                wait=True,
            )
            total += len(points)
            yield total
    finally:
        if own_client:
            qdrant.close()


def upsert_product_records(
    products: Iterable[Dict[str, object]],
    batch_size: int = 128,
    client: QdrantClient | None = None,
) -> int:
    """Crea la colección y actualiza los vectores de los productos recibidos."""
    total = 0
    for total in iter_upsert_product_records(products, batch_size=batch_size, client=client):
        pass
    return total


def delete_product_record(pk_product: int, client: QdrantClient | None = None) -> None:
    """Elimina el vector asociado a un producto operativo, si existe."""
    own_client = client is None
    qdrant = client or get_client()
    try:
        if not qdrant.collection_exists(settings.QDRANT_COLLECTION):
            return
        qdrant.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=PointIdsList(
                points=[stable_point_id(f"operational:{pk_product}")],
            ),
            wait=True,
        )
    finally:
        if own_client:
            qdrant.close()


def index_products(csv_path: Path, batch_size: int = 128) -> int:
    """Indexa productos por lotes y devuelve el número de puntos escritos."""
    def rows() -> Iterator[Dict[str, object]]:
        for dataframe_batch in pd.read_csv(csv_path, chunksize=batch_size):
            yield from dataframe_batch.to_dict("records")

    total = upsert_product_records(rows(), batch_size=batch_size)
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
