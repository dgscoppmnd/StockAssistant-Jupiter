"""Resumable, bounded CSV import into the S3 Vectors products index."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import os
from itertools import islice
from pathlib import Path
import tempfile

from .embeddings import encode_texts
from .product_indexer import (
    PRODUCT_METADATA_LIMITS,
    product_payload,
    product_text,
    stable_point_id,
)
from .s3vectors_store import S3VectorsStore, truncate_metadata, use_s3_vectors

logger = logging.getLogger(__name__)
FIELDS = {"product_id", "product_name", "description", "product_category", "brand", "sku"}


def inspect_csv(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not FIELDS.issubset(reader.fieldnames or []):
            raise ValueError("CSV must contain: " + ", ".join(sorted(FIELDS)))
        for row_number, row in enumerate(reader, start=2):
            product_id = row["product_id"]
            if (
                None in row
                or any(value is None for value in row.values())
                or not product_id.strip()
                or product_id != product_id.strip()
                or product_id in seen
            ):
                raise ValueError(f"Invalid or duplicate product at CSV row {row_number}")
            seen.add(product_id)
    if not seen:
        raise ValueError("CSV contains no products")
    return digest.hexdigest(), len(seen)


def save_checkpoint(path: Path, state: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(state, output, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_items(items: object, dimension: int) -> None:
    if not isinstance(items, list) or not items:
        raise ValueError("Invalid pending batch")
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise ValueError("Invalid vector key")
        vector = item.get("vector")
        if not isinstance(vector, list) or len(vector) != dimension:
            raise ValueError("Embedding dimension does not match the index")
        if not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in vector
        ) or not any(vector):
            raise ValueError("Invalid embedding values")
        if not isinstance(item.get("metadata"), dict):
            raise ValueError("Invalid vector metadata")
    # Reject NaN/Infinity before persisting or writing anything.
    json.dumps(items, allow_nan=False)


def run_import(csv_path: Path, checkpoint: Path, *, batch_size: int, limit: int) -> int:
    """Return cumulative confirmed writes; limit bounds writes in this invocation."""
    if not 1 <= batch_size <= 100 or limit < 1:
        raise ValueError("batch-size must be 1..100 and limit must be positive")
    if not use_s3_vectors() or os.getenv("RAG_EMBEDDING_PROVIDER", "").lower() != "openai":
        raise ValueError("Requires VECTOR_BACKEND=s3vectors and RAG_EMBEDDING_PROVIDER=openai")
    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    if model != "text-embedding-3-small":
        raise ValueError("This importer requires text-embedding-3-small (1536 dimensions)")
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise ValueError("OPENAI_API_KEY is not configured")
    csv_path = csv_path.resolve(strict=True)
    checkpoint = checkpoint.resolve()
    if checkpoint == csv_path:
        raise ValueError("CSV and checkpoint must be different files")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    lock = checkpoint.with_name(checkpoint.name + ".lock")
    if lock == csv_path:
        raise ValueError("CSV cannot be used as the checkpoint lock")
    # Fail rather than run two writers against the same checkpoint.
    with lock.open("x", encoding="ascii") as handle:
        handle.write(str(os.getpid()))
    try:
        return _run_locked(csv_path, checkpoint, batch_size, limit, model)
    finally:
        lock.unlink()


def _run_locked(
    csv_path: Path, checkpoint: Path, batch_size: int, limit: int, model: str
) -> int:
    fingerprint, row_count = inspect_csv(csv_path)
    store = S3VectorsStore(os.getenv("S3_VECTORS_PRODUCTS_INDEX", "products"))
    index = store.client.get_index(
        vectorBucketName=store.bucket, indexName=store.index_name
    )["index"]
    if (
        index["dimension"] != 1536
        or index["distanceMetric"] != "cosine"
        or index["dataType"] != "float32"
    ):
        raise ValueError("Index must use float32, 1536 dimensions and cosine distance")
    identity = {
        "version": 1,
        "csv_sha256": fingerprint,
        "row_count": row_count,
        "index_arn": index["indexArn"],
        "model": model,
        "batch_size": batch_size,
    }
    if checkpoint.exists():
        state = json.loads(checkpoint.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("identity") != identity:
            raise ValueError("Checkpoint does not match this CSV, index, model or batch size")
    else:
        state = {"identity": identity, "completed": 0, "pending": None}
        save_checkpoint(checkpoint, state)
    completed = state.get("completed")
    if type(completed) is not int or not 0 <= completed <= row_count:
        raise ValueError("Invalid checkpoint progress")
    pending = state.get("pending")
    if pending is not None:
        validate_items(pending, index["dimension"])
        if len(pending) > batch_size or completed + len(pending) > row_count:
            raise ValueError("Invalid checkpoint batch length")
        if len(pending) > limit:
            raise ValueError("limit must cover the pending batch")
    logger.info("Confirmed progress: %s/%s", completed, row_count)
    written = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        for _ in range(completed):
            next(reader)
        while written < limit:
            count = len(pending) if pending is not None else min(batch_size, limit - written)
            rows = list(islice(reader, count))
            if not rows:
                break
            if pending is None:
                records = [dict(row) for row in rows]
                vectors = encode_texts([product_text(record) for record in records])
                if len(vectors) != len(records):
                    raise ValueError("Embedding count does not match the batch")
                pending = [
                    {
                        "key": stable_point_id(record["product_id"]),
                        "vector": vector,
                        "metadata": truncate_metadata(
                            product_payload(record), PRODUCT_METADATA_LIMITS
                        ),
                    }
                    for record, vector in zip(records, vectors)
                ]
                validate_items(pending, index["dimension"])
                state["pending"] = pending
                save_checkpoint(checkpoint, state)
            expected_keys = [stable_point_id(row["product_id"]) for row in rows]
            if [item["key"] for item in pending] != expected_keys:
                raise ValueError("Pending batch does not match CSV rows")
            store.put(pending)
            completed += len(rows)
            written += len(rows)
            state.update(completed=completed, pending=None)
            save_checkpoint(checkpoint, state)
            pending = None
            logger.info("Confirmed progress: %s/%s", completed, row_count)
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--limit", type=int, default=100, help="Maximum writes this invocation")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        completed = run_import(
            args.csv, args.checkpoint, batch_size=args.batch_size, limit=args.limit
        )
    except (Exception, KeyboardInterrupt):
        logger.exception("Import stopped; preserve the CSV and checkpoint before retrying")
        raise
    logger.info("Import stopped normally. Cumulative confirmed products: %s", completed)


if __name__ == "__main__":
    main()
