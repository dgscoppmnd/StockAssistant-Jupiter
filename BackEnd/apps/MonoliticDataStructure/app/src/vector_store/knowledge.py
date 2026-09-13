"""Indexacion y recuperacion de documentos de conocimiento para Proyecto Jupiter."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Iterator

from qdrant_client.models import Distance, PointStruct, VectorParams

from ..api.config import settings
from .embeddings import encode_query, encode_texts
from .knowledge_text import chunk_text, normalize_text
from .product_indexer import get_client

SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf"}
DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge"


def read_document(path: Path) -> Iterator[tuple[str, int | None]]:
    """Produce el texto por pagina para PDF y como un unico bloque para texto plano."""
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Instala pypdf para indexar documentos PDF") from exc
        reader = PdfReader(path)
        for page_number, page in enumerate(reader.pages, start=1):
            yield page.extract_text() or "", page_number
        return
    yield path.read_text(encoding="utf-8"), None


def ensure_collection() -> None:
    client = get_client()
    try:
        if not client.collection_exists(settings.KNOWLEDGE_COLLECTION):
            client.create_collection(
                collection_name=settings.KNOWLEDGE_COLLECTION,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
    finally:
        client.close()


def stable_id(source: Path, page: int | None, chunk_number: int, text: str) -> str:
    raw = f"{source.name}:{page}:{chunk_number}:{text}".encode("utf-8")
    return hashlib.md5(raw, usedforsecurity=False).hexdigest()


def build_records(document: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for page, page_number in read_document(document):
        for chunk_number, text in enumerate(chunk_text(page)):
            records.append(
                {
                    "id": stable_id(document, page_number, chunk_number, text),
                    "text": text,
                    "source": document.name,
                    "source_type": document.suffix.lower().lstrip("."),
                    "page": page_number,
                    "chunk": chunk_number,
                }
            )
    return records


def collect_records(directory: Path) -> list[dict[str, Any]]:
    documents = sorted(path for path in directory.rglob("*") if path.suffix.lower() in SUPPORTED_SUFFIXES)
    return [record for document in documents for record in build_records(document)]


def upsert_records(records: list[dict[str, Any]], batch_size: int) -> None:
    client = get_client()
    try:
        for offset in range(0, len(records), batch_size):
            batch = records[offset : offset + batch_size]
            vectors = encode_texts(record["text"] for record in batch)
            points = [PointStruct(id=record["id"], vector=vector, payload=record) for record, vector in zip(batch, vectors)]
            client.upsert(collection_name=settings.KNOWLEDGE_COLLECTION, points=points, wait=True)
    finally:
        client.close()


def index_knowledge(directory: Path, batch_size: int = 32) -> int:
    """Indexa PDF, Markdown y texto; los IDs estables permiten reindexar."""
    if not directory.exists():
        raise FileNotFoundError(f"No existe el directorio de conocimiento: {directory}")
    records = collect_records(directory)
    if not records:
        return 0
    ensure_collection()
    upsert_records(records, batch_size)
    return len(records)


def search_knowledge(query: str, limit: int | None = None, source_type: str | None = None) -> list[dict[str, Any]]:
    """Recupera evidencia relevante y descarta coincidencias de baja confianza."""
    client = get_client()
    try:
        if not client.collection_exists(settings.KNOWLEDGE_COLLECTION):
            return []
        response = client.query_points(
            collection_name=settings.KNOWLEDGE_COLLECTION,
            query=encode_query(query),
            limit=limit or settings.KNOWLEDGE_SEARCH_LIMIT,
            with_payload=True,
        )
    finally:
        client.close()

    results = []
    for point in response.points:
        payload = dict(point.payload or {})
        if point.score < settings.KNOWLEDGE_SCORE_THRESHOLD:
            continue
        if source_type and payload.get("source_type") != source_type.lower():
            continue
        results.append({"score": round(float(point.score), 4), **payload})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa conocimiento documental de Proyecto Jupiter")
    parser.add_argument("--directory", type=Path, default=DEFAULT_KNOWLEDGE_DIR)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    print(f"Fragmentos indexados: {index_knowledge(args.directory, args.batch_size)}")


if __name__ == "__main__":
    main()
