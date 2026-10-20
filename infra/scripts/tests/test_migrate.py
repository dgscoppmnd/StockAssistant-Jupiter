import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from migrate import load_migrations, migrate, pending_migrations


class MigrationFilesTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name)

    def write(self, sql="SELECT 1;", version="20261020150000"):
        path = self.path / f"V{version}__example.sql"
        path.write_text(sql, encoding="utf-8")
        return path

    def test_empty_directory_does_not_replay_historical_files(self):
        (self.path / "README.md").write_text("Documentation", encoding="utf-8")
        self.assertEqual(load_migrations(self.path), [])

    def test_normalize_windows_line_endings_and_bom(self):
        path = self.write("SELECT 1;\n")
        original = load_migrations(self.path)[0]
        path.write_bytes(b"\xef\xbb\xbfSELECT 1;\r\n")
        self.assertEqual(load_migrations(self.path)[0].checksum, original.checksum)

    def test_duplicate_and_malformed_versions_rejected(self):
        self.write()
        (self.path / "V20261020150000__other.sql").write_text("SELECT 2;", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_migrations(self.path)
        (self.path / "V20261020150000__other.sql").unlink()
        (self.path / "05-example.sql").write_text("SELECT 1;", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "filename"):
            load_migrations(self.path)

    def test_invalid_calendar_version_rejected(self):
        self.write(version="20261320150000")
        with self.assertRaises(ValueError):
            load_migrations(self.path)

    def test_transaction_control_and_empty_files_rejected(self):
        for sql in ("-- comment only", "BEGIN; SELECT 1; COMMIT;", "SELECT 1; ROLLBACK;",
                    "START TRANSACTION;", "\\i other.sql"):
            with self.subTest(sql=sql):
                self.write(sql)
                with self.assertRaises(ValueError):
                    load_migrations(self.path)

    def test_do_block_is_one_statement(self):
        self.write("DO $$ BEGIN PERFORM 1; PERFORM 2; END $$; SELECT 'COMMIT;';")
        self.assertEqual(len(load_migrations(self.path)[0].statements), 2)

    def test_history_checksums_missing_and_renamed_files(self):
        self.write()
        migration = load_migrations(self.path)[0]
        history = [(migration.version, migration.name, migration.checksum)]
        self.assertEqual(pending_migrations([migration], history), [])
        with self.assertRaisesRegex(ValueError, "missing"):
            pending_migrations([], history)
        for column in (1, 2):
            changed = list(history[0])
            changed[column] = "modified"
            with self.assertRaisesRegex(ValueError, "modified"):
                pending_migrations([migration], [tuple(changed)])

    def test_out_of_order_rejected(self):
        self.write(version="20261020160000")
        later = load_migrations(self.path)[0]
        self.write()
        with self.assertRaisesRegex(ValueError, "Out-of-order"):
            pending_migrations(load_migrations(self.path), [(later.version, later.name, later.checksum)])


@unittest.skipUnless(os.getenv("MIGRATIONS_TEST_DSN"), "Requires isolated migrations_test database")
class MigrationDatabaseTests(unittest.TestCase):
    def setUp(self):
        import psycopg2
        from psycopg2.extensions import parse_dsn
        self.dsn = os.environ["MIGRATIONS_TEST_DSN"]
        if parse_dsn(self.dsn).get("dbname") != "migrations_test":
            raise RuntimeError("Tests require an isolated database named migrations_test")
        self.connection = psycopg2.connect(self.dsn)
        self.addCleanup(self.connection.close)
        with self.connection:
            with self.connection.cursor() as cursor:
                cursor.execute("DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='app') "
                               "THEN CREATE ROLE app; END IF; END $$")
                cursor.execute("DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='migration_runner_test') "
                               "THEN CREATE ROLE migration_runner_test; END IF; END $$")
                cursor.execute("GRANT USAGE, CREATE ON SCHEMA public TO migration_runner_test")
                cursor.execute("GRANT USAGE ON SCHEMA public TO app")
                cursor.execute("ALTER DEFAULT PRIVILEGES FOR ROLE migration_runner_test IN SCHEMA public "
                               "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app")
                cursor.execute("DROP TABLE IF EXISTS public.schema_migrations, public.migration_probe")
                cursor.execute("SET ROLE migration_runner_test")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name)

    def write(self, sql, version="20261020150000"):
        path = self.path / f"V{version}__example.sql"
        path.write_text(sql, encoding="utf-8")

    def scalar(self, query):
        with self.connection:
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchone()[0]

    def test_empty_baseline_and_recorded_success_are_idempotent(self):
        self.assertEqual(migrate(self.connection, [], "baseline-sha"), 0)
        self.write("CREATE TABLE public.migration_probe(id INTEGER); INSERT INTO public.migration_probe VALUES(1);")
        migrations = load_migrations(self.path)
        self.assertEqual(migrate(self.connection, migrations, "test-sha"), 1)
        self.assertEqual(migrate(self.connection, migrations, "other-sha"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM public.migration_probe"), 1)
        self.assertEqual(self.scalar("SELECT git_revision FROM public.schema_migrations"), "test-sha")
        self.assertFalse(self.scalar(
            "SELECT has_table_privilege('app', 'public.schema_migrations', 'INSERT')"))

    def test_failed_file_rolls_back_schema_data_and_history(self):
        import psycopg2
        self.write("CREATE TABLE public.migration_probe(id INTEGER); "
                   "INSERT INTO public.migration_probe VALUES(1); SELECT 1/0;")
        with self.assertRaises(psycopg2.errors.DivisionByZero):
            migrate(self.connection, load_migrations(self.path), "test-sha")
        self.assertIsNone(self.scalar("SELECT to_regclass('public.migration_probe')"))
        self.assertEqual(self.scalar("SELECT count(*) FROM public.schema_migrations"), 0)
        self.write("CREATE TABLE public.migration_probe(id INTEGER);")
        self.assertEqual(migrate(self.connection, load_migrations(self.path), "retry-sha"), 1)

    def test_previous_files_remain_committed_after_later_failure(self):
        import psycopg2
        self.write("CREATE TABLE public.migration_probe(id INTEGER);")
        self.write("INSERT INTO public.migration_probe VALUES(1); SELECT 1/0;", "20261020160000")
        with self.assertRaises(psycopg2.errors.DivisionByZero):
            migrate(self.connection, load_migrations(self.path), "test-sha")
        self.assertEqual(self.scalar("SELECT count(*) FROM public.schema_migrations"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM public.migration_probe"), 0)

    def test_database_lock_prevents_concurrent_execution(self):
        import psycopg2
        from migrate import LOCK_ID
        other = psycopg2.connect(self.dsn)
        try:
            with other.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            other.commit()
            with self.assertRaisesRegex(RuntimeError, "lock"):
                migrate(self.connection, [], "test-sha")
        finally:
            other.close()
        self.assertEqual(migrate(self.connection, [], "retry-sha"), 0)

    def test_non_admin_migrator_creates_objects_with_application_permissions(self):
        self.write("CREATE TABLE public.migration_probe(id INTEGER);")
        self.assertEqual(migrate(self.connection, load_migrations(self.path), "test-sha"), 1)
        self.assertEqual(self.scalar("SELECT current_user"), "migration_runner_test")
        self.assertTrue(self.scalar(
            "SELECT has_table_privilege('app', 'public.migration_probe', 'INSERT')"))
        self.assertFalse(self.scalar(
            "SELECT has_table_privilege('app', 'public.schema_migrations', 'UPDATE')"))


if __name__ == "__main__":
    unittest.main()
