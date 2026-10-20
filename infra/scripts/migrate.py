"""Apply pending canonical init.sql and ordered, immutable PostgreSQL migrations."""

import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

import psycopg2
import sqlparse
from sqlparse import tokens

sys.path.insert(0, str(Path(__file__).resolve().parents[2] /
                      "BackEnd/apps/MonoliticDataStructure/app/src"))
from schema_update_core import LOCK_KEY, load_update, validate_schema

LOGGER = logging.getLogger("stockassistant.migrations")
DIRECTORY = Path(__file__).resolve().parents[1] / "sql" / "migrations"
LOCK_ID = LOCK_KEY
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


def apply_schema_update(connection, update) -> bool:
    """Use Setup's hash ledger; actor 0 denotes an automated deployment."""
    checksum, statements = update
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '120s'")
            timezone = os.environ.get("DB_LEGACY_TIMEZONE")
            if timezone:
                cursor.execute("SELECT set_config('TimeZone', %s, true)", (timezone,))
            applied = False
            for table in ("app_schema_update_history", "app_schema_updates"):
                cursor.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                if cursor.fetchone()[0] is not None:
                    cursor.execute(f"SELECT 1 FROM public.{table} WHERE checksum=%s", (checksum,))
                    if cursor.fetchone() is not None:
                        applied = True
                        break
            if applied:
                validate_schema(connection)
                LOGGER.info("init.sql already applied; schema validated")
                return False
            LOGGER.info("Applying canonical init.sql (%s)", checksum)
            for statement in statements:
                cursor.execute(statement)
            validated = validate_schema(connection)
            cursor.execute("""INSERT INTO public.app_schema_updates
                (id,checksum,run_id,actor_id,statement_count,validated_constraints)
                VALUES (1,%s,%s,0,%s,%s) ON CONFLICT (id) DO UPDATE SET
                checksum=EXCLUDED.checksum,run_id=EXCLUDED.run_id,actor_id=EXCLUDED.actor_id,
                applied_at=CURRENT_TIMESTAMP,statement_count=EXCLUDED.statement_count,
                validated_constraints=EXCLUDED.validated_constraints""",
                (checksum, str(uuid4()), len(statements), validated))
            cursor.execute("""INSERT INTO public.app_schema_update_history
                (checksum,run_id,applied_at,statement_count,validated_constraints)
                SELECT checksum,run_id,applied_at,statement_count,validated_constraints
                FROM public.app_schema_updates WHERE id=1""")
    LOGGER.info("Canonical init.sql committed and validated")
    return True


def migrate(connection, migrations: list[Migration], revision: str, *, schema_update=None) -> int:
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
                cursor.execute("SELECT version,filename,checksum,git_revision,applied_at,applied_by "
                               "FROM public.schema_migrations LIMIT 0")
                cursor.execute("SELECT version,filename,checksum FROM public.schema_migrations ORDER BY version")
                pending = pending_migrations(migrations, cursor.fetchall())
        if schema_update is not None:
            apply_schema_update(connection, schema_update)
        for migration in pending:
            LOGGER.info("Applying %s", migration.name)
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '5s'")
                    cursor.execute("SET LOCAL statement_timeout = '120s'")
                    for statement in migration.statements:
                        cursor.execute(statement)
                    if schema_update is not None:
                        validate_schema(connection)
                        cursor.execute("SELECT version,filename,checksum,git_revision,applied_at,applied_by "
                                       "FROM public.schema_migrations LIMIT 0")
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
        schema_update = load_update()
        if args.check:
            LOGGER.info("Validated init.sql (%d statements) and %d migration files; "
                        "database validation requires execution", len(schema_update[1]), len(migrations))
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
            migrate(connection, migrations, os.environ["GITHUB_SHA"], schema_update=schema_update)
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
