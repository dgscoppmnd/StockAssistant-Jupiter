"""Apply the canonical schema using a migration DSN, without logging credentials.

Use during a maintenance window after taking a restorable backup. The application
role must not be used: this migration needs ownership of tables and dependent views.
"""
import argparse
import os
from pathlib import Path

import psycopg2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dsn-env', default='JUPITER_MIGRATION_DSN')
    parser.add_argument('--legacy-timezone', required=True,
                        help='Timezone used by legacy products.created_at/updated_at (e.g. UTC)')
    parser.add_argument('--check-only', action='store_true',
                        help='Execute and verify the full migration, then roll back')
    args = parser.parse_args()
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        parser.error(f'Set {args.dsn_env} to the schema owner/migrator connection DSN')
    schema = (Path(__file__).resolve().parents[2] /
              'BackEnd/apps/MonoliticDataStructure/app/docker/init-scripts/init.sql').read_text(encoding='utf-8')
    # The CLI owns the transaction, just like init_db(). Avoid nested BEGIN/COMMIT.
    schema = schema.split('-- BEGIN JUPITER SCHEMA\n', 1)[1].split('-- END JUPITER SCHEMA', 1)[0]
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('TimeZone', %s, true)", (args.legacy_timezone,))
            cursor.execute(schema)
            cursor.execute("""SELECT c.relname,c.relkind FROM pg_class c
                              WHERE c.oid IN ('public.products'::regclass,'public.productos'::regclass)
                              ORDER BY c.relname""")
            if cursor.fetchall() != [('productos', 'v'), ('products', 'r')]:
                raise RuntimeError('Unexpected product relations after migration')
            cursor.execute('SELECT count(*) FROM public.products')
            count = cursor.fetchone()[0]
        if args.check_only:
            connection.rollback()
            print(f'Validated {count} canonical products; all changes rolled back.')
        else:
            connection.commit()
            print(f'Schema committed; {count} canonical products.')


if __name__ == '__main__':
    main()
