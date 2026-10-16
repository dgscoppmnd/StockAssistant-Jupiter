"""Schema initialization regressions using doubles: no database is created or changed."""
from pathlib import Path
import re
import unittest
from unittest.mock import MagicMock, patch

import database_schema
from database_schema import schema_sql
from DataBaseManagement import dbConectionPostgres as db
from sales_schema import sales_schema_sql


class CanonicalSchemaTests(unittest.TestCase):
    def test_full_schema_contains_all_modules_without_database_or_table_deletion(self):
        script = schema_sql()
        for table in ('users','productos','products','inventory_stock_levels','clients',
                      'knowledge_chunks','sales_document_events','agent_action_proposals','automation_control'):
            self.assertIn(f'CREATE TABLE IF NOT EXISTS public.{table}' if table != 'products' else 'CREATE TABLE IF NOT EXISTS products', script)
        self.assertIn('ix_productos_search_trgm',script)
        self.assertNotRegex(script,re.compile(r'^\s*(?:CREATE|DROP)\s+DATABASE\b|^\s*(?:DROP\s+TABLE|TRUNCATE)\b|^\s*\\(?:c|connect)\b',re.M|re.I))
        self.assertFalse(script.lstrip().startswith('BEGIN;'))
        self.assertFalse(script.rstrip().endswith('COMMIT;'))

    def test_modules_are_extracted_from_same_file(self):
        self.assertIn('CREATE TABLE IF NOT EXISTS public.type_client',schema_sql('SCHEMA EXTENSIONS'))
        self.assertIn('automation_permissions',schema_sql('INTEGRATED AUTOMATION SCHEMA'))
        self.assertIn('sales_permissions',sales_schema_sql())
        self.assertIn('knowledge_chunks',schema_sql('RAG SCHEMA'))

    def test_existing_admin_password_and_status_are_preserved(self):
        script=schema_sql()
        self.assertIn('ON CONFLICT (email) DO NOTHING;',script)
        self.assertNotIn('password = EXCLUDED.password',script)

    def test_missing_duplicate_or_empty_block_fails_explicitly(self):
        for source in ('', '-- BEGIN SALES MODULE\n-- END SALES MODULE',
                       '-- BEGIN SALES MODULE\nSELECT 1;\n-- END SALES MODULE\n-- BEGIN SALES MODULE\nSELECT 2;\n-- END SALES MODULE'):
            path=MagicMock();path.read_text.return_value=source
            with self.subTest(source=source),patch('database_schema.SCHEMA_PATH',path),self.assertRaises(ValueError):
                schema_sql('SALES MODULE')

    def test_init_reads_one_source_and_commits_schema_on_configured_connection(self):
        expected=schema_sql()
        path=MagicMock();path.read_text.return_value=database_schema.SCHEMA_PATH.read_text(encoding='utf-8')
        connection=MagicMock()
        with patch('database_schema.SCHEMA_PATH',path),patch.object(db,'_get_postgres_connection_server',return_value=connection):
            db.init_db()
        path.read_text.assert_called_once_with(encoding='utf-8')
        cursor=connection.cursor.return_value.__enter__.return_value
        self.assertEqual(cursor.execute.call_count,2)
        self.assertIn('pg_advisory_xact_lock',cursor.execute.call_args_list[0].args[0])
        self.assertEqual(cursor.execute.call_args_list[1].args[0],expected)
        connection.commit.assert_called_once()
        connection.rollback.assert_not_called()
        connection.close.assert_called_once()

    def test_schema_failure_rolls_back_and_closes_connection(self):
        connection=MagicMock()
        connection.cursor.return_value.__enter__.return_value.execute.side_effect=[None,RuntimeError('Migration failed')]
        with patch.object(db,'_get_postgres_connection_server',return_value=connection),self.assertRaises(RuntimeError):
            db.init_db()
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()
        connection.close.assert_called_once()

    def test_missing_schema_does_not_attempt_database_connection(self):
        with patch.object(db,'schema_sql',side_effect=FileNotFoundError('init.sql')),patch.object(db,'_get_postgres_connection_server') as connect,self.assertRaises(FileNotFoundError):
            db.init_db()
        connect.assert_not_called()

    def test_legacy_entry_point_uses_canonical_initializer(self):
        with patch.object(db,'init_db') as initialize:
            db.init_products_db()
        initialize.assert_called_once_with()

    def test_standalone_extension_files_are_not_required(self):
        directory=Path(db.__file__).parent
        self.assertFalse((directory/'automation_schema.sql').exists())
        self.assertFalse((directory/'schema_extensions.sql').exists())
        self.assertIn('agent_action_proposals',schema_sql())


if __name__=='__main__':
    unittest.main(verbosity=2)
