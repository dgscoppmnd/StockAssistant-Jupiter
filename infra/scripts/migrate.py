"""Apply ordered, immutable SQL migrations to an existing PostgreSQL database."""

import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path
import re

import psycopg2
import sqlparse
from sqlparse import tokens

LOGGER = logging.getLogger("stockassistant.migrations")
DIRECTORY = Path(__file__).resolve().parents[1] / "sql" / "migrations"
LOCK_ID = 702641903120
NAME = re.compile(r"V([0-9]{14})__([a-z][a-z0-9_]*)\.sql")


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    checksum: str
    statements: tuple[str, ...]


def load_migrations(directory: Path) -> list[Migration]:
    migrations = []
    versions = set()
    for path in sorted(directory.iterdir()):
        if path.name == "README.md":
            continue
        match = NAME.fullmatch(path.name)
        if not path.is_file() or match is None:
            raise ValueError(f"Invalid migration filename: {path.name}")
        version = match[1]
        datetime.strptime(version, "%Y%m%d%H%M%S")
        if version in versions:
            raise ValueError(f"Duplicate migration version: {version}")
        versions.add(version)
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        statements = []
        for statement in sqlparse.parse(text):
            meaningful = [
                token for token in statement.flatten()
                if not token.is_whitespace and token.ttype not in tokens.Comment
            ]
            if not meaningful or all(token.value == ";" for token in meaningful):
                continue
            first = meaningful[0].value.upper()
            if first in {"BEGIN", "COMMIT", "END", "ROLLBACK", "ABORT", "START", "SAVEPOINT",
                         "RELEASE", "PREPARE"} or first.startswith("\\"):
                raise ValueError(f"{path.name}: transaction control/psql commands are not allowed")
            statements.append(str(statement))
        if not statements:
            raise ValueError(f"Empty migration: {path.name}")
        migrations.append(Migration(version, path.name, hashlib.sha256(text.encode()).hexdigest(),
                                    tuple(statements)))
    return migrations


def pending_migrations(migrations: list[Migration], history: list[tuple]) -> list[Migration]:
    available = {migration.version: migration for migration in migrations}
    applied = set()
    for version, name, checksum in history:
        migration = available.get(version)
        if migration is None:
            raise ValueError(f"Applied migration missing from checkout: {version}")
        if (migration.name, migration.checksum) != (name, checksum):
            raise ValueError(f"Applied migration has been modified: {name}")
        applied.add(version)
    pending = [migration for migration in migrations if migration.version not in applied]
    if applied and any(migration.version <= max(applied) for migration in pending):
        raise ValueError("Out-of-order migration: use a version newer than all applied migrations")
    return pending


def migrate(connection, migrations: list[Migration], revision: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,))
        if not cursor.fetchone()[0]:
            connection.rollback()
            raise RuntimeError("Another migration executor holds the database lock")
    connection.commit()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '5s'")
                cursor.execute("SET LOCAL statement_timeout = '120s'")
                cursor.execute("""CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    version VARCHAR(14) PRIMARY KEY, filename TEXT NOT NULL,
                    checksum CHAR(64) NOT NULL, git_revision TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    applied_by TEXT NOT NULL DEFAULT current_user
                )""")
                cursor.execute("REVOKE ALL ON public.schema_migrations FROM app")
                cursor.execute("SELECT version,filename,checksum FROM public.schema_migrations ORDER BY version")
                pending = pending_migrations(migrations, cursor.fetchall())
        for migration in pending:
            LOGGER.info("Applying %s", migration.name)
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '5s'")
                    cursor.execute("SET LOCAL statement_timeout = '120s'")
                    for statement in migration.statements:
                        cursor.execute(statement)
                    cursor.execute("""INSERT INTO public.schema_migrations
                        (version,filename,checksum,git_revision) VALUES (%s,%s,%s,%s)""",
                        (migration.version, migration.name, migration.checksum, revision))
            LOGGER.info("Applied %s", migration.name)
        LOGGER.info("Migrations complete: %d applied, %d already recorded", len(pending),
                    len(migrations) - len(pending))
        return len(pending)
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
        connection.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate files without connecting to PostgreSQL")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        migrations = load_migrations(DIRECTORY)
        if args.check:
            LOGGER.info("Validated %d migration files", len(migrations))
            return 0
        if os.environ.get("PGUSER") != "migrator":
            raise ValueError("PGUSER must be migrator; do not use application credentials")
        if os.environ.get("PGSSLMODE") != "verify-full" or not os.environ.get("PGSSLROOTCERT"):
            raise ValueError("PGSSLMODE=verify-full and PGSSLROOTCERT are required")
        for name in ("PGHOST", "PGDATABASE", "PGPASSWORD", "GITHUB_SHA"):
            if not os.environ.get(name):
                raise ValueError(f"{name} is required")
        connection = psycopg2.connect(connect_timeout=15, application_name="stockassistant-migrations")
        try:
            migrate(connection, migrations, os.environ["GITHUB_SHA"])
        finally:
            connection.close()
        return 0
    except (ValueError, OSError, RuntimeError, psycopg2.Error) as exc:
        # SQL messages can contain data or credentials; expose codes, not query contents.
        code = exc.pgcode if isinstance(exc, psycopg2.Error) else None
        detail = f"PostgreSQL error {code or 'connection failure'}" if isinstance(exc, psycopg2.Error) else str(exc)
        LOGGER.error("Migration failed: %s", detail)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
