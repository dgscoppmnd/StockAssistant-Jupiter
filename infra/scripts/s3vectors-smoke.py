"""Prueba de humo de S3 Vectors con vectores aleatorios (no usa OpenAI).

Uso (desde BackEnd/apps/MonoliticDataStructure/app, con boto3 instalado y credenciales AWS):
    python ../../../../infra/scripts/s3vectors-smoke.py [--index documents] [--bucket stockassistant-vectors]
Inserta N vectores con prefijo 'smoke-', consulta con filtro $in y los borra.
"""

import argparse
import random
import sys
import time

import boto3

sys.path.insert(0, "src")
from vector_store.s3vectors_store import S3VectorsStore  # noqa: E402

DIMENSION = 1536


def random_vector(rng: random.Random) -> list[float]:
    return [rng.uniform(-1, 1) for _ in range(DIMENSION)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="documents")
    parser.add_argument("--bucket", default="stockassistant-vectors")
    parser.add_argument("--region", default="eu-west-1")
    parser.add_argument("--count", type=int, default=60)
    args = parser.parse_args()

    client = boto3.client("s3vectors", region_name=args.region)
    store = S3VectorsStore(args.index, bucket=args.bucket, client=client)
    rng = random.Random(7)
    items = [
        {"key": f"smoke-{i}", "vector": random_vector(rng), "metadata": {"chunk_id": f"smoke-{i}"}}
        for i in range(args.count)
    ]
    keys = [item["key"] for item in items]

    try:
        start = time.perf_counter()
        store.put(items)
        print(f"put {len(items)} vectores: {(time.perf_counter() - start) * 1000:.0f} ms")

        target = items[3]
        start = time.perf_counter()
        hits = store.query(target["vector"], 5)
        print(f"query sin filtro: {(time.perf_counter() - start) * 1000:.0f} ms, top={hits[0]['key']} score={hits[0]['score']:.3f}")
        assert hits[0]["key"] == "smoke-3", "el vector idéntico debe ser el primero"

        # Mismo tamaño de filtro que usa la aplicación (50 ids)
        allowed = keys[:50]
        start = time.perf_counter()
        filtered = store.query(items[55]["vector"], 8, {"chunk_id": {"$in": allowed}})
        print(f"query con $in de {len(allowed)} ids: {(time.perf_counter() - start) * 1000:.0f} ms, {len(filtered)} resultados")
        assert all(hit["key"] in allowed for hit in filtered), "el filtro $in no se respeta"
        print("OK: IAM, escritura, consulta y filtro $in funcionan")
    finally:
        store.delete(keys)
        print("vectores de prueba borrados")


if __name__ == "__main__":
    main()
