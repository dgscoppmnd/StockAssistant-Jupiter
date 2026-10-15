"""App mínima para validar Lambda + Web Adapter + RDS antes de migrar el backend real."""
import os
import secrets
import socket
import time

import psycopg2
from fastapi import FastAPI, Header, HTTPException

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


def _tcp_probe(host: str, port: int) -> dict:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=5):
            return {"ok": True, "ms": round((time.monotonic() - started) * 1000)}
    except OSError as exc:
        return {"ok": False, "error": str(exc), "ms": round((time.monotonic() - started) * 1000)}


@app.get("/db-check")
def db_check(x_smoke_token: str = Header(default="")):
    expected = os.environ.get("SMOKE_TOKEN", "")
    if not expected or not secrets.compare_digest(x_smoke_token, expected):
        raise HTTPException(status_code=403, detail="forbidden")

    host = os.environ["POSTGRES_HOST"]
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    result = {"tcp": _tcp_probe(host, port)}

    started = time.monotonic()
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            sslmode="verify-full",
            sslrootcert=os.environ.get("PGSSLROOTCERT", "/opt/rds-global-bundle.pem"),
            connect_timeout=10,
        )
    except psycopg2.Error as exc:
        result["db_error"] = str(exc).strip()
        result["ms"] = round((time.monotonic() - started) * 1000)
        return result

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result["db"] = cur.fetchone()[0]
            cur.execute("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
            result["ssl"] = cur.fetchone()[0]
    finally:
        conn.close()
    result["ms"] = round((time.monotonic() - started) * 1000)
    return result
