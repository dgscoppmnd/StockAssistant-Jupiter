from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
from database_schema import schema_sql

logger = logging.getLogger("api.db")


def _get_env(*keys: str, default: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default


def _connect_with_retries(host: str, port: int, db_name: str, user: str, password: str):
    max_retries = int(_get_env("POSTGRES_CONNECT_RETRIES", default="10"))
    retry_delay_seconds = float(_get_env("POSTGRES_RETRY_DELAY_SECONDS", default="1"))

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "event=db_connect host=%s port=%s db=%s user=%s attempt=%s/%s",
                host,
                port,
                db_name,
                user,
                attempt,
                max_retries,
            )
            return psycopg2.connect(
                host=host,
                port=port,
                dbname=db_name,
                user=user,
                password=password,
            )
        except psycopg2.OperationalError:
            if attempt == max_retries:
                raise
            sleep_seconds = retry_delay_seconds * attempt
            logger.warning(
                "event=db_connect_retry host=%s db=%s attempt=%s/%s wait_seconds=%.2f",
                host,
                db_name,
                attempt,
                max_retries,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)


def _database_name(default: str = "supply_chain") -> str:
    return _get_env("POSTGRES_DB_NAME", "DB_NAME", "POSTGRES_DB", default=default)


def _get_postgres_connection_server(host: str = "postgres", db_name: str | None = None):
    resolved_host = _get_env("POSTGRES_HOST", "DB_HOST", default=host)
    resolved_port = int(_get_env("POSTGRES_PORT", "DB_PORT", default="5432"))
    resolved_db = db_name or _database_name()
    resolved_user = _get_env("POSTGRES_USER_NAME", "DB_USER", "POSTGRES_USER", default="admin")
    resolved_password = _get_env(
        "POSTGRES_PASSWORD_VALUE", "DB_PASSWORD", "POSTGRES_PASSWORD", default="admin123"
    )
    return _connect_with_retries(
        resolved_host, resolved_port, resolved_db, resolved_user, resolved_password
    )


@contextmanager
def db_context(db_name: str | None = None):
    connection = _get_postgres_connection_server(db_name=db_name)
    try:
        yield connection
    finally:
        connection.close()


def init_db() -> None:
    """Apply the canonical schema to the configured database without creating one."""
    script = schema_sql()
    with db_context() as connection:
        try:
            with connection.cursor() as cursor:
                # Serialize schema migrations when several API processes start together.
                cursor.execute("SELECT pg_advisory_xact_lock(702641903119)")
                cursor.execute(script)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    logger.info("event=init_db source=docker/init-scripts/init.sql status=ready")


def init_products_db() -> None:
    """Compatibility entry point; all tables now come from the canonical schema."""
    init_db()


def get_db() -> Generator[Any, None, None]:
    connection = _get_postgres_connection_server()
    try:
        yield connection
    finally:
        connection.close()


def get_db_products() -> Generator[Any, None, None]:
    connection = _get_postgres_connection_server()
    try:
        yield connection
    finally:
        connection.close()


def get_db_memori() -> Generator[Any, None, None]:
    connection = _get_postgres_connection_server()
    try:
        yield connection
    finally:
        connection.close()


def get_db_users() -> Generator[Any, None, None]:
    connection = _get_postgres_connection_server()
    try:
        yield connection
    finally:
        connection.close()
