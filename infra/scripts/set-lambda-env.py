"""Fusiona variables nuevas en la Lambda sin imprimir secretos.

Uso: python infra/scripts/set-lambda-env.py [--function stockassistant-api] [--region eu-west-1]
Lee las variables actuales, añade las estáticas y retira los secretos (la imagen los lee de SSM).
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile

AWS = shutil.which("aws") or "aws"

STATIC = {
    "VECTOR_BACKEND": "s3vectors",
    "S3_VECTORS_BUCKET": "stockassistant-vectors",
    "EMBEDDING_DIMENSION": "1536",
    "RAG_EMBEDDING_PROVIDER": "openai",
    "AI_PROVIDER": "openai",
    "DOCUMENTS_BUCKET": "stockassistant-files-118645514410-eu-west-1",
    "AWS_LWA_PASS_THROUGH_PATH": "/internal/index",
    "SECRETS_FROM_SSM": "true",
}

# La imagen (>= v5) los lee de SSM al arrancar; no deben estar en la función
REMOVE = [
    "OPENAI_API_KEY", "GOOGLE_CLIENT_ID", "STOCKASSISTANT_API_KEYS",
    "STOCKASSISTANT_SESSION_SECRET", "SECRET_KEY", "DB_PASSWORD", "POSTGRES_PASSWORD",
]


def aws(*args: str) -> str:
    result = subprocess.run([AWS, *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"aws {args[0]} {args[1]} falló: {result.stderr.strip()}")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--function", default="stockassistant-api")
    parser.add_argument("--region", default="eu-west-1")
    args = parser.parse_args()

    current = json.loads(
        aws(
            "lambda", "get-function-configuration",
            "--function-name", args.function, "--region", args.region,
            "--query", "Environment.Variables", "--output", "json",
        )
    ) or {}
    current.update(STATIC)
    for name in REMOVE:
        current.pop(name, None)

    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump({"Variables": current}, handle)
        aws(
            "lambda", "update-function-configuration",
            "--function-name", args.function, "--region", args.region,
            "--environment", "file://" + path.replace("\\", "/"),
            "--query", "LastUpdateStatus", "--output", "text",
        )
    finally:
        os.remove(path)
    print("Variables en la Lambda:", ", ".join(sorted(current)))


if __name__ == "__main__":
    main()
