"""Almacenamiento de ficheros subidos en S3 (Lambda no tiene disco persistente)."""
import hmac
import json
import logging
import os
from pathlib import Path

LOGGER = logging.getLogger("src.file_storage")
IS_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))


def bucket() -> str | None:
    return os.getenv("DOCUMENTS_BUCKET") or None


def _client():
    import boto3

    return boto3.client("s3")


def upload(path: Path, key: str, content_type: str | None = None) -> None:
    extra = {"ContentType": content_type} if content_type else None
    _client().upload_file(str(path), bucket(), key, ExtraArgs=extra)


def download(key: str, path: Path) -> bool:
    from botocore.exceptions import ClientError

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _client().download_file(bucket(), key, str(path))
        return True
    except ClientError:
        path.unlink(missing_ok=True)
        return False


def delete(key: str) -> None:
    try:
        _client().delete_object(Bucket=bucket(), Key=key)
    except Exception:
        LOGGER.warning("event=s3_delete_failed key=%s", key)


def read_bytes(key: str) -> bytes | None:
    from botocore.exceptions import ClientError

    try:
        return _client().get_object(Bucket=bucket(), Key=key)["Body"].read()
    except ClientError:
        return None


def trigger_indexing() -> None:
    """Lambda no tiene hilo worker: se reinvoca a sí misma de forma asíncrona."""
    if not IS_LAMBDA:
        return
    secret = os.getenv("STOCKASSISTANT_SESSION_SECRET", "")
    if not secret:
        LOGGER.warning("event=index_trigger_skipped reason=no_secret")
        return
    try:
        import boto3

        boto3.client("lambda").invoke(
            FunctionName=os.environ["AWS_LAMBDA_FUNCTION_NAME"],
            InvocationType="Event",
            Payload=json.dumps({"jupiter_index": secret}).encode(),
        )
    except Exception:
        LOGGER.warning("event=index_trigger_failed", exc_info=True)


def valid_trigger_token(token) -> bool:
    secret = os.getenv("STOCKASSISTANT_SESSION_SECRET", "")
    return bool(secret) and isinstance(token, str) and hmac.compare_digest(token, secret)
