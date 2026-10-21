import os
from contextlib import closing
from pathlib import Path
import sys
import tempfile
import unittest
import re
from uuid import uuid4
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from migrate import execute_statements, load_migrations, load_update, main, migrate, pending_migrations
from database_schema import SCHEMA_PATH
from schema_update_core import validate_schema

PERMISSIONS_SQL = Path(__file__).resolve().parents[2] / 'sql/05-migration-permissions.sql'
RUNTIME_MIGRATIONS = Path(__file__).resolve().parents[2] / 'sql/migrations'


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

    def test_canonical_init_is_loaded_without_outer_transaction(self):
        checksum, statements = load_update()
        self.assertEqual(len(checksum), 64)
        self.assertTrue(any('CREATE TABLE IF NOT EXISTS public.app_schema_updates' in s for s in statements))
        self.assertFalse(statements[-1].rstrip().upper() == 'COMMIT;')

    def test_init_requires_unique_markers_and_rejects_transaction_control(self):
        path = self.path / 'init.sql'
        for source in ('SELECT 1;', '-- BEGIN JUPITER SCHEMA\n-- END JUPITER SCHEMA',
                       '-- BEGIN JUPITER SCHEMA\nCOMMIT;\n-- END JUPITER SCHEMA'):
            path.write_text(source, encoding='utf-8')
            with self.subTest(source=source), self.assertRaises(ValueError):
                load_update(path)

    def test_init_hash_matches_manual_service_normalization(self):
        path = self.path / 'init.sql'
        source = '-- BEGIN JUPITER SCHEMA\nSELECT 1;\n-- END JUPITER SCHEMA\n'
        path.write_bytes(source.encode())
        checksum = load_update(path)[0]
        path.write_bytes(source.replace('\n', '\r\n').encode())
        self.assertEqual(checksum, load_update(path)[0])

    def test_check_rejects_invalid_init_without_connecting(self):
        with patch('sys.argv', ['migrate.py', '--check']), \
                patch('migrate.load_update', side_effect=ValueError('Invalid init.sql')), \
                patch('migrate.psycopg2.connect') as connect:
            with self.assertLogs('stockassistant.migrations', level='ERROR'):
                self.assertEqual(main(), 1)
            connect.assert_not_called()

    def test_permission_diagnostic_reports_location_without_sql_or_server_message(self):
        import psycopg2

        class PermissionError(psycopg2.Error):
            pgcode = '42501'

        cursor = MagicMock()
        cursor.execute.side_effect = PermissionError('sensitive server message')
        with self.assertLogs('stockassistant.migrations', level='ERROR') as logs:
            with self.assertRaises(PermissionError):
                execute_statements(cursor, ["INSERT INTO private_table VALUES ('secret-value');"], 'init.sql')
        output = '\n'.join(logs.output)
        self.assertIn('init.sql statement 1/1 (INSERT)', output)
        self.assertIn('SQLSTATE=42501', output)
        self.assertIn('diagnose-migration-permissions.sql', output)
        for secret in ('private_table', 'secret-value', 'sensitive server message'):
            self.assertNotIn(secret, output)

    def test_permission_repair_covers_canonical_relations(self):
        canonical = set(re.findall(
            r'^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+'
            r'(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?([a-z_][a-z0-9_]*)',
            SCHEMA_PATH.read_text(encoding='utf-8'), re.I | re.M))
        repair = PERMISSIONS_SQL.read_text(encoding='utf-8')
        for name in canonical | {'schema_migrations', 'productos_catalogo'}:
            with self.subTest(name=name):
                self.assertIn(repr(name), repair)

    def test_runtime_migration_covers_the_same_application_objects_as_admin_preparation(self):
        repair = PERMISSIONS_SQL.read_text(encoding='utf-8')
        runtime = (RUNTIME_MIGRATIONS /
                   'V20261021120000__restore_app_runtime_permissions.sql').read_text(encoding='utf-8')
        for declaration in ('application_relations', 'application_functions'):
            pattern = declaration + r' text\[\] := ARRAY\[(.*?)\];'
            self.assertEqual(set(re.findall(r"'([^']+)'", re.search(pattern, repair, re.S)[1])),
                             set(re.findall(r"'([^']+)'", re.search(pattern, runtime, re.S)[1])))

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
                cursor.execute("DROP TABLE IF EXISTS public.schema_migrations, public.migration_probe, "
                               "public.app_schema_update_history, public.app_schema_updates")
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

    def test_dml_grants_do_not_allow_altering_admin_owned_tables(self):
        import psycopg2
        with self.connection:
            with self.connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
                cursor.execute('CREATE TABLE public.migration_probe(id integer)')
                cursor.execute('GRANT ALL ON public.migration_probe TO migration_runner_test')
                cursor.execute('SET ROLE migration_runner_test')
        self.write('ALTER TABLE public.migration_probe ADD COLUMN label text;')
        with self.assertLogs('stockassistant.migrations', level='ERROR') as logs:
            with self.assertRaises(psycopg2.errors.InsufficientPrivilege):
                migrate(self.connection, load_migrations(self.path), 'denied')
        self.assertIn('statement 1/1 (ALTER)', '\n'.join(logs.output))
        self.assertIn('SQLSTATE=42501', '\n'.join(logs.output))
        self.assertEqual(self.scalar('SELECT count(*) FROM public.schema_migrations'), 0)

    def test_permission_repair_enables_real_schema_migration_without_superuser(self):
        import psycopg2
        from psycopg2 import sql
        from psycopg2.extensions import parse_dsn
        suffix = uuid4().hex
        database = 'migration_permissions_' + suffix
        administrator = 'permission_admin_' + suffix
        runner = 'permission_runner_' + suffix
        application = 'permission_app_' + suffix
        parameters = parse_dsn(self.dsn)
        control = psycopg2.connect(self.dsn)
        control.autocommit = True
        created_roles = []
        created_database = False
        try:
            with control.cursor() as cursor:
                cursor.execute(sql.SQL('CREATE ROLE {} CREATEROLE NOSUPERUSER INHERIT').format(
                    sql.Identifier(administrator)))
                created_roles.append(administrator)
                cursor.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(
                    sql.Identifier(database), sql.Identifier(administrator)))
                created_database = True
                cursor.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(administrator)))
                for role in (runner, application):
                    cursor.execute(sql.SQL('CREATE ROLE {} NOSUPERUSER').format(sql.Identifier(role)))
                    created_roles.append(role)
                cursor.execute('RESET ROLE')
            parameters['dbname'] = database
            repair = PERMISSIONS_SQL.read_text(encoding='utf-8').replace('stockassistant', database)
            repair = re.sub(r'\bmigrator\b', runner, repair)
            repair = re.sub(r'\bapp\b', application, repair)
            _, original_statements = load_update()
            statements = [re.sub(r'\bapp\b', application, statement) for statement in original_statements]
            with closing(psycopg2.connect(**parameters)) as connection:
                def run(query, values=None):
                    with connection:
                        with connection.cursor() as cursor:
                            cursor.execute(query, values)
                            row = cursor.fetchone() if cursor.description else None
                            return row[0] if row else None

                run(sql.SQL('SET ROLE {}').format(sql.Identifier(administrator)))
                # Simulate an existing installation created by dbadmin, including
                # serial/identity sequences, views and functions.
                with connection, connection.cursor() as cursor:
                    for statement in statements:
                        cursor.execute(statement)
                    cursor.execute('CREATE TABLE public.schema_migrations(version text)')
                    cursor.execute('CREATE TABLE public.unrelated_permission_probe(id serial)')
                member_before = run('SELECT pg_has_role(current_user,%s,\'MEMBER\')', (runner,))
                inherited_before = run('SELECT pg_has_role(current_user,%s,\'USAGE\')', (runner,))
                with self.assertRaisesRegex(psycopg2.errors.RaiseException, 'Connect to stockassistant'):
                    run(PERMISSIONS_SQL.read_text(encoding='utf-8'))
                for _ in range(2):
                    run(repair)
                self.assertEqual(run('SELECT pg_has_role(current_user,%s,\'MEMBER\')', (runner,)), member_before)
                self.assertEqual(run('SELECT pg_has_role(current_user,%s,\'USAGE\')', (runner,)), inherited_before)
                self.assertEqual(run("SELECT pg_get_userbyid(relowner) FROM pg_class "
                                     "WHERE oid='public.unrelated_permission_probe'::regclass"), runner)
                self.assertEqual(run("SELECT pg_get_userbyid(relowner) FROM pg_class "
                                     "WHERE oid='public.products'::regclass"), runner)
                self.assertFalse(run('SELECT rolsuper FROM pg_roles WHERE rolname=%s', (runner,)))

                # A pre-existing membership must survive, including independent
                # SET/INHERIT flags and grantors on PostgreSQL 16+.
                if connection.server_version >= 160000:
                    run(sql.SQL('GRANT {} TO {} WITH INHERIT FALSE, SET FALSE GRANTED BY {}').format(
                        sql.Identifier(runner), sql.Identifier(administrator), sql.Identifier(administrator)))
                else:
                    run(sql.SQL('GRANT {} TO {}').format(sql.Identifier(runner), sql.Identifier(administrator)))
                membership_query = ('SELECT jsonb_agg(to_jsonb(m) ORDER BY grantor) FROM pg_auth_members m '
                                    'WHERE roleid=%s::regrole AND member=%s::regrole')
                membership_before = run(membership_query, (runner, administrator))
                run(repair)
                self.assertEqual(run(membership_query, (runner, administrator)), membership_before)

                run('RESET ROLE')
                run(sql.SQL('SET ROLE {}').format(sql.Identifier(runner)))
                # The prepared migration account does not need database CREATE.
                self.assertFalse(run("SELECT has_database_privilege(current_user,current_database(),'CREATE')"))
                with connection, connection.cursor() as cursor:
                    for statement in statements:
                        cursor.execute(statement)
                    validate_schema(connection)
                run('RESET ROLE')
                run(sql.SQL('SET ROLE {}').format(sql.Identifier(application)))
                record_id = run("INSERT INTO public.products(product_id,product_name) "
                                "VALUES('permission-probe','CSV compatible product') RETURNING id")
                run('UPDATE public.products SET product_name=%s WHERE id=%s', ('updated', record_id))
                self.assertEqual(run('SELECT product_name FROM public.products WHERE id=%s', (record_id,)), 'updated')
                run('DELETE FROM public.products WHERE id=%s', (record_id,))
                self.assertTrue(run('SELECT pg_has_role(current_user,%s,\'MEMBER\')', (runner,)))
                self.assertTrue(run("SELECT has_schema_privilege(current_user,'public','CREATE')"))
                for table in ('schema_migrations', 'app_schema_updates', 'app_schema_update_history'):
                    self.assertTrue(run('SELECT has_table_privilege(current_user,%s,\'INSERT\')', ('public.' + table,)))
                run('SELECT checksum FROM public.app_schema_updates')
                run('ALTER TABLE public.products ADD COLUMN shared_owner_probe integer')
                # Real app logins must create future objects as the common owner.
                run('RESET ROLE')
                run(sql.SQL('ALTER ROLE {} LOGIN PASSWORD %s').format(sql.Identifier(application)),
                    ('shared-owner-test-only',))
                app_parameters = {**parameters, 'user': application, 'password': 'shared-owner-test-only'}
                with closing(psycopg2.connect(**app_parameters)) as app_connection:
                    with app_connection, app_connection.cursor() as cursor:
                        cursor.execute('SELECT session_user,current_user')
                        self.assertEqual(cursor.fetchone(), (application, runner))
                        cursor.execute('CREATE TABLE public.future_shared_owner_probe(id serial)')
                        cursor.execute("CREATE FUNCTION public.future_shared_owner_function() RETURNS integer "
                                       "LANGUAGE SQL AS 'SELECT 1'")
                        cursor.execute("CREATE TYPE public.shared_owner_enum AS ENUM ('one')")
                        cursor.execute('CREATE DOMAIN public.shared_owner_domain AS integer')
                run(sql.SQL('SET ROLE {}').format(sql.Identifier(runner)))
                run('ALTER TABLE public.future_shared_owner_probe ADD COLUMN label text')
                run('CREATE OR REPLACE FUNCTION public.future_shared_owner_function() RETURNS integer '
                    "LANGUAGE SQL AS 'SELECT 2'")
                # Apply the forward migration after the administrative preparation.
                with connection, connection.cursor() as cursor:
                    for migration in load_migrations(RUNTIME_MIGRATIONS):
                        for statement in migration.statements:
                            cursor.execute(re.sub(r'\bapp\b', application, statement))
                run('RESET ROLE')
                run(sql.SQL('SET ROLE {}').format(sql.Identifier(administrator)))
                run(repair)
        finally:
            with control.cursor() as cursor:
                cursor.execute('RESET ROLE')
                if created_database:
                    cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
                for role in reversed(created_roles):
                    cursor.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
            control.close()

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

    def schema_update(self, sql, checksum='a'*64):
        # Use the real ledger DDL, including grants and legacy history backfill.
        ledger = SCHEMA_PATH.read_text(encoding='utf-8').split('-- BEGIN JUPITER SCHEMA\n')[1]
        ledger = ledger.split('-- Esquema analitico local conservado.')[0]
        import sqlparse
        return checksum, [*sqlparse.split(ledger), sql]

    def test_init_new_hash_and_incremental_changes_are_applied_once(self):
        update = self.schema_update('CREATE TABLE public.migration_probe(id integer);')
        with patch('migrate.validate_schema', return_value=0):
            migrate(self.connection, [], 'first', schema_update=update)
            migrate(self.connection, [], 'repeat', schema_update=update)
            changed = self.schema_update('ALTER TABLE public.migration_probe ADD COLUMN label text;', 'b'*64)
            migrate(self.connection, [], 'new', schema_update=changed)
            # An older hash must not replay its CREATE TABLE.
            migrate(self.connection, [], 'old', schema_update=update)
            self.write("INSERT INTO public.migration_probe VALUES (1, 'ok');")
            migrate(self.connection, load_migrations(self.path), 'incremental', schema_update=changed)
        self.assertEqual(self.scalar('SELECT count(*) FROM public.app_schema_update_history'), 2)
        self.assertEqual(self.scalar('SELECT actor_id FROM public.app_schema_updates'), 0)
        self.assertEqual(self.scalar('SELECT label FROM public.migration_probe'), 'ok')
        self.assertEqual(self.scalar('SELECT count(*) FROM public.schema_migrations'), 1)

    def test_init_failure_rolls_back_ddl_and_ledgers_and_allows_retry(self):
        import psycopg2
        update = self.schema_update('CREATE TABLE public.migration_probe(id integer); SELECT 1/0;')
        with self.assertRaises(psycopg2.errors.DivisionByZero):
            migrate(self.connection, [], 'failed', schema_update=update)
        self.assertIsNone(self.scalar("SELECT to_regclass('public.app_schema_updates')"))
        self.assertIsNone(self.scalar("SELECT to_regclass('public.migration_probe')"))
        self.assertEqual(self.scalar('SELECT count(*) FROM public.schema_migrations'), 0)
        with patch('migrate.validate_schema', return_value=0):
            migrate(self.connection, [], 'retry', schema_update=self.schema_update(
                'CREATE TABLE public.migration_probe(id integer);'))
        self.assertEqual(self.scalar('SELECT count(*) FROM public.app_schema_update_history'), 1)

    def test_init_validation_failure_rolls_back(self):
        with patch('migrate.validate_schema', side_effect=ValueError('Invalid schema')):
            with self.assertRaisesRegex(ValueError, 'Invalid schema'):
                migrate(self.connection, [], 'failed', schema_update=self.schema_update(
                    'CREATE TABLE public.migration_probe(id integer);'))
        self.assertIsNone(self.scalar("SELECT to_regclass('public.migration_probe')"))
        self.assertIsNone(self.scalar("SELECT to_regclass('public.app_schema_update_history')"))

    def test_manual_ledger_is_respected_and_existing_hash_still_validated(self):
        update = self.schema_update('CREATE TABLE public.migration_probe(id integer);')
        with self.connection:
            with self.connection.cursor() as cursor:
                for statement in update[1]:
                    cursor.execute(statement)
                cursor.execute("""INSERT INTO public.app_schema_updates
                    (id,checksum,run_id,actor_id,statement_count,validated_constraints)
                    VALUES(1,%s,'manual-run',1,1,0)""", (update[0],))
        with patch('migrate.validate_schema', return_value=0) as validate:
            migrate(self.connection, [], 'manual-already-applied', schema_update=update)
            validate.assert_called_once_with(self.connection)
        self.assertEqual(self.scalar('SELECT actor_id FROM public.app_schema_updates'), 1)
        with patch('migrate.validate_schema', side_effect=ValueError('Schema drift')):
            with self.assertRaisesRegex(ValueError, 'Schema drift'):
                migrate(self.connection, [], 'drift', schema_update=update)

    def test_incremental_validation_failure_preserves_init_but_rolls_back_file(self):
        update = self.schema_update('CREATE TABLE public.migration_probe(id integer);')
        self.write('ALTER TABLE public.migration_probe ADD COLUMN invalid_column integer;')
        with patch('migrate.validate_schema', side_effect=[0, ValueError('Invalid incremental schema')]):
            with self.assertRaisesRegex(ValueError, 'Invalid incremental schema'):
                migrate(self.connection, load_migrations(self.path), 'failed', schema_update=update)
        self.assertEqual(self.scalar('SELECT count(*) FROM public.app_schema_update_history'), 1)
        self.assertEqual(self.scalar('SELECT count(*) FROM public.schema_migrations'), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM information_schema.columns "
                                     "WHERE table_name='migration_probe' AND column_name='invalid_column'"), 0)

    def test_manual_update_and_deployment_share_lock(self):
        import psycopg2
        from schema_update_core import LOCK_KEY
        with psycopg2.connect(self.dsn) as other:
            with other.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_KEY,))
            with self.assertRaisesRegex(RuntimeError, 'lock'):
                migrate(self.connection, [], 'concurrent', schema_update=load_update())

    def test_canonical_init_on_real_database_and_repeat(self):
        # Trusted extensions need CREATE on this isolated database.
        with self.connection:
            with self.connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
                cursor.execute('GRANT CREATE ON DATABASE migrations_test TO migration_runner_test')
                cursor.execute('SET ROLE migration_runner_test')
        update = load_update()
        migrate(self.connection, [], 'canonical', schema_update=update)
        migrate(self.connection, [], 'repeat', schema_update=update)
        self.assertEqual(self.scalar('SELECT checksum FROM public.app_schema_updates'), update[0])
        self.assertEqual(self.scalar('SELECT count(*) FROM public.app_schema_update_history'), 1)
        self.assertIsNotNone(self.scalar("SELECT to_regclass('public.schema_migrations')"))
        self.assertIsNotNone(self.scalar("SELECT to_regclass('public.inventory_stock_levels')"))

    def test_bootstrap_grants_runtime_access_and_protects_existing_history(self):
        from psycopg2 import sql
        import sqlparse
        suffix = uuid4().hex
        runner, application = 'bootstrap_runner_' + suffix, 'bootstrap_app_' + suffix
        administrator = self.scalar('SELECT session_user')
        source = (RUNTIME_MIGRATIONS.parent / '01-roles.sql').read_text(encoding='utf-8')
        source = source.replace('stockassistant', 'migrations_test')
        source = source.replace(":'migpass'", "'bootstrap-test-only'")
        source = source.replace(":'apppass'", "'bootstrap-test-only'")
        for original, replacement in (('migrator', runner), ('app', application),
                                      ('dbadmin', sql.Identifier(administrator).as_string(self.connection))):
            source = re.sub(r'\b' + original + r'\b', replacement, source)
        try:
            with self.connection, self.connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
                cursor.execute('CREATE TABLE public.bootstrap_probe(id serial)')
                cursor.execute('CREATE TABLE public.schema_migrations(version text)')
                cursor.execute('CREATE TABLE public.app_schema_updates(id integer)')
                cursor.execute('CREATE TABLE public.app_schema_update_history(id integer)')
                for statement in sqlparse.split(source):
                    cursor.execute(statement)
                for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
                    cursor.execute("SELECT has_table_privilege(%s,'public.bootstrap_probe',%s)",
                                   (application, privilege))
                    self.assertTrue(cursor.fetchone()[0])
                cursor.execute("SELECT has_sequence_privilege(%s,'public.bootstrap_probe_id_seq','USAGE')",
                               (application,))
                self.assertTrue(cursor.fetchone()[0])
                for table in ('schema_migrations', 'app_schema_updates', 'app_schema_update_history'):
                    cursor.execute('SELECT has_table_privilege(%s,%s,\'INSERT\')', (application, 'public.' + table))
                    self.assertFalse(cursor.fetchone()[0])
                cursor.execute("SELECT has_schema_privilege(%s,'public','CREATE')", (application,))
                self.assertTrue(cursor.fetchone()[0])
                cursor.execute('SELECT pg_has_role(%s,%s,\'MEMBER\')', (application, runner))
                self.assertTrue(cursor.fetchone()[0])
        finally:
            with self.connection, self.connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
                cursor.execute('DROP TABLE IF EXISTS public.bootstrap_probe')
                for role in (application, runner):
                    cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,))
                    if cursor.fetchone():
                        cursor.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
                        cursor.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))

    def test_runtime_grants_restore_operations_without_granting_schema_or_history_writes(self):
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute('RESET ROLE')
            cursor.execute('GRANT CREATE ON DATABASE migrations_test TO migration_runner_test')
            cursor.execute('SET ROLE migration_runner_test')
        migrate(self.connection, [], 'canonical', schema_update=load_update())
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute('CREATE TABLE public.unrelated_runtime_probe(id integer)')
            cursor.execute('REVOKE ALL ON public.unrelated_runtime_probe FROM app')
            cursor.execute('REVOKE ALL ON public.automation_rules, public.automation_events FROM app')
            cursor.execute('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app')
            cursor.execute('REVOKE ALL ON FUNCTION public.update_updated_at_column() FROM app, PUBLIC')
        # The original DML repair remains immutable; shared DDL access is covered
        # above after the administrator grants membership and the login setting.
        migrations = load_migrations(RUNTIME_MIGRATIONS)[:1]
        self.assertEqual(migrate(self.connection, migrations, 'restore'), len(migrations))
        self.assertEqual(migrate(self.connection, migrations, 'repeat'), 0)
        # The SQL itself is repeatable too, independently of the migration ledger.
        with self.connection, self.connection.cursor() as cursor:
            for migration in migrations:
                execute_statements(cursor, migration.statements, migration.name)
            cursor.execute('CREATE TABLE public.future_runtime_probe(id serial)')
        def cleanup_probes():
            with self.connection, self.connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
                cursor.execute('DROP TABLE public.unrelated_runtime_probe, public.future_runtime_probe')
        self.addCleanup(cleanup_probes)
        for table in ('automation_rules', 'automation_events', 'inventory_warehouses',
                      'clients', 'inventory_suppliers', 'future_runtime_probe'):
            for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
                self.assertTrue(self.scalar(
                    f"SELECT has_table_privilege('app', 'public.{table}', '{privilege}')"))
        self.assertTrue(self.scalar("SELECT has_sequence_privilege('app', "
                                    "'public.future_runtime_probe_id_seq', 'USAGE')"))
        self.assertTrue(self.scalar("SELECT has_function_privilege('app', "
                                    "'public.update_updated_at_column()', 'EXECUTE')"))
        self.assertFalse(self.scalar("SELECT has_table_privilege('app', "
                                     "'public.unrelated_runtime_probe', 'SELECT')"))
        for table in ('schema_migrations', 'app_schema_updates', 'app_schema_update_history'):
            for privilege in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
                self.assertFalse(self.scalar(
                    f"SELECT has_table_privilege('app', 'public.{table}', '{privilege}')"))
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute('SET ROLE app')
            cursor.execute('UPDATE public.automation_rules SET is_active=is_active')
            cursor.execute("INSERT INTO public.automation_events(phase,detail) "
                           "VALUES('permission_test','{}') RETURNING id")
            self.assertGreater(cursor.fetchone()[0], 0)
            cursor.execute("DELETE FROM public.automation_events WHERE phase='permission_test'")
            cursor.execute("SELECT has_schema_privilege(current_user,'public','CREATE')")
            self.assertFalse(cursor.fetchone()[0])
            cursor.execute('RESET ROLE')
            cursor.execute('SET ROLE migration_runner_test')

    def test_shared_owner_migration_explains_missing_administrative_preparation(self):
        migration = [item for item in load_migrations(RUNTIME_MIGRATIONS)
                     if item.name.endswith('__shared_schema_owner_access.sql')]
        with self.assertLogs('stockassistant.migrations', level='ERROR') as logs:
            with self.assertRaisesRegex(Exception, '05-migration-permissions.sql'):
                migrate(self.connection, migration, 'requires-admin')
        self.assertIn('05-migration-permissions.sql as dbadmin', '\n'.join(logs.output))
        self.assertEqual(self.scalar('SELECT count(*) FROM public.schema_migrations'), 0)


if __name__ == "__main__":
    unittest.main()
