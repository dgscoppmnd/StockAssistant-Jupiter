"""Run inside the API container; integration tests use a disposable database."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

import schema_update_service as service
from endpoints import endpointsSetup as endpoints


class SchemaUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = service._get_postgres_connection_server()
        cls.admin.autocommit = True
        cls.name = 'schema_button_test_' + uuid4().hex
        with cls.admin.cursor() as cursor:
            cursor.execute('CREATE DATABASE ' + cls.name)
        cls.parameters = cls.admin.get_dsn_parameters()
        cls.parameters.pop('options', None)
        cls.parameters.update(dbname=cls.name, password=os.getenv('DB_PASSWORD', 'admin123'))

    @classmethod
    def tearDownClass(cls):
        with cls.admin.cursor() as cursor:
            cursor.execute('DROP DATABASE ' + cls.name + ' WITH (FORCE)')
        cls.admin.close()

    def connect(self):
        return psycopg2.connect(**self.parameters)

    def exists(self, name):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(%s)', (name,))
            return cursor.fetchone()[0] is not None

    def test_01_complete_schema_commit_and_idempotence(self):
        checksum, statements = service.load_update()
        for _ in range(2):
            events = list(service.apply_update(1, checksum, statements, connect=self.connect))
            self.assertEqual(events[-1]['stage'], 'complete', events[-1])
            self.assertEqual(events[-1]['percent'], 100)
            self.assertTrue(all(event.get('percent', 0) < 100 for event in events[:-1]))
        with self.connect() as connection:
            self.assertEqual(service.last_update(connection)['checksum'], checksum)
        self.assertTrue(events[-1]['result']['already_applied'])
        # The guard must prevent actual SQL execution, not just hide the button.
        events = list(service.apply_update(1, checksum, ['CREATE TABLE duplicate_probe(id integer)'], connect=self.connect))
        self.assertTrue(events[-1]['result']['already_applied'])
        self.assertFalse(self.exists('duplicate_probe'))

    def test_history_prevents_reapplying_an_older_file(self):
        original, _ = service.load_update()
        events = list(service.apply_update(1, 'b'*64, ['SELECT 1'], connect=self.connect))
        self.assertEqual(events[-1]['stage'], 'complete', events[-1])
        events = list(service.apply_update(1, original, ['CREATE TABLE older_file_probe(id integer)'], connect=self.connect))
        self.assertTrue(events[-1]['result']['already_applied'])
        self.assertFalse(self.exists('older_file_probe'))

    def test_sql_error_rolls_back_ddl_and_data(self):
        statements = ['CREATE TABLE rollback_probe(id integer)', 'INSERT INTO rollback_probe VALUES (1)', 'SELECT missing_schema_button_column']
        events = list(service.apply_update(1, 'a'*64, statements, connect=self.connect))
        self.assertEqual(events[-1]['stage'], 'error')
        self.assertTrue(events[-1]['rolled_back'])
        self.assertFalse(self.exists('rollback_probe'))

    def test_failed_validation_rolls_back(self):
        statements = ['CREATE TABLE invalid_probe(id integer)', 'INSERT INTO invalid_probe VALUES (-1)',
                      'ALTER TABLE invalid_probe ADD CONSTRAINT positive CHECK (id>0) NOT VALID']
        events = list(service.apply_update(1, 'a'*64, statements, connect=self.connect))
        self.assertTrue(events[-1]['rolled_back'], events[-1])
        self.assertFalse(self.exists('invalid_probe'))

    def test_disconnect_before_commit_rolls_back(self):
        events = service.apply_update(1, 'a'*64, ['CREATE TABLE disconnect_probe(id integer)'], connect=self.connect)
        while next(events)['stage'] != 'validating':
            pass
        events.close()
        self.assertFalse(self.exists('disconnect_probe'))

    def test_concurrent_run_rejected(self):
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', (service.LOCK_KEY,))
            events = list(service.apply_update(1, 'a'*64, [], connect=self.connect))
            self.assertEqual(events[-1]['stage'], 'error')
            self.assertIn('Otra actualización', events[-1]['detail'])

    def test_explicit_commit_blocked(self):
        with patch.object(Path, 'read_text', return_value='-- BEGIN JUPITER SCHEMA\nSELECT 1; COMMIT;\n-- END JUPITER SCHEMA'):
            with self.assertRaises(ValueError):
                service.load_update()

    def test_permissions_and_stale_checksum(self):
        app = FastAPI()
        app.include_router(endpoints.router)
        client = TestClient(app)
        self.assertEqual(client.post('/setup/database/update', json={'expected_checksum':'a'*64}).status_code, 401)
        app.dependency_overrides[endpoints.setup_user] = lambda: 9999
        self.assertEqual(client.get('/setup/database/status').json(), {'can_update':False})
        self.assertEqual(client.post('/setup/database/update', json={'expected_checksum':'a'*64}).status_code, 403)
        app.dependency_overrides[endpoints.setup_user] = lambda: 1
        with patch.dict(os.environ, {'SCHEMA_ADMIN_USER_IDS':'1'}):
            self.assertEqual(client.post('/setup/database/update', json={'expected_checksum':'a'*64}).status_code, 409)
            self.assertEqual(client.post('/setup/database/update', json={'expected_checksum':'a'*64,'sql':'DROP TABLE users'}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
