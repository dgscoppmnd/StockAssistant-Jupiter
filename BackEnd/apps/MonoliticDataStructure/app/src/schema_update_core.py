"""Canonical schema loading and validation shared by Setup and deployment.

This module deliberately has no application/environment initialization dependencies.
"""
import hashlib

from psycopg2 import sql
import sqlparse
from sqlparse import tokens as T

from database_schema import SCHEMA_PATH

LOCK_KEY = 702641903119


def load_update(path=None):
    source = (SCHEMA_PATH if path is None else path).read_text(encoding='utf-8')
    begin, end = '-- BEGIN JUPITER SCHEMA\n', '-- END JUPITER SCHEMA'
    if source.count(begin) != 1 or source.count(end) != 1:
        raise ValueError('Bloque de esquema ausente o duplicado.')
    body = source.split(begin, 1)[1].split(end, 1)[0].strip()
    statements = []
    for statement in sqlparse.parse(body):
        meaningful = [token for token in statement.flatten()
                      if not token.is_whitespace and token.ttype not in T.Comment]
        if not meaningful or all(token.value == ';' for token in meaningful):
            continue
        first = meaningful[0].normalized.upper()
        if first in {'BEGIN', 'START', 'COMMIT', 'END', 'ROLLBACK', 'ABORT', 'SAVEPOINT',
                     'RELEASE', 'PREPARE', 'VACUUM', 'COPY', '\\'} or first.startswith('\\'):
            raise ValueError('init.sql contiene una instrucción incompatible con la transacción única.')
        statements.append(str(statement).strip())
    if not statements:
        raise ValueError('init.sql no contiene instrucciones para aplicar.')
    return hashlib.sha256(source.encode('utf-8')).hexdigest(), statements


def validate_schema(connection):
    with connection.cursor() as cursor:
        for query in (
            'SELECT id, product_id, product_name FROM public.products LIMIT 0',
            'SELECT pk_product, cdgo_producto_externo, name_product FROM public.productos LIMIT 0',
            'SELECT id, email, status FROM public.users LIMIT 0',
            'SELECT product_id, warehouse_id FROM public.inventory_stock_levels LIMIT 0',
            'SELECT id FROM public.sales_orders LIMIT 0',
            'SELECT id FROM public.automation_rules LIMIT 0',
            'SELECT checksum,run_id,actor_id,statement_count,validated_constraints FROM public.app_schema_updates LIMIT 0',
            'SELECT checksum,run_id,applied_at,statement_count,validated_constraints FROM public.app_schema_update_history LIMIT 0',
        ):
            cursor.execute(query)
        cursor.execute("""SELECT n.nspname,t.relname,c.conname FROM pg_constraint c
                          JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
                          WHERE n.nspname='public' AND c.contype IN ('c','f') AND NOT c.convalidated""")
        constraints = cursor.fetchall()
        for namespace, table, name in constraints:
            cursor.execute(sql.SQL('ALTER TABLE {}.{} VALIDATE CONSTRAINT {}').format(
                sql.Identifier(namespace), sql.Identifier(table), sql.Identifier(name)))
        cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        return len(constraints)
